"""Gordon College course schedule scraper.

Gordon's public schedule lives in an iframe at
``https://wwwapps.gordon.edu/apps/courses/schedule.cfm?strTerm={FA|SP|SU}``,
served as a single static HTML table per term. There is no term-history
parameter — the three URLs only ever return the most recent Fall, Spring,
and Summer — so we capture whatever appears (parsing the academic year
from the page title) rather than iterating a fixed history.

The schedule page renders fully on the server, so we hit it with
``requests`` and parse the table directly. CS sections are filtered by the
``CPS`` course prefix. Lab rows show up as ``"CPS121 L"`` in the Course
column and become ``(course_code="CPS 121", section="Lab")``.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import (  # noqa: E402
    CourseScheduleScraper,
    format_academic_year,
)

BASE_URL = "https://wwwapps.gordon.edu/apps/courses/schedule.cfm"

# Map our internal term code to Gordon's strTerm value.
TERM_CODES = {"F": "FA", "S": "SP", "Su": "SU"}

# Match the page title's "<start>-<end> <Season>" header — Gordon's only
# canonical signal of which academic year a page is showing.
TITLE_RE = re.compile(r"(\d{4})\s*-\s*(\d{4})\s+(Fall|Spring|Summer)", re.I)

REQUEST_TIMEOUT = 30


class GordonScraper(CourseScheduleScraper):
    college = College.GORDON
    # Gordon only exposes the current Fall/Spring/Summer in the iframe app,
    # so iterating over `years_back` doesn't help — we scrape one of each.
    terms: list = []
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None

    def _ensure_session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (cs-lac course-schedule scraper)",
            })
            self._session = s
        return self._session

    def scrape(self):
        rows = []
        s = self._ensure_session()
        for term_code, str_term in TERM_CODES.items():
            url = f"{BASE_URL}?strTerm={str_term}"
            try:
                resp = s.get(url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{str_term}] failed to load: {e}", flush=True)
                continue
            ay = _parse_academic_year(resp.text)
            if ay is None:
                print(f"  [{str_term}] could not parse academic year", flush=True)
                continue
            page_rows = self._parse_html(resp.text, ay, term_code, url)
            label = f"{format_academic_year(ay)}/{term_code}"
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _parse_html(self, html, academic_year, term, url):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 12:
                continue
            course_raw = _clean(cells[1].get_text())
            if not course_raw.startswith("CPS"):
                continue
            course_code, section = _split_code(course_raw)
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=_clean(cells[3].get_text()),
                    instructor=_clean(cells[5].get_text()),
                    time=_format_time(_clean(cells[9].get_text()),
                                      _clean(cells[10].get_text()),
                                      _clean(cells[11].get_text())),
                    url=url,
                )
            )
        return rows

    def close(self):
        super().close()
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def _parse_academic_year(html):
    m = TITLE_RE.search(html)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _split_code(raw):
    """``"CPS121"`` -> ``("CPS 121", "")``; ``"CPS121 L"`` -> ``("CPS 121", "Lab")``."""
    m = re.match(r"^([A-Za-z]+)\s*(\d+)\s*([A-Za-z]?)$", raw)
    if not m:
        return raw, ""
    prefix, number, suffix = m.group(1), m.group(2), m.group(3)
    section = "Lab" if suffix.upper() == "L" else suffix
    return f"{prefix} {number}", section


def _format_time(days, times, location):
    days_compact = "".join(days.split())  # "M W F" -> "MWF"
    time_str = _compact_time_range(times)
    parts = [p for p in (days_compact, time_str) if p]
    s = " ".join(parts)
    if location:
        s = f"{s} ({location})" if s else f"({location})"
    return s


def _compact_time_range(times):
    """``"12:40PM - 01:40PM"`` -> ``"12:40-13:40"``."""
    if not times:
        return ""
    m = re.match(
        r"^(\d{1,2}:\d{2})\s*([AP]M)\s*-\s*(\d{1,2}:\d{2})\s*([AP]M)$",
        times,
        re.I,
    )
    if not m:
        return times
    return f"{_to_24h(m.group(1), m.group(2))}-{_to_24h(m.group(3), m.group(4))}"


def _to_24h(hhmm, suffix):
    h, mm = hhmm.split(":")
    h = int(h)
    suffix = suffix.upper()
    if suffix == "AM" and h == 12:
        h = 0
    elif suffix == "PM" and h != 12:
        h += 12
    return f"{h:02d}:{mm}"
