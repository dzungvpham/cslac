"""Hope College course schedule scraper.

Hope publishes a Banner-backed schedule at `schedule.hope.edu`. The page
itself is a DataTables UI (the "pagination" is purely client-side), but
the data is loaded from a single `data.php` POST that returns every
section for the given term as JSON. We hit that endpoint directly and
filter to `SSBSECT_SUBJ_CODE == "CSCI"`.

Term codes are `YYYY{01|08}` where 08 is fall (start of an academic
year) and 01 is spring (end of an academic year), e.g. Fall 2025 =
`202508`, Spring 2026 = `202601`.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

API_URL = "https://schedule.hope.edu/data.php"
SUBJECT = "CSCI"


class HopeScraper(CourseScheduleScraper):
    college = College.HOPE
    terms = ["F", "S"]
    public_url_template = True

    def _term_code(self, academic_year, term):
        start, end = academic_year
        if term == "F":
            return f"{start}08"
        if term == "S":
            return f"{end}01"
        raise ValueError(f"unsupported term: {term!r}")

    def url_for(self, academic_year, term):
        # Just for display in error messages; the real fetch hits the API.
        return f"https://schedule.hope.edu/?term={self._term_code(academic_year, term)}&subj={SUBJECT}"

    def fetch_page(self, academic_year, term):
        code = self._term_code(academic_year, term)
        resp = requests.post(API_URL, data={"term": code}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, payload, academic_year, term):
        try:
            data = json.loads(payload).get("data") or []
        except json.JSONDecodeError:
            return []

        rows = []
        for d in data:
            if d.get("SSBSECT_SUBJ_CODE") != SUBJECT:
                continue
            crse_num = (d.get("SSBSECT_CRSE_NUMB") or "").strip()
            if not crse_num:
                continue
            course_code = f"{SUBJECT} {crse_num}"
            section = (d.get("SSBSECT_SEQ_NUMB") or "").strip()
            course_name = (
                d.get("SCBCRSE_TITLE")
                or d.get("SSRSYLN_LONG_COURSE_TITLE")
                or d.get("SSBSECT_CRSE_TITLE")
                or ""
            )
            instructor = (d.get("FACULTY_NAME") or "").strip()
            time_text = _format_meetings(d)

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name.strip(),
                    instructor=instructor,
                    time=time_text,
                )
            )
        return rows


def _format_meetings(d):
    """Join one or more meeting blocks into a single 'days HH:MMam-HH:MMpm'
    string (multiple meetings separated by ' / '). Returns 'TBA' when the
    section has no scheduled time."""
    meetings = d.get("MEETTIMES") or []
    parts = []
    for m in meetings:
        days = "".join(
            m.get(day) or ""
            for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
        )
        start = _mil_to_12h(m.get("starttime"))
        end = _mil_to_12h(m.get("endtime"))
        if not start or not end:
            continue
        chunk = f"{start}-{end}"
        if days:
            chunk = f"{days} {chunk}"
        parts.append(chunk)
    if not parts:
        meetdays = (d.get("MEETDAYS") or "").strip()
        return meetdays if meetdays and meetdays != "TBA" else ("TBA" if meetdays == "TBA" else "")
    return " / ".join(parts)


def _mil_to_12h(t):
    """`'1400'` -> `'2:00pm'`, `'0830'` -> `'8:30am'`."""
    if not t or len(t) != 4 or not t.isdigit():
        return ""
    hour = int(t[:2])
    minute = int(t[2:])
    suffix = "pm" if hour >= 12 else "am"
    hour12 = ((hour + 11) % 12) + 1
    return f"{hour12}:{minute:02d}{suffix}"
