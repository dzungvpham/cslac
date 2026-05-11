"""Hamilton College course catalog scraper.

Hamilton publishes a course catalog (not a schedule) on
`hamilton.smartcatalogiq.com`. There is no instructor, term, or meeting-time
information — just the courses offered in each academic year. We populate
the standard output columns with what we have and leave `term`, `instructor`,
and `time` blank.

Each catalog year lives at a URL like
`/en/2023-2024/college-catalogue/.../computer-science-courses`. The current
year uses `current` in place of the `YYYY-YYYY` segment; older years use the
literal range.

The course list is a table of `<td class="coursetitle"><a>CPSCI-101</a></td>
<td class="coursename">Computer Science for All</td>` pairs. The page is
plain HTML, so we use `requests`.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_HOST = "https://hamilton.smartcatalogiq.com"
PATH_TEMPLATE = "/en/{year}/college-catalogue/academicprograms/computer-science/computer-science-courses"


class HamiltonScraper(CourseScheduleScraper):
    college = College.HAMILTON
    # Catalog page is per academic year — no term breakdown.
    terms = []

    def __init__(self, driver=None):
        super().__init__(driver)
        # Decide which academic year maps to `current` exactly once per run.
        self._current_ay = self.past_academic_years(1)[0]

    def _year_segment(self, academic_year):
        if academic_year == self._current_ay:
            return "current"
        start, end = academic_year
        return f"{start}-{end}"

    def url_for(self, academic_year, term):
        return BASE_HOST + PATH_TEMPLATE.format(year=self._year_segment(academic_year))

    def fetch_page(self, academic_year, term):
        url = self.url_for(academic_year, term)
        resp = requests.get(url, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for title_cell in soup.select("td.coursetitle"):
            link = title_cell.find("a")
            if link is None:
                continue
            course_code = _clean(link.get_text(" "))
            if not course_code:
                continue
            name_cell = title_cell.find_next_sibling("td", class_="coursename")
            course_name = _clean(name_cell.get_text(" ")) if name_cell else ""
            href = link.get("href", "")
            course_url = href if href.startswith("http") else f"{BASE_HOST}{href}"
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    course_name=course_name,
                    url=course_url,
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
