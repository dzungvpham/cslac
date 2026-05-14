"""Covenant College course schedule scraper.

Covenant publishes each term's course offerings as a Google Sheet,
linked from

    https://covenant.edu/academics/records/class-schedules.html

Link labels read e.g. "Spring 2026 Course Offerings", "Fall 2026 Course
Offerings", "Spring 2027 Course Tentative Offerings"; each `<a>` points
at a Google Sheets URL of the form

    https://docs.google.com/spreadsheets/d/<KEY>

which we hit as `…/<KEY>/export?format=csv` to pull the raw CSV. The
sheet groups courses by department: a department-name line ("Computer
Science"), then a header row
``CRN, Subject, Course #, Section, Course Title, Days, Begins, Ends,
Credit Hours, Instructor, …``, then one row per section. Blank rows
separate departments.

Only the upcoming term sheets stay linked from the page; once a term
ends, Covenant unlinks it. The merge logic in
`CourseScheduleScraper.run` keeps prior terms in our CSV.
"""

import csv
import io
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

SCHEDULES_URL = "https://covenant.edu/academics/records/class-schedules.html"
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{key}/export?format=csv"

LINK_LABEL_RE = re.compile(
    r"^(?P<season>Fall|Spring|Summer|May\s+Term)\s+(?P<year>\d{4})\b.*Offerings",
    re.I,
)
SEASON_TERM = {
    "fall": "F",
    "spring": "S",
    "summer": "Su",
    "may term": "Su",
}
SHEET_KEY_RE = re.compile(
    r"docs\.google\.com/spreadsheets/d/(?P<key>[A-Za-z0-9_-]+)"
)
HEADER_ROW = {
    "crn",
    "subject",
    "course #",
    "section",
}
TITLE_KEYS = ("course title", "title")
SUBJECTS = {"COS"}  # Computer Science.


class CovenantScraper(CourseScheduleScraper):
    college = College.COVENANT
    terms = []
    fresh_driver_per_load = False

    def scrape(self):
        try:
            sheets = self._discover_sheets()
        except requests.RequestException as e:
            print(f"  schedules page fetch failed: {e}", flush=True)
            return []
        if not sheets:
            print("  no term sheets linked from schedules page", flush=True)
            return []
        rows = []
        for academic_year, term, sheet_url, export_url in sheets:
            label = f"{academic_year[0]}-{academic_year[1] % 100:02d}/{term}"
            try:
                resp = requests.get(export_url, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{label}] sheet download failed: {e}", flush=True)
                continue
            page_rows = self._parse_csv(
                resp.content.decode("utf-8", errors="replace"),
                academic_year,
                term,
                sheet_url,
            )
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _discover_sheets(self):
        """Return ``[((start, end), term, sheet_url, export_url), ...]``."""
        resp = requests.get(SCHEDULES_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        out = []
        for a in soup.find_all("a", href=True):
            m = LINK_LABEL_RE.match(a.get_text(" ", strip=True))
            if not m:
                continue
            km = SHEET_KEY_RE.search(a["href"])
            if not km:
                continue
            year = int(m.group("year"))
            season = re.sub(r"\s+", " ", m.group("season").strip().lower())
            term = SEASON_TERM.get(season)
            if term is None:
                continue
            if term == "F":
                ay = (year, year + 1)
            else:
                # Spring + Summer/May term sit in the AY ending that year.
                ay = (year - 1, year)
            key_tuple = (ay, term, km.group("key"))
            if key_tuple in seen:
                continue
            seen.add(key_tuple)
            sheet_url = a["href"]
            out.append(
                (ay, term, sheet_url, EXPORT_URL.format(key=km.group("key")))
            )
        return out

    def _parse_csv(self, text, academic_year, term, url):
        reader = csv.reader(io.StringIO(text))
        rows = []
        headers = None
        for raw in reader:
            cells = [c.strip() for c in raw]
            if not any(cells):
                headers = None  # blank row resets state
                continue
            lower = {c.lower() for c in cells if c}
            if HEADER_ROW.issubset(lower):
                headers = [c.lower() for c in cells]
                continue
            if headers is None:
                continue
            row = dict(zip(headers, cells))
            subject = row.get("subject", "").upper()
            if subject not in SUBJECTS:
                continue
            course_num = row.get("course #", "")
            if not course_num:
                continue
            course_name = next(
                (row[k] for k in TITLE_KEYS if row.get(k)), ""
            )
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=f"{subject} {course_num}",
                    section=row.get("section", ""),
                    course_name=course_name,
                    instructor=row.get("instructor", ""),
                    time=_meeting(row),
                    url=url,
                )
            )
        return rows


def _meeting(row):
    days = row.get("days", "")
    begin = row.get("begins", "")
    end = row.get("ends", "")
    parts = []
    if days:
        parts.append(days)
    if begin and end:
        parts.append(f"{begin}–{end}")
    elif begin:
        parts.append(begin)
    return " ".join(parts)
