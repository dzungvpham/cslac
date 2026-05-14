"""Westminster College (PA) course schedule scraper.

Westminster's public schedule lives in an iframe served straight from
ColdFusion at

    https://www4.westminster.edu/resources/academics/course-schedule.cfm
        ?year=YYYY&term=TT&subject=CS&clusters_only=0&open_only=0
        &sl_only=0&rs_only=0&division=UG

`year` is the academic year as a four-digit string of the two-digit
start year followed by the two-digit end year (`2526` = 2025-26).
`term` is a two-digit code: `10` = Fall, `20` = Spring, `30` = Summer.

The page is server-rendered HTML — no Selenium needed. Each section is
a `<tr>` in `<table id="course-schedule">` with columns
``Course | Title | Credits | Instructor | Meetings | Location | …``.
The "Course" cell wraps `"CS  <num>  <section>  <subterm-label>"`
(e.g. ``"CS   112  01  1st 7-weeks"``).

Westminster only exposes the current and the upcoming academic year on
this page (older years just render "No courses match the search
criteria"); the merge logic in `CourseScheduleScraper.run` preserves
whatever we captured for prior terms.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = (
    "https://www4.westminster.edu/resources/academics/course-schedule.cfm"
    "?year={year}&term={term}&subject=CS&clusters_only=0&open_only=0"
    "&sl_only=0&rs_only=0&division=UG"
)

TERM_CODE = {"F": "10", "S": "20", "Su": "30"}

COURSE_CELL_RE = re.compile(
    r"^(?P<subject>[A-Z]+)\s+(?P<num>\d+)\s+(?P<section>\w+)\b"
)


class WestminsterPAScraper(CourseScheduleScraper):
    college = College.WESTMINSTER
    terms = ["F", "S"]
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None

    def _ensure_session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(
                {"User-Agent": "Mozilla/5.0 (cs-lac scraper)"}
            )
        return self._session

    @staticmethod
    def _year_code(academic_year):
        start, end = academic_year
        return f"{start % 100:02d}{end % 100:02d}"

    def url_for(self, academic_year, term):
        return BASE_URL.format(
            year=self._year_code(academic_year), term=TERM_CODE[term]
        )

    def fetch_page(self, academic_year, term):
        s = self._ensure_session()
        resp = s.get(self.url_for(academic_year, term), timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", id="course-schedule")
        if table is None:
            return []
        tbody = table.find("tbody")
        if tbody is None:
            return []
        url = self.url_for(academic_year, term)
        rows = []
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue
            course_cell = _clean(cells[0].get_text(" "))
            m = COURSE_CELL_RE.match(course_cell)
            if not m:
                continue
            course_code = f"{m.group('subject')} {m.group('num')}"
            section = m.group("section")
            course_name = _clean(cells[1].get_text(" "))
            instructor = _instructor(cells[3])
            meeting = _clean(cells[4].get_text(" "))
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=meeting,
                    url=url,
                )
            )
        return rows

    def close(self):
        super().close()
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def _instructor(cell):
    """Names are separated by `<br />` inside the instructor cell. Some
    rows append a trailing empty entry, leaving a stray comma; drop it.
    """
    parts = [
        _clean(p) for p in cell.get_text("|").split("|") if _clean(p)
    ]
    return ", ".join(parts)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
