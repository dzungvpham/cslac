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


def clean_url(url):
    if (
        url is None
        or re.match(r"(mailto|tel):", url) is not None
        or url == "#"
        or url == ""
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
        name = ""
        for l in line:
            name += lines[l].strip() + " "
        return clean_name(name[:-1])


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
        or re.match(r"^\s*(Dr.|Lt. Col.|Col.|Maj.|Mr.|Mrs.|Ms.)", text) is not None
    ):  # Handle LAST, FIRST and Dr.
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
    subject_regex = r"([a-z]{3,11}\s?(,|and|&|/)\s?)?(((practice of )?computer)|(data (science|analytics))|(information (science|technology|system))|(bioinformatics)|(computing)|(software engineering)|(cyber))( and)?"

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


def auto_detect_scraper(soup):
    """
    Infer faculty card pattern from page content when the hardcoded scraper returns nothing.
    Finds elements containing job title keywords, walks up to the card boundary using the
    common ancestor, and returns a scrape_class_f scraper for the most discriminative class.
    Returns None if detection fails at any step.
    """
    TITLE_RE = re.compile(r"\b(professor|lecturer|instructor)\b", re.I)
    SKIP_TAGS = {"header", "nav", "footer", "aside"}

    def is_title_leaf(tag):
        if not getattr(tag, "name", None):
            return False
        # Use space-separated text so "ProfessorX@email.com" becomes "Professor X@email.com"
        text = tag.get_text(" ", strip=True)
        if not (5 < len(text) < 150) or not TITLE_RE.search(text):
            return False
        return not any(
            TITLE_RE.search(c.get_text(" ", strip=True)) and len(c.get_text(" ", strip=True)) < 150
            for c in tag.find_all(True)
        )

    title_elems = [
        t for t in soup.find_all(is_title_leaf)
        if not any(getattr(a, "name", None) in SKIP_TAGS for a in t.parents)
    ]
    if not (1 < len(title_elems) <= 50):
        return None

    def get_depth(tag):
        return sum(1 for _ in tag.parents)

    depths = [get_depth(t) for t in title_elems]
    depth_counts = Counter(depths)
    max_freq = depth_counts.most_common(1)[0][1]
    mode_depth = max(d for d, c in depth_counts.items() if c == max_freq)
    title_elems = [t for t, d in zip(title_elems, depths) if d == mode_depth]
    if not (1 < len(title_elems) <= 50):
        return None

    def get_ancestors(tag):
        return list(reversed(list(tag.parents)))  # root → immediate parent

    anc_lists = [get_ancestors(t) for t in title_elems]
    lca = anc_lists[0][-1]
    for i, anc in enumerate(anc_lists[0]):
        if all(i < len(lst) and lst[i] is anc for lst in anc_lists):
            lca = anc
        else:
            break

    def count_titles(tag):
        return sum(1 for te in title_elems if any(a is tag for a in te.parents))

    def find_cards(node):
        children = [c for c in node.children if getattr(c, "name", None)]
        if not children:
            return None
        relevant = [(c, count_titles(c)) for c in children if count_titles(c) > 0]
        if not relevant:
            return None
        max_n = max(n for _, n in relevant)
        # If no child has many title elements, treat them all as cards.
        # ≤ 3 allows for faculty with multiple title lines (e.g., endowed chair + rank).
        if max_n <= 3:
            return [c for c, _ in relevant]
        # Otherwise the children are section containers — recurse into all of them.
        # Sections that yield no CS-title faculty (sub=None) are silently skipped.
        cards = []
        for child, _ in relevant:
            sub = find_cards(child)
            if sub is not None:
                cards.extend(sub)
        return cards if cards else None

    cards = find_cards(lca)
    if not cards or not (1 < len(cards) <= 50):
        return None

    page_freq = Counter(
        cls for t in soup.find_all(True) for cls in t.get("class", [])
    )

    def best_class_for(card_list):
        """Return (best_cls, passes) for a list of candidate cards."""
        classes = [set(c.get("class", [])) for c in card_list]
        common = classes[0].intersection(*classes[1:])
        if not common:
            return None, False
        best = min(common, key=lambda c: page_freq[c])
        return best, page_freq[best] <= len(card_list) * 3

    def probe_name_line(cls):
        sample = soup.find_all(lambda t: soup_has_class(t, cls))[:5]
        v0 = sum(1 for t in sample if extract_name(t, line=0) is not None)
        v1 = sum(1 for t in sample if extract_name(t, line=1) is not None)
        return 1 if v1 > v0 else 0

    # Classes that belong to the title elements themselves — used to avoid
    # descending into them during class-based fallbacks.
    title_elem_classes = set().union(*(set(te.get("class", [])) for te in title_elems))

    # Try class-based match on the cards returned by find_cards
    best_cls, ok = best_class_for(cards)
    if ok and best_cls not in title_elem_classes:
        return scrape_class_f(best_cls, name_line=probe_name_line(best_cls))

    # Fallback 1: descend repeatedly through classless wrappers until reaching
    # class-bearing cards (e.g., W&L: two classless wrapper divs → div.listing-thumb)
    current = cards
    for _ in range(6):  # at most 6 extra levels
        next_level = []
        any_progress = False
        for card in current:
            children_with_titles = [
                c for c in card.children
                if getattr(c, "name", None) and count_titles(c) > 0
            ]
            if children_with_titles:
                next_level.extend(children_with_titles)
                any_progress = True
            else:
                next_level.append(card)
        if not any_progress or not (1 < len(next_level) <= 50):
            break
        best_cls, ok = best_class_for(next_level)
        if ok and best_cls not in title_elem_classes:
            return scrape_class_f(best_cls, name_line=probe_name_line(best_cls))
        current = next_level

    # Fallback 2: tag + parent class (e.g., Willamette: <li> inside <ul class="grid">)
    # `current` is the deepest level reached by Fallback 1 (may equal cards if no descent occurred).
    work_cards = current if len(current) > len(cards) else cards
    tag_counts = Counter(c.name for c in work_cards)
    common_tag = tag_counts.most_common(1)[0][0]
    same_tag_cards = [c for c in work_cards if c.name == common_tag]
    parent_class_sets = [set(c.parent.get("class", [])) for c in same_tag_cards if c.parent]
    if parent_class_sets:
        common_parent_cls = parent_class_sets[0].intersection(*parent_class_sets[1:])
        if common_parent_cls:
            best_parent_cls = min(common_parent_cls, key=lambda c: page_freq[c])
            if page_freq[best_parent_cls] <= len(same_tag_cards) * 3:
                tag, pcls = common_tag, best_parent_cls
                sample = [
                    c for c in soup.find_all(tag)
                    if c.parent and soup_has_class(c.parent, pcls)
                ][:5]
                v0 = sum(1 for t in sample if extract_name(t, line=0) is not None)
                v1 = sum(1 for t in sample if extract_name(t, line=1) is not None)
                nl = 1 if v1 > v0 else 0
                return scrape_f(
                    lambda s, _t=tag, _p=pcls: (
                        s.name == _t and s.parent is not None and soup_has_class(s.parent, _p)
                    ),
                    name_line=nl,
                )

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


def get_faculty_list(df, selenium_backup=False):
    names = df["Name"].tolist()
    urls = df["Faculty Link"].tolist()

    # Override bad urls
    for name, url in faculty_url_override_map.items():
        if name not in names:
            continue
        urls[names.index(name)] = url

    name_to_url_map = {name: url for name, url in zip(names, urls)}
    faculty_list = []

    if selenium_backup:
        driver = create_selenium_driver()

    print("Fetching from urls...")
    results = fetch_all_urls(urls)

    print("Parsing...")
    for name, text, url in zip(names, results, urls):
        if name not in faculty_scraper_map:
            continue

        if selenium_backup and name in use_selenium_map:
            print(f"Retrying {name} with Selenium...")
            text = retry_with_selenium(driver, url)

        print(f"Parsing {name}...")
        if text is None:
            print("Nothing to parse!")
            continue

        soup = BeautifulSoup(text, features="html.parser")
        try:
            faculty = faculty_scraper_map[name](soup)
        except Exception:
            print(f"Error parsing {name}!")
            print(traceback.format_exc())
            continue

        if len(faculty) > 0:
            for f in faculty:
                f["college"] = name
            faculty_list.extend(faculty)
        else:
            print(f"No faculty found for {name}! Attempting auto-detection...")
            auto_scraper = auto_detect_scraper(soup)
            if auto_scraper is not None:
                try:
                    faculty = auto_scraper(soup)
                except Exception:
                    print(f"Auto-detection scraper failed for {name}!")
                    print(traceback.format_exc())
                    faculty = []
                if faculty:
                    print(f"Auto-detection found {len(faculty)} for {name}.")
                    for f in faculty:
                        f["college"] = name
                    faculty_list.extend(faculty)
                else:
                    print(f"Auto-detection also found nothing for {name}.")
            else:
                print(f"Auto-detection could not identify a pattern for {name}.")

    if selenium_backup:
        driver.quit()

    print("Post-processing...")
    output = pd.DataFrame(faculty_list).drop_duplicates()
    output["url"] = output.apply(
        lambda row: get_full_faculty_url(name_to_url_map[row["college"]], row["url"]),
        axis=1,
    )

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
    parser = argparse.ArgumentParser(description="Script for scraping faculty.")
    parser.add_argument(
        "--selenium-backup",
        action="store_true",
        help="Use Selenium in case a college does not have any results. (Default: Disabled)",
    )
    args = parser.parse_args()

    df = get_valid_colleges("../data/colleges.csv")
    df = df[df["Name"].isin(faculty_scraper_map.keys())]
    results = get_faculty_list(df, selenium_backup=args.selenium_backup)
    print(results.to_string())
    print(results.groupby(["college"]).size().to_string())
    results.to_csv("../data/faculty_list.csv", index=False)
