"""Jenzabar JICS portal course-schedule scraper.

Several LACs publish their public course search via the Jenzabar JICS
``Course_Schedules`` portlet, reachable at a URL of the form

    https://{host}/ics/...?portlet=Course_Schedules&screen=Advanced+Course+Search&screenType=next

It's an ASP.NET WebForms page with a ~20 KB `__VIEWSTATE` and a
JavaScript-driven postback search, so we drive it with Selenium: select
the term + department, click Search, walk the alphabetic
"letterNavigator" pagination, and parse the rendered
`pg0_V_dgCourses` grid.

Term descriptions vary across deployments:

* Claflin renders them as ``"Fall 2024-2025"``.
* Hendrix renders them as ``"2024-2025 - Fall Semester"``.

Each option's *description* is parsed (not the opaque value) so a new
school can usually be added with no code change — just a config entry
in `JENZABAR_JICS_COLLEGES`.

Each result row's course-code cell reads like ``"CSCI 206 01 UG MC"``
(subject, number, section, division, location-code); only the
subject+number and section are kept. The schedule cell looks like
``"MWF 10:00 AM-10:50 AM; Main Campus, James S. Thomas, Room 310"`` or
``"MTWRFSU; Online Program, Online, Online Course"`` for online
sections.
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

# ---- term-description parsing ---------------------------------------------

# Accept the known forms:
#   "Fall 2024-2025"                       (Claflin)
#   "Fall 2024-2025 Academic Year"         (Johnson C. Smith)
#   "2024-2025 - Fall Semester"            (Hendrix, Lyon)
#   "2024-2025 - Fall"                     (Hampden-Sydney, recent years)
#   "2024-2025 Fall" / "2026-2027 Fall"    (Illinois, Hampden-Sydney older years)
#   "FALL TERM 2026"                       (Beloit)
#   "2026 - Fall" / "2025 - Spring"        (Tougaloo)
#
# The whole description must match — anything extra (e.g. "- Fall I Subterm"
# trailers, "Fall 1st half", "Summer Session", "Summer 1 Semester",
# "Graduate Fall") falls through and is skipped so we don't double-count
# subterms or pick up graduate-only sections.
TERM_DESC_RE = re.compile(
    r"^\s*(?:"
    r"(?P<season1>Fall|Spring)\s+(?P<range1>\d{4}-\d{2,4})(?:\s+Academic\s+Year)?"
    r"|"
    r"(?P<range2>\d{4}-\d{2,4})\s*-\s*(?P<season2>Fall|Spring)(?:\s+Semester)?"
    r"|"
    r"(?P<range3>\d{4}-\d{2,4})\s+(?P<season3>Fall|Spring)"
    r"|"
    r"(?P<season4>Fall|Spring)\s+Term\s+(?P<single_year>\d{4})"
    r"|"
    r"(?P<single_year2>\d{4})\s*-\s*(?P<season5>Fall|Spring)"
    r")\s*$",
    re.I,
)
SEASON_TERM = {"fall": "F", "spring": "S"}


def parse_term_description(desc):
    """Return ((start_year, end_year), term) or (None, None).

    `term` is `"F"` or `"S"`. Returns `(None, None)` for summer / subterm /
    unrecognized descriptions.
    """
    m = TERM_DESC_RE.match(desc or "")
    if not m:
        return None, None
    season_word = (
        m.group("season1")
        or m.group("season2")
        or m.group("season3")
        or m.group("season4")
        or m.group("season5")
        or ""
    ).lower()
    term = SEASON_TERM.get(season_word)
    if term is None:
        return None, None
    single = m.group("single_year") or m.group("single_year2")
    if single:
        # Single-year forms ("Fall Term 2026", "2026 - Fall") — the season
        # determines which side of the academic-year boundary it falls on.
        year = int(single)
        if term == "F":
            return (year, year + 1), term
        return (year - 1, year), term
    year_range = m.group("range1") or m.group("range2") or m.group("range3")
    start_str, end_str = year_range.split("-")
    start = int(start_str)
    end_yy = int(end_str)
    end = end_yy if end_yy >= 100 else (start // 100) * 100 + end_yy
    if end < start:
        end += 100  # century wrap (e.g. "1999-00")
    return (start, end), term


# Course-code link text like "CSCI 206 01 UG MC".
COURSE_CODE_RE = re.compile(
    r"^(?P<subj>[A-Z]+)\s+(?P<num>\d+\w*)\s+(?P<section>\w+)"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


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


# ---- the scraper ----------------------------------------------------------


class JenzabarJICSScraper(CourseScheduleScraper):
    """Base scraper for Jenzabar JICS Course_Schedules portlets.

    Subclass attributes:
        - `search_url`: full URL to the Advanced Course Search portlet.
        - `subject`: department code passed to the `Department` dropdown
          (e.g. `"CSCI"`).
    """

    search_url: str = ""
    subject: str = ""
    fresh_driver_per_load = False
    page_load_timeout = 60
    post_load_sleep = 1.0
    terms = []  # discovered at runtime; the base loop is overridden

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._available = None  # (academic_year, term) -> option_value

    def _load_form(self):
        d = self.driver
        d.get(self.search_url)
        WebDriverWait(d, self.page_load_timeout).until(
            lambda x: x.find_elements(By.ID, "pg0_V_ddlTerm")
            and x.find_elements(By.ID, "pg0_V_ddlDept")
        )

    def _discover_terms(self):
        if self._available is not None:
            return self._available
        self._load_form()
        out = {}
        for opt in self.driver.find_elements(
            By.CSS_SELECTOR, "#pg0_V_ddlTerm option"
        ):
            value = (opt.get_attribute("value") or "").strip()
            desc = _clean(opt.text)
            academic_year, term = parse_term_description(desc)
            if academic_year is None or term is None or not value:
                continue
            # Multiple options can map to the same (ay, t) — take the first
            # (typically the bare-semester option, not a subterm).
            out.setdefault((academic_year, term), value)
        self._available = out
        return out

    def schedule_pages(self):
        available = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in ("F", "S"):
                if (ay, t) in available:
                    yield ay, t

    def fetch_page(self, academic_year, term):
        available = self._discover_terms()
        value = available.get((academic_year, term))
        if value is None:
            return None
        # Re-load the form for a clean __VIEWSTATE on every search; otherwise
        # repeated postbacks accumulate state and the second search returns
        # the wrong term.
        self._load_form()
        d = self.driver
        Select(d.find_element(By.ID, "pg0_V_ddlTerm")).select_by_value(value)
        Select(d.find_element(By.ID, "pg0_V_ddlDept")).select_by_value(self.subject)
        # Some deployments (e.g. Hendrix) default the Division dropdown to
        # "GR" (Graduate), which filters out every undergrad CS section.
        # Force it to "UG" when present.
        div_selects = d.find_elements(By.ID, "pg0_V_ddlDivision")
        if div_selects:
            try:
                Select(div_selects[0]).select_by_value("UG")
            except Exception:
                pass
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
                    url=self.search_url,
                )
            )
        return rows


# ---- per-college configs --------------------------------------------------

# (College, search_url, subject)
#
# The same form (term + dept + division dropdowns, `pg0_V_dgCourses` result
# grid, `letterNavigator` pagination) is also exposed by some deployments
# under `portlet=AddDrop_Courses` instead of `portlet=Course_Schedules`.
# Both are public and use identical HTML, so they share this scraper.
JENZABAR_JICS_COLLEGES = [
    (
        College.BELOIT,
        "https://my.beloit.edu/ICS/Course_Search/Default_Page.jnz"
        "?portlet=Course_Schedules&screen=Advanced+Course+Search&screenType=next",
        "CSCI",
    ),
    (
        College.CLAFLIN,
        "https://my.claflin.edu/ics/Portal_Homepage.jnz"
        "?portlet=Course_Schedules&screen=Advanced+Course+Search&screenType=next",
        "CSCI",
    ),
    (
        College.HAMPDEN_SYDNEY,
        "https://tigerweb.hsc.edu/ICS/Course_Search.jnz"
        "?portlet=AddDrop_Courses_2014-08-05T12-46-04-281"
        "&screen=Advanced+Course+Search&screenType=next",
        "COMS",
    ),
    (
        College.HENDRIX,
        "https://campusweb.hendrix.edu/ICS/Academics/Course_Search.jnz"
        "?portlet=Course_Schedules&screen=Advanced+Course+Search&screenType=next",
        "CSCI",
    ),
    (
        College.ILLINOIS,
        "https://connect2.ic.edu/ICS/default.aspx"
        "?portlet=Course_Schedules&screen=Advanced+Course+Search&screenType=next",
        "CS",
    ),
    (
        College.JOHNSON_C_SMITH,
        "https://my.jcsu.edu/ICS/Students/Student_Resources/Default_Page.jnz"
        "?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next",
        "CSC",
    ),
    (
        College.LYON,
        "https://my.lyon.edu/ICS/default.aspx"
        "?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next",
        "CSC",
    ),
    (
        College.TOUGALOO,
        "https://theloo.tougaloo.edu/ICS/Academics/Academics_Homepage.jnz"
        "?portlet=AddDrop_Courses&screen=Advanced+Course+Search&screenType=next",
        "CSC",
    ),
]


def _make_class(coll, search_url, subject):
    safe = re.sub(r"\W+", "", str(coll))
    return type(
        f"{safe}JenzabarJICSScraper",
        (JenzabarJICSScraper,),
        {"college": coll, "search_url": search_url, "subject": subject},
    )


def jenzabar_jics_scrapers():
    """Return one scraper class per configured Jenzabar JICS college."""
    return [_make_class(*cfg) for cfg in JENZABAR_JICS_COLLEGES]
