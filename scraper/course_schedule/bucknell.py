"""Bucknell University course schedule scraper.

Bucknell exposes its full term catalog as JSON at::

    https://pubapps.bucknell.edu/CourseInformation/data/course/term/{TERM}

where ``TERM`` is ``<YYYY><01|05|09>`` — ``01`` Fall, ``05`` Spring, ``09``
Summer, and ``YYYY`` is the *end* calendar year of the academic year
(e.g. ``202701`` is Fall of AY 2026-27). The lookup UI at
``/CourseInformation/#/lookup`` is just a SPA on top of this endpoint, so we
hit the JSON directly with ``requests`` and skip Selenium.

We filter to ``Subj == "CSCI"`` (CS sections only). CSCI summer offerings
have been empty for every recent year, so we only iterate Fall / Spring.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper, format_meeting_slots

DATA_URL = "https://pubapps.bucknell.edu/CourseInformation/data/course/term/{term}"
LOOKUP_URL = "https://pubapps.bucknell.edu/CourseInformation/#/lookup"

TERM_SUFFIX = {"F": "01", "S": "05", "Su": "09"}

# Ordered weekday columns as they appear in the JSON (Banner convention:
# U=Sun, R=Thu). We display Thursday as "Th" for readability.
DAY_FLAGS = [
    ("M", "M"),
    ("T", "T"),
    ("W", "W"),
    ("R", "Th"),
    ("F", "F"),
    ("S", "Sa"),
    ("U", "Su"),
]


class BucknellScraper(CourseScheduleScraper):
    college = College.BUCKNELL
    terms = ["F", "S"]
    # No Selenium needed — we hit a JSON endpoint directly.
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        return DATA_URL.format(term=_term_code(academic_year, term))

    def fetch_page(self, academic_year, term):
        resp = requests.get(self.url_for(academic_year, term), timeout=self.page_load_timeout)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        try:
            data = json.loads(html)
        except json.JSONDecodeError:
            return []
        rows = []
        for entry in data:
            if entry.get("Subj") != "CSCI":
                continue
            number = (entry.get("Number") or "").strip()
            course_code = f"CSCI {number}".strip() if number else "CSCI"
            section = (entry.get("Section") or "").strip()
            course_name = (entry.get("Title") or "").strip()
            instructor = _format_instructors(entry.get("Instructors") or [])
            time_str = _format_meetings(entry.get("Meetings") or [])
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_str,
                    url=LOOKUP_URL,
                )
            )
        return rows


def _term_code(academic_year, term):
    """Return Bucknell's `<end_year><suffix>` term code for an (AY, term)."""
    suffix = TERM_SUFFIX[term]
    end_year = academic_year[1]
    return f"{end_year}{suffix}"


def _format_instructors(instructors):
    names = []
    for inst in instructors:
        display = (inst.get("Display") or "").strip()
        if display and display not in names:
            names.append(display)
    return ", ".join(names)


def _format_meetings(meetings):
    """Render a `Meetings` list as `"MWF 11:00-11:50 (DANA 137); T 13:00-15:50"`."""
    slots = []
    for m in meetings:
        days = "".join(abbr for flag, abbr in DAY_FLAGS if (m.get(flag) or "").upper() == "Y")
        time_range = _format_time_range(m.get("Start"), m.get("End"))
        location = (m.get("Location") or "").strip()
        slots.append((days, time_range, location))
    return format_meeting_slots(slots)


def _format_time_range(start, end):
    s = _format_hhmm(start)
    e = _format_hhmm(end)
    if s and e:
        return f"{s}-{e}"
    return s or e or ""


def _format_hhmm(value):
    if not value:
        return ""
    s = str(value).strip()
    if len(s) == 4 and s.isdigit():
        return f"{s[:2]}:{s[2:]}"
    return s
