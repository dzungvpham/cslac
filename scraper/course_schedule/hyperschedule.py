"""Harvey Mudd and Pomona course schedule scraper.

Both schools belong to the Claremont Colleges consortium and publish their
schedules through Hyperschedule (https://hyperschedule.io/). The backing
API at `https://banana.hyperschedule.io/v4/sections/<TERM><YEAR>` returns
every section across all 5Cs for one term; we filter by `course.code.affiliation`
("HM" / "PO") and `course.code.department == "CSCI"`.

Terms are "FA" (Fall) and "SP" (Spring); we map the project's standard
"F"/"S" term codes onto these for the API request, but record "F"/"S" in
the output CSV.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

API_URL = "https://banana.hyperschedule.io/v4/sections/{term}{year}"

DEPARTMENT = "CSCI"

# Project term -> Hyperschedule term.
TERM_TO_API = {"F": "FA", "S": "SP"}

# Hyperschedule day codes are already M/T/W/R/F/S/U; preserve order.
DAY_ORDER = ["M", "T", "W", "R", "F", "S", "U"]

# Module-level cache so HarveyMudd and Pomona scrapers (each pulling the
# same all-5Cs payload) only hit the API once per term per process.
_API_CACHE: dict[str, list] = {}


def fetch_term(api_term: str) -> list:
    if api_term in _API_CACHE:
        return _API_CACHE[api_term]
    resp = requests.get(API_URL.format(term=api_term[:2], year=api_term[2:]), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    _API_CACHE[api_term] = data
    return data


def format_time(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    return f"{h:d}:{m:02d}"


def format_schedule(schedules: list) -> str:
    """Render a list of schedule blocks as e.g. "TR 9:35-10:50; M 13:15-14:30"."""
    parts = []
    for s in schedules:
        days = s.get("days") or []
        start = s.get("startTime") or 0
        end = s.get("endTime") or 0
        if not days and start == 0 and end == 0:
            continue
        days_str = "".join(d for d in DAY_ORDER if d in days)
        parts.append(f"{days_str} {format_time(start)}-{format_time(end)}".strip())
    return "; ".join(parts)


def format_course_code(code: dict) -> str:
    """`{department: CSCI, courseNumber: 5, suffix: "L"}` -> "CSCI-005L"."""
    return f"{code['department']}-{code['courseNumber']:03d}{code.get('suffix') or ''}"


class HyperscheduleScraper(CourseScheduleScraper):
    """Base class for HM/PO. Subclasses set `affiliation` to "HM" or "PO"."""

    affiliation: str = ""
    terms = ["F", "S"]
    # We hit a JSON API directly, so no Selenium driver is needed.
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        api_term = TERM_TO_API[term]
        # Fall term sits in the start year of an AY; Spring in the end year.
        api_year = academic_year[0] if term == "F" else academic_year[1]
        return API_URL.format(term=api_term, year=api_year)

    def fetch_page(self, academic_year, term):
        api_term = TERM_TO_API[term]
        api_year = academic_year[0] if term == "F" else academic_year[1]
        try:
            return fetch_term(f"{api_term}{api_year}")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def parse_page(self, sections, academic_year, term):
        if not sections:
            return []
        rows = []
        for s in sections:
            code = s["course"]["code"]
            if code.get("affiliation") != self.affiliation:
                continue
            if code.get("department") != DEPARTMENT:
                continue
            ident = s["identifier"]
            instructors = ", ".join(
                i.get("name", "").strip() for i in (s.get("instructors") or []) if i.get("name")
            )
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=format_course_code(code),
                    section=f"{ident.get('sectionNumber', 0):02d}",
                    course_name=s["course"].get("title", "").strip(),
                    instructor=instructors,
                    time=format_schedule(s.get("schedules") or []),
                )
            )
        return rows


class HarveyMuddScraper(HyperscheduleScraper):
    college = College.HARVEY_MUDD
    affiliation = "HM"


class PomonaScraper(HyperscheduleScraper):
    college = College.POMONA
    affiliation = "PO"
