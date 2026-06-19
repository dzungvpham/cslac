"""Massachusetts College of Liberal Arts course schedule scraper.

MCLA publishes its schedule through an old Banner 8 self-service "Schedule of
Classes" page (not the Banner 9 SSB JSON API), reachable by URL:

    https://banweb.mcla.edu:8443/PRD8/bwzkcsch.P_DispSchedule?term=<TERM>&levl=UD&display_opt=ALL

The page is server-rendered HTML (no JS) but served over a host whose TLS chain
doesn't verify cleanly, so we fetch with `requests` + `verify=False`.

Term codes are `YYYY<season>` where season is 20=Spring, 40=Summer, 60=Fall.
Fall belongs to the academic year's start year; Spring/Summer to its end year.

The whole-college listing is one big table whose data rows have nine cells:

    Course#-Section (CRN) | Levl | Title | Credits | Meeting Times & Location |
    Seats | Instructor | Core | Requirements

The table repeats its header and interleaves single-cell department headings
between blocks; both are skipped because only rows whose first cell matches the
``CSCI-<num>-<sec> (<crn>)`` pattern are kept. The Title cell links to the
course's catalog detail page, which we keep as the per-row URL.
"""

import re
import sys
import warnings
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE = "https://banweb.mcla.edu:8443/PRD8/bwzkcsch.P_DispSchedule"
SUBJECT = "CSCI"

# First-cell course token, e.g. "CSCI-120-01 (20145)".
COURSE_RE = re.compile(r"^([A-Z]+)-(\d+)-(\w+)\s*\(\d+\)$")
# Leading date range on a meeting cell, e.g. "01/22-05/12  TR  09:00am-...".
DATE_RANGE_RE = re.compile(r"^\d{1,2}/\d{1,2}-\d{1,2}/\d{1,2}\s*")

# Banner season suffix for the term code.
_SEASON = {"F": "60", "S": "20", "Su": "40"}


class MCLAScraper(CourseScheduleScraper):
    college = College.MASSACHUSETTS_LAC
    terms = ["F", "S", "Su"]
    fresh_driver_per_load = False  # plain HTTP, no Selenium
    public_url_template = True     # the DispSchedule page is user-facing

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers["User-Agent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        return self._session

    def _term_code(self, academic_year, term):
        start, end = academic_year
        year = start if term == "F" else end
        return f"{year}{_SEASON[term]}"

    def url_for(self, academic_year, term):
        code = self._term_code(academic_year, term)
        return f"{BASE}?term={code}&levl=UD&display_opt=ALL"

    def fetch_page(self, academic_year, term):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # silence InsecureRequestWarning
            r = self.session.get(
                self.url_for(academic_year, term),
                timeout=self.page_load_timeout,
                verify=False,
            )
        r.raise_for_status()
        return r.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 9:
                continue
            m = COURSE_RE.match(tds[0].get_text(" ", strip=True))
            if not m or m.group(1) != SUBJECT:
                continue
            course_code = f"{m.group(1)} {m.group(2)}"
            section = m.group(3)
            course_name = _clean(tds[2].get_text(" ", strip=True))
            time_text = _clean_time(tds[4].get_text(" ", strip=True))
            instructor = _format_instructor(tds[6].get_text(" ", strip=True))
            link = tds[2].find("a", href=True)
            url = link["href"] if link else self.url_for(academic_year, term)
            rows.append(self.make_row(
                academic_year, term,
                course_code=course_code,
                section=section,
                course_name=course_name,
                instructor=instructor,
                time=time_text,
                url=url,
            ))
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_time(text):
    """Drop the leading semester date range and collapse whitespace."""
    return _clean(DATE_RANGE_RE.sub("", text or ""))


def _format_instructor(text):
    """Banner gives "Last, First"; flip to "First Last" to match the faculty
    list. Leave anything else (TBA, multi-instructor cells) untouched."""
    text = _clean(text)
    parts = text.split(",")
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return f"{parts[1].strip()} {parts[0].strip()}"
    return text
