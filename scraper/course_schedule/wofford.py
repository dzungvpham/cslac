"""Wofford College course schedule scraper.

Wofford publishes one PDF per registration period at

    https://connect.wofford.edu/myWofford/registrar/courseSchedule/courseSchedules/courseSchedule{TERMCODE}.pdf

The Course Schedule page only links to the *current* term's PDF, but the
URL pattern is predictable: term codes look like ``YYYYMM`` where ``MM``
is the Wofford period — ``01`` Interim (January), ``02`` Spring, ``06``
Summer I, ``09`` Fall. The actual term label (e.g. ``"Spring 2026"``) is
on page 1 of every PDF, so we probe the regular semesters back ~5 years
and read the season+year from each PDF rather than trusting the code.

Each PDF lists every department under a single-line subject header
(``"COSC"``); rows look like

    9145 COSC 235A FYF Programming & Problem Solving 3 MWF 1130-1220 OLIN 213 24 21 3Christ, Beau Books

Columns: ``CRN  COSC  NUM<SECT>  [<flags>]  <title>  <cred>  <days
time room>  <max>  <enrolled>  <avail><instructor>  Books``. The avail
count is glued to the instructor's surname, the trailing word
``"Books"`` is always present, and ``<flags>`` is a sequence of short
tokens from a small known vocabulary (``Pre``, ``FYF``, ``IP``, ``Y``).
Independent-study sections drop days/time/room in favor of a single
``-`` placeholder.
"""

import re
import sys
from io import BytesIO
from pathlib import Path

import pdfplumber
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = (
    "https://connect.wofford.edu/myWofford/registrar/courseSchedule/"
    "courseSchedules/courseSchedule{code}.pdf"
)

# We only chase Fall (09) and Spring (02). Wofford's "Interim" (January, code
# 01) and Summer (code 06) terms rarely run CS sections and are skipped for
# parity with every other school's Fall/Spring scope.
TERM_PROBES = [("F", "09"), ("S", "02")]

TERM_LABEL_RE = re.compile(
    r"\b(?P<season>Fall|Spring)\s+(?P<year>20\d{2})\b", re.I
)
SEASON_TERM = {"fall": "F", "spring": "S"}

# Row anchor: `<CRN>  COSC  <NUM><SECT>  ...`
HEAD_RE = re.compile(
    r"^(?P<crn>\d{4,6})\s+COSC\s+(?P<num>\d+)(?P<section>[A-Z]\w*)\s+(?P<rest>.+)$"
)

# Trailing `<max>  <enrolled>  <avail><instructor>  Books`. The avail field
# can be negative. Newer PDFs (~ Fall 2024 onward) glue the avail count to
# the instructor's surname with no space (``"8Sykes, David"``,
# ``"-1Christ, Beau"``); older PDFs print them with a space
# (``"0 Garrett, Aaron"``). Accept either form.
TRAIL_RE = re.compile(
    r"\s+(?P<max>\d+)\s+(?P<enrolled>\d+)\s+(?P<avail>-?\d+)\s*"
    r"(?P<instructor>[A-Z][^\d]+?)\s+Books\s*$"
)

# Within the middle portion (after trail strip), find credits + meeting.
# Credits is a 1-digit number that immediately precedes either a day-code
# token (M/T/W/R/F mix) or the literal ``-`` placeholder for arranged
# sections.
CRED_RE = re.compile(
    r"\s+(?P<credits>\d+)\s+(?P<meeting>(?:[MTWRF]+(?:\s|$)|-).*)$"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class WoffordScraper(CourseScheduleScraper):
    college = College.WOFFORD
    terms = []  # discovery is per-year probing
    fresh_driver_per_load = False

    def scrape(self):
        rows = []
        for ay in self.past_academic_years(self.years_back):
            for term, mm in TERM_PROBES:
                # Term-code year is the calendar year the period falls in:
                # Fall (code 09) of AY 2025-26 → 202509; Spring (code 02) of
                # AY 2025-26 → 202602.
                year = ay[0] if term == "F" else ay[1]
                code = f"{year}{mm}"
                url = BASE_URL.format(code=code)
                label = f"{ay[0]}-{ay[1] % 100:02d}/{term}"
                try:
                    resp = requests.get(url, timeout=60)
                except requests.RequestException as e:
                    print(f"  [{label}] download failed: {e}", flush=True)
                    continue
                if resp.status_code == 404:
                    continue
                if resp.status_code != 200:
                    print(f"  [{label}] HTTP {resp.status_code}", flush=True)
                    continue
                try:
                    with pdfplumber.open(BytesIO(resp.content)) as pdf:
                        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                except Exception as e:
                    print(f"  [{label}] pdf parse failed: {e}", flush=True)
                    continue
                # Verify the PDF's printed term label matches what we asked
                # for; if Wofford reuses a code for a different term, skip.
                if not self._term_matches(text, term, year):
                    print(f"  [{label}] PDF term label mismatch, skipping", flush=True)
                    continue
                page_rows = self._parse_cs_section(text, ay, term, url)
                print(f"  [{label}] {len(page_rows)} sections", flush=True)
                rows.extend(page_rows)
        return rows

    @staticmethod
    def _term_matches(text, term, year):
        m = TERM_LABEL_RE.search(text)
        if not m:
            return False
        season = m.group("season").lower()
        return SEASON_TERM.get(season) == term and int(m.group("year")) == year

    def _parse_cs_section(self, text, academic_year, term, url):
        lines = text.splitlines()
        rows = []
        in_cosc = False
        for raw in lines:
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped == "COSC":
                in_cosc = True
                continue
            if in_cosc and re.match(r"^[A-Z]{2,5}$", stripped) and stripped != "COSC":
                # Next department's subject header.
                break
            if not in_cosc:
                continue
            row = self._parse_row(stripped, academic_year, term, url)
            if row is not None:
                rows.append(row)
        return rows

    def _parse_row(self, line, academic_year, term, url):
        head_m = HEAD_RE.match(line)
        if not head_m:
            return None
        rest = head_m.group("rest")
        trail_m = TRAIL_RE.search(rest)
        if not trail_m:
            return None
        middle = rest[: trail_m.start()]
        cred_m = CRED_RE.search(middle)
        if not cred_m:
            return None
        title = _clean(self._strip_flags(middle[: cred_m.start()]))
        meeting = _clean(cred_m.group("meeting"))
        instructor = _clean(trail_m.group("instructor"))
        return self.make_row(
            academic_year,
            term,
            course_code=f"COSC {head_m.group('num')}",
            section=head_m.group("section"),
            course_name=title,
            instructor=instructor,
            time=meeting,
            url=url,
        )

    @staticmethod
    def _strip_flags(title):
        """Drop leading short-flag tokens (``Pre``, ``FYF``, ``IP``, ``Y``).

        These appear as a prefix on the title — e.g. ``"Pre FYF Modeling &
        Simulation"`` — and aren't really part of the course name. Keep
        going until we hit a token that doesn't look like a flag.
        """
        tokens = title.split()
        flags = {"Pre", "FYF", "IP", "Y"}
        while tokens and tokens[0] in flags:
            tokens.pop(0)
        return " ".join(tokens)
