import pandas as pd
import json
import re
import requests
import traceback
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from constants import College
from nameparser import HumanName
from urllib.parse import urlparse


def extract_base_url(url):
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}/"


def get_full_url(faculty_url, url):
    if url is None:
        return None
    base_url = extract_base_url(faculty_url)
    if url.startswith("/"):
        if base_url.endswith("/"):
            return base_url[:-1] + url
        return base_url + url
    return url


def clean_url(url):
    if url is None or re.match(r"(mailto|tel):", url) is not None:
        return None
    return url


def fetch_url(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(url, headers=headers)
        return response.text
    except Exception as e:
        if e.__class__.__name__ == "SSLError" and (
            url.startswith("https://www.coe.edu/")
            or url.startswith("https://www.westpoint.edu/")
        ):
            print(f"Retrying {url} with verify=False")
            try:
                response = requests.get(url, verify=False)
                return response.text
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


def extract_name(soup):
    text = soup.get_text("||", strip=True).split("||")[0]
    return clean_name(text)


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
    text = re.sub(r"\s+", " ", text)  # Condense consecutive whitespaces
    return text.strip()


def extract_title(soup):
    text = soup.get_text("\n", strip=True)
    return clean_title(text)


# Get a valid professor title
def clean_title(text):
    if text is None:
        return None
    text = text.lower()
    if (
        (re.search(r"(professor|centennial|lecturer|instructor)", text) is None)
        or (re.search(r"(emerit)", text) is not None)
        or (
            re.search(r"(professor|lecturer|instructor) of ", text) is not None
            and re.search(r"(computer|data) science", text) is None
        )
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
    all_urls = list(set(all_urls))  # Dedup
    all_urls = [url for url in all_urls if "email-protection" not in url]

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


def scrape(soup, filter):
    res = []
    for t in soup.find_all(filter):
        try:
            faculty_name = extract_name(t)
            faculty_title = extract_title(t)
            faculty_url = extract_url(t, faculty_name)
            if faculty_name is None or faculty_title is None:
                continue

            res.append(create_faculty(faculty_name, faculty_title, url=faculty_url))
        except Exception:
            print(f"Error scraping the following tag:\n{t.prettify()}")
            print(traceback.format_exc())
            continue
    return res


def scrape_f(filter):
    return lambda soup: scrape(soup, filter)


def soup_has_class(soup_tag, classname):
    return classname in soup_tag.attrs.get("class", [])


def soup_has_class_stub(soup_tag, class_stub):
    return any(class_stub in classname for classname in soup_tag.attrs.get("class", []))


def scrape_class_f(classname):
    return scrape_f(lambda soup: soup_has_class(soup, classname))


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
    College.ALLEGHENY: scrape_class_f("emp"),
    College.AMHERST: scrape_class_f("faculty_listing_small"),
    College.BOWDOIN: scrape_class_f("profile-card"),
    College.BRYN_MAWR: scrape_f(
        lambda t: t.name == "li"
        and (h3 := t.parent.find_previous_sibling("h3")) is not None
        and h3.text == "Faculty"
    ),
    College.BUCKNELL: scrape_class_f("fac-staff-details"),
    College.CARLETON: scrape_class_f("faculty-staff--item"),
    College.COLGATE: scrape_class_f("faculty-staff__list-member"),
    College.GRINNEL: scrape_class_f("user__content"),
    College.HARVEY_MUDD: scrape_class_f("person-details"),
    College.HAVERFORD: scrape_class_f("entity"),
    College.MACALESTER: scrape_f(
        lambda t: soup_has_class(t, "card-body")
        and t.find_next("h3") is not None
        and "emerit" in t.find_next("h3").text.lower()
    ),
    College.MOUNT_HOLYOKE: scrape_class_f("directory-list__result"),
    College.OBERLIN: scrape_class_f("biography-grid-item"),
    College.POMONA: scrape_class_f("text-brown-300"),
    College.SMITH: scrape_class_f("teaser__content"),
    College.SWARTHMORE: scrape_class_f("c-person-detail__content"),
    College.TRINITY_C: scrape_f(
        lambda t: t.name == "table" and soup_has_class(t, "deptmember")
    ),
    College.VASSAR: scrape_class_f("node--faculty--teaser"),
    College.WELLESLEY: scrape_class_f("listing-profile"),
    College.WESLEYAN: scrape_wesleyan_college,
    College.WILLIAMS: scrape_f(lambda t: t.name == "td" and not t.attrs),
}

# In rare cases, the faculty list is dynamically generated on the client side
faculty_url_override_map = {
    College.TRINITY_C: "https://internet3.trincoll.edu/pTools/DeptMembership_wp.aspx?dc=CPSC",
    College.WESLEYAN: "https://webapps.wesleyan.edu/wapi/v1/public/professional_information/academic_plan/COMP",
}


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

    print("Fetching from urls...")
    results = fetch_all_urls(urls)

    print("Parsing...")
    for name, text in zip(names, results):
        if text is None or name not in faculty_scraper_map:
            continue
        print(f"Parsing {name}...")
        soup = BeautifulSoup(text, features="html.parser")
        faculty = faculty_scraper_map[name](soup)
        for f in faculty:
            f["college"] = name
        faculty_list.extend(faculty)

    print("Post-processing...")
    output = pd.DataFrame(faculty_list).drop_duplicates()
    output["url"] = output.apply(
        lambda row: get_full_url(name_to_url_map[row["college"]], row["url"]), axis=1
    )

    return output


if __name__ == "__main__":
    df = get_valid_colleges("../data/colleges.csv")
    df = df[df["Name"].isin(faculty_scraper_map.keys())]
    print(get_faculty_list(df).to_string())
