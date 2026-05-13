"""Wabash College course schedule scraper.

The registrar exposes a server-rendered course-sections page that accepts
both a department and term as URL query parameters:

    https://www.wabash.edu/apps/registrar/course-sections?pages_id=1
        &dept=CSC&term={YY}/{TT}

Term codes are `{YY}/FA`, `{YY}/SP`, `{YY}/SU` where `YY` is the last two
digits of the term's calendar year (e.g. `24/SP` is Spring 2024). The
dropdown lists summer terms, but Wabash does not actually run CS courses
in summer; we still scrape them for completeness — empty results are
simply written as zero rows.

Each section is a `<tr class="content-row">` with cells:

    td.term            "24/SP"
    td.course          <a>CSC-106-01</a><br />Retro 2D Game Programming
    td.dept            <strong>Computer Science</strong><br />HAY 003
    td.dates           1/15/24-3/1/24
    td.days            <div>M W F <br>8:00AM-8:50AM</div>
    td.faculty         <ul><li>McKinney, Colin</li>...</ul>
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

LIST_URL = (
    "https://www.wabash.edu/apps/registrar/course-sections"
    "?pages_id=1&dept=CSC&term={code}"
)

# "CSC-106-01" -> code "CSC-106", section "01".
COURSE_ID_RE = re.compile(r"^(?P<code>[A-Z]+-\d+\w*)-(?P<section>\w+)$")


class WabashScraper(CourseScheduleScraper):
    college = College.WABASH
    terms = ["F", "S", "Su"]
    wait_for = "table.registrar-list-table"

    def url_for(self, academic_year, term):
        start_year, end_year = academic_year
        if term == "F":
            code = f"{start_year % 100:02d}/FA"
        elif term == "S":
            code = f"{end_year % 100:02d}/SP"
        elif term == "Su":
            code = f"{end_year % 100:02d}/SU"
        else:
            raise ValueError(f"unsupported term: {term!r}")
        return LIST_URL.format(code=code)

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.select("table.registrar-list-table tr.content-row"):
            course_cell = tr.select_one("td.course")
            if course_cell is None:
                continue
            link = course_cell.select_one("a")
            if link is None:
                continue
            course_id = _clean(link.get_text(" ", strip=True))
            m = COURSE_ID_RE.match(course_id)
            if m:
                course_code = m.group("code")
                section = m.group("section")
            else:
                course_code, section = course_id, ""

            # Course name is the text in `td.course` after the link, sitting
            # in the same first `<div>` as the link.
            course_name = ""
            link_div = link.find_parent("div")
            if link_div is not None:
                link.extract()
                course_name = _clean(link_div.get_text(" ", strip=True))

            days_cell = tr.select_one("td.days")
            time_text = _clean(days_cell.get_text(" ", strip=True)) if days_cell else ""

            faculty_cell = tr.select_one("td.faculty")
            instructors = []
            if faculty_cell is not None:
                for li in faculty_cell.select("li"):
                    name = _clean(li.get_text(" ", strip=True))
                    if name:
                        instructors.append(name)
            instructor = "; ".join(instructors)

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
