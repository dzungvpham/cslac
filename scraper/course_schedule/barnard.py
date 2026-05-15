"""Barnard College course schedule scraper.

Source: https://cs.barnard.edu/course-catalogue — the Barnard CS
department's own catalogue page. It lists every COMS course offered to
Barnard CS students: Barnard-owned (BC-prefixed) courses plus the
Columbia cross-listings (COMS W*, COMS E*) that count toward the Barnard
CS major. We keep all of them — they are the courses a Barnard CS student
can actually enroll in.

The page is server-rendered HTML so we fetch with `requests`; no Selenium
needed. Only currently-offered terms are exposed (typically the active
spring + the upcoming fall); historical terms are not browsable.

Page structure:

  div.courseblock                  — one per course
    p.courseblocktitle             — "COMS BC1016 Introduction to ..."
    table.scheduletbl              — zero or more; each table can hold
                                     several term blocks in sequence
      tr > td.unifyTerm            — "Spring 2026: COMS BC1016" header
      tr > th                      — column header row (skipped)
      tr > td.unifyRow1            — one per offered section, belonging to
                                     the most recent unifyTerm row above

We walk a table's rows in order, tracking the current term as we go, so a
single scheduletbl can yield rows for multiple terms.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

LIST_URL = "https://cs.barnard.edu/course-catalogue"

# "COMS BC1016 Introduction to ..." → code "COMS BC1016", title rest.
TITLE_RE = re.compile(r"^(?P<code>[A-Z]+(?:\s+[A-Z]+)?\s*\d+\w*)\s+(?P<title>.+)$")

# Keep every COMS code (BC, W, E). Other subjects occasionally appear in
# pre-reqs/cross-list text — guard against parsing those as course rows.
SUBJECT_RE = re.compile(r"^COMS\b", re.IGNORECASE)

# "Spring 2026: COMS BC1016" — \s catches non-breaking spaces too.
TERM_HDR_RE = re.compile(
    r"^(?P<season>Fall|Spring|Summer|Winter|January)\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)


class BarnardScraper(CourseScheduleScraper):
    college = College.BARNARD
    # One URL covers every currently-listed offering; the per-row term comes
    # from each scheduletbl's unifyTerm header(s).
    terms = []
    years_back = 1

    def url_for(self, academic_year, term):
        return LIST_URL

    def fetch_page(self, academic_year, term):
        r = requests.get(
            LIST_URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        r.raise_for_status()
        return r.text

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
                current_term = None
                for tr in tbl.find_all("tr"):
                    term_td = tr.find("td", class_="unifyTerm")
                    if term_td is not None:
                        current_term = _parse_term_header(
                            _clean(term_td.get_text(" ", strip=True))
                        )
                        continue
                    if current_term is None:
                        continue
                    cells = tr.find_all("td")
                    if len(cells) < 6:
                        continue
                    ay, row_term = current_term
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
    """`'Spring 2026: COMS BC1016'` -> `((2025, 2026), 'S')`."""
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
