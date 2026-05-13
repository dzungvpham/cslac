"""University of Minnesota Morris course schedule scraper.

The University of Minnesota system publishes a public Schedule Builder
SPA at ``https://schedulebuilder.umn.edu/``. For each campus only the
currently-active terms are exposed (typically the previous, current,
and next 1-2 terms) — the API explicitly rejects historical terms with
``{"error":true,"error_detail":"Invalid term."}``.

Term URLs look like ``/explore/{CalendarYear}{TermWord}/{Subject}/``,
e.g. ``/explore/2026Fall/CSCI/``. We:

  1. Load the home page and read the Term dropdown after selecting the
     Morris campus, to discover whichever terms are currently exposed.
  2. For each term, navigate to its explore URL, click the
     "Show all sections" action so every section table is rendered,
     and parse the resulting per-course tables.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

HOME_URL = "https://schedulebuilder.umn.edu/"
EXPLORE_URL = "https://schedulebuilder.umn.edu/explore/{term_slug}/CSCI/"

TERM_WORD_TO_CODE = {"Fall": "F", "Spring": "S", "Summer": "Su", "Winter": "W"}

# Course-header pattern: "CSCI 1251: Computational Data Management..."
COURSE_RE = re.compile(r"^(?P<code>[A-Z]+\s+\d+\w*)\s*:\s*(?P<name>.+)$")


class MinnesotaMorrisScraper(CourseScheduleScraper):
    college = College.MINNESOTA_MORRIS
    terms = []  # discovered at runtime
    page_load_timeout = 60
    post_load_sleep = 1.5
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        return HOME_URL

    def scrape(self):
        try:
            term_options = self._discover_terms()
        except Exception as e:
            print(f"  failed to discover terms: {e}", flush=True)
            return []
        rows = []
        for label, (academic_year, term) in term_options:
            slug = re.sub(r"\s+", "", label)  # "Fall 2026" -> "Fall2026"; but URL is "2026Fall"
            year_word = label.split()
            term_slug = f"{year_word[1]}{year_word[0]}"  # "2026Fall"
            url = EXPLORE_URL.format(term_slug=term_slug)
            try:
                page_rows = self._scrape_term(url, academic_year, term)
            except Exception as e:
                print(f"  [{label}] failed: {e}", flush=True)
                continue
            print(f"  [{self._label(academic_year, term)}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _discover_terms(self):
        """Return [(label, (academic_year, term))] for every term the home
        page's term dropdown lists for the Morris campus.
        """
        self.driver.get(HOME_URL)
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "select")
        )
        # The page has the Morris campus pre-selected via cookies after a
        # first visit, but force it via JS to be safe — then read the term
        # dropdown options.
        terms = self.driver.execute_script(
            "var sels = document.querySelectorAll('select');"
            "var camp = Array.from(sels).find(s => s.options[0] &&"
            "  /Crookston|Morris|Duluth/.test(s.options[0].text + s.options[1].text));"
            "if (camp && camp.value !== 'UMNMO') {"
            "  camp.value = 'UMNMO';"
            "  camp.dispatchEvent(new Event('change', {bubbles: true}));"
            "}"
            "var term = Array.from(document.querySelectorAll('select')).find(s =>"
            "  Array.from(s.options).some(o => /Fall|Spring|Summer|Winter/.test(o.text)));"
            "return term ? Array.from(term.options).map(o => o.text.trim()) : [];"
        )
        out = []
        for label in terms or []:
            parsed = _parse_term_label(label)
            if parsed is None:
                continue
            out.append((label, parsed))
        out.sort(key=lambda x: (x[1][0], _term_sort_key(x[1][1])))
        return out

    def _scrape_term(self, url, academic_year, term):
        self.driver.get(url)
        # Wait for either the course list or the empty placeholder to appear.
        try:
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, ".action-sections")
                or "no courses" in (d.page_source or "").lower()
            )
        except TimeoutException:
            return []
        # Click "Show all sections" so each course card renders its section table.
        try:
            self.driver.execute_script(
                "var b = document.querySelector('.action-sections');"
                "if (b) b.click();"
            )
        except Exception:
            pass
        time.sleep(self.post_load_sleep)
        return _parse_page(self, self.driver.page_source, academic_year, term)


def _parse_term_label(label):
    """`'Fall 2026'` -> `((2026, 2027), 'F')`, `'Spring 2027'` ->
    `((2026, 2027), 'S')`, etc. Returns None for empty / unknown labels.
    """
    parts = (label or "").strip().split()
    if len(parts) != 2:
        return None
    word, year_s = parts
    code = TERM_WORD_TO_CODE.get(word)
    if code is None:
        return None
    try:
        year = int(year_s)
    except ValueError:
        return None
    if code == "F":
        return (year, year + 1), code
    return (year - 1, year), code


def _term_sort_key(term):
    return {"F": 0, "W": 1, "S": 2, "Su": 3}.get(term, 9)


def _parse_page(scraper, html, academic_year, term):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # Walk each course card; its heading sits before the section table.
    for table in soup.select("table.table-condensed"):
        course_code, course_name = _find_course_header(table)
        if course_code is None:
            continue
        for tr in table.select("tbody.section_info > tr, tbody > tr"):
            row = _parse_section_row(
                scraper, tr, academic_year, term, course_code, course_name
            )
            if row is not None:
                rows.append(row)
    return rows


def _find_course_header(table):
    """Walk up from `table` looking for an h2/h3/h4 with the course code."""
    node = table
    for _ in range(8):
        node = node.parent
        if node is None:
            break
        heading = node.find(["h2", "h3", "h4"])
        if heading is None:
            continue
        text = _clean(heading.get_text(" ", strip=True))
        m = COURSE_RE.match(text)
        if m:
            return m.group("code"), m.group("name")
    return None, None


def _parse_section_row(scraper, tr, academic_year, term, course_code, course_name):
    tds = tr.find_all("td")
    if len(tds) < 7:
        return None
    # Schedule Builder columns: [status, class#, section, meeting times,
    # period (date range), room, instructors, seats]
    class_nbr = _clean(tds[1].get_text(" ", strip=True))
    section_cell = _clean(tds[2].get_text(" ", strip=True))
    # `section_cell` looks like "001 LEC" — keep as section identifier.
    section = section_cell
    time_text = _clean(tds[3].get_text(" ", strip=True))
    instr_cell = tds[6]
    instructors = _dedupe([_clean(a.get_text()) for a in instr_cell.find_all("a")])
    if not instructors:
        instructors = [_clean(instr_cell.get_text(" ", strip=True))]
    return scraper.make_row(
        academic_year,
        term,
        course_code=course_code,
        section=section,
        course_name=course_name,
        instructor=_blank_if_placeholder("; ".join(n for n in instructors if n)),
        time=_blank_if_placeholder(time_text),
    )


def _blank_if_placeholder(text):
    """Schedule Builder uses the literal string "None listed." for cells
    with no data yet (e.g. independent study sections). Treat it as
    empty so it doesn't leak through as if it were real instructor /
    time data."""
    return "" if text in ("None listed.", "TBA") else text


def _dedupe(items):
    seen, out = set(), []
    for x in items:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
