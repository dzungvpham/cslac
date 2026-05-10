"""Occidental College course schedule scraper.

Schedule lives behind a single ASP.NET WebForms page at
`counts.oxy.edu/public/default.aspx`. To pull one term's CS sections we:

  1. Load the form. Pick the term in `#tabContainer_TabPanel1_ddlSemesters`
     — option values look like `202501` (= Fall 2024) or `202602` (= Spring
     2026); the 4-digit prefix is the academic-year ENDING year and the
     trailing 1/2/3 marks Fall/Spring/Summer. The dropdown has
     `AutoPostBack=true`, so we have to wait for the UpdatePanel to settle
     before touching anything else.
  2. Pick `COMP` (Computer Science) in `#tabContainer_TabPanel1_ddlSubjects`.
  3. Click `#tabContainer_TabPanel1_btnGo`. The results land in an
     UpdatePanel (`#searchResultsPanel`) without a navigation, populating
     `<table id="gvResults">`.

Each results row's cells are direct `<td>` children of the row; the
Instructor and Meeting-Times cells contain inner tables (one row per
instructor / per meeting block) that we flatten ourselves.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

FORM_URL = "https://counts.oxy.edu/public/default.aspx"
TERM_SELECT = "#tabContainer_TabPanel1_ddlSemesters"
SUBJECT_SELECT = "#tabContainer_TabPanel1_ddlSubjects"
GO_BUTTON = "#tabContainer_TabPanel1_btnGo"
RESULTS_PANEL = "#searchResultsPanel"
RESULTS_TABLE = "#gvResults"

SUBJECT = "COMP"

# "COMP 101 0" -> subject "COMP", number "101", section "0".
COURSE_RE = re.compile(r"^([A-Z]+)\s+(\w+)\s+(\w+)$")


class OccidentalScraper(CourseScheduleScraper):
    college = College.OCCIDENTAL
    terms = ["F", "S"]
    fresh_driver_per_load = False
    wait_for = TERM_SELECT
    page_load_timeout = 60

    def url_for(self, academic_year, term):
        return FORM_URL

    @staticmethod
    def _term_code(academic_year, term):
        # The term-code prefix is the academic-year ENDING year, so
        # AY (start, end) maps onto codes `{end}{01|02}`.
        _, end = academic_year
        if term == "F":
            return f"{end}01"
        if term == "S":
            return f"{end}02"
        return None

    def fetch_page(self, academic_year, term):
        code = self._term_code(academic_year, term)
        if code is None:
            return None

        # Always start from a clean form: AutoPostBack on the term dropdown
        # leaves the page in different states depending on prior selections.
        self.load(FORM_URL)
        term_select_el = self.driver.find_element("css selector", TERM_SELECT)
        available = {
            opt.get_attribute("value")
            for opt in term_select_el.find_elements("css selector", "option")
        }
        if code not in available:
            return None

        Select(term_select_el).select_by_value(code)
        # AutoPostBack rebuilds the form via UpdatePanel — wait for the old
        # element reference to go stale before we touch the subject dropdown.
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: _is_stale(term_select_el)
        )
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements("css selector", SUBJECT_SELECT)
        )

        Select(self.driver.find_element("css selector", SUBJECT_SELECT)).select_by_value(SUBJECT)
        self.driver.find_element("css selector", GO_BUTTON).click()
        # The Go click triggers another UpdatePanel cycle. Poll until the
        # results panel either renders the gvResults table or finishes
        # showing its "Please wait." spinner with empty content.
        deadline = time.time() + self.page_load_timeout
        while time.time() < deadline:
            srp = self.driver.find_element("css selector", RESULTS_PANEL)
            html = srp.get_attribute("innerHTML") or ""
            if "id=\"gvResults\"" in html or "id='gvResults'" in html:
                break
            if "Please wait" not in html and len(html) > 200:
                # Spinner is gone but no results table — empty result.
                break
            time.sleep(0.5)
        if self.post_load_sleep:
            time.sleep(self.post_load_sleep)
        return self.driver.page_source

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one(RESULTS_TABLE)
        if table is None:
            return []

        tbody = table.find("tbody") or table
        rows = []
        for tr in tbody.find_all("tr", recursive=False):
            cells = tr.find_all("td", recursive=False)
            # Header rows have <th> (no direct <td>); skip pager/footer rows
            # that don't carry the full layout.
            if len(cells) < 6:
                continue
            course_text = _clean(cells[1].get_text(" ", strip=True))
            m = COURSE_RE.match(course_text)
            if not m:
                continue
            if m.group(1) != SUBJECT:
                continue
            course_code = f"{m.group(1)} {m.group(2)}"
            section = m.group(3)
            course_name = _clean(cells[2].get_text(" ", strip=True))
            instructor = _join_inner_rows(cells[4], one_per_row=True)
            time_text = _join_inner_rows(cells[5], one_per_row=False)

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


def _join_inner_rows(cell, one_per_row):
    """Flatten the nested tables Occidental uses for instructors and
    meeting times.

    Instructor cell: one `<tr>` per instructor; each row has one `<td>`
    that holds the abbreviated name. We join these with `, `.

    Meeting-time cell: one `<tr>` per meeting block, with two `<td>`s —
    the time range and the day codes. We join the two cells with a space
    and the rows with `; `.
    """
    inner = cell.find("table")
    if inner is None:
        return _clean(cell.get_text(" ", strip=True))
    parts = []
    for r in inner.find_all("tr"):
        tds = r.find_all("td", recursive=False)
        if not tds:
            continue
        if one_per_row:
            text = _clean(tds[0].get_text(" ", strip=True))
        else:
            text = " ".join(_clean(td.get_text(" ", strip=True)) for td in tds).strip()
        if text:
            parts.append(text)
    sep = ", " if one_per_row else "; "
    return sep.join(parts)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _is_stale(element):
    try:
        element.is_enabled()
        return False
    except StaleElementReferenceException:
        return True
    except Exception:
        return True
