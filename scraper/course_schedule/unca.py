"""UNC Asheville course schedule scraper.

UNCA's registrar exposes a clean per-semester JSON API at
`meteor.unca.edu/registrar/class-schedules/api/v1/courses/{year}/{semester}`
where `semester` is `fall`, `spring`, or `summer`. Each call returns every
section across all departments for that term; we filter to `Department ==
"CSCI"`.

Each entry's `Code` looks like `"CSCI 201.001"` — we split on `.` to get
`course_code` (`CSCI 201`) and `section` (`001`, occasionally `0X1` for
special sections). `Days` is already a clean `MWF`-style string. Times are
ISO timestamps with a placeholder date (`2019-05-07T...Z`); the time-of-day
portion is the only meaningful part, presented as 24-hour `HH:MM`.
`AdditionalMeetings` carries extra meeting patterns (lab + lecture) and is
folded into the same `time` field with `; ` separators.
"""

import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

API_TEMPLATE = (
    "https://meteor.unca.edu/registrar/class-schedules/api/v1/courses/{year}/{semester}"
)
DEPT = "CSCI"

# F starts an academic year, S/Su belong to the following calendar year.
TERM_TO_SEMESTER = {"F": "fall", "S": "spring", "Su": "summer"}


class UNCAshevilleScraper(CourseScheduleScraper):
    college = College.NORTH_CAROLINA_ASHEVILLE
    terms = ["F", "S", "Su"]

    @staticmethod
    def _api_url(academic_year, term):
        start_year, end_year = academic_year
        year = start_year if term == "F" else end_year
        return API_TEMPLATE.format(year=year, semester=TERM_TO_SEMESTER[term])

    def url_for(self, academic_year, term):
        return self._api_url(academic_year, term)

    def fetch_page(self, academic_year, term):
        resp = requests.get(self._api_url(academic_year, term), timeout=60)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def parse_page(self, data, academic_year, term):
        if not data:
            return []
        url = self._api_url(academic_year, term)
        rows = []
        for entry in data:
            if entry.get("Department") != DEPT:
                continue
            code, section = _split_code(entry.get("Code") or "")
            instructor = ", ".join(
                (i.get("Name") or "").strip()
                for i in entry.get("Instructors") or []
                if i.get("Name")
            )
            meetings = [_format_meeting(entry)]
            for extra in entry.get("AdditionalMeetings") or []:
                meetings.append(_format_meeting(extra))
            time_str = "; ".join(m for m in meetings if m)
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=code,
                    section=section,
                    course_name=(entry.get("Title") or "").strip(),
                    instructor=instructor,
                    time=time_str,
                    url=url,
                )
            )
        return rows


def _split_code(raw):
    """`"CSCI 201.001"` -> `("CSCI 201", "001")`."""
    if "." in raw:
        code, section = raw.rsplit(".", 1)
        return code.strip(), section.strip()
    return raw.strip(), ""


def _format_meeting(meeting):
    days = (meeting.get("Days") or "").strip()
    start = _time_of_day(meeting.get("StartTime"))
    end = _time_of_day(meeting.get("EndTime"))
    location = (((meeting.get("Location") or {}).get("FullLocation")) or "").strip()
    time_range = f"{start}-{end}" if start and end else (start or end)
    bits = [b for b in (days, time_range) if b]
    s = " ".join(bits)
    if location:
        s = f"{s} ({location})" if s else f"({location})"
    return s


_TIME_RE = re.compile(r"T(\d{2}):(\d{2})")


def _time_of_day(iso):
    if not iso:
        return ""
    m = _TIME_RE.search(iso)
    return f"{m.group(1)}:{m.group(2)}" if m else ""
