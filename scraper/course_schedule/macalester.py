"""Macalester College course schedule scraper.

URL: /macssb/customPage/page/classSchedule?term={code}#COMP
where the term code is `{end_year}10` for the Fall semester of an academic
year and `{end_year}30` for the Spring semester (e.g. 202610 = Fall 2025,
202630 = Spring 2026 — both in AY 2025-26).

The page lists every department on one URL, so we filter by the COMP code
prefix in the course-id cell. Each section is a row of:

    <tr class="TableRowClass" data-id="12523" id="12523">
      <td class="col1">COMP 112-01 (12523)</td>
      <td class="col2">Introduction to Data Science</td>
      <td class="col3">
        <span>Meeting: </span>
        <span class="DaysSpan"> T R </span>
        <span class="TimesSpan">8:00 - 9:30 am</span>
        <span class="RoomsSpan">THEATR 200</span>
      </td>
      <td class="col4"><span>Instructor: </span>Andrew Beveridge</td>
      ...
    </tr>

The page is Angular-rendered and loading every department's detail blocks
takes several seconds, so we wait for actual COMP rows before parsing.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

LIST_URL = "https://macadmsys.macalester.edu/macssb/customPage/page/classSchedule?term={code}#COMP"

# "COMP 112-01 (12523)" -> code "COMP 112", section "01".
COURSE_ID_RE = re.compile(
    r"^(?P<code>COMP\s+\d+\w*)-(?P<section>\w+)\s*(?:\(\d+\))?\s*$"
)


class MacalesterScraper(CourseScheduleScraper):
    college = College.MACALESTER
    terms = ["F", "S"]
    # Wait until the COMP department's table has rendered, not just any
    # `TableRowClass` (the page paints other departments' rows first).
    wait_for = "tr.TableRowClass[data-id]"
    page_load_timeout = 60
    post_load_sleep = 4.0

    def url_for(self, academic_year, term):
        end_year = academic_year[1]
        suffix = "10" if term == "F" else "30" if term == "S" else None
        if suffix is None:
            raise ValueError(f"unsupported term: {term!r}")
        return LIST_URL.format(code=f"{end_year}{suffix}")

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.select("tr.TableRowClass[data-id]"):
            col1 = tr.select_one("td.col1")
            if col1 is None:
                continue
            col1_text = _clean(col1.get_text(" ", strip=True))
            if not col1_text.startswith("COMP "):
                continue
            m = COURSE_ID_RE.match(col1_text)
            if not m:
                continue
            course_code = _clean(m.group("code"))
            section = m.group("section")

            col2 = tr.select_one("td.col2")
            course_name = _clean(col2.get_text(" ", strip=True)) if col2 else ""

            col3 = tr.select_one("td.col3")
            days = col3.select_one(".DaysSpan") if col3 else None
            times = col3.select_one(".TimesSpan") if col3 else None
            day_text = _clean(days.get_text(" ", strip=True)) if days else ""
            time_text = _clean(times.get_text(" ", strip=True)) if times else ""
            if day_text and time_text:
                meeting = f"{day_text} {time_text}"
            else:
                meeting = day_text or time_text

            col4 = tr.select_one("td.col4")
            instructor = ""
            if col4 is not None:
                # Drop the "Instructor:" label span before reading text.
                for label in col4.select("span.mobileOnly"):
                    label.decompose()
                instructor = _clean(col4.get_text(" ", strip=True))

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=meeting,
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
