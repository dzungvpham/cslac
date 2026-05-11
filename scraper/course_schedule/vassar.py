"""Vassar College course schedule scraper.

The schedule lives behind a form at `/cgi-bin/geninfo.cgi` that POSTs to
`/cgi-bin/courses.cgi`. The form takes a `session` code (e.g. `202603` for
Fall 2026, `202601` for Spring 2026) and a `dept` code (`CMPU` for CS).
GETing `courses.cgi` directly returns 500; the form must be submitted.

The response is fixed-width plain text inside a `<pre>`, with a header row
and a dashes row identifying column starts. We derive column boundaries
from the dashes row at parse time (robust to width drift) and split each
data line on those boundaries. Some courses span two lines — the second
line has an empty COURSE_ID column but populated DAYS/TIME for an
additional meeting pattern; we fold that meeting into the prior row's
`time` field, joined by `; `.

The session dropdown only goes back as far as Vassar exposes (currently
late 1990s), but we only need `years_back` recent terms.
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

FORM_URL = "https://aisapps.vassar.edu/cgi-bin/geninfo.cgi"
DEPT = "CMPU"

# "CMPU-100-01" -> code "CMPU-100", section "01". Section is alphanumeric
# (e.g. "51" for evening sections).
COURSE_ID_RE = re.compile(r"^(?P<code>[A-Z]+-\d+\w*)-(?P<section>\w+)$")


class VassarScraper(CourseScheduleScraper):
    college = College.VASSAR
    terms = ["F", "S"]
    # The form is at `geninfo.cgi`; submitting it navigates to
    # `courses.cgi`. We re-navigate to the form for each term rather than
    # spinning up a new driver.
    fresh_driver_per_load = False
    page_load_timeout = 60

    def url_for(self, academic_year, term):
        return FORM_URL

    @staticmethod
    def _session_code(academic_year, term):
        start_year, end_year = academic_year
        if term == "F":
            return f"{start_year}03"
        if term == "S":
            return f"{end_year}01"
        raise ValueError(f"unsupported term: {term!r}")

    def fetch_page(self, academic_year, term):
        target_session = self._session_code(academic_year, term)
        self.driver.get(FORM_URL)
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements("css selector", "form[name=advanced]")
        )

        session_el = self.driver.find_element("css selector", "select[name=session]")
        available = {opt.get_attribute("value") for opt in session_el.find_elements("css selector", "option")}
        if target_session not in available:
            return None

        Select(session_el).select_by_value(target_session)
        Select(self.driver.find_element("css selector", "select[name=dept]")).select_by_value(DEPT)
        self.driver.find_element("css selector", "form[name=advanced]").submit()
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: "courses.cgi" in d.current_url
        )
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements("css selector", "pre")
        )
        if self.post_load_sleep:
            time.sleep(self.post_load_sleep)
        return self.driver.page_source

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        pre = soup.find("pre")
        if pre is None:
            return []
        lines = pre.get_text().split("\n")

        dash_idx = _find_dash_line(lines)
        if dash_idx is None:
            return []
        boundaries = _column_boundaries(lines[dash_idx])
        # We only need a few columns; map by index into the dash-derived list.
        # Labels (in order): COURSE_ID, TITLE, UNITS, SP, MAX, ENR, AVL, WL,
        # GMOD, YL, PR, FR, LA, QA, PREREQ, FORMAT, DIV, DEPT, XLIST, DAYS,
        # TIME, LOCATION, INSTRUCTOR, CRN.
        COL_COURSE_ID, COL_TITLE = 0, 1
        COL_DAYS, COL_TIME = 19, 20
        COL_INSTRUCTOR = 22
        if len(boundaries) <= COL_INSTRUCTOR:
            return []

        def slice_col(line, idx):
            start = boundaries[idx]
            end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(line)
            return line[start:end].strip()

        rows = []
        for raw in lines[dash_idx + 1 :]:
            if not raw.strip():
                continue
            course_id = slice_col(raw, COL_COURSE_ID)
            days = slice_col(raw, COL_DAYS)
            time_text = slice_col(raw, COL_TIME)
            meeting = _format_meeting(days, time_text)

            if not course_id:
                # continuation row: extra meeting pattern for the prior course
                if rows and meeting:
                    rows[-1]["time"] = _append_meeting(rows[-1]["time"], meeting)
                continue

            m = COURSE_ID_RE.match(course_id)
            if m:
                course_code = m.group("code")
                section = m.group("section")
            else:
                course_code, section = course_id, ""

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=slice_col(raw, COL_TITLE),
                    instructor=slice_col(raw, COL_INSTRUCTOR),
                    time=meeting,
                    url=FORM_URL,
                )
            )
        return rows


def _find_dash_line(lines):
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and "-" in stripped and set(stripped) <= {"-", " "}:
            return i
    return None


def _column_boundaries(dash_line):
    """Return the start column of each run of `-` in `dash_line`."""
    boundaries = []
    in_run = False
    for j, c in enumerate(dash_line):
        if c == "-":
            if not in_run:
                boundaries.append(j)
                in_run = True
        else:
            in_run = False
    return boundaries


def _format_meeting(days, time_text):
    if days and time_text:
        return f"{days} {time_text}"
    return days or time_text


def _append_meeting(existing, meeting):
    if not existing:
        return meeting
    if not meeting:
        return existing
    return f"{existing}; {meeting}"
