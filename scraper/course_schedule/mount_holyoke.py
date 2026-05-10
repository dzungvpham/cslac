"""Mount Holyoke College course schedule scraper.

The class schedule lives behind a WebAdvisor "Search for Classes" form at
`wadv1.mtholyoke.edu`. To list one term's CS sections we have to:

  1. Load the form page (one URL, all terms behind it).
  2. Pick a term from `#VAR1` — option values look like `2025/FA`, `2026/SP`,
     `2026/JA` (visible labels are "Fall Semester 2025", etc.).
  3. Pick the subject from `#VAR2` (`COMSC` for Computer Science).
  4. Click `input[name=SUBMIT2]`. The next page either shows a results table
     with `summary="Select Section(s)"` or, when the term has no matching
     sections, re-renders the form with no results table — we treat that as
     an empty page.

Each fresh hit of the form URL gets a new TOKENIDX in the redirect, so we
just re-navigate to the canonical form URL for every (year, term).

Results-row layout (cells matched by class so layout shuffles don't break
us):

  - `LIST_VAR3`  : `"COMSC-151-01  (111346) Intro Comput. Problem Solving"`
  - `LIST_VAR7`  : `"09/03/2025-12/15/2025 Lecture Mon, Wed 10:00AM - ..."`
                   (multi-meeting sections concatenate the same date range
                   in front of each block; we strip the dates).
  - `LIST_VAR13` : instructor name.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

FORM_URL = "https://wadv1.mtholyoke.edu/wadvg/mhc?TYPE=P&PID=ST-XWSTS12A"

# "COMSC-151-01  (111346) Intro Comput. Problem Solving"
# "COMSC-341CD-01  (111368) Causal Inference for Data Sci"
COURSE_RE = re.compile(
    r"^(?P<code>[A-Z]+-\w+)-(?P<section>\w+)\s*\(\d+\)\s*(?P<title>.*)$"
)

# Each meeting block is prefixed with a "MM/DD/YYYY-MM/DD/YYYY " date range
# that's redundant with academic_year + term — strip it for readability.
DATE_RANGE_RE = re.compile(r"\d{2}/\d{2}/\d{4}-\d{2}/\d{2}/\d{4}\s+")


class MountHolyokeScraper(CourseScheduleScraper):
    college = College.MOUNT_HOLYOKE
    terms = ["F", "W", "S"]
    # We re-navigate to the form URL on every fetch, so reusing one driver
    # across terms is fine and faster than spinning up a new Chrome each time.
    fresh_driver_per_load = False
    wait_for = "#VAR1"
    page_load_timeout = 60

    def url_for(self, academic_year, term):
        return FORM_URL

    @staticmethod
    def _term_code(academic_year, term):
        start, end = academic_year
        if term == "F":
            return f"{start}/FA"
        if term == "W":
            # January Term — runs in January of the spring-semester year.
            return f"{end}/JA"
        if term == "S":
            return f"{end}/SP"
        return None

    def fetch_page(self, academic_year, term):
        code = self._term_code(academic_year, term)
        if code is None:
            return None

        self.load(FORM_URL)
        term_select = self.driver.find_element("css selector", "#VAR1")
        available = {
            opt.get_attribute("value")
            for opt in term_select.find_elements("css selector", "option")
        }
        if code not in available:
            return None

        Select(term_select).select_by_value(code)
        Select(self.driver.find_element("css selector", "#VAR2")).select_by_value("COMSC")
        self.driver.find_element("css selector", "input[name=SUBMIT2]").click()
        # After submit the DOM is replaced — either with a results screen or
        # with a re-rendered empty form. Either way the cached `term_select`
        # element goes stale, which is our signal to stop waiting.
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: _is_stale(term_select)
        )
        if self.post_load_sleep:
            time.sleep(self.post_load_sleep)
        return self.driver.page_source

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", attrs={"summary": "Select Section(s)"})
        if table is None:
            return []

        rows = []
        for tr in table.find_all("tr"):
            name_cell = tr.find("td", class_="LIST_VAR3")
            if name_cell is None:
                continue
            name_text = _clean(name_cell.get_text(" ", strip=True))
            m = COURSE_RE.match(name_text)
            if not m:
                continue

            meeting_cell = tr.find("td", class_="LIST_VAR7")
            faculty_cell = tr.find("td", class_="LIST_VAR13")
            meeting_raw = _clean(meeting_cell.get_text(" ", strip=True)) if meeting_cell else ""
            meeting = _clean(DATE_RANGE_RE.sub("", meeting_raw))
            instructor = _clean(faculty_cell.get_text(" ", strip=True)) if faculty_cell else ""

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=m.group("code"),
                    section=m.group("section"),
                    course_name=m.group("title").strip(),
                    instructor=instructor,
                    time=meeting,
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _is_stale(element):
    try:
        element.is_enabled()
        return False
    except Exception:
        return True
