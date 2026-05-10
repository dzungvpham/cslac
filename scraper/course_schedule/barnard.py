"""Barnard College course schedule scraper.

The catalog's "Course Search" page renders every CS section on one URL — no
form interaction, no per-term URL. Barnard's catalog only exposes whatever
is currently being offered (typically the upcoming/active fall + later
spring); historical terms are not browsable.

Page structure (rendered client-side, hence Selenium):

  div.courseblock                  — one per course
    p.courseblocktitle             — "COMS W1001 INTRO TO INFORMATION SCIENCE. 3.00 points ."
    table.scheduletbl              — zero or more, one per offering
      td.unifyTerm                 — "Fall 2025: COMS W1001"
      <th> row                     — column headers (Course Number / Section/Call # / Times/Location / Instructor / Points / Enrollment)
      <td> rows                    — one per section

We pull `(academic_year, term)` from each scheduletbl's term header rather
than from the scrape loop, so a single fetch can cover whatever mix of
terms the page is currently showing.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

LIST_URL = (
    "https://catalog.barnard.edu/barnard-college/courses-instruction/"
    "course-search/?department=COMB&pl=0&ph=10&college=BC"
)

# "COMS W1001 INTRO TO INFORMATION SCIENCE" -> code "COMS W1001", title rest.
# Codes look like "COMS W1001", "COMS BC1016", "COMS E4762" — i.e. a subject
# prefix, an optional letter group, then digits with an optional trailing
# alpha tag.
TITLE_RE = re.compile(r"^(?P<code>[A-Z]+(?:\s+[A-Z]+)?\s*\d+\w*)\s+(?P<title>.+)$")

# Despite the `department=COMB` filter in the URL, the rendered page also
# lists cross-listed Education courses (EDUC BC...). Keep only COMS rows.
SUBJECT_RE = re.compile(r"^COMS\b")

# "Fall 2025: COMS W1001" — non-breaking spaces show up here so we use \s.
TERM_HDR_RE = re.compile(
    r"^(?P<season>Fall|Spring|Summer|Winter|January)\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)


class BarnardScraper(CourseScheduleScraper):
    college = College.BARNARD
    # One URL covers every currently-listed offering; the per-row term comes
    # from the schedule-table header, not the loop.
    terms = []
    years_back = 1
    wait_for = "div.courseblock table.scheduletbl"

    def url_for(self, academic_year, term):
        return LIST_URL

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for block in soup.find_all("div", class_="courseblock"):
            title_p = block.find("p", class_="courseblocktitle")
            if title_p is None:
                continue
            first_strong = title_p.find("strong")
            if first_strong is None:
                continue
            title_text = _clean(first_strong.get_text(" ", strip=True)).rstrip(".").strip()
            m = TITLE_RE.match(title_text)
            if not m:
                continue
            course_code = re.sub(r"\s+", " ", m.group("code")).strip()
            if not SUBJECT_RE.match(course_code):
                continue
            course_name = m.group("title").strip()

            for tbl in block.find_all("table", class_="scheduletbl"):
                hdr_cell = tbl.find("td", class_="unifyTerm")
                if hdr_cell is None:
                    continue
                hdr_text = _clean(hdr_cell.get_text(" ", strip=True))
                parsed = _parse_term_header(hdr_text)
                if parsed is None:
                    continue
                ay, row_term = parsed

                for tr in tbl.find_all("tr"):
                    cells = tr.find_all("td")
                    # Skip the term-header row (single colspan td) and
                    # any non-data rows.
                    if len(cells) < 6:
                        continue
                    section_call = _clean(cells[1].get_text(" ", strip=True))
                    section = section_call.split("/", 1)[0].strip() if section_call else ""
                    time_text = _clean(cells[2].get_text(" ", strip=True))
                    instructor = _clean(cells[3].get_text(" ", strip=True))

                    rows.append(
                        self.make_row(
                            ay,
                            row_term,
                            course_code=course_code,
                            section=section,
                            course_name=course_name,
                            instructor=instructor,
                            time=time_text,
                        )
                    )
        return rows


def _parse_term_header(text):
    """`'Fall 2025: COMS W1001'` -> `((2025, 2026), 'F')`."""
    m = TERM_HDR_RE.match(text)
    if not m:
        return None
    season = m.group("season").lower()
    year = int(m.group("year"))
    if season == "fall":
        return (year, year + 1), "F"
    if season == "spring":
        return (year - 1, year), "S"
    if season == "summer":
        return (year - 1, year), "Su"
    if season in ("winter", "january"):
        return (year - 1, year), "W"
    return None


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
