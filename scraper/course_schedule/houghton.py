"""Houghton University course-schedule scraper.

Houghton publishes each semester's course offering as a PDF linked from
the registrar's "Course Offerings" page. There is no live catalog and no
HTML schedule — the PDFs are the source of truth.

The registrar page (``INDEX_URL``) lists one PDF per term; the filename
encodes the year + term, e.g.::

    2025-Fall-Undergraduate-Course-Offering-Houghton-University-2025.09.26.pdf
    2026-Spring-Undergraduate-Course-Offering-Houghton-University-2026.01.14.pdf

Only undergraduate PDFs are scraped (graduate/SOM offerings are a separate
listing). Each PDF is a fixed-column layout with these columns (left to
right by x-coordinate):

    Gen Ed | LA | Course ID | Section | Course Title | Credits | Meeting
    Type | Days | Start Time | End Time | Start Date | End Date |
    Instructors | Building | Room

We extract every word with its x position via ``pdfplumber``, assign each
to a column by its x-center, then assemble per-line rows. The site only
exposes the current ~1 academic year of PDFs, so this captures whatever
PDFs are currently linked rather than iterating a fixed history.
"""

from __future__ import annotations

import io
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

INDEX_URL = (
    "https://www.houghton.edu/current-students/registrar/"
    "houghton-ny-undergraduate-students/course-offerings/"
)

# Column boundaries (in PDF user-space units) for the Houghton PDF layout.
# Each word is assigned to a column by where its horizontal center falls,
# which avoids the off-by-one issues that hit a strict left-edge boundary
# (some rows place "ONL" at x0=866, others at x0=867; centers always fall
# above 867 so building/instructor split cleanly).
COL_BOUNDS = [
    ("course",   95,   155),
    ("section",  155,  193),
    ("title",    193,  398),
    ("credits",  398,  406),
    ("mtype",    406,  484),
    ("days",     484,  520),
    ("start_t",  520,  582),
    ("end_t",    582,  636),
    ("start_d",  636,  699),
    ("end_d",    699,  757),
    ("instr",    757,  860),
    ("bldg",     860,  920),
    ("room",     920,  9999),
]

# Maps a PDF-filename term keyword to our internal term code.
# Houghton's Mayterm is a short intensive between Spring and Summer; we
# bucket it as "W" (the closest analog to a J-term-style mini-semester).
FILENAME_TERM_MAP = [
    ("Mayterm", "W"),
    ("Fall",    "F"),
    ("Spring",  "S"),
    ("Summer",  "Su"),
    ("Winter",  "W"),
]

# Only scrape undergraduate course PDFs; the same page links graduate and
# SOM (School of Music) offerings that we don't care about.
UNDERGRAD_RE = re.compile(r"Undergraduate-Course-Offering", re.I)

# Filename pattern: leading "YYYY-<Term>-..." (the leading year is the
# calendar year the term begins in, not the academic year). Houghton's
# Spring/Mayterm/Summer PDFs are dated with the spring calendar year, so
# we map calendar-year -> academic-year per term.
FILENAME_PREFIX_RE = re.compile(
    r"/(?P<year>\d{4})-(?P<term>Fall|Spring|Mayterm|Summer|Winter)\b",
    re.I,
)

# Course-code prefixes to keep. Houghton's CS department lives under
# CSCI; data-science cross-listings are a separate code and are excluded
# (matches the per-college subject filtering used by other scrapers).
SUBJECTS = ("CSCI",)


def _col_for(x_center):
    for name, lo, hi in COL_BOUNDS:
        if lo <= x_center < hi:
            return name
    return None


def _parse_pdf(pdf_bytes):
    """Yield row dicts (keyed by column name) from a Houghton offering PDF.

    Words on the same baseline are grouped by their rounded `top`; words
    that wrap onto a second visual line (e.g. multi-instructor cells)
    are emitted as separate rows and filtered out later by the row-type
    classifier.
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            buckets: dict[int, list] = defaultdict(list)
            for w in page.extract_words(use_text_flow=False, keep_blank_chars=False):
                buckets[round(w["top"])].append(w)
            for y in sorted(buckets):
                ws = sorted(buckets[y], key=lambda w: w["x0"])
                cols: dict[str, list[str]] = defaultdict(list)
                for w in ws:
                    center = (w["x0"] + w["x1"]) / 2
                    c = _col_for(center)
                    if c:
                        cols[c].append(w["text"])
                yield {c: " ".join(v).strip() for c, v in cols.items()}


def _is_section_row(row):
    """A real course row has a course code AND at least one date column.

    (Subject headers populate only `course`/`section` with header text;
    continuation rows populate only days/time/instructor with no dates.)
    Some PDFs run the credits and meeting-type cells together — e.g.
    ``"4LEC"`` instead of ``"4 LEC"`` — so the date columns are the most
    reliable signal that this is a section row.
    """
    return bool(row.get("course")) and bool(row.get("start_d") or row.get("end_d"))


def _academic_year_for(year, term_code):
    """Map (calendar year in filename, term code) -> (start, end) AY.

    Fall N opens AY (N, N+1); every other term sits in AY (N-1, N).
    """
    if term_code == "F":
        return (year, year + 1)
    return (year - 1, year)


def _term_from_filename(href):
    m = FILENAME_PREFIX_RE.search(href)
    if not m:
        return None, None
    year = int(m.group("year"))
    word = m.group("term").lower()
    for keyword, code in FILENAME_TERM_MAP:
        if word == keyword.lower():
            return _academic_year_for(year, code), code
    return None, None


class HoughtonScraper(CourseScheduleScraper):
    college = College.HOUGHTON
    # We don't use Selenium — the index page is plain HTML and the PDFs are
    # fetched directly. `terms` is left empty so the base loop wouldn't fire
    # even if we accidentally called it; `scrape()` is fully overridden.
    fresh_driver_per_load = False
    terms = []

    request_timeout = 60

    def scrape(self):
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "Mozilla/5.0 (cs-lac course-schedule scraper)"}
        )

        resp = session.get(INDEX_URL, timeout=self.request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect unique (academic_year, term, url) triples — the index page
        # links multiple PDFs per term family (e.g. graduate + undergraduate
        # + online graduate) and we want just the undergraduate one per term.
        seen = set()
        pdfs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.lower().endswith(".pdf"):
                continue
            if not UNDERGRAD_RE.search(href):
                continue
            url = urljoin(INDEX_URL, href)
            ay, term = _term_from_filename(href)
            if ay is None or term is None:
                continue
            key = (ay, term)
            if key in seen:
                continue
            seen.add(key)
            pdfs.append((ay, term, url))

        # Oldest first so the progress log reads chronologically.
        pdfs.sort(key=lambda t: (t[0], {"F": 0, "W": 1, "S": 2, "Su": 3}.get(t[1], 9)))

        rows = []
        for ay, term, url in pdfs:
            label = f"{ay[0]}-{str(ay[1])[-2:]}/{term}"
            try:
                r = session.get(url, timeout=self.request_timeout)
                r.raise_for_status()
                page_rows = self._parse_pdf_rows(r.content, ay, term, url)
            except Exception as e:
                print(f"  [{label}] failed: {e}", flush=True)
                continue
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _parse_pdf_rows(self, pdf_bytes, academic_year, term, url):
        rows = []
        for raw in _parse_pdf(pdf_bytes):
            if not _is_section_row(raw):
                continue
            course_code = raw["course"]
            if not any(course_code.startswith(s) for s in SUBJECTS):
                continue
            time_text = self._format_time(raw.get("days"), raw.get("start_t"), raw.get("end_t"))
            location = self._format_location(raw.get("bldg"), raw.get("room"))
            if location:
                time_text = f"{time_text} ({location})" if time_text else f"({location})"
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=raw.get("section", ""),
                    course_name=raw.get("title", ""),
                    instructor=raw.get("instr", ""),
                    time=time_text,
                    url=url,
                )
            )
        return rows

    @staticmethod
    def _format_time(days, start, end):
        days = (days or "").strip()
        start = (start or "").strip()
        end = (end or "").strip()
        if start.upper() == "TBA" and end.upper() == "TBA":
            time_range = "TBA"
        elif start and end:
            time_range = f"{start} - {end}"
        else:
            time_range = start or end
        if days and time_range:
            return f"{days} {time_range}"
        return days or time_range

    @staticmethod
    def _format_location(building, room):
        building = (building or "").strip()
        room = (room or "").strip()
        if building.upper() == "ONL" or room.lower() == "online":
            return "Online"
        return " ".join(x for x in [building, room] if x)
