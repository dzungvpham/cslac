"""Bennington College course schedule scraper.

URL pattern: /curriculum/courses/term/{fall|spring}-{YYYY}?aos[26]=26
where YYYY is the term's calendar year (Fall uses the academic year's start
year, Spring its end year) and `aos[26]=26` is Bennington's "Computer Science"
area-of-study filter. Each page lists one term and is server-rendered, so we
fetch it with `requests` instead of Selenium.

Each course is an `<article class="course-listing-teaser">` whose `<h2>` reads
"Course Name — CODE.SECTION" (em-dash separator, e.g. "Data Structures and
Algorithms — CS4388.01"); the meeting block carries `.faculty`
("Instructor: …") and `.daytime` ("Days & Time: …").

Computer Science is a recent area of study at Bennington, so the CS filter
returns nothing for terms before Fall 2025 (those term pages load fine but list
no CS courses). Coverage therefore accrues going forward via the quarterly
top-up run, like the Self-Service catalogs.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://www.bennington.edu"
# aos[26]=26 is Bennington's Computer Science area-of-study taxonomy filter.
LIST_URL = BASE_URL + "/curriculum/courses/term/{slug}?aos%5B26%5D=26"

# h2 text: "Course Name — CS4388.01". The name itself may contain a dash, so
# anchor the trailing "<DASH> SUBJNNN.SECTION" at the end of the string.
CODE_RE = re.compile(r"\s*[—–-]\s*(?P<code>[A-Z]{2,4}\d+)\.(?P<section>\w+)\s*$")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}


class BenningtonScraper(CourseScheduleScraper):
    college = College.BENNINGTON
    terms = ["F", "S"]
    public_url_template = True

    def url_for(self, academic_year, term):
        # Fall uses the academic year's start calendar year; Spring its end.
        year = academic_year[0] if term == "F" else academic_year[1]
        slug = f"{'fall' if term == 'F' else 'spring'}-{year}"
        return LIST_URL.format(slug=slug)

    def fetch_page(self, academic_year, term):
        # Pages are server-rendered — fetch directly, no Selenium needed.
        resp = requests.get(
            self.url_for(academic_year, term), headers=HEADERS, timeout=30
        )
        return resp.text if resp.status_code == 200 else None

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for art in soup.select("article.course-listing-teaser"):
            head = art.find(["h2", "h3"])
            if head is None:
                continue
            heading = re.sub(r"\s+", " ", head.get_text(" ", strip=True)).strip()
            m = CODE_RE.search(heading)
            if m:
                course_code = m.group("code")
                section = m.group("section")
                course_name = heading[: m.start()].strip()
            else:
                course_code, section, course_name = "", "", heading

            link = head.find("a", href=True) or art.find("a", href=True)
            href = link["href"] if link else ""
            if href and not href.startswith("http"):
                href = BASE_URL + href

            fac = art.select_one(".faculty")
            instructor = ""
            if fac is not None:
                instructor = re.sub(r"\s+", " ", fac.get_text(" ", strip=True))
                instructor = re.sub(r"^Instructor:\s*", "", instructor).strip()

            day = art.select_one(".daytime")
            time_str = ""
            if day is not None:
                time_str = re.sub(r"\s+", " ", day.get_text(" ", strip=True))
                time_str = re.sub(r"^Days?\s*&\s*Time:\s*", "", time_str).strip()

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_str,
                    url=href,
                )
            )
        return rows
