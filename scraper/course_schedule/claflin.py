"""Claflin University course schedule scraper.

Claflin runs its public course search on the Jenzabar JICS portal at
``https://my.claflin.edu/ics/Portal_Homepage.jnz?portlet=Course_Schedules
&screen=Advanced+Course+Search``. It's an ASP.NET WebForms page with a
massive `__VIEWSTATE` that hand-rolling postbacks against is brittle, so
we drive it with Selenium: select the term + department, click Search,
and parse the rendered `pg0_V_dgCourses` results table.

Term option values look like `"2024;FA"` (= academic year 2024-25 / Fall)
and `"2024;SP"` (= academic year 2024-25 / Spring). Per-term subterms like
`"2024;FA;F1"` are ignored — the bare-season option already covers all
sections for that semester. Each result row's course-code cell reads like

    CSCI 206 01 UG MC

(subject, number, section, division, location-code); we only keep the
subject+number and section. The schedule cell looks like
``"MWF 10:00 AM-10:50 AM; Main Campus, James S. Thomas, Room 310"`` or
``"MTWRFSU; Online Program, Online, Online Course"`` for online sections.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

SEARCH_URL = (
    "https://my.claflin.edu/ics/Portal_Homepage.jnz"
    "?portlet=Course_Schedules&screen=Advanced+Course+Search&screenType=next"
)
SUBJECT = "CSCI"

# `Term` option value like `"2024;FA"` or `"2024;SP"`. We ignore subterms
# (those have a trailing `;F1`/`;S2`/etc.) — the parent option lists every
# section in that semester.
TERM_VALUE_RE = re.compile(r"^(?P<year>\d{4});(?P<season>FA|SP)$")
SEASON_TERM = {"FA": "F", "SP": "S"}

# Course-code link text like "CSCI 206 01 UG MC".
COURSE_CODE_RE = re.compile(
    r"^(?P<subj>[A-Z]+)\s+(?P<num>\d+\w*)\s+(?P<section>\w+)"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class ClaflinScraper(CourseScheduleScraper):
    college = College.CLAFLIN
    fresh_driver_per_load = False
    page_load_timeout = 60
    post_load_sleep = 1.0
    terms = []  # discovered at runtime; the base loop is overridden

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._available = None  # list of (academic_year, term, option_value)

    def _load_form(self):
        d = self.driver
        d.get(SEARCH_URL)
        WebDriverWait(d, self.page_load_timeout).until(
            lambda x: x.find_elements(By.ID, "pg0_V_ddlTerm")
            and x.find_elements(By.ID, "pg0_V_ddlDept")
        )

    def _discover_terms(self):
        if self._available is not None:
            return self._available
        self._load_form()
        out = []
        for opt in self.driver.find_elements(
            By.CSS_SELECTOR, "#pg0_V_ddlTerm option"
        ):
            value = (opt.get_attribute("value") or "").strip()
            m = TERM_VALUE_RE.match(value)
            if not m:
                continue
            year = int(m.group("year"))
            term = SEASON_TERM[m.group("season")]
            ay = (year, year + 1)
            out.append((ay, term, value))
        self._available = out
        return out

    def schedule_pages(self):
        available = {(ay, t): v for ay, t, v in self._discover_terms()}
        for ay in self.past_academic_years(self.years_back):
            for t in ("F", "S"):
                if (ay, t) in available:
                    yield ay, t

    def fetch_page(self, academic_year, term):
        available = {(ay, t): v for ay, t, v in self._discover_terms()}
        value = available.get((academic_year, term))
        if value is None:
            return None
        # Re-load the form for a clean __VIEWSTATE on every search; otherwise
        # repeated postbacks accumulate state and the second search returns
        # the wrong term.
        self._load_form()
        d = self.driver
        Select(d.find_element(By.ID, "pg0_V_ddlTerm")).select_by_value(value)
        Select(d.find_element(By.ID, "pg0_V_ddlDept")).select_by_value(SUBJECT)
        d.find_element(By.ID, "pg0_V_btnSearch").click()
        try:
            WebDriverWait(d, self.page_load_timeout).until(
                lambda x: x.find_elements(By.ID, "pg0_V_dgCourses")
                or "No courses" in x.page_source
            )
        except TimeoutException:
            print("  timed out waiting for results", flush=True)
            return None
        time.sleep(self.post_load_sleep)

        # Walk every "letter navigator" page. Results are split alphabetically
        # by course-code prefix; the navigator emits a "Next page" link with a
        # postback target like `pg0$V$ltrNav` and argument `1`, `2`, ... until
        # we're on the last page. Concatenate every page's results table so
        # `parse_page` can read them all from one HTML blob.
        pages = [d.page_source]
        seen_args = {"0"}  # the initial page is implicitly index 0
        for _ in range(20):  # safety cap
            next_arg = self._next_letter_nav_arg(d, seen_args)
            if next_arg is None:
                break
            seen_args.add(next_arg)
            try:
                d.execute_script(
                    "__doPostBack(arguments[0], arguments[1]);",
                    "pg0$V$ltrNav",
                    next_arg,
                )
            except Exception:
                break
            try:
                WebDriverWait(d, self.page_load_timeout).until(
                    lambda x: x.find_elements(By.ID, "pg0_V_dgCourses")
                )
            except TimeoutException:
                break
            time.sleep(self.post_load_sleep)
            pages.append(d.page_source)
        return "\n<!-- PAGE BREAK -->\n".join(pages)

    @staticmethod
    def _next_letter_nav_arg(driver, seen_args):
        """Return the argument for the 'Next page' postback, or None."""
        anchors = driver.find_elements(By.CSS_SELECTOR, ".letterNavigator a")
        for a in anchors:
            text = (a.text or "").strip().lower()
            if "next" not in text:
                continue
            href = a.get_attribute("href") or ""
            m = re.search(r"__doPostBack\('pg0\$V\$ltrNav','(\d+)'\)", href)
            if not m:
                continue
            arg = m.group(1)
            if arg in seen_args:
                return None
            return arg
        return None

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        seen = set()
        for table in soup.find_all("table", id="pg0_V_dgCourses"):
            for row in self._parse_table(table, academic_year, term):
                key = (row["course_code"], row["section"], row["time"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return rows

    def _parse_table(self, table, academic_year, term):
        rows = []
        for tr in table.select("tbody tr"):
            # Skip the bookstore expansion rows (class includes "subItem").
            classes = tr.get("class") or []
            if "subItem" in classes:
                continue
            code_link = tr.find("a", id=re.compile(r"lnkCourse$"))
            if code_link is None:
                continue
            code_text = _clean(code_link.get_text(" ", strip=True))
            m = COURSE_CODE_RE.match(code_text)
            if not m:
                continue
            course_code = f"{m.group('subj')} {m.group('num')}"
            section = m.group("section")
            tds = tr.find_all("td", recursive=False)
            # Column layout: Add | Textbooks(+/-) | CourseCode | Name |
            # Faculty | SeatsOpen | Status | Schedule | Credits | Begin | End
            course_name = _clean(tds[3].get_text(" ", strip=True)) if len(tds) > 3 else ""
            instructor = _format_faculty(tds[4]) if len(tds) > 4 else ""
            time_text = _format_schedule(tds[7]) if len(tds) > 7 else ""
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                    url=SEARCH_URL,
                )
            )
        return rows


def _format_faculty(td):
    names = []
    for span in td.find_all("span"):
        name = _clean(span.get_text(" ", strip=True))
        if name and name not in names:
            names.append(name)
    if not names:
        return _clean(td.get_text(" ", strip=True))
    return "; ".join(names)


def _format_schedule(td):
    """Render the schedule `<ul>` as `meeting1 | meeting2 | ...`.

    Each `<li>` is one meeting in the form
    ``"MWF 10:00 AM-10:50 AM; Main Campus, James S. Thomas, Room 310"``;
    we keep the literal string (collapsed whitespace) so the location
    survives without imposing a fixed structure.
    """
    meetings = []
    for li in td.find_all("li"):
        text = _clean(li.get_text(" ", strip=True))
        if text:
            meetings.append(text)
    if meetings:
        return " | ".join(meetings)
    return _clean(td.get_text(" ", strip=True))
