"""Knox College course schedule scraper.

Knox publishes one PDF per term at

    https://www.knox.edu/documents/Registrar/CourseSchedules/
        courseschedule{FA|WI|SP}{YY}.pdf

Knox runs on a trimester calendar (Fall, Winter, Spring) so each
academic year produces three PDFs.

Each PDF is a single-column listing. CS rows look like

    CS 141-1 INTRO TO COMPUTER SCIENCE 1.0 QR R.Bose 5 MWF SMC A201
    CS 141L-A Laboratory .0 --- R.Bose 5 Th SMC E016

with the form

    CS {num}-{section} {title} {credits} {element} {faculty} {period} {days} {bldg} {room}

We extract code/section/title/instructor/period+days; the room is
dropped (`time` already has the meeting info via period + days).

A multi-instructor course adds a continuation line that's just a
faculty name (e.g. `J.Spacco` on the line below). Cross-reference
lines (`CS 195B See description of STAT 195B.`) and prose
description-continuation lines lack the `-section` marker and are
ignored.

Some terms haven't been posted yet — those URLs return HTTP 404 and
the scraper reports them as "not available".
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

URL_TEMPLATE = (
    "https://www.knox.edu/documents/Registrar/CourseSchedules/"
    "courseschedule{code}.pdf"
)

LINE_RE = re.compile(
    r"^CS\s+(?P<num>\d+[A-Z]*)-(?P<section>\w+)\s+"
    r"(?P<title>.+?)\s+"
    r"(?P<credits>\d*\.\d+)\s+"
    r"(?P<rest>.+)$"
)

# A bare-faculty continuation line like "J.Spacco" or "J.McCarthy Foubert".
FACULTY_RE = re.compile(r"^[A-Z][A-Za-z]*\.[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*$")

DAY_TOK_RE = re.compile(r"^[MTWRFSU][MTWRFSUhu]*$")


class KnoxScraper(CourseScheduleScraper):
    college = College.KNOX
    terms = ["F", "W", "S"]

    def _term_code(self, academic_year, term):
        start, end = academic_year
        if term == "F":
            return f"FA{start % 100:02d}"
        if term == "W":
            return f"WI{end % 100:02d}"
        if term == "S":
            return f"SP{end % 100:02d}"
        raise ValueError(f"unsupported term: {term!r}")

    def url_for(self, academic_year, term):
        return URL_TEMPLATE.format(code=self._term_code(academic_year, term))

    def fetch_page(self, academic_year, term):
        url = self.url_for(academic_year, term)
        try:
            resp = requests.get(url, timeout=60)
        except requests.RequestException:
            return None
        if resp.status_code != 200:
            return None
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    def parse_page(self, text, academic_year, term):
        rows = []
        # Bare-faculty continuation lines (e.g. `J.Spacco` under a CS row
        # with two instructors) look like normal faculty references that
        # also appear in other departments' sections later in the PDF, so
        # we only honor them while we're still inside the CS section --
        # tracked via this flag, which flips back off as soon as we hit a
        # line that's neither a CS row nor a continuation faculty line.
        in_cs_row = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            m = LINE_RE.match(line)
            if m:
                row = _build_row(
                    self,
                    academic_year,
                    term,
                    m.group("num"),
                    m.group("section"),
                    m.group("title"),
                    m.group("rest"),
                )
                if row is not None:
                    rows.append(row)
                in_cs_row = True
                continue
            if in_cs_row and rows and FACULTY_RE.match(line):
                rows[-1]["instructor"] = _join_instructors(
                    rows[-1]["instructor"], line
                )
                continue
            in_cs_row = False
        return rows


def _build_row(scraper, academic_year, term, num, section, title, rest):
    instructor, period_days = _parse_after_credits(rest)
    return scraper.make_row(
        academic_year,
        term,
        course_code=f"CS {num}",
        section=section,
        course_name=_clean(title),
        instructor=instructor,
        time=period_days,
    )


def _parse_after_credits(rest):
    """`rest` is everything after credits — `ELEMENT FACULTY PERIOD [pm]
    DAYS BLDG ROOM ...`. Return (faculty, "Period N days...")."""
    tokens = rest.split()
    if not tokens:
        return "", ""
    # tokens[0] is the element marker (`---`, `—-`, `QR`, `SA,QR`, ...);
    # faculty starts at index 1.
    i = 1
    period_idx = None
    for j in range(i, len(tokens)):
        # Period token starts with a digit but isn't a credits-style decimal
        # (which the line regex already consumed). Real-world period tokens
        # we've seen: `5`, `3,4`, `4-5`, `12-12:50`, `2s`.
        if tokens[j][:1].isdigit() and not re.match(r"^\d+\.\d+$", tokens[j]):
            period_idx = j
            break
    if period_idx is None:
        return _clean(" ".join(tokens[i:])), ""
    faculty = _clean(" ".join(tokens[i:period_idx]))
    period_end = period_idx + 1
    if period_end < len(tokens) and tokens[period_end].lower() == "pm":
        period_end += 1
    period = " ".join(tokens[period_idx:period_end])
    day_end = period_end
    while day_end < len(tokens) and DAY_TOK_RE.match(tokens[day_end]):
        day_end += 1
    days = " ".join(tokens[period_end:day_end])
    return faculty, _clean(f"Period {period} {days}".strip())


def _join_instructors(existing, addition):
    if not existing:
        return addition
    if addition in existing.split("; "):
        return existing
    return f"{existing}; {addition}"


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
