"""Trinity College course schedule scraper.

The CS schedule lives in an iframe pointing at an ASP.NET form on
`internet3.trincoll.edu`. To list a different term we have to:

  1. Load the form page (one URL, all terms behind it).
  2. Pick an option from the `#ddlTermList` dropdown — visible-text labels
     look like "Fall 2026", "Spring 2027" (the underlying option values are
     opaque Banner term codes like "1271").
  3. Click `#btnSubmit`, which posts back ASP.NET viewstate and re-renders
     the page with a `<table class="TITLE_tbl">` of sections.

Result rows alternate between two row types:
  - data rows have `td.TITLE_id` (Class No / Course ID like `CPSC-103-01` /
    Title / Credits / Type / Instructor / Days:Times / Location / ...)
  - notes rows have `td.TITLE_notes` (prereqs, enrollment caps, descriptions)
We keep only the data rows and split `CPSC-103-01` into code + section.

The dropdown only goes back to Fall 2022, so older academic years return
`None` from `fetch_page` (which the base class logs as "not available").
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

LIST_URL = "https://internet3.trincoll.edu/ptools/CourseListing_wp.aspx?dc=CPSC"

# "CPSC-103-01" -> code "CPSC-103", section "01". Section may be alphanumeric.
COURSE_ID_RE = re.compile(r"^(?P<code>[A-Z]+-\d+\w*)-(?P<section>\w+)$")


class TrinityScraper(CourseScheduleScraper):
    college = College.TRINITY_C
    terms = ["F", "S"]
    # The form is rebuilt in place after each submit, so reusing one driver
    # across terms is both fine and faster than spinning up a new one.
    fresh_driver_per_load = False
    wait_for = "#ddlTermList"
    page_load_timeout = 60

    def url_for(self, academic_year, term):
        return LIST_URL

    def _term_label(self, academic_year, term):
        if term == "F":
            return f"Fall {academic_year[0]}"
        if term == "S":
            return f"Spring {academic_year[1]}"
        raise ValueError(f"unsupported term: {term!r}")

    def fetch_page(self, academic_year, term):
        # Make sure the form is on screen (first call, or after a previous
        # navigation lost it for some reason). Cold-starting Chrome + the
        # ASP.NET page is occasionally slow, so retry once on failure.
        if not self.driver.find_elements("css selector", "#ddlTermList"):
            try:
                self.load(self.url_for(academic_year, term))
            except Exception:
                self.load(self.url_for(academic_year, term))

        select_el = self.driver.find_element("css selector", "#ddlTermList")
        target = self._term_label(academic_year, term)
        available = {
            opt.text.strip(): opt
            for opt in select_el.find_elements("css selector", "option")
        }
        if target not in available:
            return None

        Select(select_el).select_by_visible_text(target)
        # Cache an element from the current page so we can wait for the
        # postback to actually swap the DOM, not just race with the next
        # `find_element` call.
        old_select = select_el
        self.driver.find_element("css selector", "#btnSubmit").click()
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: _is_stale(old_select)
        )
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements("css selector", "#ddlTermList")
        )
        if self.post_load_sleep:
            time.sleep(self.post_load_sleep)
        return self.driver.page_source

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.TITLE_tbl")
        if table is None:
            return []

        rows = []
        for tr in table.select("tr.TITLE_row, tr.TITLE_row_alt"):
            id_cell = tr.select_one("td.TITLE_id")
            if id_cell is None:
                # notes / description / prereq row — skip
                continue
            cells = tr.find_all("td", recursive=False)
            # Expected layout: 0=ClassNo, 1=CourseID, 2=Title, 3=Credits,
            # 4=Type, 5=Instructor, 6=Days:Times, 7=Location, 8..=Permission/Dist/Qtr.
            if len(cells) < 7:
                continue

            course_id = _clean(cells[1].get_text(" ", strip=True))
            m = COURSE_ID_RE.match(course_id)
            if m:
                course_code = m.group("code")
                section = m.group("section")
            else:
                course_code, section = course_id, ""

            course_name = _clean(cells[2].get_text(" ", strip=True))
            instructor = _clean(cells[5].get_text(" ", strip=True))
            time_text = _clean(cells[6].get_text(" ", strip=True))

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


def _is_stale(element):
    try:
        element.is_enabled()
        return False
    except Exception:
        return True
