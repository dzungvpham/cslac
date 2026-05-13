"""Coe College course schedule scraper.

The registrar publishes one PDF per term at
``https://www.coe.edu/academics/academic-resources/registrar/schedules`` —
the page has a list of links labelled e.g. "Courses - Fall 2025" or
"Courses - Spring 2026". Each PDF has the full schedule for the term,
organized by department; the Computer Science section starts at a
standalone "Computer Science" heading and ends at the next department
heading.

Rows look like

    CS 125 01 Introduction to Programming Staff MWF 10:00 AM 10:50 AM Stuart Hall 1.00
    Staff R 12:30 PM 01:50 PM Stuart Hall

The first line is a section; the second is an additional meeting time
for that section (no credits column, just instructor / days / start / end
/ location). Continuation lines are folded into the prior row's `time`.
"""

import re
import sys
from io import BytesIO
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

INDEX_URL = "https://www.coe.edu/academics/academic-resources/registrar/schedules"

# Link labels look like "Courses - Fall 2025", "Courses - Spring 2026",
# "Courses - May Term 2026". Final-exam PDFs use "Final Exam Schedule"
# and are skipped.
LABEL_RE = re.compile(
    r"^Courses\s*-\s*(?P<season>Fall|Spring|May Term|Summer|Winter|J[\s-]?Term)\s+(?P<year>\d{4})\s*$",
    re.I,
)

SEASON_TERM = {
    "fall": "F",
    "spring": "S",
    "may term": "W",  # Coe's May Term is a 3-week block; treat as Winter for sort order
    "summer": "Su",
    "winter": "W",
    "jterm": "W",
    "j term": "W",
    "j-term": "W",
}

# Row tail: days, start, end, location, credits (credits may be ".00")
TAIL_RE = re.compile(
    r"\s+(?P<days>[MTWRFSU]+|TBA|ARR)\s+"
    r"(?P<start>\d{1,2}:\d{2}\s*[AP]M)\s+"
    r"(?P<end>\d{1,2}:\d{2}\s*[AP]M)\s+"
    r"(?P<location>.+?)\s+"
    r"(?P<credits>\d*\.\d{2})\s*$"
)
# Continuation line: instructor days start end location (no credits)
CONT_RE = re.compile(
    r"^(?P<instructor>.+?)\s+"
    r"(?P<days>[MTWRFSU]+|TBA|ARR)\s+"
    r"(?P<start>\d{1,2}:\d{2}\s*[AP]M)\s+"
    r"(?P<end>\d{1,2}:\d{2}\s*[AP]M)\s+"
    r"(?P<location>.+?)\s*$"
)
HEAD_RE = re.compile(r"^CS\s+(?P<num>\d+\w*)\s+(?P<section>\w+)\s+(?P<rest>.+)$")
# Instructor is the trailing 1-2 tokens of `rest`. Single token = "Staff" or
# a last name; two tokens = "<initial> <last name>" (e.g. "S Hughes").
INSTRUCTOR_TAIL_RE = re.compile(
    r"^(?P<title>.+?)\s+(?P<instructor>(?:[A-Z]\.?\s+)?[A-Z][A-Za-z'\-]+|Staff)$"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _format_time(days, start, end):
    days = _clean(days)
    start = _clean(start)
    end = _clean(end)
    return f"{days} {start}-{end}".strip()


class CoeScraper(CourseScheduleScraper):
    college = College.COE
    # Discovery via the index page; the base loop is irrelevant.
    terms = []
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._index = None  # list of (academic_year, term, pdf_url)

    def _discover(self):
        if self._index is not None:
            return self._index
        resp = requests.get(INDEX_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        out = []
        for a in soup.find_all("a", href=True):
            label = _clean(a.get_text(" ", strip=True))
            m = LABEL_RE.match(label)
            if not m:
                continue
            season = m.group("season").lower()
            term = SEASON_TERM.get(re.sub(r"\s+", " ", season))
            if not term:
                continue
            year = int(m.group("year"))
            if season == "fall":
                ay = (year, year + 1)
            else:
                ay = (year - 1, year)
            out.append((ay, term, a["href"]))
        # Stable ordering: oldest first by (academic_year, term).
        out.sort(key=lambda r: (r[0], {"F": 0, "W": 1, "S": 2, "Su": 3}.get(r[1], 9)))
        self._index = out
        return out

    def scrape(self):
        rows = []
        for ay, term, url in self._discover():
            label = f"{ay[0]}-{ay[1] % 100:02d}/{term}"
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{label}] download failed: {e}", flush=True)
                continue
            try:
                with pdfplumber.open(BytesIO(resp.content)) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            except Exception as e:
                print(f"  [{label}] pdf parse failed: {e}", flush=True)
                continue
            page_rows = self._parse_cs_section(text, ay, term, url)
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _parse_cs_section(self, text, academic_year, term, url):
        lines = text.splitlines()
        # CS appears as a standalone "Computer Science" line; the next
        # standalone short heading (not starting with "CS ") ends the section.
        rows = []
        in_cs = False
        last_row = None
        for ln in lines:
            stripped = ln.strip()
            if stripped == "Computer Science":
                in_cs = True
                continue
            if not in_cs:
                continue
            if not stripped:
                continue

            head_m = HEAD_RE.match(stripped)
            if head_m:
                row = self._parse_section_row(head_m, academic_year, term, url)
                if row is not None:
                    rows.append(row)
                    last_row = row
                continue

            # Continuation line: same section, extra meeting time.
            cont_m = CONT_RE.match(stripped)
            if cont_m and last_row is not None:
                extra = _format_time(
                    cont_m.group("days"),
                    cont_m.group("start"),
                    cont_m.group("end"),
                )
                last_row["time"] = f"{last_row['time']} / {extra}".strip(" /")
                continue

            # Anything else: we've left the CS section.
            break

        return rows

    def _parse_section_row(self, head_m, academic_year, term, url):
        num = head_m.group("num")
        section = head_m.group("section")
        rest = head_m.group("rest")
        tail_m = TAIL_RE.search(rest)
        if not tail_m:
            return None
        head_part = rest[: tail_m.start()].rstrip()
        instr_m = INSTRUCTOR_TAIL_RE.match(head_part)
        if instr_m:
            course_name = _clean(instr_m.group("title"))
            instructor = _clean(instr_m.group("instructor"))
        else:
            course_name = _clean(head_part)
            instructor = ""
        time_str = _format_time(
            tail_m.group("days"),
            tail_m.group("start"),
            tail_m.group("end"),
        )
        return self.make_row(
            academic_year,
            term,
            course_code=f"CS {num}",
            section=section,
            course_name=course_name,
            instructor=instructor,
            time=time_str,
            url=url,
        )
