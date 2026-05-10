import pandas as pd
import re
from nameparser import HumanName
from pathlib import Path
from urllib.parse import urlparse

SOURCE_PATH = "../data/faculty_list.csv"
ORIG_WEBSITE_PATH = "../data/faculty_websites"
CLEANED_WEBSITE_PATH = "../data/faculty_websites_cleaned"


def get_base_path(path):
    if path.endswith("/"):
        path = path[:-1]
    if path == "":
        return None
    idx = -2 if path.endswith("/index.html") else -1
    return "/".join(path.split("/")[:idx])


def deduplicate_text(t1, t1_lines, t2, t2_lines):
    l1 = len(t1_lines)
    l2 = len(t2_lines)
    if l1 < 10 or l2 < 10:
        return None, None

    # Compare header
    t1_start_idx_offset = t2_start_idx_offset = 1
    same_header = False
    if "\n".join(t1_lines[1:6]) in t2:
        same_header = True
        while t2_start_idx_offset < l2 and t1_lines[1] != t2_lines[t2_start_idx_offset]:
            t2_start_idx_offset += 1
    elif "\n".join(t2_lines[1:6]) in t1:
        same_header = True
        while t1_start_idx_offset < l1 and t2_lines[1] != t1_lines[t1_start_idx_offset]:
            t1_start_idx_offset += 1

    start_idx = 0
    if same_header:
        while (
            (start_idx + t1_start_idx_offset) < l1
            and (start_idx + t2_start_idx_offset) < l2
            and t1_lines[start_idx + t1_start_idx_offset]
            == t2_lines[start_idx + t2_start_idx_offset]
        ):
            start_idx += 1
    if (start_idx + t1_start_idx_offset) == l1 or (
        start_idx + t2_start_idx_offset
    ) == l2:
        return None, None

    # Compare footer
    t1_end_idx_offset = t2_end_idx_offset = -1
    same_footer = False
    if "\n".join(t1_lines[-5:]) in t2:
        same_footer = True
        while t2_end_idx_offset >= -l2 and t1_lines[-1] != t2_lines[t2_end_idx_offset]:
            t2_end_idx_offset -= 1
    elif "\n".join(t2_lines[-5:]) in t1:
        same_footer = True
        while t1_end_idx_offset >= -l1 and t2_lines[-1] != t1_lines[t1_end_idx_offset]:
            t1_end_idx_offset -= 1

    end_idx = 0
    if same_footer:
        while (
            t1_lines[end_idx + t1_end_idx_offset]
            == t2_lines[end_idx + t2_end_idx_offset]
        ):
            end_idx -= 1

    if not same_header and not same_footer:
        return None, None

    return (
        "\n".join(
            t1_lines[
                (start_idx + t1_start_idx_offset) : (end_idx + t1_end_idx_offset + 1 + l1)
            ]
        ),
        "\n".join(
            t2_lines[
                (start_idx + t2_start_idx_offset) : (end_idx + t2_end_idx_offset + 1 + l2)
            ]
        ),
    )


def has_multiple_fields(t):
    if len(t.split(" ")) >= 8:
        return False
    return len(re.findall(r"(Mathematics|Statistics|Computer Science)", t)) > 1


# Single-line noise patterns — match against a stripped, lowercased line.
NOISE_LINE_PATTERNS = [
    re.compile(r"^(facebook|instagram|twitter|x\.com|linkedin|youtube|github|tiktok|threads|bluesky|mastodon|orcid|cv)$"),
    re.compile(r"^(menu|search|home|visit|apply|give|donate|contact|news|events|calendar|sitemap|directory|directions|jobs|careers|alumni|admissions|admission|login|log\s*in|sign\s*in|skip\s+(to|navigation).*|toggle.*|open\s+menu|close\s+menu|main\s+menu|sub\s*menu|breadcrumb)$"),
    re.compile(r"^(©.*|copyright.*\d{4}.*|all\s+rights\s+reserved.*|privacy(\s+policy)?|terms(\s+of\s+(use|service))?|accessibility(\s+statement)?|cookie(\s+policy)?|do\s+not\s+sell.*|legal|sitemap)$"),
    re.compile(r"^\(?\+?\d[\d\s().-]{6,}$"),                       # phone numbers
    re.compile(r"^[\w.+-]+@[\w.-]+\.[a-z]{2,}$"),                  # email
    re.compile(r"^https?://\S+$"),                                  # URL
    re.compile(r"^\d{1,5}\s+([a-z][\w'.-]*\s+){1,6}(street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln|drive|dr|way|hall|building|center|court|ct|highway|hwy|parkway|pkwy)(\s|,|$).*$"),  # street address
    re.compile(r"^[a-z]{2}\s+\d{5}(-\d{4})?$"),                    # state ZIP
    re.compile(r"^(she|he|they|her|him|them)(/(she|he|they|her|him|them|hers|his|theirs))+$"),  # pronouns
    re.compile(r"^(view\s+(in\s+)?(the\s+)?course\s+catalog|see\s+(the\s+)?course\s+catalog)$"),
    re.compile(r"^terms\s+taught$"),
    re.compile(r"^course\s+description$"),
    re.compile(r"^(office|tel|telephone|phone|fax|email|address|mail)\s*:?\s*$"),
    re.compile(r"^(department|departments|faculty|staff|people|directory)\s*:?\s*$"),
    re.compile(r"^(in\s+this\s+section|on\s+this\s+page|quick\s+links?|related\s+links?)\s*:?\s*$"),
    re.compile(r"^(read\s+more|learn\s+more|see\s+more|show\s+more|view\s+(all|more)|expand|collapse)\s*\.?\s*$"),
]


def is_noise_line(line):
    s = line.strip().lower().rstrip(":.")
    if not s:
        return True
    return any(p.match(s) for p in NOISE_LINE_PATTERNS)


def strip_noise(text):
    return "\n".join(line for line in text.split("\n") if not is_noise_line(line))


def drop_college_boilerplate(college_texts):
    """Given {name: text} for a college, drop lines that recur in >=40% of pages.

    Catches college-wide nav/footer text that survives the same-base-path dedup
    (e.g. when faculty have heterogeneous personal URLs). Skips short collections
    where the heuristic isn't reliable.
    """
    if len(college_texts) < 5:
        return college_texts

    line_counts = {}
    for text in college_texts.values():
        for line in set(l.strip() for l in text.split("\n") if l.strip()):
            line_counts[line] = line_counts.get(line, 0) + 1

    threshold = int(len(college_texts) * 0.4)
    if threshold < 2:
        threshold = 2
    boilerplate = {l for l, c in line_counts.items() if c >= threshold and len(l) >= 3}

    out = {}
    for name, text in college_texts.items():
        kept = [l for l in text.split("\n") if l.strip() not in boilerplate]
        out[name] = "\n".join(kept)
    return out


Path(CLEANED_WEBSITE_PATH).mkdir(parents=True, exist_ok=True)

# Remove duplicated content like header and footer within the same college
faculty = pd.read_csv(SOURCE_PATH)
colleges = faculty["college"].unique()
for college in colleges:
    # Find all .edu urls in the same college
    college_faculty = faculty[
        (faculty["college"] == college) & (faculty["url"].notna())
    ]
    if len(college_faculty) <= 1:
        print(f"Fewer than 2 websites found for {college}!")
        continue

    valid_faculty = []
    for _, row in college_faculty.iterrows():
        url = row["url"]
        parsed_url = urlparse(url)
        if parsed_url.hostname.endswith(".edu"):
            valid_faculty.append((row, parsed_url))
    if len(valid_faculty) <= 1:
        print(f"No valid website found for {college}!")
        continue

    # Find the largest group(s) of urls that share the same hostname and base path
    group_dict = {}
    for row, url in valid_faculty:
        url_host = url.hostname
        if url_host.startswith("www."):
            url_host = url_host[4:]
        url_path = get_base_path(url.path)
        if url_path is None:
            continue
        key = url_host + " " + url_path
        if key not in group_dict:
            group_dict[key] = [row]
        else:
            group_dict[key].append(row)

    max = 0
    for k, v in group_dict.items():
        if len(v) > max:
            max = len(v)
    if max == 1:
        print(f"No group with > 1 faculty for {college}!")
        continue

    max_keys = []
    for k, v in group_dict.items():
        if len(v) == max:
            max_keys.append(k)

    # Process each similar-base-path group    
    for k in max_keys:
        faculty_list = group_dict[k]
        r0 = faculty_list[0]
        reference = Path(
            f"{ORIG_WEBSITE_PATH}/{college}/{r0['name']}.txt"
        ).read_text(encoding="utf8")
        reference_lines = reference.split("\n")
        reference_cleaned = None
        for r in faculty_list[1:]:
            text = Path(
                f"{ORIG_WEBSITE_PATH}/{college}/{r['name']}.txt"
            ).read_text(encoding="utf8")
            text_lines = text.split("\n")
            candidate_reference_cleaned, t_cleaned = deduplicate_text(
                reference, reference_lines, text, text_lines
            )
            if reference_cleaned is None and candidate_reference_cleaned is not None:
                reference_cleaned = candidate_reference_cleaned
            if t_cleaned is not None:
                Path(f"{CLEANED_WEBSITE_PATH}/{college}").mkdir(parents=True, exist_ok=True)
                Path(
                    f"{CLEANED_WEBSITE_PATH}/{college}/{r['name']}.txt"
                ).write_text(t_cleaned, encoding="utf8")
            else:
                print(f"Cannot clean {college}/{r['name']}")
        if candidate_reference_cleaned is not None:
            Path(f"{CLEANED_WEBSITE_PATH}/{college}/{r0['name']}.txt").write_text(
                candidate_reference_cleaned, encoding="utf8"
            )
        else:
            print(f"Cannot clean {college}/{r0['name']}")

# Include lines near mentions of names only
NUM_LINES_TO_KEEP = 30
pass2_results = {}  # (college, name) -> text after pass 2

for _, row in faculty[faculty["url"].notna()].iterrows():
    college = row["college"]
    name = row["name"]
    path = Path(f"{CLEANED_WEBSITE_PATH}/{college}/{name}.txt")
    if not path.is_file():
        path = Path(f"{ORIG_WEBSITE_PATH}/{college}/{name}.txt")
    if not path.is_file():
        continue

    parsed_name = HumanName(name.lower())
    lines = path.read_text(encoding="utf8").split("\n")
    lines = list(filter(lambda l: len(l) > 0, lines))
    num_lines = len(lines)
    line_nums = []
    for i, line in enumerate(lines):
        line = line.lower()
        if any([t in line for t in [parsed_name.first, parsed_name.last, "area", "research", "interest", "courses", "teaching", "paper", "publication"]]):
            line_nums.extend(list(range(i, min(num_lines, i + NUM_LINES_TO_KEEP))))

    line_nums = sorted(list(set(line_nums)))
    if len(line_nums) == 0:
        print(f"No mention of names for {college}/{name}")
        new_lines = lines
    else:
        new_lines = [lines[i] for i in line_nums]

    for i, line in enumerate(new_lines):
        new_lines[i] = re.sub(r"\s+", " ", line)

    new_lines = filter(lambda l: not has_multiple_fields(l), new_lines)
    pass2_results[(college, name)] = strip_noise("\n".join(new_lines))

# Pass 3 (final): drop college-wide boilerplate that survived pass 1, then write.
by_college = {}
for (college, name), text in pass2_results.items():
    by_college.setdefault(college, {})[name] = text

for college, college_texts in by_college.items():
    deboilerplated = drop_college_boilerplate(college_texts)
    for name, text in deboilerplated.items():
        Path(f"{CLEANED_WEBSITE_PATH}/{college}").mkdir(parents=True, exist_ok=True)
        Path(f"{CLEANED_WEBSITE_PATH}/{college}/{name}.txt").write_text(text, encoding="utf8")