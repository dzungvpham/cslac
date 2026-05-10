"""Bowdoin College course schedule scraper.

Bowdoin publishes one PDF per semester from their registrar index:

    https://www.bowdoin.edu/registrar/course-information/index.html

We scrape the index for `sched-f{YY}.pdf` / `sched-s{YY}.pdf` links (skipping
`reg-sched-...` registration snapshots and supplemental enrollment PDFs),
download each PDF, and pull out CSCI rows.

Two on-page formats coexist:

  * Old (Spring 2025 and earlier): per-department tables with columns
    ``CRN | Class | Cross-Listings | Course Title | Div-Distrib |
    Instructor(s) | Meeting Times | Location``. The Class cell is laid
    out like ``CSCI\\n2101A`` — subject + number with an optional alpha
    section suffix.

  * New (Fall 2025 and later): one big sortable table with columns
    ``Course Section | Course Section Title | [Description] | Meeting
    Patterns | Location[s] | Instructors | Course Tags | Public Notes``.
    The Course Section cell is ``"CSCI 2350-0/ DCS 2350-0 - Social and
    Economic Networks"`` — primary code + cross-listings + " - " title;
    each cross-listing yields a duplicate row, so we keep only the
    primary code's row for each section.

Tables routinely span multiple PDF pages — continuation pages have no
header row, so we remember the most recently seen header to keep parsing.
"""

import io
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

INDEX_URL = "https://www.bowdoin.edu/registrar/course-information/index.html"

# Match the "main" semester schedule PDFs only. The negative lookbehind
# rules out `reg-sched-...` (registration snapshots, same data) and the
# `s24-schedule-with-enrollments.pdf` supplemental.
SCHED_PDF_RE = re.compile(r"(?<!reg-)sched-([fs])(\d{2})\.pdf", re.IGNORECASE)
# Newer PDFs use a freer name like `2026-spring-schedule-of-course-offerings-v2.pdf`.
DATED_PDF_RE = re.compile(
    r"(?P<year>\d{4})-(?P<season>spring|fall|summer|winter)-schedule",
    re.IGNORECASE,
)

# Old-format Class cell, e.g. "CSCI 2101A", "CSCI 2330", "CHEM 1102L1".
OLD_CLASS_RE = re.compile(r"^([A-Z]+)\s+(\d+)(\w*)$")
# New-format primary section, e.g. "CSCI 1101-A", "CSCI 1101-LC1", "CSCI 2350-0".
NEW_CODE_RE = re.compile(r"^([A-Z]+)\s+(\d+)-(\w+)$")

SUBJECT = "CSCI"


class BowdoinScraper(CourseScheduleScraper):
    college = College.BOWDOIN
    terms = ["F", "S"]
    # Plain HTTP — no Selenium needed.
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._session = None
        self._url_map = None

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers["User-Agent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        return self._session

    def _load_url_map(self):
        if self._url_map is not None:
            return
        r = self.session.get(INDEX_URL, timeout=self.page_load_timeout)
        r.raise_for_status()
        url_map = {}
        for href in re.findall(r'href="([^"]+\.pdf)"', r.text, re.IGNORECASE):
            key = _term_from_href(href)
            if key is None:
                continue
            # First occurrence wins; the index lists the canonical schedule
            # before any later supplemental copies.
            url_map.setdefault(key, urljoin(INDEX_URL, href))
        self._url_map = url_map

    def url_for(self, academic_year, term):
        self._load_url_map()
        return self._url_map.get((academic_year, term))

    def fetch_page(self, academic_year, term):
        url = self.url_for(academic_year, term)
        if url is None:
            return None
        r = self.session.get(url, timeout=self.page_load_timeout)
        r.raise_for_status()
        return r.content

    def parse_page(self, pdf_bytes, academic_year, term):
        rows = []
        seen_keys = set()
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            fmt = None
            cols = None
            for page in pdf.pages:
                for tbl in page.extract_tables() or []:
                    if not tbl:
                        continue
                    new_fmt, new_cols, data = _classify_table(tbl)
                    if new_fmt is not None:
                        fmt = new_fmt
                        cols = new_cols
                    if fmt is None:
                        continue
                    for raw in data:
                        parsed = (
                            _parse_old_row(raw)
                            if fmt == "old"
                            else _parse_new_row(raw, cols)
                        )
                        if parsed is None:
                            continue
                        # New-format cross-listings produce duplicate rows
                        # (one per cross-listed subject); dedupe on the
                        # primary code+section so we keep only the CSCI row.
                        key = (parsed["course_code"], parsed["section"])
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        rows.append(
                            self.make_row(
                                academic_year,
                                term,
                                **parsed,
                            )
                        )
        return rows


# ---- header / format detection -------------------------------------------


def _classify_table(tbl):
    """Inspect `tbl[0]` and return `(fmt, cols, data_rows)`.

    `fmt` is `"old"`, `"new"`, or `None` (continuation table — caller
    keeps the previously detected format). `cols` is the list of column
    header strings from the matched header row, or `None`.
    """
    header = [(c or "").strip() for c in tbl[0]]
    h0 = header[0] if header else ""
    if h0 == "Course Section":
        return "new", header, tbl[1:]
    if h0 == "CRN":
        return "old", header, tbl[1:]
    return None, None, tbl


# ---- row parsers ---------------------------------------------------------


def _parse_old_row(row):
    """Old-format row -> course fields, or `None` to skip."""
    if len(row) < 7:
        return None
    cls = _flat(row[1])
    m = OLD_CLASS_RE.match(cls)
    if not m or m.group(1) != SUBJECT:
        return None
    course_code = f"{m.group(1)} {m.group(2)}"
    section = m.group(3)
    course_name = _clean(row[3])
    instructor = _clean(row[5])
    meeting = _clean(row[6])
    location = _clean(row[7]) if len(row) > 7 else ""
    time_text = ", ".join(p for p in (meeting, location) if p)
    return {
        "course_code": course_code,
        "section": section,
        "course_name": course_name,
        "instructor": instructor,
        "time": time_text,
    }


def _parse_new_row(row, cols):
    """New-format row -> course fields, or `None` to skip."""
    by_name = _by_name(row, cols)
    course_section = _flat(by_name.get("Course Section", ""))
    if not course_section:
        return None
    # "CSCI 2350-0/ DCS 2350-0 - Social and Economic Networks"
    primary, _, fallback_title = course_section.partition(" - ")
    primary_first = primary.split("/")[0].strip()
    m = NEW_CODE_RE.match(primary_first)
    if not m or m.group(1) != SUBJECT:
        return None
    course_code = f"{m.group(1)} {m.group(2)}"
    section = m.group(3)
    course_name = _clean(by_name.get("Course Section Title", "")) or _clean(fallback_title)
    instructor = _join_lines(by_name.get("Instructors", ""))
    meeting = _clean(by_name.get("Meeting Patterns", ""))
    location = _clean(by_name.get("Location", "") or by_name.get("Locations", ""))
    time_text = ", ".join(p for p in (meeting, location) if p)
    return {
        "course_code": course_code,
        "section": section,
        "course_name": course_name,
        "instructor": instructor,
        "time": time_text,
    }


# ---- index parsing -------------------------------------------------------


def _term_from_href(href):
    """`'pdf-schedules/fall-semesters/sched-f25.pdf'` -> `((2025, 2026), 'F')`.

    Returns `None` if the href isn't a recognized per-semester schedule PDF.
    """
    m = SCHED_PDF_RE.search(href)
    if m:
        season = m.group(1).lower()
        year = 2000 + int(m.group(2))
        if season == "f":
            return (year, year + 1), "F"
        return (year - 1, year), "S"
    m = DATED_PDF_RE.search(href)
    if m:
        year = int(m.group("year"))
        season = m.group("season").lower()
        if season == "fall":
            return (year, year + 1), "F"
        if season == "spring":
            return (year - 1, year), "S"
    return None


# ---- helpers -------------------------------------------------------------


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _flat(text):
    """Like `_clean`, but specifically for cells where line breaks split a
    single logical token (e.g. ``CSCI\\n2101A`` -> ``CSCI 2101A``)."""
    return _clean(text)


def _join_lines(text):
    """Multi-instructor cells use ``\\n`` to separate names. Join with `, `
    so the result fits on one CSV line without losing the boundary."""
    if not text:
        return ""
    parts = [_clean(p) for p in text.split("\n")]
    return ", ".join(p for p in parts if p)


def _by_name(row, cols):
    return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}
