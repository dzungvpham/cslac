import argparse
from collections import Counter
import difflib
import pandas as pd
import json
import re
import requests
import time
import traceback
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from constants import College
from googlesearch import search
from mimetypes import guess_type
from nameparser import HumanName
from selenium import webdriver
from urllib.parse import urljoin, urlparse


def get_full_faculty_url(faculty_site_url, url):
    if not isinstance(url, str):
        return None
    elif not any(url.startswith(p) for p in ["./", "../", "/", "http"]):
        parsed_faculty_site_url = urlparse(faculty_site_url)
        path = parsed_faculty_site_url.path
        if len(path) > 1 and path.split("/")[1] == url.split("/")[0]:
            return f"{parsed_faculty_site_url.scheme}://{parsed_faculty_site_url.hostname}/{url}"    
    return urljoin(faculty_site_url, url)


_IMAGE_URL_RE = re.compile(r"\.(jpe?g|png|gif|svg|webp|bmp|ico|tiff?)(\?|#|$)", re.I)


def clean_url(url):
    if (
        url is None
        or re.match(r"(mailto|tel|javascript):", url) is not None
        or url == "#"
        or url == ""
        or _IMAGE_URL_RE.search(url) is not None
    ):
        return None
    return url


def fetch_url(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return r.text
        else:
            raise Exception(f"Status code: {r.status_code}")
    except Exception as e:
        if e.__class__.__name__ == "SSLError" and (
            url.startswith("https://www.coe.edu/")
            or url.startswith("https://cs.colby.edu/")
            or url.startswith("https://www.westpoint.edu/")
        ):
            print(f"Retrying {url} with verify=False")
            try:
                return requests.get(url, verify=False).text
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                return None
        else:
            print(f"Error fetching {url}: {e}")
            return None


def fetch_all_urls(urls):
    with ThreadPoolExecutor() as executor:
        return list(executor.map(fetch_url, urls))


def get_valid_colleges(filepath):
    df = pd.read_csv(filepath)
    return df[df["Major"] == 1]


def create_faculty(name, title, college=None, url=None):
    return {
        "name": name,
        "title": title,
        "college": college,
        "url": url,
    }


def extract_name(soup, line=0):
    lines = soup.get_text("||", strip=True).split("||")
    if type(line).__name__ == "int":
        if len(lines) <= line:
            return None
        return clean_name(lines[line])
    else:
        if any(l >= len(lines) for l in line):
            return None
        return clean_name(" ".join(lines[l].strip() for l in line))


def clean_name(text):
    if text is None:
        return None
    text = re.sub(r"\(.*\)", "", text)  # Eg: (TEXT)
    text = re.sub(r"\s+.?\d+", "", text)  # Eg: '10
    text = re.sub(r"[A-Z]{3,}", "", text)  # Eg: POM
    if "," in text:
        part = text.split(",")[0]
        if len(part.split()) >= 2:  # Avoid LAST, FIRST
            text = part

    if (
        "," in text
        or re.match(r"^\s*(Prof\.|Dr\.|Lt\. Col\.|Col\.|Maj\.|Mr\.|Mrs\.|Ms\.)", text) is not None
    ):  # Handle LAST, FIRST and Prof./Dr./etc.
        parsed = HumanName(text)
        text = f"{parsed.first} {parsed.middle} {parsed.last}"

    text = re.sub(r"\s+", " ", text).strip()  # Condense consecutive whitespaces
    text = re.sub(r"\u2019", "'", text)  # Get rid of UTF quotation
    text = re.sub(r"\u200b", "", text)  # Get rid of zero-width space
    if len(text) < 3:
        return None
    return text


def extract_title(soup, include_subject=False):
    text = soup.get_text("\n", strip=True)
    return clean_title(text, include_subject=include_subject)


# Get a valid professor title
def clean_title(text, include_subject=False):
    if text is None:
        return None
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()

    position_of_regex = r"(prof\.|professor|lecturer|instructor|chair|director) (of|in) "
    # Subject regex matches a CS-related subject, optionally preceded by a list of
    # other subject words joined by `,`/`&`/`/`/`and` (e.g. "Mathematics, Statistics,
    # & Computer Science" or "Math, Stat, and Computer Science"). The prefix
    # repeats; an extra `,`/`&`/`/`/`and` separator may appear before the subject.
    subject_regex = r"([a-z]{3,11}\s*(,|and|&|/)\s*)*(\s*(,|&|/|and)\s*)?(((practice of )?computer)|(data (science|analytics))|(information (science|technology|system))|(bioinformatics)|(computing)|(software engineering)|(cyber))( and)?"

    if (
        (
            re.search(r"(prof\.|professor|centennial|lecturer|instructor|chair)", text)
            is None
        )
        or (re.search(r"(emerit|program contact)", text) is not None)
        or (
            re.search(position_of_regex, text) is not None
            and re.search(
                f"{position_of_regex}{subject_regex}",
                text,
            )
            is None
        )
        or (include_subject and re.search(subject_regex, text) is None)
    ):
        return None

    title = ""
    if "lecturer" in text:
        if re.search(r"(lab|laboratory) lecturer", text) is not None:
            return None
        title = "Lecturer"
        if "senior lecturer" in text:
            title = "Senior " + title
    elif "instructor" in text:
        title = "Instructor"
        if re.search(r"(lab|laboratory)", text) is not None:
            title = "Lab " + title
        if "senior" in text:
            title = "Senior " + title
    else:
        title = "Professor"
        if re.search(r"teaching (professor|assistant|associate)", text):
            title = "Teaching " + title
        if "associate" in text:
            title = "Associate " + title
        elif "assistant" in text:
            title = "Assistant " + title

    if "visiting" in text:
        title = "Visiting " + title
    elif "adjunct" in text:
        title = "Adjunct " + title
    elif "professor of practice" in text:
        title = title + " of Practice"

    return title


def extract_url(soup, name):
    all_urls = [
        url
        for a in soup.find_all("a", href=True)
        if (url := clean_url(a["href"])) is not None
    ]
    if soup.name == "a":
        all_urls.append(clean_url(soup["href"]))
    all_urls = list(set(all_urls))  # Dedup
    all_urls = [
        url for url in all_urls if re.search(r"(email-protection|/map)", url) is None
    ]

    n = len(all_urls)
    if n == 0:
        return None
    elif n == 1:
        return all_urls[0]
    elif name is None:
        return None

    parsed_name = HumanName(name)
    first_name = parsed_name.first.lower()
    last_name = parsed_name.last.lower()
    urls_with_name = [url for url in all_urls if last_name in url or first_name in url]

    if len(urls_with_name) >= 1:
        return min(urls_with_name, key=len)

    return min(all_urls, key=len)


def longest_common_substring_len(str1, str2):
    seq_matcher = difflib.SequenceMatcher(None, str1, str2)
    match = seq_matcher.find_longest_match(0, len(str1), 0, len(str2))
    return match.size


def is_strange_url(url, name):
    if pd.isna(url):
        return False
    url = url.lower()
    if url.endswith("/"):
        url = url[:-1]
    name = name.lower()
    parsed_name = HumanName(name)
    name_abbr = parsed_name.first[0] + parsed_name.last
    url_parsed = urlparse(url)
    url_type = guess_type(url)[0]
    return (
        re.search(r"\d+(/|-)?$", url) is None  # Valid if ends with numbers
        and all(
            t.lower().replace("'", "") not in url for t in re.split(r" |-", name)
        )  # Either first or last should be in the url
        and longest_common_substring_len(name_abbr, url_parsed.path + url_parsed.query)
        < 4  # Name and url should have at least 4 consecutive letters in common
    ) or (url_type is not None and not re.search(r"(html|xml)$", url_type))


def scrape(soup_parts, name_line=0, include_subject=False):
    res = []
    for t in soup_parts:
        try:
            faculty_name = extract_name(t, line=name_line)
            faculty_title = extract_title(t, include_subject=include_subject)
            faculty_url = extract_url(t, faculty_name)
            if faculty_name is None or faculty_title is None:
                continue

            res.append(create_faculty(faculty_name, faculty_title, url=faculty_url))
        except Exception:
            print(f"Error scraping the following tag:\n{t.prettify()}")
            print(traceback.format_exc())
            continue
    return res


def scrape_f(filter, **kwargs):
    return lambda soup: scrape(soup.find_all(filter), **kwargs)


def soup_has_class(soup_tag, classname):
    return classname in soup_tag.attrs.get("class", [])


def soup_has_class_stub(soup_tag, class_stub):
    return any(class_stub in classname for classname in soup_tag.attrs.get("class", []))


def scrape_class_f(*classnames, **kwargs):
    return scrape_f(
        lambda soup: all([soup_has_class(soup, classname) for classname in classnames]),
        **kwargs,
    )


def scrape_tag_f(tagname, **kwargs):
    return scrape_f(lambda s: s.name == tagname, **kwargs)


def scrape_coe_college(soup):
    col = soup.find(lambda s: soup_has_class(s, "col-beta"))
    parts = [
        BeautifulSoup(s, features="html.parser")
        for s in re.split(r"<hr[^>]*/>", col.prettify())
    ]
    return scrape(parts)


def scrape_dickinson_college(soup):
    j = json.loads(soup.text)
    faculty_list = [f for p in j for f in p["faculty"]]
    res = []
    for faculty in faculty_list:
        faculty_name = clean_name(faculty["NAME"])
        faculty_title = clean_title(faculty["TITLE"])
        if faculty_name is None or faculty_title is None:
            continue
        faculty_url = faculty["PROFILE"]
        res.append(create_faculty(faculty_name, faculty_title, url=faculty_url))
    return res


def scrape_st_norbert(soup):
    res = []
    for card in soup.find_all("ptp-card"):
        faculty_name = clean_name(card.get("label"))
        faculty_title = clean_title(card.get_text(" ", strip=True))
        if faculty_name is None or faculty_title is None:
            continue
        res.append(create_faculty(faculty_name, faculty_title, url=card.get("url")))
    return res


def scrape_new_florida(soup):
    parts = [
        BeautifulSoup(s, features="html.parser")
        for s in soup.find(id="facultytextcontainer")
        .p.prettify(formatter="minimal")
        .split("<br/>")
    ]
    return scrape(parts)


def scrape_wesleyan_college(soup):
    soup = json.loads(soup.text)
    res = []
    for o in soup["faculty"] + soup["vice_chairs"] + soup["chairs"]:
        name = o["name"]
        appointments = o["appointments"]
        faculty_name = clean_name(f"{name['first']} {name['middle']} {name['last']}")
        faculty_title = clean_title(", ".join(app["title"] for app in appointments))
        if faculty_name is None or faculty_title is None:
            continue
        faculty_url = o["personal_web_url"]
        res.append(create_faculty(faculty_name, faculty_title, url=faculty_url))
    return res


NAME_LINE_OPTIONS = [0, 1, [0, 1], 2, [1, 2], [0, 1, 2]]
TITLE_RE = re.compile(r"\b(professor|lecturer|instructor)\b", re.I)
NON_NAME_RE = re.compile(
    r"\b(chair|director|computer|mathematics|math|statistics|science|"
    r"department|program|office|phone|email|read more|view|"
    r"profile|bio|more info|faculty|staff|professor|lecturer|"
    r"instructor|emeritus|emerita|emeriti|adjunct|visiting|teaching|"
    r"general|contact|home|search|learn more|click|"
    r"title|role|position|location|biography|expertise|address|"
    r"website|publications|research|courses|education|degree|"
    r"about|frequently|asked|questions|reach)\b",
    re.I,
)


def looks_like_name(name):
    """Heuristic: does this string look like a person's full name?"""
    if name is None or NON_NAME_RE.search(name):
        return False
    if any(c in name for c in ":;@/|()") or any(c.isdigit() for c in name):
        return False
    parts = [p.strip(".,") for p in name.split()]
    if len(parts) < 2 or len(parts) > 6:
        return False

    def initial_or_word(p):
        return (
            p and p[0].isalpha()
            and (p[0].isupper() or p.startswith(("de", "von", "van")))
        )

    def name_word(p):
        # Full name token: 3+ letters, capitalized.
        return initial_or_word(p) and len(p) >= 3

    def short_name_word(p):
        # Short surname token: 2+ letters, capitalized (e.g. "Wu", "Li", "Ng").
        return initial_or_word(p) and len(p) >= 2

    # Common English short words that masquerade as 2-letter "name" tokens but
    # never appear in real human names — used to reject junk like "Of An".
    SHORT_BLACKLIST = {
        "of", "an", "on", "or", "in", "at", "to", "by", "as", "is", "be", "do",
        "go", "if", "it", "us", "we", "he", "me", "my", "no", "up", "so", "ai",
    }

    # Last token can be a 2-letter capitalized surname; first token must be a
    # capitalized initial or word. If no token is a full 3+ char word
    # (e.g. all tokens are 2 chars like "Yi Lu"), reject only if any token is a
    # common English short word — otherwise accept (real Asian names are 2+2).
    if not short_name_word(parts[-1]):
        return False
    if not initial_or_word(parts[0]):
        return False
    if not all(initial_or_word(p) for p in parts):
        return False
    if not any(name_word(p) for p in parts):
        if any(p.lower() in SHORT_BLACKLIST for p in parts):
            return False
    return True


NAME_ATTRS = ("label", "data-name", "aria-label", "alt")
URL_ATTRS = ("url", "data-url", "data-href")


def extract_name_with_attrs(tag, line=0):
    """Like extract_name but also tries common attributes that hold a person's name."""
    n = extract_name(tag, line=line)
    if looks_like_name(n):
        return n
    if hasattr(tag, "get"):
        for attr in NAME_ATTRS:
            v = tag.get(attr)
            if not v:
                continue
            cleaned = clean_name(v)
            if looks_like_name(cleaned):
                return cleaned
    return n


def extract_url_with_attrs(tag, name):
    """Like extract_url but also checks enclosing <a> ancestors and common attributes
    for non-anchor card layouts (e.g. cards wrapped in a single <a> link)."""
    u = extract_url(tag, name)
    if u is not None:
        return u
    if hasattr(tag, "parents"):
        for anc in list(tag.parents)[:3]:
            if getattr(anc, "name", None) == "a":
                href = clean_url(anc.get("href"))
                if href is not None:
                    return href
    if hasattr(tag, "get"):
        for attr in URL_ATTRS:
            v = clean_url(tag.get(attr))
            if v is not None:
                return v
    return None


_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
# Section headings that indicate the cards beneath them are NOT the department's
# primary faculty: cross-listings from other colleges, emeriti, alumni, staff,
# scholars in residence, etc. When a page splits into multiple labeled sections
# (e.g. Bryn Mawr's "Faculty" / "Haverford Faculty" / "Affiliated Faculty"), we
# drop cards whose nearest preceding heading matches this pattern.
_BAD_HEADING_RE = re.compile(
    r"\b(haverford|bryn mawr|swarthmore|amherst|smith|hampshire|"
    r"emerit|alumn|former|associated|affiliated|"
    r"visiting scholar|scholar in residence|in residence|"
    r"advisory|guest)\b",
    re.I,
)


def _nearest_preceding_heading(tag):
    """Find the nearest section heading preceding `tag` in document order.

    Walks up parents and looks at preceding siblings of each. Only returns a
    heading that sits as a direct preceding sibling — does NOT descend into
    sibling subtrees. This avoids picking up a previous card's inner <hN> (e.g.
    Lafayette, where each faculty card contains <h4>/<h5>) and treating that as
    a section divider.
    """
    cur = tag
    while cur is not None:
        sib = cur.previous_sibling
        while sib is not None:
            if getattr(sib, "name", None) in _HEADING_TAGS:
                return sib
            sib = sib.previous_sibling
        cur = cur.parent
    return None


def filter_cards_by_heading(cards):
    """Drop cards that fall under a section heading indicating they are not the
    department's primary faculty (cross-listings, emeriti, affiliated, etc.).

    Only filters when (a) the cards span multiple distinct heading texts and
    (b) at least one of those headings matches `_BAD_HEADING_RE`. Otherwise the
    list is returned unchanged so single-section pages aren't disturbed.
    """
    if not cards:
        return cards
    headings = []
    for c in cards:
        h = _nearest_preceding_heading(c)
        headings.append(h.get_text(" ", strip=True) if h else "")
    distinct = {h for h in headings if h}
    if len(distinct) <= 1:
        return cards
    if not any(_BAD_HEADING_RE.search(h) for h in distinct):
        return cards
    return [c for c, h in zip(cards, headings) if not _BAD_HEADING_RE.search(h)]


def scrape_with_attrs(parts, name_line=0, include_subject=False):
    """Scrape variant that uses extract_name_with_attrs / extract_url_with_attrs.

    With include_subject=True, only keep entries whose title text contains a
    CS-related subject (Computer Science, Data Science, Information Science,
    Bioinformatics, Computing, Software Engineering, Cyber). Used to filter
    full-school faculty directories down to CS faculty.
    """
    res = []
    for t in parts:
        try:
            n = extract_name_with_attrs(t, line=name_line)
            ttl = extract_title(t, include_subject=include_subject)
            if not n or ttl is None or not looks_like_name(n):
                continue
            u = extract_url_with_attrs(t, n)
            res.append(create_faculty(n, ttl, url=u))
        except Exception:
            print(f"Error scraping the following tag:\n{t.prettify()}")
            print(traceback.format_exc())
            continue
    return res


def auto_detect_scraper(soup):
    """
    Infer the faculty card pattern from page content. Multi-stage:
      1. Enumerate candidate selectors (classes and a few structural tags) and score each
         (selector, name_line) pair by the number of valid (name, title) extractions.
      2. If no selector clears the threshold, try splitting an `<hr>`- or `<br>`-separated
         block (e.g. faculty entries that are sibling paragraphs separated by `<hr/>`).
      3. Fall back to a per-leaf walk-up: for each title leaf, find the smallest ancestor
         that yields a valid extraction (with attribute-name fallback for custom elements).
    Returns a scraper function or None if no stage finds at least one valid card.
    """
    SKIP_TAGS = {"nav", "footer", "aside"}
    VOID_TAGS = {"br", "hr", "img", "input", "link", "meta", "wbr", "source", "track", "col", "param"}

    NON_TITLE_RE = re.compile(
        r"\b(prerequisite|corequisite|permission of|consent of|"
        r"the (instructor|professor|lecturer)|by the )\b",
        re.I,
    )

    def is_title_leaf(tag):
        if not getattr(tag, "name", None) or tag.name in VOID_TAGS:
            return False
        text = tag.get_text(" ", strip=True)
        if not (5 < len(text) < 300) or not TITLE_RE.search(text):
            return False
        if NON_TITLE_RE.search(text):
            return False
        return not any(
            c.name not in VOID_TAGS
            and TITLE_RE.search(c.get_text(" ", strip=True))
            and len(c.get_text(" ", strip=True)) < 300
            for c in tag.find_all(True)
        )

    title_elems = [
        t for t in soup.find_all(is_title_leaf)
        if not any(getattr(a, "name", None) in SKIP_TAGS for a in t.parents)
    ]
    if not (0 < len(title_elems) <= 500):
        return None

    te_ids = {id(t) for t in title_elems}

    def count_titles(tag):
        return (1 if id(tag) in te_ids else 0) + sum(
            1 for te in title_elems if any(a is tag for a in te.parents)
        )

    def evaluate(instances, nl):
        # Score on descendant-filtered instances — matches what the chosen
        # scraper actually returns at runtime. Excludes wrapper-level matches
        # of self-nesting classes that would extract one person's name paired
        # with another person's title text.
        names = []
        url_count = 0
        instance_ids = set(map(id, instances))
        for t in instances:
            if any(id(d) in instance_ids and id(d) != id(t) for d in t.find_all(True)):
                continue
            n = extract_name(t, line=nl)
            if looks_like_name(n) and extract_title(t) is not None:
                names.append(n)
                if extract_url_with_attrs(t, n) is not None:
                    url_count += 1
        # (valid_count, unique_count, url_count) — duplicates suggest a label was
        # extracted, not a name; url_count tie-breaks between candidates that wrap
        # the same content at different depths (we prefer the wrapper that includes
        # the profile link, e.g. an outer <a> that wraps the inner card).
        return len(names), len(set(names)), url_count

    # ---- Stage 1: class- and tag-based selector scoring ----
    candidate_classes = set()
    for t in title_elems:
        for anc in t.parents:
            for cls in anc.get("class", []) or []:
                candidate_classes.add(cls)

    def _filter_descendants(cards):
        """Among same-class matches, drop those that strictly contain another match.
        This collapses to the deepest level of a self-nesting class (e.g. Mary
        Washington's `wp-block-column-is-layout-flow` matches both per-faculty
        cards and the multi-faculty grid wrappers — keep only the leaf-level
        cards). Cards whose internal multi-title structure represents one person
        with multiple roles (Boerkoel: named chair + "Professor" label) are not
        affected: those don't contain another *same-class* match.
        """
        if not cards:
            return cards
        card_ids = set(map(id, cards))
        out = []
        for t in cards:
            if any(id(d) in card_ids and id(d) != id(t) for d in t.find_all(True)):
                continue
            out.append(t)
        return out

    def class_factory(cls):
        return lambda nl, _c=cls: (
            lambda soup, _cc=_c, _nl=nl, _is=False: scrape_with_attrs(
                filter_cards_by_heading(
                    _filter_descendants(
                        [t for t in soup.find_all(class_=_cc)
                         if not any(getattr(a, "name", None) in SKIP_TAGS for a in t.parents)]
                    )
                ),
                name_line=_nl,
                include_subject=_is,
            )
        )

    def tag_factory(tag_name):
        return lambda nl, _t=tag_name: (
            lambda soup, _tt=_t, _nl=nl, _is=False: scrape_with_attrs(
                filter_cards_by_heading(
                    _filter_descendants(
                        [t for t in soup.find_all(_tt)
                         if not any(getattr(a, "name", None) in SKIP_TAGS for a in t.parents)]
                    )
                ),
                name_line=_nl,
                include_subject=_is,
            )
        )

    candidates = []  # (instances, factory(nl))
    for cls in candidate_classes:
        instances = [
            t for t in soup.find_all(class_=cls)
            if not any(getattr(a, "name", None) in SKIP_TAGS for a in t.parents)
        ]
        with_title = [t for t in instances if count_titles(t) > 0]
        if not (1 < len(with_title) <= 500):
            continue
        if sum(count_titles(t) for t in with_title) / len(with_title) > 3:
            continue
        candidates.append((with_title, class_factory(cls)))

    for tag_name in ("tr", "li", "article", "dt"):
        instances = [
            t for t in soup.find_all(tag_name)
            if not any(getattr(a, "name", None) in SKIP_TAGS for a in t.parents)
        ]
        with_title = [t for t in instances if count_titles(t) > 0]
        if not (1 < len(with_title) <= 500):
            continue
        if sum(count_titles(t) for t in with_title) / len(with_title) > 3:
            continue
        candidates.append((with_title, tag_factory(tag_name)))

    best = None
    # Score: (unique_valid, url_fraction, -duplicates, -wasted, -size). Require valid>=2.
    # url_fraction: bucketed url-rate per valid card; tie-breaks between candidates that
    # wrap the same content at different depths (prefer the wrapper that includes the
    # profile link). -duplicates penalizes selectors that match a row containing
    # multiple people, where the same first name gets extracted twice (e.g.
    # `row-eq-height` matching a 2-up grid where one row holds two faculty cards).
    best_key = (1, 0, 0, 0, 0)
    for instances, factory in candidates:
        for nl in NAME_LINE_OPTIONS:
            valid, unique, urls = evaluate(instances, nl)
            url_fraction = round(urls / valid * 10) if valid else 0
            duplicates = valid - unique
            key = (unique, url_fraction, -duplicates, -(len(instances) - valid), -len(instances))
            if key > best_key:
                best_key = key
                best = (factory, nl)

    if best is not None:
        factory, nl = best
        loose_fn = factory(nl)
        return _maybe_subject_filter(loose_fn, soup)

    # ---- Stage 2: separator-based split (<hr> or <br> between sibling entries) ----
    sep_fn = _try_separator_split(title_elems)

    # ---- Stage 3: walk-up fallback (with attribute-name fallback for custom cards) ----
    def find_card(leaf):
        cur = leaf
        while cur is not None:
            if count_titles(cur) > 1:
                return None
            if extract_title(cur) is not None:
                for nl in NAME_LINE_OPTIONS:
                    if looks_like_name(extract_name_with_attrs(cur, line=nl)):
                        return cur, nl
            cur = cur.parent
        return None

    found = [find_card(t) for t in title_elems]
    found = [f for f in found if f is not None]

    walk_fn = None
    walk_count = 0
    if found:
        name_lines = [nl for _, nl in found]
        common_nl_str = Counter(map(str, name_lines)).most_common(1)[0][0]
        common_nl = next(nl for nl in name_lines if str(nl) == common_nl_str)

        seen = set()
        cards = []
        for c, _ in found:
            if id(c) not in seen:
                seen.add(id(c))
                cards.append(c)

        walk_fn = lambda _soup, _cards=cards, _nl=common_nl: scrape_with_attrs(
            filter_cards_by_heading(_cards), name_line=_nl,
        )
        try:
            walk_count = len(walk_fn(soup))
        except Exception:
            walk_count = 0

    sep_count = 0
    if sep_fn is not None:
        try:
            sep_count = len(sep_fn(soup))
        except Exception:
            sep_count = 0

    # Prefer separator-split when it yields strictly more results — handles cases
    # like New College of Florida, where walk-up succeeds at the wrong level
    # and returns just the first faculty member out of many.
    if sep_fn is not None and sep_count > walk_count:
        return sep_fn
    if walk_fn is not None:
        return walk_fn
    return sep_fn


def _maybe_subject_filter(loose_fn, soup):
    """Wrap loose_fn so it falls back to a CS-subject filtered version when the page
    is clearly a full-school directory.

    Calls loose_fn twice (once normally, once with `include_subject=True`). If the
    strict run returns at least 2 results AND drops the loose count by >50%, the
    loose run was scraping the entire school's faculty (e.g. Lane College, Wheaton
    MA), so we use the strict version. Otherwise we use loose.
    """
    try:
        loose = loose_fn(soup)
    except Exception:
        return loose_fn
    try:
        strict = loose_fn(soup, _is=True)
    except TypeError:
        return loose_fn
    except Exception:
        return loose_fn
    # Apply CS-subject filter only when the strict run drops the loose count by
    # roughly 80%+ — a directory page where only a small fraction of cards are
    # actually CS faculty. Pure CS pages (Williams 14→4, ratio 0.29) and mixed
    # CS+math+stats departments (Macalester 35→18, ratio 0.51) don't trip this;
    # full-school directories like Lane (26→3), Wheaton MA (49→4), and
    # Bridgewater (13→2) do. The `loose >= 10` floor avoids over-filtering
    # tiny pages.
    if len(strict) >= 2 and len(loose) >= 10 and len(loose) > 5 * len(strict):
        return lambda _s, _f=loose_fn: _f(_s, _is=True)
    return loose_fn


def _try_separator_split(title_elems):
    """Detect <hr>- or <br>-separated faculty entries.

    Two patterns:
      (A) Single title leaf whose text contains multiple title mentions — split the
          leaf's HTML by <br/> (e.g. New College of Florida: one <p> with all faculty).
      (B) Multiple title leaves sharing a parent — split that parent's HTML by <hr/>
          (e.g. Coe College: <p> name + <h3> title repeated, separated by <hr>).
    Returns a scraper callable or None.
    """
    if not title_elems:
        return None

    sep_patterns = (r"<hr\s*[^>]*/?\s*>", r"<br\s*[^>]*/?\s*>")

    def make_fn(html, sep_re):
        return lambda _soup, _h=html, _r=sep_re: scrape_with_attrs([
            BeautifulSoup(p, "html.parser") for p in re.split(_r, _h, flags=re.I)
        ])

    # Case A: single leaf with multiple "professor" mentions inside.
    if len(title_elems) == 1:
        leaf = title_elems[0]
        mention_count = len(TITLE_RE.findall(leaf.get_text(" ", strip=True)))
        if mention_count < 2:
            return None
        html = leaf.decode()
        for sep_re in sep_patterns:
            parts = re.split(sep_re, html, flags=re.I)
            if len(parts) < 2:
                continue
            soups = [BeautifulSoup(p, "html.parser") for p in parts]
            if len(scrape_with_attrs(soups)) >= 2:
                return make_fn(html, sep_re)
        return None

    # Case B: multiple leaves — split their LCA by <hr> (or <br>).
    common = set(title_elems[0].parents)
    for t in title_elems[1:]:
        common &= set(t.parents)
    if not common:
        return None
    lca = max(common, key=lambda x: sum(1 for _ in x.parents))

    for sep_re in sep_patterns:
        html = lca.decode()
        parts = re.split(sep_re, html, flags=re.I)
        if len(parts) < len(title_elems):
            continue
        soups = [BeautifulSoup(p, "html.parser") for p in parts]
        results = scrape_with_attrs(soups)
        if len(results) >= max(2, len(title_elems) // 2):
            return make_fn(html, sep_re)
    return None


faculty_scraper_map = {
    College.ALBION: scrape_class_f("list--person"),
    College.ALBRIGHT: scrape_class_f("faculty-item"),
    College.ALLEGHENY: scrape_class_f("col-md-4"),
    College.AMHERST: scrape_class_f("faculty_listing_small"),
    College.AUGUSTANA: scrape_class_f("profile-list-item__details"),
    College.AUSTIN: scrape_class_f("fsConstituentItem"),
    College.BARD: scrape_class_f("multitext"),
    College.BARNARD: scrape_class_f("c--featured-person", name_line=1),
    College.BELOIT: scrape_class_f("profile-card-text"),
    College.BEREA: scrape_class_f("not-prose"),
    College.BETHANY: scrape_class_f("sp-team-pro-item"),
    College.BETHANY_LUTHERAN: scrape_class_f("deptContacts", name_line=1),
    College.BOWDOIN: scrape_class_f("profile-card"),
    College.BRIDGEWATER: scrape_class_f("faculty-page-card", "math-computer-science"),
    College.BRYN_ATHYN: scrape_tag_f("tr"),  # selenium; general faculty dir filtered by CS
    College.BRYN_MAWR: scrape_f(
        lambda s: s.name == "li"
        and (h3 := s.parent.find_previous_sibling("h3")) is not None
        and h3.text == "Faculty"
    ),
    College.BUCKNELL: scrape_class_f("fac-staff-details"),
    College.CARLETON: scrape_class_f("faculty-staff--item"),
    College.CENTRAL: scrape_class_f("staffListing"),
    College.CENTRE: scrape_class_f("block-head"),
    College.COLGATE: scrape_class_f("faculty-staff__list-member"),
    College.COE: scrape_coe_college,
    College.COLBY: scrape_f(
        lambda s: s.name == "td" and s.attrs is not None and "width" in s.attrs
    ),
    College.CLAFLIN: scrape_class_f("profile"),
    College.ST_BENEDICT: scrape_class_f("person-card"),
    College.HOLY_CROSS: scrape_class_f("people_list_card"),
    College.WOOSTER: scrape_class_f("person-entry"),
    College.COLORADO: scrape_class_f("panel-content"),
    College.CONCORDIA: scrape_class_f("directory_item_header"),
    College.CONNECTICUT: scrape_f(lambda s: s.name == "a" and s.h3 is not None),
    College.CORNELL: scrape_class_f("b-text"),
    College.COVENANT: scrape_tag_f("tr"),
    College.DAVIDSON: scrape_class_f("person-teaser__content"),
    College.DENISON: scrape_class_f("people"),
    College.DEPAUW: scrape_f(
        lambda s: soup_has_class(s, "row")
        and s.parent.find_previous_sibling("h2") is None
    ),
    College.DICKINSON: scrape_dickinson_college,
    College.DREW: scrape_class_f("et_pb_accordion_item"),
    College.EARLHAM: scrape_tag_f("main"),
    College.EAST_WEST: scrape_class_f("faculty-bio"),
    College.ECKERD: scrape_class_f("wpb_content_element"),
    College.FRANKLIN: scrape_f(
        lambda s: s.name == "a" and s.find("div", class_="staff-title") is not None
    ),
    College.FRANKLIN_MARSHALL: scrape_class_f("peopleBlock"),
    College.FURMAN: scrape_class_f("module-content-block-people-group-item-contents"),
    College.GETTYSBURG: scrape_class_f("gb-c-link-list__item"),
    College.GORDON: scrape_f(lambda s: s.name == "td" and s.find("h2") is not None),
    College.GOUCHER: scrape_f(
        lambda s: s.name == "p"
        and soup_has_class(s.parent, "user-markup")
        and "Faculty"
        in s.parent.parent.find_previous_sibling("div").get_text(strip=True)
    ),
    College.GRINNEL: scrape_class_f("user__content"),
    College.GUSTAVUS_ADOLPHUS: scrape_class_f("person-container"),
    College.HARVEY_MUDD: scrape_class_f("wp-block-mudd-person-2"),
    College.HAVERFORD: scrape_class_f("faculty-staff-row"),
    College.HAMILTON: scrape_class_f("entity_info"),
    College.HAMPDEN_SYDNEY: scrape_class_f("user-markup"),
    College.HANOVER: scrape_class_f("staff-member"),
    College.HARTWICK: scrape_class_f("slick-slide"),
    College.HENDRIX: scrape_class_f("employeeList-info"),
    College.HOBART_AND_WILLIAM_SMITH: scrape_class_f("listing", name_line=1),
    College.HOPE: scrape_class_f("staff-card", name_line=1),
    College.HOUGHTON: scrape_class_f("excerpt-content"),
    College.ILLINOIS: scrape_class_f("staff"),
    College.JUNIATA: scrape_class_f("show-for-large-up"),
    College.KALAMAZOO: scrape_class_f("wp-block-column"),
    College.KNOX: scrape_class_f("contact-block-link"),
    College.LAFAYETTE: scrape_class_f("people_information"),
    College.LAKE_FOREST: scrape_class_f("profile-box"),
    College.LANE: scrape_class_f("body-block", include_subject=True),
    College.LAWRENCE: scrape_class_f("views-row"),
    College.LEWIS_CLARK: scrape_class_f("profile-list_item_text"),
    College.LINFIELD: scrape_class_f("card-image-3up__card-copy-container"),
    College.LUTHER: scrape_class_f("contact__details"),
    College.LYCOMING: scrape_class_f("lyco-profile"),
    College.LYON: scrape_f(
        lambda s: s.name == "p" and soup_has_class(s.parent, "templatecontent"),
        include_subject=True,
    ),
    College.MACALESTER: scrape_class_f("card-profile"),
    College.MARYVILLE: scrape_class_f("col-md-8"),
    College.MEREDITH: scrape_class_f("people"),
    College.MIDDLEBURY: scrape_class_f("media-object__body"),
    College.MONMOUTH: scrape_class_f("profile-item-text"),
    College.MOUNT_HOLYOKE: scrape_class_f("directory-list__result"),
    College.MUHLENBERG: scrape_class_f("directory-card"),
    College.NEW_FLORIDA: scrape_new_florida,
    College.OBERLIN: scrape_class_f("biography-grid-item"),
    College.OCCIDENTAL: scrape_class_f("profile-details"),
    College.OHIO_WESLEYAN: scrape_class_f("text_image_callout_content"),
    College.POMONA: scrape_class_f("text-brown-300"),
    College.PRESBYTERIAN: scrape_class_f("wpb_column"),
    College.RANDOLPH: scrape_class_f("faculty-member"),
    College.RANDOLPH_MACON: scrape_class_f("wp-block-rmc-profile-info"),
    College.REED: scrape_tag_f("tr"),
    College.RHODES: scrape_class_f("member-info"),
    College.ROANOKE: scrape_f(
        lambda s: soup_has_class(s, "space-y-4") and s.parent.name == "section"
    ),
    College.SAINT_ANSELM: scrape_class_f("o-card__content"),
    College.SAINT_MICHAEL: scrape_class_f("inner", name_line=1),
    College.SKIDMORE: scrape_tag_f("tr"),
    College.SMITH: scrape_class_f("teaser__content"),
    College.SOUTHERN_VIRGINIA: scrape_class_f("bio-card"),
    College.SOUTHWESTERN: scrape_class_f(
        "inpage-search-result__item-data", name_line=1
    ),
    College.ST_LAWRENCE: scrape_class_f("department-item"),
    College.ST_MARY_MD: scrape_class_f("views-row"),
    College.ST_NORBERT: scrape_st_norbert,
    College.ST_OLAF: scrape_class_f("c-faculty__info"),
    College.STONEHILL: scrape_class_f("directory_items", "layout_faculty"),
    College.SUSQUEHANNA: scrape_class_f("faculty-profile"),
    College.SWARTHMORE: scrape_class_f("c-person-detail__content"),
    College.TOUGALOO: scrape_class_f("faculty-card"),
    College.TRANSYLVANIA: scrape_class_f("innerwrap"),
    College.TRINITY_C: scrape_f(
        lambda s: s.name == "table" and soup_has_class(s, "deptmember")
    ),
    College.TRINITY_U: scrape_class_f("paragraph--type--faculty-staff"),
    College.UNION: scrape_class_f("teaser_faculty_card"),
    College.MARY_WASHINGTON: scrape_class_f("wp-block-column"),
    College.MINNESOTA_MORRIS: scrape_f(
        lambda s: s.name == "a"
        and s.div is not None
        and soup_has_class(s.div, "related-wrapper")
    ),
    College.NORTH_CAROLINA_ASHEVILLE: scrape_f(
        lambda s: s.name == "div" and s.h3 is not None
        and s.find("p", class_="FacultyCard__title") is not None
    ),
    College.PUGET_SOUND: scrape_class_f("field-content"),
    College.RICHMOND: scrape_class_f("card"),
    College.SOUTH: scrape_class_f("topic_row"),
    College.VIRGINIA_WISE: scrape_class_f(
        "node--type__person--nametag", name_line=[0, 1]
    ),
    College.URSINUS: scrape_class_f("lw_profiles_type_faculty"),
    College.VASSAR: scrape_class_f("node--faculty--teaser"),
    College.VIRGINIA_WESLEYAN: scrape_class_f("directory-listing"),
    College.WABASH: scrape_class_f("staff-result"),
    College.WARTBURG: scrape_class_f("wbc-person"),
    College.WASHINGTON_LEE: scrape_class_f("listing-thumb"),
    College.WASHINGTON: scrape_class_f("contact-block", name_line=1),
    College.WASHINGTON_JEFFERSON: scrape_class_f("faculty-block"),
    College.WELLESLEY: scrape_class_f("listing-profile"),
    College.WESLEYAN: scrape_wesleyan_college,
    College.WESTMINSTER: scrape_class_f("contact-info"),
    College.WHEATON_IL: scrape_class_f("bm-card--faculty"),
    College.WHEATON_MA: scrape_class_f("department-computer-science"),
    College.WHITMAN: scrape_class_f("card"),
    College.WILLAMETTE: scrape_f(
        lambda s: s.name == "li" and s.parent and soup_has_class(s.parent, "grid")
    ),
    College.WILLIAMS: scrape_f(lambda s: s.name == "td" and not s.attrs),
    College.WITTENBERG: scrape_tag_f("tr"),
    College.WOFFORD: scrape_class_f("staff-profile"),
}

# In rare cases, the faculty list is dynamically generated on the client side
faculty_url_override_map = {
    College.DICKINSON: "https://www2.dickinson.edu/lis/angularJS_services/Data/facultyListsData.cfc?method=f_getDeptFaculty&dID=65",
    College.TRINITY_C: "https://internet3.trincoll.edu/pTools/DeptMembership_wp.aspx?dc=CPSC",
    College.WESLEYAN: "https://webapps.wesleyan.edu/wapi/v1/public/professional_information/academic_plan/COMP",
}

# Some colleges actively block requests
use_selenium_map = {
    College.BEREA: True,      # JS-rendered
    College.CORNELL: True,
    College.DREW: True,
    College.HANOVER: True,    # faculty urls are dynamically generated
    College.HARTWICK: True,   # slick carousel, JS-rendered
    College.HAVERFORD: True,  # blocks requests
    College.HOLY_CROSS: True, # JS-rendered faculty directory
    College.JUNIATA: True,
    College.PRESBYTERIAN: True,
    College.TRINITY_U: True,
    College.WILLAMETTE: True, # JS-rendered
    College.WILLIAMS: True,   # blocks requests
}


def create_selenium_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--ignore-certificate-errors")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def retry_with_selenium(driver, url):
    driver.get(url)
    time.sleep(10)
    return driver.page_source


_PII_PIPELINE = None


def _get_pii_pipeline():
    """Lazy-load the openai/privacy-filter token-classification pipeline."""
    global _PII_PIPELINE
    if _PII_PIPELINE is None:
        from transformers import pipeline
        _PII_PIPELINE = pipeline(
            task="token-classification",
            model="openai/privacy-filter",
            aggregation_strategy="simple",
        )
    return _PII_PIPELINE


def classify_human_names(names, batch_size=32):
    """Return {name: bool} indicating which strings the privacy-filter model
    tags as a person name. Each name is wrapped in `"Hello, {name}."` to give
    the model the contextual signal it expects (calling it on bare tokens
    yields no entities for most real names — see the model card's "Limitations").
    A name passes when at least one `private_person` entity covers >=50% of its
    non-space characters.
    """
    if not names:
        return {}
    pipe = _get_pii_pipeline()
    unique = list(dict.fromkeys(names))
    prompts = [f"Hello, {n}." for n in unique]
    outputs = pipe(prompts, batch_size=batch_size)
    verdicts = {}
    for n, ents in zip(unique, outputs):
        persons = [e for e in ents if e.get("entity_group") == "private_person"]
        coverage = sum(len(e["word"].strip()) for e in persons)
        name_len = max(len(n.replace(" ", "")), 1)
        verdicts[n] = bool(persons) and coverage / name_len >= 0.5
    return verdicts


def url_matches_name(url, name):
    """True if every >=3-char word in `name` appears (lowercased) in `url`.

    Used to rescue real-but-unusual names that the privacy-filter model
    doesn't recognize (April Grow, Georgia Doing) — when the URL contains a
    matching slug, the entry is genuinely about that person.
    """
    if not isinstance(url, str) or not url or not isinstance(name, str):
        return False
    name_parts = [p for p in re.split(r"[\s,.]+", name.lower()) if len(p) >= 3]
    if not name_parts:
        return False
    url_lower = url.lower()
    return all(p in url_lower for p in name_parts)


def filter_non_human_rows(output):
    """Drop rows whose `name` is rejected by the privacy-filter model unless
    the row's `url` matches the name (URL slug rescue). Returns the filtered
    DataFrame and the set of colleges whose entries were ALL dropped.
    """
    if output.empty:
        return output, set()
    names = output["name"].dropna().unique().tolist()
    print(f"Classifying {len(names)} unique names with privacy-filter model...")
    verdicts = classify_human_names(names)
    drop_idx = []
    for idx, row in output.iterrows():
        n = row["name"]
        if not isinstance(n, str) or verdicts.get(n, True):
            continue
        if url_matches_name(row.get("url"), n):
            print(f"  rescued by URL: {n!r} ({row['college']}) -> {row['url']}")
            continue
        print(f"  drop non-human: {n!r} ({row['college']}) url={row.get('url')!r}")
        drop_idx.append(idx)
    if not drop_idx:
        return output, set()
    before_colleges = set(output["college"].unique())
    filtered = output.drop(index=drop_idx).reset_index(drop=True)
    after_colleges = set(filtered["college"].unique())
    emptied = before_colleges - after_colleges
    return filtered, emptied


def get_faculty_list(df):
    names = df["Name"].tolist()
    urls = df["Faculty Link"].tolist()

    # Override bad urls
    for name, url in faculty_url_override_map.items():
        if name not in names:
            continue
        urls[names.index(name)] = url

    name_to_url_map = {name: url for name, url in zip(names, urls)}
    faculty_list = []
    soups_per_college = {}
    used_auto = set()

    driver = create_selenium_driver()

    print("Fetching from urls...")
    results = fetch_all_urls(urls)

    print("Parsing...")
    for name, text, url in zip(names, results, urls):
        if name not in faculty_scraper_map:
            continue

        if name in use_selenium_map:
            print(f"Retrying {name} with Selenium...")
            text = retry_with_selenium(driver, url)

        print(f"Parsing {name}...")
        if text is None:
            print("Nothing to parse!")
            continue

        soup = BeautifulSoup(text, features="html.parser")
        soups_per_college[name] = soup

        faculty = []
        auto_scraper = auto_detect_scraper(soup)
        if auto_scraper is not None:
            try:
                faculty = auto_scraper(soup)
            except Exception:
                print(f"Auto-detection scraper failed for {name}!")
                print(traceback.format_exc())
                faculty = []

        if not faculty:
            print(f"Auto-detection found nothing for {name}; falling back to hardcoded.")
            try:
                faculty = faculty_scraper_map[name](soup)
            except Exception:
                print(f"Error parsing {name} with hardcoded scraper!")
                print(traceback.format_exc())
                faculty = []
        else:
            print(f"Auto-detection found {len(faculty)} for {name}.")
            used_auto.add(name)

        if faculty:
            for f in faculty:
                f["college"] = name
            faculty_list.extend(faculty)
        else:
            print(f"No faculty found for {name}.")

    driver.quit()

    print("Post-processing...")
    output = pd.DataFrame(faculty_list).drop_duplicates(subset=["name", "college"])
    output["url"] = output.apply(
        lambda row: get_full_faculty_url(name_to_url_map[row["college"]], row["url"]),
        axis=1,
    )

    output, emptied_colleges = filter_non_human_rows(output)

    # Colleges where auto returned only entries the model rejected (e.g. SVU's
    # "Apply Now") get a hardcoded fallback now that auto's output is gone.
    fallback_rows = []
    for college_name in emptied_colleges:
        if college_name not in used_auto or college_name not in soups_per_college:
            continue
        print(f"  {college_name}: auto+ML left nothing; running hardcoded fallback...")
        try:
            hard = faculty_scraper_map[college_name](soups_per_college[college_name])
        except Exception:
            hard = []
        if not hard:
            continue
        for f in hard:
            f["college"] = college_name
        fallback_rows.extend(hard)
        print(f"    hardcoded gave {len(hard)} entries")
    if fallback_rows:
        fb_df = pd.DataFrame(fallback_rows).drop_duplicates(subset=["name", "college"])
        fb_df["url"] = fb_df.apply(
            lambda row: get_full_faculty_url(name_to_url_map[row["college"]], row["url"]),
            axis=1,
        )
        output = pd.concat([output, fb_df], ignore_index=True)

    print("Fixing URLs")
    dup = output[pd.notna(output["url"])]
    dup = dup[dup.duplicated(subset=["url"])]
    no_urls = output[pd.isna(output["url"])]
    fix_urls(dup, output)
    fix_urls(no_urls, output)

    return output


def google_search_url(terms, name):
    for url in search(terms, num_results=1): # For some reason, num_results=1 yields 3
        if not is_strange_url(url, name) and not any(p in url for p in ["facebook", "ratemyprofessors", "coursicle"]):
            return url
    return None


def fix_urls(target, output):
    for _, row in target.iterrows():
        if any(
            [
                t in row["title"]
                for t in ["Visiting", "Adjunct", "Instructor", "Lecturer"]
            ]
        ):
            continue
        name = row["name"]
        college = row["college"]
        url = google_search_url(f"{name} Computer Science {college}", name)
        if url is not None:
            print(f"{name}, {college}: {url}")
            output.loc[
                (output["name"] == name) & (output["college"] == college), "url"
            ] = url


if __name__ == "__main__":
    df = get_valid_colleges("../data/colleges.csv")
    df = df[df["Name"].isin(faculty_scraper_map.keys())]
    results = get_faculty_list(df)
    print(results.to_string())
    print(results.groupby(["college"]).size().to_string())
    results.to_csv("../data/faculty_list.csv", index=False)
