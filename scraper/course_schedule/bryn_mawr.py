"""Bryn Mawr College course schedule scraper.

The Tri-Co course search exposes a server-rendered results page that
takes the semester, department, and college as repeated query
parameters:

    https://www.brynmawr.edu/inside/academic-information/registrar/
        tri-co-course-search/results
        ?semester[0]={fall|spring}_{YYYY}
        &department[0]=Computer Science
        &college[0]=bryn_mawr
        &page=1&per_page=50

Only fall/spring semesters are searchable. Each section is a `<tr>` in
`table.result-table` with cells:

    Registration-ID  (e.g. "CMSCB113001" — subject+campus letter+number+section)
    Course Name
    Instructor       (mailto link wrapping "Last,First")
    Misc             ("Class Nbr: 2106 NOAPPR;QM;QR;")
    Days and Times   (multiple <span>...</span><br> meeting blocks)
    Location
"""

import re
import sys
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

LIST_URL = (
    "https://www.brynmawr.edu/inside/academic-information/registrar/"
    "tri-co-course-search/results"
)

# "CMSCB113001" -> code "CMSCB113", section "001".
# "CMSCB11300A" -> code "CMSCB113", section "00A".
COURSE_ID_RE = re.compile(r"^(?P<code>[A-Z]+\d+)(?P<section>\w{3})$")


class BrynMawrScraper(CourseScheduleScraper):
    college = College.BRYN_MAWR
    terms = ["F", "S"]
    wait_for = "table.result-table"

    def url_for(self, academic_year, term):
        start_year, end_year = academic_year
        if term == "F":
            semester = f"fall_{start_year}"
        elif term == "S":
            semester = f"spring_{end_year}"
        else:
            raise ValueError(f"unsupported term: {term!r}")
        params = [
            ("semester[0]", semester),
            ("department[0]", "Computer Science"),
            ("college[0]", "bryn_mawr"),
            ("page", "1"),
            ("per_page", "50"),
        ]
        return f"{LIST_URL}?{urllib.parse.urlencode(params)}"

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.result-table")
        if table is None:
            return []

        rows = []
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) < 5:
                continue

            reg_id = _clean(cells[0].get_text(" ", strip=True))
            m = COURSE_ID_RE.match(reg_id)
            if m:
                course_code = m.group("code")
                section = m.group("section")
            else:
                course_code, section = reg_id, ""

            course_name = _clean(cells[1].get_text(" ", strip=True))
            instructor = _clean(cells[2].get_text(" ", strip=True))

            # `Days and Times` cell holds one or more `<span>...</span><br>`
            # meeting blocks; join them with " / ".
            times_cell = cells[4]
            meetings = [
                _clean(span.get_text(" ", strip=True))
                for span in times_cell.find_all("span")
            ]
            meetings = [m for m in meetings if m]
            time_text = " / ".join(meetings) if meetings else _clean(
                times_cell.get_text(" ", strip=True)
            )

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
