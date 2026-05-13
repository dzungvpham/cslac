"""Washington and Lee University course schedule scraper.

W&L publishes course offerings at

    https://managementtools4.wlu.edu/CourseOfferings/

The page is an ASP.NET WebForms app that accepts ``AP`` (academic
period) and ``SUBJ`` query-string parameters and renders matching
sections into a table with id ``EmbededContentsPlaceHolder_CoursesTable``.
The schedule does not include meeting times — only subject, course
section ("CSCI 111-01 - Fundamentals of Programming I"), faculty,
prerequisite text, credit, and curricular tags.

W&L runs on a Fall / Winter / Spring trimester calendar (plus a
Summer term that's usually empty for CS).
"""

import re
import sys
from html import unescape
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://managementtools4.wlu.edu/CourseOfferings/"

TERM_LABEL = {"F": "Fall", "W": "Winter", "S": "Spring", "Su": "Summer"}

# `CSCI 111-01 - Fundamentals of Programming I` -> (`CSCI 111`, `01`, name)
SECTION_RE = re.compile(
    r"^(?P<subj>[A-Z]+)\s+(?P<num>\d+\w*)-(?P<section>\w+)\s*-\s*(?P<name>.+)$"
)


class WashingtonLeeScraper(CourseScheduleScraper):
    college = College.WASHINGTON_LEE
    terms = ["F", "W", "S"]
    fresh_driver_per_load = False  # no Selenium needed

    def url_for(self, academic_year, term):
        start, end = academic_year
        ap = f"{start}-{end} Undergraduate {TERM_LABEL[term]}"
        return f"{BASE_URL}?AP={ap}&SUBJ=CSCI"

    def fetch_page(self, academic_year, term):
        start, end = academic_year
        ap = f"{start}-{end} Undergraduate {TERM_LABEL[term]}"
        try:
            r = requests.get(BASE_URL, params={"AP": ap, "SUBJ": "CSCI"}, timeout=60)
        except requests.RequestException:
            return None
        if r.status_code != 200:
            return None
        return r.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find(id="EmbededContentsPlaceHolder_CoursesTable")
        if table is None:
            return []
        rows = []
        for tr in table.find_all("tr")[1:]:  # skip header
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            section_text = _clean(unescape(tds[1].get_text(" ", strip=True)))
            m = SECTION_RE.match(section_text)
            if not m:
                continue
            instructor = _clean(unescape(tds[2].get_text(" ", strip=True)))
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=f"{m.group('subj')} {m.group('num')}",
                    section=m.group("section"),
                    course_name=m.group("name"),
                    instructor=instructor,
                    time="",
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
