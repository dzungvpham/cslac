"""College of the Holy Cross course schedule scraper.

Holy Cross publishes one PDF per term, linked from

    https://www.holycross.edu/about-holy-cross/offices-services/registrar/schedule-of-classes/

The link text encodes the term (e.g. "Fall 2025 Course Schedule",
"Spring 2026 Schedule of Classes"); the URL slug is inconsistent
(`/document/fall-2025-course-schedule` vs
`/document/spring-2026-schedule-of-classes`) but the registrar page
keeps the current handful of terms linked, so we just follow whatever
links it lists. Older terms are removed when new ones go up.

The PDF lays each department out with this shape::

    CSCI - Computer Science
    CSCI - 131 - Techniques of Programming  Common Requirement Met: MATH  Units: 1.25
    1262   01    LEC          TR  09:30 AM  10:45 AM  21  P  Lammert,Adam C.
    1266   10A   LAB SWORD219  W  08:00 AM  09:55 AM  18  P  Lammert,Adam C.
    Prerequisite: CSCI 131 or equivalent.   ← free-text annotation, skip

Each section line is ``<schedule_no> <section> <type> [<room>] <days>
<begin> <end> <cap> <mode> <instructor>``. Room is glued to the type
token only when present (LAB sections meet in a room, LECs usually
don't). Comments such as "Prerequisite: …", "Department Consent
Required" appear between course headers and section rows and are
ignored.
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

REGISTRAR_URL = (
    "https://www.holycross.edu/about-holy-cross/offices-services/registrar/schedule-of-classes/"
)
BASE = "https://www.holycross.edu"

LINK_LABEL_RE = re.compile(
    r"^(?P<season>Fall|Spring|Summer)\s+(?P<year>\d{4})\s+"
    r"(?:Course\s+Schedule|Schedule\s+of\s+Classes)\s*$",
    re.I,
)
SEASON_TERM = {"fall": "F", "spring": "S", "summer": "Su"}

# Department header e.g. `"CSCI - Computer Science"` (subject + "-" + name,
# *no* third dash, *no* "Units:"). Course headers always carry "Units:".
DEPT_RE = re.compile(r"^([A-Z]{2,5})\s*-\s*[A-Za-z][^-]*$")

# Course header. Title can contain anything up to "Common Requirement Met:"
# or "Units:".
COURSE_RE = re.compile(
    r"^(?P<subject>[A-Z]{2,5})\s*-\s*(?P<num>\d+\w*)\s*-\s*"
    r"(?P<title>.+?)\s+(?:Common\s+Requirement\s+Met:.*?\s+)?Units:\s*[\d.]+\s*$"
)

# Section row. Room (e.g. "SWORD219") is one capitalized token glued to no
# space; it only appears for LAB/some LEC. Days: 1-5 chars from `MTWRFSU`
# (also `TBD`). Times: `HH:MM AM/PM`. Instructor can have spaces, commas,
# periods, apostrophes (e.g. "Muccino S.J.,Keith F"). Some sections list
# `TBD` for room+days; we accept either form.
SECTION_RE = re.compile(
    r"^(?P<sched>\d{3,5})\s+"
    r"(?P<section>\w+)\s+"
    r"(?P<kind>LEC|LAB|SEM|DIS|REC|IND|STU|TUT|CLN|PRC)"
    r"(?:\s+(?P<room>[A-Z][A-Z0-9]+))?\s+"
    r"(?P<days>TBD|[MTWRFSU]{1,7})\s+"
    r"(?P<begin>\d{1,2}:\d{2}\s*[AP]M|TBD)\s+"
    r"(?P<end>\d{1,2}:\d{2}\s*[AP]M|TBD)\s+"
    r"(?P<cap>\d+)\s+"
    r"(?P<mode>[A-Z])\s+"
    r"(?P<instructor>.+?)\s*$"
)

# Page footer/headers to skip.
PAGE_FOOTER_RE = re.compile(r"^Class Schedule\s*-\s*Page:\s*\d+\s*$", re.I)
PAGE_HEADER_RE = re.compile(r"^Schedule No\.\s+Building/Room\s+Days", re.I)

SUBJECTS = {"CSCI"}


class HolyCrossScraper(CourseScheduleScraper):
    college = College.HOLY_CROSS
    # Term discovery is per-link on the registrar page, not per AY/term
    # iteration.
    terms = []
    fresh_driver_per_load = False

    def scrape(self):
        try:
            links = self._discover_links()
        except requests.RequestException as e:
            print(f"  registrar fetch failed: {e}", flush=True)
            return []
        if not links:
            print("  no schedule PDFs linked from registrar", flush=True)
            return []
        rows = []
        for academic_year, term, url in links:
            label = f"{academic_year[0]}-{academic_year[1] % 100:02d}/{term}"
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
            page_rows = self._parse_text(text, academic_year, term, url)
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _discover_links(self):
        """Return ``[((start, end), term, url), ...]``.

        Fall AY = (Fall.year, Fall.year + 1). Spring AY = (Spring.year - 1,
        Spring.year). Summer is bucketed into the AY whose summer it falls
        after (start = Summer.year - 1 if you treat AY as Aug-July).
        """
        resp = requests.get(REGISTRAR_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        out = []
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            m = LINK_LABEL_RE.match(label)
            if not m:
                continue
            href = a["href"]
            if href.startswith("/"):
                href = BASE + href
            year = int(m.group("year"))
            season = m.group("season").lower()
            term = SEASON_TERM.get(season)
            if term is None:
                continue
            if term == "F":
                ay = (year, year + 1)
            elif term == "S":
                ay = (year - 1, year)
            else:  # Summer counts as part of the AY that just ended.
                ay = (year - 1, year)
            key = (ay, term, href)
            if key in seen:
                continue
            seen.add(key)
            out.append((ay, term, href))
        return out

    def _parse_text(self, text, academic_year, term, url):
        rows = []
        last_subject = ""
        last_num = ""
        last_title = ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line or PAGE_FOOTER_RE.match(line) or PAGE_HEADER_RE.match(line):
                continue
            cm = COURSE_RE.match(line)
            if cm:
                last_subject = cm.group("subject")
                last_num = cm.group("num")
                last_title = _clean(cm.group("title"))
                continue
            if last_subject and last_subject not in SUBJECTS:
                continue
            if DEPT_RE.match(line) and "Units:" not in line:
                # Bare department header — no state to update; section
                # lines carry their own subject via prior course header.
                continue
            if not last_subject:
                continue
            sm = SECTION_RE.match(line)
            if not sm:
                continue
            if sm.group("subject") if "subject" in sm.groupdict() else None:
                pass  # SECTION_RE has no `subject` group; placeholder.
            days = sm.group("days")
            begin = _clean(sm.group("begin"))
            end = _clean(sm.group("end"))
            if begin == "TBD" or end == "TBD":
                meeting = "TBD"
            else:
                meeting = f"{days} {begin}–{end}".strip()
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=f"{last_subject} {last_num}",
                    section=sm.group("section"),
                    course_name=last_title,
                    instructor=_clean(sm.group("instructor")),
                    time=meeting,
                    url=url,
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
