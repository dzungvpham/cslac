"""University of Puget Sound course schedule scraper.

Puget Sound runs the standard PeopleSoft Class Search at

    https://campus.pugetsound.edu/psc/PUBLIC/EMPLOYEE/CAMPPUB/c/
    COMMUNITY_ACCESS.CLASS_SEARCH.GBL

The term dropdown only exposes the currently registerable terms
(usually 3-4: current + next + summer variants), so this scraper
discovers whatever terms appear at run time rather than iterating a
fixed year × term loop.

Driver flow per term:
    1. Open the search form.
    2. Set Institution=PUGET, Term=<code>, Subject=CSCI.
    3. Click Search; uncheck "Open Classes Only" first.
    4. Parse the rendered grid, where each course is a collapsible
       group containing one ``SSR_CLSRCH_MTG1`` section table.
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

FORM_URL = (
    "https://campus.pugetsound.edu/psc/PUBLIC/EMPLOYEE/CAMPPUB/c/"
    "COMMUNITY_ACCESS.CLASS_SEARCH.GBL"
)

INSTITUTION_ID = "CLASS_SRCH_WRK2_INSTITUTION$31$"
TERM_ID = "CLASS_SRCH_WRK2_STRM$35$"
SUBJECT_ID = "SSR_CLSRCH_WRK_SUBJECT_SRCH$0"
OPEN_ONLY_ID = "SSR_CLSRCH_WRK_SSR_OPEN_ONLY$5"
SEARCH_BTN_ID = "CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH"

TERM_WORD_RE = re.compile(r"^(?P<year>\d{4})\s+(?P<word>Fall|Spring|Summer|Winter)\b")
TERM_WORD_TO_CODE = {"Fall": "F", "Spring": "S", "Summer": "Su", "Winter": "W"}

# Course-header text inside `win0divSSR_CLSRSLT_WRK_GROUPBOX2GP$N`.
COURSE_HEADER_RE = re.compile(
    r"^(?P<subj>[A-Z]+)\s+(?P<num>\d+\w*)\s*-\s*(?P<name>.+?)\s*$"
)


class PugetSoundScraper(CourseScheduleScraper):
    college = College.PUGET_SOUND
    terms = []  # discovered at runtime
    page_load_timeout = 60
    post_load_sleep = 2.0
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        return FORM_URL

    def scrape(self):
        try:
            term_options = self._discover_terms()
        except Exception as e:
            print(f"  failed to discover terms: {e}", flush=True)
            return []
        rows = []
        for code, label, (academic_year, term) in term_options:
            try:
                page_rows = self._search_term(code, label, academic_year, term)
            except Exception as e:
                print(f"  [{label}] failed: {e}", flush=True)
                continue
            print(
                f"  [{self._label(academic_year, term)}] {len(page_rows)} sections",
                flush=True,
            )
            rows.extend(page_rows)
        return rows

    def _open_form(self):
        self.driver.get(FORM_URL)
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements(By.ID, INSTITUTION_ID)
        )
        time.sleep(1)

    def _discover_terms(self):
        """Read the term dropdown after picking Institution=PUGET."""
        self._open_form()
        Select(self.driver.find_element(By.ID, INSTITUTION_ID)).select_by_value("PUGET")
        time.sleep(self.post_load_sleep)
        term_opts = self.driver.execute_script(
            f"var s = document.getElementById('{TERM_ID}');"
            "return s ? Array.from(s.options).map(o => [o.value, o.text.trim()]) : [];"
        )
        out = []
        for value, label in term_opts or []:
            parsed = _parse_term_label(label)
            if value and parsed is not None:
                out.append((value, label, parsed))
        out.sort(key=lambda x: (x[2][0], _term_sort_key(x[2][1])))
        return out

    def _search_term(self, term_code, term_label, academic_year, term):
        # Re-open the form before each search — PeopleSoft postback state
        # accumulates and a fresh navigation is the most reliable reset.
        self._open_form()
        Select(self.driver.find_element(By.ID, INSTITUTION_ID)).select_by_value("PUGET")
        time.sleep(0.7)
        Select(self.driver.find_element(By.ID, TERM_ID)).select_by_value(term_code)
        time.sleep(0.7)
        # Subject list can vary per term — e.g. limited "Summer FYI"-style
        # terms only offer a handful of subjects. If CSCI isn't available
        # for this term, skip it cleanly.
        subject_values = self.driver.execute_script(
            f"var s = document.getElementById('{SUBJECT_ID}');"
            "return s ? Array.from(s.options).map(o => o.value) : [];"
        )
        if "CSCI" not in (subject_values or []):
            return []
        Select(self.driver.find_element(By.ID, SUBJECT_ID)).select_by_value("CSCI")
        time.sleep(0.4)

        # "Open Classes Only" is unchecked by default but be defensive.
        self.driver.execute_script(
            f"var c = document.getElementById('{OPEN_ONLY_ID}');"
            "if (c && c.checked) c.checked = false;"
        )
        self.driver.find_element(By.ID, SEARCH_BTN_ID).click()

        # PeopleSoft sometimes interstitial-warns "Your search will exceed
        # the maximum of 50 rows. Please narrow your search." For CSCI
        # that's unlikely, but auto-click "OK" if it shows up.
        time.sleep(self.post_load_sleep)
        self._dismiss_max_rows_warning()

        try:
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: d.find_elements(
                    By.CSS_SELECTOR, "[id^=win0divSSR_CLSRSLT_WRK_GROUPBOX2GP]"
                )
                or "did not return any results" in (d.page_source or "").lower()
                or "no classes were found" in (d.page_source or "").lower()
            )
        except TimeoutException:
            return []
        time.sleep(1)
        return _parse_results(self, self.driver.page_source, academic_year, term)

    def _dismiss_max_rows_warning(self):
        """If a PeopleSoft modal warns about too many rows, click OK."""
        try:
            ok = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type=button][value='OK'], a#\\#ICOK, a[id$=DERIVED_SSE_DSP_SSR_MSG_LONG_OK]",
            )
            if ok:
                ok[0].click()
                time.sleep(1)
        except Exception:
            pass


def _parse_term_label(label):
    """`'2026 Fall'` -> `((2026, 2027), 'F')`, `'2026 Spring'` ->
    `((2025, 2026), 'S')`, etc. Returns None for empty / unknown labels.
    Special "Summer FYI"-style suffix is preserved by `_term_sort_key`
    but normalized to Su for our term column.
    """
    m = TERM_WORD_RE.match((label or "").strip())
    if not m:
        return None
    code = TERM_WORD_TO_CODE.get(m.group("word"))
    if code is None:
        return None
    year = int(m.group("year"))
    if code == "F":
        return (year, year + 1), code
    return (year - 1, year), code


def _term_sort_key(term):
    return {"F": 0, "W": 1, "S": 2, "Su": 3}.get(term, 9)


def _parse_results(scraper, html, academic_year, term):
    soup = BeautifulSoup(html, "html.parser")
    headers = soup.select("[id^=win0divSSR_CLSRSLT_WRK_GROUPBOX2GP]")
    rows = []
    for idx, hdr in enumerate(headers):
        text = _clean(hdr.get_text(" ", strip=True))
        m = COURSE_HEADER_RE.match(text)
        if not m:
            continue
        course_code = f"{m.group('subj')} {m.group('num')}"
        course_name = m.group("name")
        # The matching section grid for header N has id suffix `$N`.
        grid = soup.find("table", id=f"SSR_CLSRCH_MTG1$scroll${idx}")
        if grid is None:
            continue
        for tr in grid.select("tr[id^=trSSR_CLSRCH_MTG1]"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 8:
                continue
            class_nbr = _clean(tds[0].get_text(" ", strip=True))
            section_raw = _clean(tds[1].get_text(" ", strip=True))
            section = _section_id(section_raw)
            days_times = _clean(tds[2].get_text(" ", strip=True))
            room = _clean(tds[5].get_text(" ", strip=True))
            instructor = _clean(tds[6].get_text(" ", strip=True))
            rows.append(
                scraper.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=_blank_if_placeholder(instructor),
                    time=_blank_if_placeholder(days_times),
                )
            )
    return rows


def _section_id(text):
    """`'A-LEC Full Term'` -> `'A-LEC'`. Strip the session label."""
    return text.split()[0] if text else ""


def _blank_if_placeholder(text):
    cleaned = (text or "").strip()
    if cleaned in ("Staff", "TBA", "TBD", "T B A"):
        return ""
    return cleaned


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
