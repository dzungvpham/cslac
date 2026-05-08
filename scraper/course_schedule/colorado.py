"""Colorado College course schedule scraper.

The catalog page (`schedule.html`) is a single server-rendered table covering
many years at once, filtered client-side via jPList. Each section is one
`<tr data-jplist-item>`:

    <tr data-jplist-item="">
      <td><a class="courseID" href="courses/cp122.html">CP122</a></td>
      <td class="term term-Fall2025">Fall 2025</td>
      <td class="block block3">Block 3</td>
      <td class="title program-ComputerScience">Computer Science I</td>
    </tr>

We keep only rows whose title cell carries `program-ComputerScience`. The page
has no instructor info; CC runs the block plan, so the "block" cell goes into
the `time` field.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper, NO_TERM

BASE_URL = "https://www.coloradocollege.edu/academics/curriculum/catalog/"
LIST_URL = BASE_URL + "schedule.html"

TERM_CLASS_RE = re.compile(r"term-(?P<season>Fall|Spring|Summer)(?P<year>\d{4})")
TERM_CODE = {"Fall": "F", "Spring": "S", "Summer": "Su"}


class ColoradoScraper(CourseScheduleScraper):
    college = College.COLORADO

    def schedule_pages(self):
        # The single page already lists every term it knows about, so we
        # ignore years_back / terms and yield exactly one fetch.
        yield (0, 0), NO_TERM

    def url_for(self, academic_year, term):
        return LIST_URL

    def fetch_page(self, academic_year, term):
        # Plain server-rendered HTML — no JS needed, skip Selenium.
        resp = requests.get(LIST_URL, timeout=self.page_load_timeout)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.select("tr[data-jplist-item]"):
            title_td = tr.select_one("td.title.program-ComputerScience")
            if title_td is None:
                continue
            course_name = _clean(title_td.get_text(" ", strip=True))

            code_link = tr.select_one("a.courseID")
            if code_link is None:
                continue
            course_code = _clean(code_link.get_text(" ", strip=True))
            href = code_link.get("href", "")
            if href and not href.startswith("http"):
                href = BASE_URL + href.lstrip("/")

            row_year, row_term = _parse_term(tr.select_one("td.term"))
            if row_year is None:
                continue

            block_td = tr.select_one("td.block")
            time_text = _clean(block_td.get_text(" ", strip=True)) if block_td else ""

            rows.append(
                self.make_row(
                    row_year,
                    row_term,
                    course_code=course_code,
                    course_name=course_name,
                    time=time_text,
                    url=href,
                )
            )
        return rows


def _parse_term(td):
    """Return ((start, end), term_code) for a `<td class="term term-FallYYYY">`."""
    if td is None:
        return None, ""
    for cls in td.get("class", []):
        m = TERM_CLASS_RE.match(cls)
        if not m:
            continue
        season = m.group("season")
        year = int(m.group("year"))
        # Fall starts an academic year; Spring/Summer end one.
        academic_year = (year, year + 1) if season == "Fall" else (year - 1, year)
        return academic_year, TERM_CODE[season]
    return None, ""


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
