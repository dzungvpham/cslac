import argparse
import pandas as pd
import json
import re
import requests
import time
import traceback
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from constants import College
from nameparser import HumanName
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from urllib.parse import urljoin

WEB_DRIVER_PATH = "../driver/chromedriver.exe"


def get_full_faculty_url(faculty_site_url, url):
    return urljoin(faculty_site_url, url) if url is not None else None


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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
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
    if len(lines) <= line:
        return None
    return clean_name(lines[line])


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
        "," in text or re.match(r"^\s*Dr.", text) is not None
    ):  # Handle LAST, FIRST and Dr.
        parsed = HumanName(text)
        text = f"{parsed.first} {parsed.middle} {parsed.last}"

    text = re.sub(r"\s+", " ", text).strip()  # Condense consecutive whitespaces
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

    position_of_regex = r"(professor|lecturer|instructor|chair|director) (of|in) "
    subject_regex = r"([a-z]{3,11}\s?(,|and|&|/)\s?)?(((practice of )?computer)|(data (science|analytics))|(information (science|technology))|(bioinformatics)|(computing))( and)?"

    if (
        (re.search(r"(professor|centennial|lecturer|instructor|chair)", text) is None)
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

    parsed_name = HumanName(name)
    first_name = parsed_name.first.lower()
    last_name = parsed_name.last.lower()
    urls_with_name = [url for url in all_urls if last_name in url or first_name in url]

    if len(urls_with_name) >= 1:
        return min(urls_with_name, key=len)

    return min(all_urls, key=len)


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
        BeautifulSoup(s, features="html.parser") for s in col.prettify().split("<hr/>")
    ]
    return scrape(parts)


def scrape_dickinson_college(soup):
    j = json.loads(soup.text)
    faculty_list = [f for p in j for f in p["FACULTY"]]
    res = []
    for faculty in faculty_list:
        faculty_name = clean_name(faculty["NAME"])
        faculty_title = clean_title(faculty["TITLE"])
        faculty_url = faculty["PROFILE"]
        res.append(create_faculty(faculty_name, faculty_title, url=faculty_url))
    return res


def scrape_holy_cross(soup):
    col = soup.find(lambda s: soup_has_class(s, "prose")).div
    delimiter = "<h3>\n  <strong>\n"
    parts = [
        BeautifulSoup(delimiter + s, features="html.parser")
        for s in col.prettify(formatter="minimal").split(delimiter)
    ]
    return scrape(parts)


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
    College.BETHANY_LUTHERAN: scrape_f(
        lambda s: s.name == "div"
        and soup_has_class(s.parent, "stafflink_smallscreen_container")
    ),
    College.BOWDOIN: scrape_class_f("profile-card"),
    College.BRIDGEWATER: scrape_class_f("faculty-page-card", "math-computer-science"),
    College.BRYN_ATHYN: scrape_tag_f("tr"),
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
        lambda s: s.name == "td" and s.attrs is not None and len(s.attrs) > 0
    ),
    College.CLAFLIN: scrape_class_f("profile"),
    College.ST_BENEDICT: scrape_tag_f("h5"),
    College.HOLY_CROSS: scrape_holy_cross,
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
    College.FRANKLIN: scrape_class_f("post-info", name_line=1),
    College.FRANKLIN_MARSHALL: scrape_class_f("peopleBlock"),
    College.FURMAN: scrape_class_f("module-content-block-people-group-item-contents"),
    College.GETTYSBURG: scrape_class_f("gb-c-link-list__item"),
    College.GORDON: scrape_class_f("facstaff-list-item"),
    College.GOUCHER: scrape_f(
        lambda s: s.name == "p"
        and soup_has_class(s.parent, "user-markup")
        and "Faculty"
        in s.parent.parent.find_previous_sibling("div").get_text(strip=True)
    ),
    College.GRINNEL: scrape_class_f("user__content"),
    College.GUSTAVUS_ADOLPHUS: scrape_class_f("person-container"),
    College.HARVEY_MUDD: scrape_class_f("person-details"),
    College.HAVERFORD: scrape_class_f("entity"),
    College.HAMILTON: scrape_class_f("entity_info"),
    College.HAMPDEN_SYDNEY: scrape_class_f("user-markup"),
    College.HANOVER: scrape_class_f("staff-member"),
    College.HARTWICK: scrape_tag_f("tr"),
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
    College.MACALESTER: scrape_f(
        lambda s: soup_has_class(s, "card-body")
        and s.find_next("h3") is not None
        and "emerit" in s.find_next("h3").text.lower()
    ),
    College.MARYVILLE: scrape_class_f("col-md-8"),
    College.MEREDITH: scrape_class_f("people"),
    College.MIDDLEBURY: scrape_class_f("media-object__body"),
    College.MONMOUTH: scrape_class_f("profile-item-text"),
    College.MOUNT_HOLYOKE: scrape_class_f("directory-list__result"),
    College.MUHLENBERG: lambda s: scrape_tag_f("tr")(
        s.find(lambda ss: ss.name == "table")
    ),
    College.NEW_FLORIDA: scrape_new_florida,
    College.OBERLIN: scrape_class_f("biography-grid-item"),
    College.OCCIDENTAL: scrape_class_f("profile-details"),
    College.OHIO_WESLEYAN: scrape_class_f("text_image_callout_content"),
    College.POMONA: scrape_class_f("text-brown-300"),
    College.SMITH: scrape_class_f("teaser__content"),
    College.SWARTHMORE: scrape_class_f("c-person-detail__content"),
    College.TRINITY_C: scrape_f(
        lambda s: s.name == "table" and soup_has_class(s, "deptmember")
    ),
    College.VASSAR: scrape_class_f("node--faculty--teaser"),
    College.WABASH: scrape_class_f("employee"),
    College.WELLESLEY: scrape_class_f("listing-profile"),
    College.WESLEYAN: scrape_wesleyan_college,
    College.WILLIAMS: scrape_f(lambda s: s.name == "td" and not s.attrs),
}

# In rare cases, the faculty list is dynamically generated on the client side
faculty_url_override_map = {
    College.DICKINSON: "https://www2.dickinson.edu/lis/angularJS_services/Data/facultyListsData.cfc?method=f_getDeptFaculty&dID=65",
    College.TRINITY_C: "https://internet3.trincoll.edu/pTools/DeptMembership_wp.aspx?dc=CPSC",
    College.WESLEYAN: "https://webapps.wesleyan.edu/wapi/v1/public/professional_information/academic_plan/COMP",
}

# Some colleges actively block requests
use_selenium_map = {
    College.BIRMINGHAM_SOUTHERN: True,
    College.DREW: True,
    College.HANOVER: True,  # faculty urls are dynamically generated
}


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
        service = Service(executable_path=WEB_DRIVER_PATH)
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        driver = webdriver.Chrome(service=service, options=options)

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
        faculty = faculty_scraper_map[name](soup)

        if len(faculty) > 0:
            for f in faculty:
                f["college"] = name
            faculty_list.extend(faculty)
        else:
            print(f"No faculty found for {name}!")

    if selenium_backup:
        driver.quit()

    print("Post-processing...")
    output = pd.DataFrame(faculty_list).drop_duplicates()
    output["url"] = output.apply(
        lambda row: get_full_faculty_url(name_to_url_map[row["college"]], row["url"]),
        axis=1,
    )

    return output


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
