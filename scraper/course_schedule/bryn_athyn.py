"""Bryn Athyn College course schedule scraper.

Bryn Athyn publishes its public schedule on a Jenzabar Cloud form at
``https://brynathyn.jenzabarcloud.com/GENSRsC.cfm``. POSTing a year +
semester + campus selection returns a static HTML table of every course
across the school; we filter to the ``CSci`` subject ourselves since the
form has no department dropdown.

Term values are a 6-digit academic-year code (e.g. ``"202526"`` for AY
2025-26) plus a one-character semester code (``"1 "`` Fall, ``"2 "``
Winter, ``"3 "`` Spring; trailing space is part of the value). Only the
current and next academic years are usually exposed.

Each result row is a single ``<tr>`` with cells: course title (with the
course code in trailing parentheses, e.g. ``"Introduction to Computer
Systems (QR) (CSci105)"``), section, blank, credits, division
(``"College Undergraduate"``), instructor, schedule string, enrollment
count, blank, blank, blank.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

URL = "https://brynathyn.jenzabarcloud.com/GENSRsC.cfm"
SUBJECT = "CSci"

# Bryn Athyn's six-digit academic-year value: "202526" = AY 2025-26.
YEAR_VALUE_RE = re.compile(r"^(\d{4})(\d{2})$")

# Semester values include trailing spaces in the option `value` attr
# (``"1 "`` etc.), so the dict keys must match exactly.
SEMESTER_VALUES = {"F": "1 ", "S": "3 "}

# Course-code pattern inside the title cell: "(CSci105)" — the subject is
# mixed-case and the number can have trailing alpha (e.g. "CSci105L").
COURSE_CODE_RE = re.compile(r"\(CSci\s*(?P<num>\d+\w*)\)")


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class BrynAthynScraper(CourseScheduleScraper):
    college = College.BRYN_ATHYN
    terms = []  # discovered at runtime
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._session = requests.Session()
        self._available = None  # (academic_year, term) -> form value

    def _discover_terms(self):
        if self._available is not None:
            return self._available
        resp = self._session.get(URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        year_select = soup.find("select", {"name": "chkschyear"})
        years = []
        if year_select is not None:
            for opt in year_select.find_all("option"):
                value = (opt.get("value") or "").strip()
                m = YEAR_VALUE_RE.match(value)
                if m:
                    start = int(m.group(1))
                    end_yy = int(m.group(2))
                    end = (start // 100) * 100 + end_yy
                    if end < start:
                        end += 100
                    years.append(((start, end), value))
        out = {}
        for ay, year_value in years:
            for term, sem_value in SEMESTER_VALUES.items():
                out[(ay, term)] = (year_value, sem_value)
        self._available = out
        return out

    def schedule_pages(self):
        available = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in ("F", "S"):
                if (ay, t) in available:
                    yield ay, t

    def fetch_page(self, academic_year, term):
        available = self._discover_terms()
        pair = available.get((academic_year, term))
        if pair is None:
            return None
        year_value, sem_value = pair
        data = {
            "chkschyear": year_value,
            "chkschsem": sem_value,
            "chckcamp": "",
            "Submit": "Search",
        }
        resp = self._session.post(URL, data=data, timeout=45)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        # Each course is one <tr> whose first <td> contains an anchor whose
        # text holds the title and the parenthesized course code.
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 7:
                continue
            title_text = _clean(cells[0].get_text(" ", strip=True))
            code_m = COURSE_CODE_RE.search(title_text)
            if not code_m:
                continue
            course_code = f"CSci {code_m.group('num')}"
            # Strip the trailing "(CSciNNN)" from the title.
            title = _clean(re.sub(r"\(CSci\s*\d+\w*\)\s*$", "", title_text))
            section = _clean(cells[1].get_text(" ", strip=True))
            instructor = _clean(cells[5].get_text(" ", strip=True))
            schedule = _clean(cells[6].get_text(" ", strip=True))
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=title,
                    instructor=instructor,
                    time=schedule,
                    url=URL,
                )
            )
        return rows
