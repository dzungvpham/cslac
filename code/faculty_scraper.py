import pandas as pd
import json
import re
import requests
import traceback
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from constants import College
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


def create_faculty(name, title, college, url=None):
    return {
        "name": name,
        "title": title,
        "college": college,
        "url": url,
    }


def clean_name(text):
    if text is None:
        return None
    text = re.sub(r"\(.*\)", "", text)  # Eg: (TEXT)
    text = re.sub(r"\s+.?\d+", "", text)  # Eg: '10
    text = re.sub(r"[A-Z]{3,}", "", text)  # Eg: POM
    text = re.sub(r"\s+", " ", text)  # Condense consecutive whitespaces
    return text.strip()


# Get a valid professor title
def clean_title(text):
    if text is None:
        return None
    text = text.lower()
    if not ("professor" in text or "centennial" in text):
        return None
    if re.search(r"(emerit|practice|visiting|teaching)", text) is not None:
        return None
    if " of " in text and re.search(r"(computer science|data science)", text) is None:
        return None
    if "associate" in text:
        return "Associate Professor"
    if "assistant" in text:
        return "Assistant Professor"
    return "Professor"


def scrape(soup, filter, name, title, college, url=None):
    res = []
    for t in soup.find_all(filter):
        try:
            faculty_name = clean_name(name(t))
            faculty_title = clean_title(title(t))
            if faculty_name is None or faculty_title is None:
                continue

            faculty_url = None
            if url is not None:
                try:
                    faculty_url = url(t)
                except Exception:
                    print(f"Error scraping url for {faculty_name} of {college}:")
                    print(traceback.format_exc())

            res.append(
                create_faculty(faculty_name, faculty_title, college, faculty_url)
            )
        except Exception:
            print(f"Error scraping the following tag for {college}:\n{t.prettify()}")
            print(traceback.format_exc())
            continue
    return res


def soup_has_class(soup_tag, classname):
    return classname in soup_tag.attrs.get("class", [])


def soup_has_class_stub(soup_tag, class_stub):
    return any(class_stub in classname for classname in soup_tag.attrs.get("class", []))


def scrape_albion_college(soup):
    return scrape(
        soup.find(class_="main__side"),
        filter=lambda t: soup_has_class(t, "list--person"),
        name=lambda t: t.find(class_="list__person__name").text,
        title=lambda t: t.find(class_="list__person__title").text,
        url=lambda t: t.find("a", href=True)["href"],
        college=College.ALBION,
    )


def scrape_albright_college(soup):
    return scrape(
        soup.find(id="faculty"),
        filter=lambda t: soup_has_class(t, "faculty-item"),
        name=lambda t: t.find("strong").text.split(",")[0],
        title=lambda t: t.find("br").next_sibling.strip(),
        url=lambda t: t.find("a", href=True)["href"],
        college=College.ALBRIGHT,
    )


def scrape_allegheny_college(soup):
    return scrape(
        soup.find(class_="flex-container"),
        filter=lambda t: soup_has_class(t, "emp"),
        name=lambda t: t.find(class_="sc-name").text,
        title=lambda t: t.find(class_="sc-professional-title").text,
        url=lambda t: t.find(class_="full-profile", href=True)["href"],
        college=College.ALLEGHENY,
    )


def scrape_amherst_college(soup):
    return scrape(
        soup.find(class_="faculty-list"),
        filter=lambda t: soup_has_class(t, "faculty_listing_small"),
        name=lambda t: t.find(class_="faculty_listing_small_name").a.text,
        title=lambda t: t.find(class_="faculty_listing_small_title").text,
        url=lambda t: t.find(class_="faculty_listing_small_name").a["href"],
        college=College.AMHERST,
    )


def scrape_bowdoin_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "profile-card"),
        name=lambda t: t.find(class_="profile-card-name").a.text,
        title=lambda t: t.find(class_="profile-card-title").text,
        url=lambda t: t.find(class_="profile-card-name").a["href"],
        college=College.BOWDOIN,
    )


def scrape_bryn_mawr_college(soup):
    return scrape(
        soup.find(class_="node__content").ul,
        filter=lambda t: t.name == "li",
        name=lambda t: t.a.text,
        title=lambda t: t.em.text,
        url=lambda t: t.a["href"],
        college=College.BRYN_MAWR,
    )


def scrape_bucknell_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "fac-staff-details"),
        name=lambda t: t.a.text,
        title=lambda t: t.find(class_="m-staff-information__title").text,
        url=lambda t: t.a["href"],
        college=College.BUCKNELL,
    )


def scrape_carleton_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "faculty-staff--item"),
        name=lambda t: t.find(class_="faculty-staff--name").text.split("\n")[0],
        title=lambda t: t.find(class_="faculty-staff--title").text,
        url=lambda t: t.find(class_="bio-link")["href"],
        college=College.CARLETON,
    )


def scrape_colgate_college(soup):
    return scrape(
        soup.find(id="current-faculty"),
        filter=lambda t: soup_has_class(t, "faculty-staff__list-member"),
        name=lambda t: t.find(class_="profile__name").a.text,
        title=lambda t: t.find(class_="profile__title").text,
        url=lambda t: t.find(class_="profile__name").a["href"],
        college=College.COLGATE,
    )


def scrape_grinnel_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "user__content"),
        name=lambda t: t.find(class_="user__name").a.text,
        title=lambda t: t.find(class_="user__position").text,
        url=lambda t: t.find(class_="user__name").a["href"],
        college=College.GRINNEL,
    )


def scrape_harvey_mudd_college(soup):
    return scrape(
        soup.find(class_="person-block-wrapper"),
        filter=lambda t: soup_has_class(t, "person-details"),
        name=lambda t: t.find(class_="person-name-text").text,
        title=lambda t: t.find(class_="person-contact").text,
        url=lambda t: t.find(class_="person-name-url")["href"],
        college=College.HARVEY_MUDD,
    )


def scrape_haverford_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "entity"),
        name=lambda t: t.find(class_="profile_link-full-name").a.text,
        title=lambda t: t.find(class_="profile_diplay-title").text,
        url=lambda t: t.find(class_="profile_link-full-name").a["href"],
        college=College.HAVERFORD,
    )


def scrape_macalester_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "card-body")
        and t.find_next("h3") is not None
        and "emerit" in t.find_next("h3").text.lower(),
        name=lambda t: t.find(class_="fn").text,
        title=lambda t: t.find(class_="title").text,
        url=lambda t: t.find(class_="fn").a["href"],
        college=College.MACALESTER,
    )


def scrape_moho_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "directory-list__result"),
        name=lambda t: t.h2.a.text,
        title=lambda t: " ".join(
            li.text for li in t.find(class_="positions").find_all("li")
        ),
        url=lambda t: t.h2.a["href"],
        college=College.MOUNT_HOLYOKE,
    )


def scrape_oberlin_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "biography-grid-item"),
        name=lambda t: t.a.text,
        title=lambda t: t.find(class_="biography-grid-item__title").text,
        url=lambda t: t.a["href"],
        college=College.OBERLIN,
    )


def scrape_pomona_college(soup):
    return scrape(
        soup.find(class_="view-id-staff_listing"),
        filter=lambda t: soup_has_class(t, "text-brown-300"),
        name=lambda t: t.a.text,
        title=lambda t: t.a.parent.div.text,
        url=lambda t: t.a["href"],
        college=College.POMONA,
    )


def scrape_smith_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "teaser__content"),
        name=lambda t: t.find(class_="heading__link").span.text,
        title=lambda t: t.find(class_="teaser__subheading").text,
        url=lambda t: t.find(class_="heading__link")["href"],
        college=College.SMITH,
    )


def scrape_swarthmore_college(soup):
    return scrape(
        soup.find(id="computer-science-faculty-"),
        filter=lambda t: soup_has_class(t, "c-person-detail__content"),
        name=lambda t: t.find(class_="c-person-detail__title").text,
        title=lambda t: t.find(class_="c-person-detail__role").text,
        url=lambda t: t.find(class_="c-person-detail__links").a["href"],
        college=College.SWARTHMORE,
    )


def scrape_trinity_college(soup):
    return scrape(
        soup,
        filter=lambda t: t.name == "table" and soup_has_class(t, "deptmember"),
        name=lambda t: t.td.a.text,
        title=lambda t: t.find_all("td")[1].text,
        url=lambda t: t.td.a["href"],
        college=College.TRINITY_C,
    )


def scrape_vassar_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "node--faculty--teaser"),
        name=lambda t: t.a.text,
        title=lambda t: t.find(class_="faculty-title").text,
        url=lambda t: t.a["href"],
        college=College.VASSAR,
    )


def scrape_wellesley_college(soup):
    return scrape(
        soup,
        filter=lambda t: soup_has_class(t, "listing-profile"),
        name=lambda t: t.find(class_="profile-name").h4.text,
        title=lambda t: t.find(lambda t: t.name == "p" and t.text != "").em.text,
        url=lambda t: t.find(class_="profile-name").a["href"],
        college=College.WELLESLEY,
    )


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
        res.append(
            create_faculty(faculty_name, faculty_title, College.WESLEYAN, faculty_url)
        )
    return res


def scrape_williams_college(soup):
    return scrape(
        soup,
        filter=lambda t: t.name == "td" and not t.attrs,
        name=lambda t: t.strong.text.split(",")[0],
        title=lambda t: t.strong.text,
        url=lambda t: t.find_all("a")[1]["href"],
        college=College.WILLIAMS,
    )


faculty_scraper_map = {
    College.ALBION: scrape_albion_college,
    College.ALBRIGHT: scrape_albright_college,
    College.ALLEGHENY: scrape_allegheny_college,
    College.AMHERST: scrape_amherst_college,
    College.BOWDOIN: scrape_bowdoin_college,
    College.BRYN_MAWR: scrape_bryn_mawr_college,
    College.BUCKNELL: scrape_bucknell_college,
    College.CARLETON: scrape_carleton_college,
    College.COLGATE: scrape_colgate_college,
    College.GRINNEL: scrape_grinnel_college,
    College.HARVEY_MUDD: scrape_harvey_mudd_college,
    College.HAVERFORD: scrape_haverford_college,
    College.MACALESTER: scrape_macalester_college,
    College.MOUNT_HOLYOKE: scrape_moho_college,
    College.OBERLIN: scrape_oberlin_college,
    College.POMONA: scrape_pomona_college,
    College.SMITH: scrape_smith_college,
    College.SWARTHMORE: scrape_swarthmore_college,
    College.TRINITY_C: scrape_trinity_college,
    College.VASSAR: scrape_vassar_college,
    College.WELLESLEY: scrape_wellesley_college,
    College.WESLEYAN: scrape_wesleyan_college,
    College.WILLIAMS: scrape_williams_college,
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
        soup = BeautifulSoup(text, features="html.parser")
        faculty_list.extend(faculty_scraper_map[name](soup))

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
