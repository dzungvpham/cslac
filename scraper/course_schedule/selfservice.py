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
        rows = self._load_and_parse(url)
        if rows is None:
            return []

        # Some deployments expose more terms in the filter sidebar than the
        # default (no-filter) load actually returns sections for — e.g.
        # Augustana lists 4 sidebar terms but the default load only contains
        # sections from 1. Re-load with `?terms=` populated for every sidebar
        # term to surface the extras. Skip when the default load already
        # covers more terms than the sidebar advertises (Susquehanna's
        # deployment exposes years of history that no sidebar checkbox
        # represents — we'd lose data by constraining to it).
        sidebar_terms = self._sidebar_term_ids()
        seen_terms = {(r["academic_year"], r["term"]) for r in rows}
        if len(sidebar_terms) > len(seen_terms):
            print(
                f"  default load covered {len(seen_terms)} term(s); "
                f"sidebar advertises {len(sidebar_terms)} — re-loading with all",
                flush=True,
            )
            params = "&".join(f"terms={t}" for t in sidebar_terms)
            extra = self._load_and_parse(f"{url}&{params}")
            if extra:
                # Merge: dedupe on (year, term, course_code, section).
                key = lambda r: (r["academic_year"], r["term"], r["course_code"], r["section"])
                by_key = {key(r): r for r in rows}
                for r in extra:
                    by_key.setdefault(key(r), r)
                rows = list(by_key.values())
        return rows

    def _load_and_parse(self, url):
        """Return parsed rows for `url`, or `None` on failure / login wall."""
        try:
            self.driver.get(url)
        except Exception as e:
            print(f"  failed to load {url}: {e}", flush=True)
            return None

        # Settle briefly, then check for login redirect before waiting on
        # term-filter elements that won't exist on the login page.
        time.sleep(2)
        if self._is_login_page():
            print("  requires login, skipping", flush=True)
            return None

        # Wait for the term-filter sidebar OR (as a fallback) the section-
        # expansion buttons. A handful of deployments (e.g. Emmanuel) hide the
        # term sidebar but still render course cards with expandable sections;
        # in that case the term comes from the <h4> heading inside each
        # expanded section, so we can proceed without the sidebar.
        try:
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "input[id^=STATICterm]")
                or d.find_elements(
                    By.CSS_SELECTOR,
                    "button[id^=collapsible-view-available-sections-for-]",
                )
            )
        except TimeoutException:
            print("  timed out waiting for course list", flush=True)
            return None
        time.sleep(self.post_load_sleep)

        # Self-Service paginates results client-side (Knockout) — by default
        # only the first page's cards are in the DOM. Walk through every page,
        # expanding + parsing each in turn, since navigating away rebuilds
        # the card list and we lose the previous page's expansions.
        rows = []
        page_count = 0
        while True:
            self._expand_all_sections()
            rows.extend(self._parse(self.driver.page_source) or [])
            page_count += 1
            if not self._goto_next_page():
                break
            if page_count >= 50:
                print(f"  pagination safety cap hit at {page_count} pages", flush=True)
                break
        return rows

    def _sidebar_term_ids(self):
        """Return the term codes advertised by the filter sidebar.

        e.g. an `<input id="STATICterm20253SP">` yields `"20253SP"`.
        """
        ids = self.driver.execute_script(
            "return Array.from(document.querySelectorAll('input[id^=STATICterm]'))"
            ".map(e => e.id);"
        ) or []
        return [i[len("STATICterm"):] for i in ids if i.startswith("STATICterm")]

    def _is_login_page(self):
        from urllib.parse import urlparse
        cur = self.driver.current_url or ""
        cur_l = cur.lower()
        title = (self.driver.title or "").lower()
        if "/account/login" in cur_l or "sign in" in title or "single sign-on" in title:
            return True
        # SSO redirect to a different host (e.g. Westmont -> login.westmont.edu).
        try:
            base_host = urlparse(self.base_url).hostname or ""
            cur_host = urlparse(cur).hostname or ""
            if base_host and cur_host and cur_host != base_host:
                return True
        except Exception:
            pass
        return False

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

    def _goto_next_page(self):
        """Advance to the next results page. Return False if already on last."""
        info = self.driver.execute_script(
            "var cur = document.getElementById('course-results-current-page');"
            "var tot = document.getElementById('course-results-total-pages');"
            "var btn = document.getElementById('course-results-next-page');"
            "if (!cur || !tot || !btn) return null;"
            "return {cur: parseInt(cur.value, 10) || 1,"
            "        tot: parseInt(tot.textContent, 10) || 1};"
        )
        if not info or info["cur"] >= info["tot"]:
            return False

        # Knockout re-renders the card list on page change. Fingerprint the
        # cards before clicking so we can wait for the swap rather than
        # sleeping a fixed amount.
        before = self.driver.execute_script(
            "return Array.from(document.querySelectorAll("
            "  'button[id^=collapsible-view-available-sections-for-]'"
            ")).map(b => b.id).join('|');"
        )
        self.driver.execute_script(
            "document.getElementById('course-results-next-page').click();"
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            now = self.driver.execute_script(
                "return Array.from(document.querySelectorAll("
                "  'button[id^=collapsible-view-available-sections-for-]'"
                ")).map(b => b.id).join('|');"
            )
            if now and now != before:
                break
            time.sleep(0.3)
        time.sleep(self.post_load_sleep)
        return True

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
    # Self-Service deployments hosted under non-`selfservice.*` subdomains.
    # Emmanuel (https://ecss.emmanuel.edu) is intentionally NOT listed: its
    # deployment renders the course catalog skeleton publicly but leaves the
    # `<collapsible-group>` Knockout components unbound, so section data
    # (term, instructor, time) is only available after sign-in.
    (College.GRINNELL, "https://colss-prod.ec.grinnell.edu", "CSC"),
    (College.GUSTAVUS_ADOLPHUS, "https://colselfsrvprod.gac.edu", "MCS"),
    (College.LUTHER, "https://norsehub.luther.edu", "CS"),
    (College.LYCOMING, "https://collslfsrv-live.lycoming.edu", "CPTR"),
    (College.MEREDITH, "https://mcis.meredith.edu", "CS"),
    (College.SUSQUEHANNA, "https://su-ss-live.susqu.edu", "CSCI"),
    (College.WASHINGTON_JEFFERSON, "https://jaysource.washjeff.edu", "CIS"),
    (College.WESTMONT, "https://waypoint.westmont.edu", "CS"),
    (College.WILLAMETTE, "https://collslfsrv.willamette.edu", "CS"),
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
