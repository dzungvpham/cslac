"""Davidson College course schedule scraper.

Davidson exposes a public JSON API at

    https://api.davidson.edu/api/public/v2/courses
        ?departments=CSC&limit=...&offset=0&term_code={CODE}

Term codes are six digits — `YYYY01` is Fall YYYY, `YYYY02` is Spring YYYY+1
(so 202502 is Spring 2026, paired in academic year 2025-26 with 202501).

The endpoint returns a flat JSON list of one record per section, already
filtered to the requested department; each record carries `subject.code`,
`course_number`, `section`, `course_title`, `instructors_string`, and a
`meetings` array (we only see length-1 in practice). No Selenium needed.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

API_URL = "https://api.davidson.edu/api/public/v2/courses"
PUBLIC_URL = "https://course-schedule.davidson.edu/#/schedule"
DEPARTMENT = "CSC"
PAGE_LIMIT = 500


class DavidsonScraper(CourseScheduleScraper):
    college = College.DAVIDSON
    terms = ["F", "S"]
    # Plain HTTP — no Selenium.
    fresh_driver_per_load = False

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

    @staticmethod
    def _term_code(academic_year, term):
        start, _ = academic_year
        if term == "F":
            return f"{start}01"
        if term == "S":
            return f"{start}02"
        return None

    def url_for(self, academic_year, term):
        code = self._term_code(academic_year, term)
        if code is None:
            return None
        return (
            f"{API_URL}?departments={DEPARTMENT}"
            f"&limit={PAGE_LIMIT}&offset=0&term_code={code}"
        )

    def public_url_for(self, academic_year, term):
        # `url_for` hits the JSON API; the user-facing equivalent is the
        # frontend SPA at `course-schedule.davidson.edu`.
        code = self._term_code(academic_year, term)
        if code is None:
            return None
        return (
            f"{PUBLIC_URL}?departments={DEPARTMENT}"
            f"&limit=100&offset=0&term_code={code}"
        )

    def fetch_page(self, academic_year, term):
        url = self.url_for(academic_year, term)
        if url is None:
            return None
        r = self.session.get(url, timeout=self.page_load_timeout)
        r.raise_for_status()
        return r.content

    def parse_page(self, payload, academic_year, term):
        records = json.loads(payload)
        rows = []
        for c in records:
            subject = (c.get("subject") or {}).get("code") or ""
            number = c.get("course_number") or ""
            if not number:
                continue
            # The `departments=CSC` filter also returns cross-listings whose
            # primary subject is something else (e.g. BIO 209 cross-listed
            # with CSC). Keep only rows whose primary listing is CSC so
            # `course_code` is unambiguous.
            if subject != DEPARTMENT:
                continue
            course_code = f"{subject} {number}".strip()
            section = c.get("section") or ""
            course_name = c.get("course_title") or ""
            instructor = c.get("instructors_string") or ""
            time_text = _format_meetings(c.get("meetings") or [])

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                )
            )
        return rows


def _format_meetings(meetings):
    parts = []
    for m in meetings:
        days = m.get("weekdays") or ""
        when = m.get("class_time") or ""
        room = m.get("room") or ""
        building = (m.get("building") or {}).get("description") or ""
        location = " ".join(p for p in (building, room) if p)
        chunk = " ".join(p for p in (days, when) if p)
        if location:
            chunk = f"{chunk}, {location}" if chunk else location
        if chunk:
            parts.append(chunk)
    return "; ".join(parts)
