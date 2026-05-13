"""St. Mary's College of Maryland course schedule scraper.

The schedule lives behind an ASP.NET WebForms search form at

    https://portal.smcm.edu/CMCPortal/Common/CourseSchedule.aspx

We drive the form with Selenium: pick each term offered in the
`cbTerm` dropdown, type `COSC` into the course-code box, switch the
section-availability radio to `Open & Closed`, and click Search. The
results table is a DataTables widget paginated at 10 rows by default;
we ask it to render every row in one go via
`$('#CourseList').DataTable().page.len(-1).draw()`.

The term dropdown only exposes the terms the registrar has built so
far (typically the current and upcoming year — at the time of writing,
Fall 2024 through Spring 2027), so this scraper grabs whatever the
form lists rather than iterating a fixed year×term loop.

Row columns (after rendering):

    0 course code    "COSC120"
    1 course title   "COMPUTER SCIENCE I (MA)"
    2 section        "03"
    3 date range
    4 credits
    5 schedule       "MoWeFr 2:10PM - 3:00PM"
    6 instructor     "Saleem,Waqar"
    ... (other columns ignored)
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

FORM_URL = "https://portal.smcm.edu/CMCPortal/Common/CourseSchedule.aspx"

TERM_RE = re.compile(r"^(?P<word>Fall|Spring|Summer|Winter)\s+(?P<year>\d{4})$")
TERM_CODE = {"Fall": "F", "Spring": "S", "Summer": "Su", "Winter": "W"}


class StMaryMdScraper(CourseScheduleScraper):
    college = College.ST_MARY_MD
    # Terms are discovered from the form's term dropdown at run time, so
    # the base class's year×term loop doesn't apply.
    terms = []
    page_load_timeout = 60
    post_load_sleep = 2.0
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        return FORM_URL

    def scrape(self):
        rows = []
        try:
            self._load_form()
        except TimeoutException:
            print("  [SMCM] search form never rendered", flush=True)
            return rows

        term_options = self._term_options()
        for label, (academic_year, term) in term_options:
            try:
                page_rows = self._search_term(label, academic_year, term)
            except Exception as e:
                print(f"  [SMCM] {label} failed: {e}", flush=True)
                continue
            print(f"  [{_format_ay(academic_year)}/{term}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
            # The page-state survives postbacks, so navigate back to a
            # clean form before the next search.
            self._load_form()
        return rows

    def _load_form(self):
        self.driver.get(FORM_URL)
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "#_ctl0_PlaceHolderMain__ctl0_cbTerm")
        )

    def _term_options(self):
        """Return [(label, (academic_year, term_code))] for every term in
        the dropdown that we know how to handle, sorted oldest-first."""
        sel = Select(
            self.driver.find_element(By.CSS_SELECTOR, "#_ctl0_PlaceHolderMain__ctl0_cbTerm")
        )
        out = []
        for opt in sel.options:
            label = (opt.text or "").strip()
            parsed = _parse_term_label(label)
            if parsed is None:
                continue
            out.append((label, parsed))
        out.sort(key=lambda x: (x[1][0], _term_sort_key(x[1][1])))
        return out

    def _search_term(self, term_label, academic_year, term):
        sel = Select(
            self.driver.find_element(By.CSS_SELECTOR, "#_ctl0_PlaceHolderMain__ctl0_cbTerm")
        )
        sel.select_by_visible_text(term_label)
        code_input = self.driver.find_element(
            By.CSS_SELECTOR, "#_ctl0_PlaceHolderMain__ctl0_txtCode"
        )
        code_input.clear()
        code_input.send_keys("COSC")
        self.driver.find_element(
            By.CSS_SELECTOR, "#_ctl0_PlaceHolderMain__ctl0_rbOC"
        ).click()
        self.driver.find_element(
            By.CSS_SELECTOR, "#_ctl0_PlaceHolderMain__ctl0_btnSearch"
        ).click()

        # Wait for either the table or a "no results" banner. DataTables
        # initializes once the table is in the DOM, so we then ask it to
        # show every row to skip pagination.
        try:
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "#CourseList tbody tr")
                or d.find_elements(By.CSS_SELECTOR, "#CourseList_info")
            )
        except TimeoutException:
            return []
        self.driver.execute_script(
            "if (typeof $ === 'function' && $('#CourseList').length) { "
            "$('#CourseList').DataTable().page.len(-1).draw(); }"
        )
        time.sleep(self.post_load_sleep)
        return _parse_table(self, self.driver.page_source, academic_year, term)


def _parse_term_label(label):
    """`'Fall 2025'` -> `((2025, 2026), 'F')`, `'Spring 2026'` ->
    `((2025, 2026), 'S')`, etc. Returns None for empty / unknown labels.
    """
    m = TERM_RE.match(label)
    if not m:
        return None
    year = int(m.group("year"))
    code = TERM_CODE.get(m.group("word"))
    if code is None:
        return None
    if code == "F":
        return (year, year + 1), code
    return (year - 1, year), code


def _term_sort_key(term):
    return {"F": 0, "W": 1, "S": 2, "Su": 3}.get(term, 9)


def _parse_table(scraper, html, academic_year, term):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#CourseList")
    if table is None:
        return []
    rows = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 7:
            continue
        course_code = _clean(cells[0].get_text(" ", strip=True))
        # `COSC120` -> `COSC 120`. Section numbers can be alphanumeric (the
        # column is text already in cells[2]).
        m = re.match(r"^(?P<subj>[A-Z]+)(?P<num>\d+\w*)$", course_code)
        if m:
            course_code = f"{m.group('subj')} {m.group('num')}"
        course_name = _clean(cells[1].get_text(" ", strip=True))
        section = _clean(cells[2].get_text(" ", strip=True))
        schedule = _clean(cells[5].get_text(" ", strip=True))
        instructor = _dedupe_instructor(cells[6].get_text(" ", strip=True))
        rows.append(
            scraper.make_row(
                academic_year,
                term,
                course_code=course_code,
                section=section,
                course_name=course_name,
                instructor=instructor,
                time=schedule,
            )
        )
    return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _dedupe_instructor(text):
    """The `lblInstructor` span sometimes lists the same person twice with
    different comma spacing (e.g. `Lane,Chunchao; Lane, Chunchao`). Split
    on `;`, normalize whitespace, and drop duplicates."""
    seen = []
    seen_keys = set()
    for part in (text or "").split(";"):
        cleaned = _clean(part)
        if not cleaned:
            continue
        key = re.sub(r"\s+", "", cleaned).lower()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        seen.append(cleaned)
    return "; ".join(seen)


def _format_ay(academic_year):
    s, e = academic_year
    return f"{s}-{str(e)[-2:]}"
