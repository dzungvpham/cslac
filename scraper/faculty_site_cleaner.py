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
    new_text = "\n".join(new_lines)
    Path(f"{CLEANED_WEBSITE_PATH}/{college}").mkdir(parents=True, exist_ok=True)
    Path(f"{CLEANED_WEBSITE_PATH}/{college}/{name}.txt").write_text(new_text, encoding="utf8")