"""Hobart and William Smith course schedule scraper.

The registrar publishes the current Fall and Spring schedules as PDFs at

    https://www.hws.edu/images/offices/registrar/docs/FallSchedule.pdf
    https://www.hws.edu/images/offices/registrar/docs/SpringSchedule.pdf

Each PDF holds every department's listings for that term; the Computer
Science (CPSC) section is bracketed by lines that read

    Hobart and William Smith - Subject: Computer Science
    ...
    Hobart and William Smith - Subject: <next dept>

Within the CPSC block, each section appears on a fixed-column row:

    MAX COURSE       CRED DAYS  TIME                  BLDG ROOM INSTR
    28  CPSC- 124-01 1    F     01:10 PM - 02:10 PM   TBA  TBA  Herman,Bridger
    28  CPSC- 045-01 0.5  TBA   TBA                   TBA       Staff

When fields are unknown, HWS prints a literal `TBA` in each column; the
"TBA TBA TBA Staff" form (no time range, no location, just instructor)
is parsed as a TBA meeting. Continuation rows for a multi-meeting
section repeat days/time/loc/instr without the leading MAX/COURSE/CRED
fields and are folded into the prior row's `time`. Prerequisite /
antirequisite notes look like prose and are skipped.

HWS exposes only the current term per PDF — there is no historical
archive — so this scraper produces two rows per year (current Fall +
current Spring) inferred from the "Schedule of Classes for {Season}
{Year}" header on page 1 of each PDF.
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

FALL_URL = "https://www.hws.edu/images/offices/registrar/docs/FallSchedule.pdf"
SPRING_URL = "https://www.hws.edu/images/offices/registrar/docs/SpringSchedule.pdf"
SUBJECT = "CPSC"
SUBJECT_HEADER = "Subject: Computer Science"

HEADER_KEYWORDS = (
    "Report ID:",
    "Name : Worksheet",
    "Schedule of Classes for",
    "Regular Academic Run Time",
)

TERM_HEADER_RE = re.compile(
    r"Schedule of Classes for\s+(?P<season>Fall|Spring)\s+(?P<year>\d{4})", re.I
)

# A primary row: `MAX CPSC- NUM-SECT <title> <credits> <trailing>`.
MAIN_RE = re.compile(
    r"^(?P<max>\d+)\s+CPSC-\s*(?P<num>\d+\w*)-(?P<section>\w+)\s+"
    r"(?P<rest>.+)$"
)

# Time range like "01:10 PM - 02:40 PM" or the literal "TBA". We scan for
# this from the end of the trailing portion to split off the meeting time.
TIME_RE = re.compile(
    r"(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM)\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM)|TBA)"
)

# Continuation meeting: `<days> <time> <bldg> <room> <instr>` (no leading
# MAX/COURSE/CRED). The trailing instructor token contains a comma
# ("Last,First") or is the literal "Staff".
CONT_RE = re.compile(
    r"^(?P<days>[A-Z][A-Za-z]*|TBA)\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM)\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM)|TBA)\s+"
    r"(?P<rest>.+)$"
)

# Free-form notes that follow a section and don't represent meetings.
NOTE_PREFIXES = (
    "Seek Permission",
    "Prerequisite",
    "Antirequisite",
    "Corequisite",
    "Open to ",
    "Note:",
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _looks_like_note(line):
    s = line.strip()
    if not s:
        return True
    if any(s.startswith(p) for p in NOTE_PREFIXES):
        return True
    # Continuation of a prior note (lowercase start) — no leading digit /
    # course-code / day code.
    if s[0].islower():
        return True
    return False


def _parse_credits_and_trailing(rest):
    """Split `rest` into (title, credits, trailing).

    `rest` looks like ``"Coding in Python 1 TuTh 01:10 PM - 02:40 PM TBA TBA Herman,Bridger"``.
    Credits is the first whole-or-decimal numeric token after the title;
    everything after it is the trailing `<days> <time> <bldg> <room> <instr>`
    block.
    """
    # Walk tokens and pick the first numeric one as credits.
    tokens = rest.split()
    for i, tok in enumerate(tokens):
        if re.match(r"^\d+(?:\.\d+)?$", tok) and i > 0:
            title = " ".join(tokens[:i])
            credits = tok
            trailing = " ".join(tokens[i + 1:])
            return title, credits, trailing
    return rest, "", ""


def _parse_trailing(trailing):
    """Return (days, time, instructor) parsed from the trailing block."""
    s = _clean(trailing)
    if not s:
        return "", "", ""
    m = TIME_RE.search(s)
    if not m:
        # No recognizable time — treat whole string as TBA + instructor.
        return "TBA", "", _clean(s)
    pre = _clean(s[: m.start()])
    days = pre
    time_str = _clean(m.group("time"))
    tail = _clean(s[m.end():])
    # Tail is `<bldg> <room> <instr>`; instructor is the last token
    # containing a comma or matching the literal `Staff`. We don't try to
    # split bldg/room — HWS frequently leaves them both `TBA`, and our
    # output schema only carries `time` + `instructor`.
    instructor = _extract_instructor(tail)
    return days, time_str, instructor


def _extract_instructor(tail):
    """Find the instructor name at the end of `tail`.

    Names look like ``"Herman,Bridger"`` or ``"Bridgeman,Stina S"``; the
    literal ``"Staff"`` is also valid. We scan from the right for the
    first ``Last,First`` token and include any trailing initials.
    """
    if not tail:
        return ""
    tokens = tail.split()
    # Find the right-most token containing a comma.
    for i in range(len(tokens) - 1, -1, -1):
        if "," in tokens[i]:
            return " ".join(tokens[i:])
    # No comma found — fall back to the last token (handles "Staff").
    return tokens[-1]


class HobartWilliamSmithScraper(CourseScheduleScraper):
    college = College.HOBART_AND_WILLIAM_SMITH
    terms = []  # discovery comes from the PDFs themselves
    fresh_driver_per_load = False

    def scrape(self):
        rows = []
        for season, url in (("F", FALL_URL), ("S", SPRING_URL)):
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{season}] download failed: {e}", flush=True)
                continue
            try:
                with pdfplumber.open(BytesIO(resp.content)) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            except Exception as e:
                print(f"  [{season}] pdf parse failed: {e}", flush=True)
                continue
            academic_year = self._infer_year(text, season)
            if academic_year is None:
                print(f"  [{season}] could not infer term year", flush=True)
                continue
            page_rows = self._parse_cs_section(text, academic_year, season, url)
            label = f"{academic_year[0]}-{academic_year[1] % 100:02d}/{season}"
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    @staticmethod
    def _infer_year(text, term):
        m = TERM_HEADER_RE.search(text)
        if not m:
            return None
        year = int(m.group("year"))
        season = m.group("season").lower()
        if season == "fall" and term == "F":
            return (year, year + 1)
        if season == "spring" and term == "S":
            return (year - 1, year)
        return None

    def _parse_cs_section(self, text, academic_year, term, url):
        rows = []
        last_row = None
        in_cs = False
        for raw in text.splitlines():
            ln = raw
            if any(k in ln for k in HEADER_KEYWORDS):
                continue
            # Strip column header / dashes lines.
            stripped = ln.strip()
            if stripped.startswith("MAX COURSE") or (stripped and set(stripped) <= set("- ")):
                continue
            if SUBJECT_HEADER in ln:
                in_cs = True
                continue
            if in_cs and "Subject:" in ln:
                break
            if not in_cs or not stripped:
                continue

            m = MAIN_RE.match(stripped)
            if m:
                title, credits, trailing = _parse_credits_and_trailing(m.group("rest"))
                days, time_str, instructor = _parse_trailing(trailing)
                meeting = _clean(f"{days} {time_str}".strip())
                row = self.make_row(
                    academic_year,
                    term,
                    course_code=f"CPSC {m.group('num')}",
                    section=m.group("section"),
                    course_name=_clean(title),
                    instructor=instructor,
                    time=meeting,
                    url=url,
                )
                rows.append(row)
                last_row = row
                continue

            cont_m = CONT_RE.match(stripped)
            if cont_m and last_row is not None and not _looks_like_note(stripped):
                extra_days = _clean(cont_m.group("days"))
                extra_time = _clean(cont_m.group("time"))
                extra = f"{extra_days} {extra_time}".strip()
                if extra:
                    last_row["time"] = f"{last_row['time']} / {extra}".strip(" /")
                continue

            # Otherwise: prose note — skip.
        return rows
