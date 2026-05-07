"""Ellucian Self-Service Course Catalog scraper.

A large family of LACs run their public course search on Ellucian
Self-Service, all behind a URL of the form

    {host}/Student/Courses/Search?subjects={SUBJECT}

The page renders a course list via Knockout. Each course has a
"View Available Sections for {CODE}" collapsible button; expanding it
fires an XHR that pulls every section currently in the term filter and
groups them under `<h4>{Academic Year} {Term} Semester</h4>` headings
followed by a `<ul>` of section `<li>` items.

The Self-Service term filter sidebar (`input#STATICterm{TERMCODE}`) only
exposes terms that are currently registerable — typically the last
finished semester, the current semester, and the next one or two — so
this scraper captures whatever terms appear, not a fixed five-year
history. Year/term values are derived from each `<h4>` label.

Several institutions running Self-Service gate the search behind a login
(Allegheny, Wooster). We detect the redirect to `/Account/Login` and
return an empty result set rather than failing.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup, Comment
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

# ---- term-label parsing ----------------------------------------------------

_TERM_WORD = r"Fall|Spring|Summer|Winter|Jterm|J[\s-]?Term|January"
# "2025-26 Spring Semester" — Augustana, Linfield, etc.
_TERM_RANGE_RE = re.compile(
    rf"(?P<start>\d{{4}})-(?P<end_yy>\d{{2}})\s+(?P<word>{_TERM_WORD})", re.I
)
# "Spring 2026" / "Fall Term 2026" / "Fall Term, 2026" — Franklin, Juniata, Roanoke, etc.
_TERM_SINGLE_RE = re.compile(
    rf"(?P<word>{_TERM_WORD})(?:\s+(?:Term|Semester))?,?\s+(?P<year>\d{{4}})", re.I
)

TERM_CODE = {
    "fall": "F",
    "spring": "S",
    "summer": "Su",
    "winter": "W",
    "january": "W",
    "jterm": "W",
    "j term": "W",
    "j-term": "W",
}


def _term_code(word):
    return TERM_CODE.get(re.sub(r"\s+", " ", word.strip().lower()))


def parse_term_label(label):
    """Return ((start_year, end_year), term_code) or (None, None).

    Self-Service installs use a couple of different conventions for term
    headings: some emit `2025-26 Spring Semester`, others emit just
    `Spring 2026`. We accept either; for the single-year form we infer the
    academic year (Fall N -> AY N..N+1; Spring/Winter/Summer N -> AY N-1..N).
    """
    s = label or ""
    m = _TERM_RANGE_RE.search(s)
    if m:
        start = int(m.group("start"))
        end = (start // 100) * 100 + int(m.group("end_yy"))
        if end < start:
            end += 100  # century wrap (e.g. "1999-00")
        return (start, end), _term_code(m.group("word"))
    m = _TERM_SINGLE_RE.search(s)
    if m:
        year = int(m.group("year"))
        word = m.group("word").lower()
        if word.startswith("fall"):
            start, end = year, year + 1
        else:
            start, end = year - 1, year
        return (start, end), _term_code(word)
    return None, None


# Section name -> (course code, section). Handles all observed forms:
#   "CSC-201-01"     (Augustana, Whitman, Juniata, ...)
#   "CISC-118-1A"    (Hartwick — alphanumeric section)
#   "COMP*121-01"    (Linfield, Franklin — Datatel `*` prefix separator)
#   "CSC54-144-01"   (Southwestern — digits inside the subject prefix)
SECTION_RE = re.compile(r"^(?P<code>[A-Z]+\d*[*-]\d+\w*)-(?P<section>\w+)$")


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _visible_text(elem):
    """Concatenate text under `elem`, skipping descendants hidden via an
    inline `display: none` style. Self-Service inlines hidden TBD/fallback
    spans into the same cell, and BeautifulSoup ignores CSS, so we filter
    them ourselves to avoid noise like 'M/W/F 10:00 AM - 11:15 AM TBD'.
    """
    if elem is None:
        return ""
    parts = []
    for descendant in elem.descendants:
        if not isinstance(descendant, str) or isinstance(descendant, Comment):
            continue
        hidden = False
        ancestor = descendant.parent
        while ancestor is not None and ancestor is not elem:
            style = (ancestor.get("style") or "").lower().replace(" ", "")
            if "display:none" in style:
                hidden = True
                break
            ancestor = ancestor.parent
        if not hidden:
            parts.append(descendant)
    return _clean(" ".join(parts))


# ---- the scraper -----------------------------------------------------------


class EllucianSelfServiceScraper(CourseScheduleScraper):
    """Base for Ellucian Self-Service Course Catalog sites.

    Concrete subclasses set:
        college   — `College` enum member
        base_url  — host root like `https://selfservice.foo.edu`
        subject   — subject code passed to `?subjects=` (e.g. "CSC")
    """

    base_url: str = ""
    subject: str = ""

    page_load_timeout = 60
    post_load_sleep = 2.0
    fresh_driver_per_load = False
    # The base class's year×term loop doesn't apply — terms are discovered
    # at run time from the page itself, so we override `scrape()`.
    terms = []

    def url_for(self, academic_year, term):
        return f"{self.base_url}/Student/Courses/Search?subjects={self.subject}"

    def scrape(self):
        url = self.url_for(None, None)
        try:
            self.driver.get(url)
        except Exception as e:
            print(f"  failed to load {url}: {e}", flush=True)
            return []

        # Settle briefly, then check for login redirect before waiting on
        # term-filter elements that won't exist on the login page.
        time.sleep(2)
        if self._is_login_page():
            print("  requires login, skipping", flush=True)
            return []

        try:
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "input[id^=STATICterm]")
            )
        except TimeoutException:
            print("  timed out waiting for term filter", flush=True)
            return []
        time.sleep(self.post_load_sleep)

        self._expand_all_sections()
        return self._parse(self.driver.page_source)

    def _is_login_page(self):
        url = (self.driver.current_url or "").lower()
        title = (self.driver.title or "").lower()
        return "/account/login" in url or "sign in" in title

    def _expand_all_sections(self):
        """Click every 'View Available Sections' header to load sections."""
        buttons = self.driver.find_elements(
            By.CSS_SELECTOR,
            "button[id^=collapsible-view-available-sections-for-][id$=-groupHeading]",
        )
        for btn in buttons:
            try:
                self.driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass
        # Each click fires an XHR that paints a spinner; wait for them all
        # to clear. The spinner container has style toggled inline.
        deadline = time.time() + 60
        while time.time() < deadline:
            still_loading = self.driver.execute_script(
                "return Array.from(document.querySelectorAll("
                "  '.esg-spinner-container'"
                ")).some(e => e.offsetParent !== null);"
            )
            if not still_loading:
                break
            time.sleep(0.5)
        time.sleep(1)

    def _parse(self, html):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for body in soup.select(
            "[id^=collapsible-view-available-sections-for-][id$=-collapseBody]"
        ):
            # Each h4 inside is a term heading; sections live in the next ul.
            for h4 in body.find_all("h4"):
                term_label = _clean(h4.get_text(" ", strip=True))
                academic_year, term = parse_term_label(term_label)
                if academic_year is None or term is None:
                    continue
                ul = h4.find_next_sibling("ul")
                if ul is None:
                    continue
                for li in ul.select("li.search-nestedaccordionitem"):
                    rows.append(self._parse_section(li, academic_year, term))
        return [r for r in rows if r is not None]

    def _parse_section(self, li, academic_year, term):
        link = li.select_one("a.search-sectiondetailslink")
        section_name = _clean(link.get_text(" ", strip=True)) if link else ""
        m = SECTION_RE.match(section_name)
        if m:
            course_code = m.group("code")
            section = m.group("section")
        else:
            course_code, section = section_name, ""

        title_span = li.select_one('[id^="section-title-"]')
        course_name = _clean(title_span.get_text(" ", strip=True)) if title_span else ""

        time_text, instructor = "", ""
        first_row = li.select_one("table.search-sectiontable tbody tr")
        if first_row is not None:
            time_cell = first_row.select_one("td.search-sectiondaystime")
            instr_cell = first_row.select_one(
                "td.search-sectioninstructormethods, td.search-sectioninstructors"
            )
            # The days/time cell stacks two divs: meeting time first, then
            # the date range. Keep just the first div.
            if time_cell is not None:
                first_div = time_cell.find("div")
                time_text = _visible_text(first_div if first_div else time_cell)
            if instr_cell is not None:
                raw = _visible_text(instr_cell)
                # Self-Service appends a meeting-type tag like `( Lecture )`
                # after each instructor; strip all such parentheticals so a
                # multi-instructor cell reads "Smith, A; Jones, B" instead of
                # "Smith, A ( Lecture ) Jones, B".
                instructor = _clean(re.sub(r"\s*\([^)]*\)", " ", raw))

        return self.make_row(
            academic_year,
            term,
            course_code=course_code,
            section=section,
            course_name=course_name,
            instructor=instructor,
            time=time_text,
        )


# ---- per-college configs ---------------------------------------------------

# (College, base_url, subject)
SELFSERVICE_COLLEGES = [
    (College.AUGUSTANA, "https://selfservice.augustana.edu", "CSC"),
    (College.FRANKLIN, "https://selfservice.franklin.edu", "COMP"),
    (College.HARTWICK, "https://selfservice.hartwick.edu", "CISC"),
    (College.JUNIATA, "https://selfservice.juniata.edu", "CS"),
    (College.LINFIELD, "https://selfservice.linfield.edu", "COMP"),
    (College.ROANOKE, "https://selfservice.roanoke.edu", "CPSC"),
    (College.SAINT_MICHAEL, "https://selfservice.smcvt.edu", "CS"),
    (College.SAINT_VINCENT, "https://selfservice.stvincent.edu", "CS"),
    (College.SOUTHWESTERN, "https://selfservice.southwestern.edu", "CSC54"),
    (College.UNION, "https://selfservice.union.edu", "CSC"),
    (College.URSINUS, "https://selfservice.ursinus.edu", "CS"),
    (College.WHITMAN, "https://selfservice.whitman.edu", "CS"),
    (College.WITTENBERG, "https://selfservice.wittenberg.edu", "COMP"),
]


def _make_class(coll, base_url, subject):
    safe = re.sub(r"\W+", "", str(coll))
    return type(
        f"{safe}SelfServiceScraper",
        (EllucianSelfServiceScraper,),
        {"college": coll, "base_url": base_url, "subject": subject},
    )


def selfservice_scrapers():
    """Return one scraper class per configured Self-Service college."""
    return [_make_class(*cfg) for cfg in SELFSERVICE_COLLEGES]
