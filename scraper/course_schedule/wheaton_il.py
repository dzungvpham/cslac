"""Wheaton College (IL) course schedule scraper.

The registrar publishes the current term's "Registration Packet" PDFs at

    https://www.wheaton.edu/about-wheaton/offices-and-services/office-of-the-registrar/schedules/

Links labelled e.g. ``"Spring 2026 Course Schedule"`` point at PDFs under
``/media/registrar/schedule/{Season}-{YEAR}-Registration-Packet*.pdf``.
Only the active terms (last finished + current + next 1-2) are exposed;
the page does not carry historical packets.

Each PDF has every department's listings under a ``Subject: <Name>``
header. The Computer Science block reads

    Subject: Computer Science
    CRN Subj Num Sec Quad XL Title / Comment Cred Meeting Time Days Max Cap Fees Attributes
    80130 CSCI 235 0 1 Programming I: Problem Solving 4 11:35 AM - 12:45 PM M W F 28 AAQR
    ...

There is no instructor column in this packet, so we leave that field
blank. Lab sections (e.g. ``CSCI 235L``) use the same row format.
"""

import re
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

INDEX_URL = (
    "https://www.wheaton.edu/about-wheaton/offices-and-services/"
    "office-of-the-registrar/schedules/"
)

# Link labels read "Fall 2026 Course Schedule" etc. Final-exam packets use
# "Fall 2026 Exam Schedule" — different word, so the negative lookahead on
# the trailing token rejects them.
LABEL_RE = re.compile(
    r"^(?P<season>Fall|Spring|Summer|Winter|January|J\s*Term|J-Term)\s+"
    r"(?P<year>\d{4})\s+Course\s+Schedule\s*$",
    re.I,
)

SEASON_TERM = {
    "fall": "F",
    "spring": "S",
    "summer": "Su",
    "winter": "W",
    "january": "W",
    "j term": "W",
    "j-term": "W",
    "jterm": "W",
}

# A CS row: `<CRN> CSCI <NUM>[L] <SEC> <QUAD> <TITLE> <CRED> <TIME> <DAYS> <MAX> ...`
# Times have an explicit ` - ` separator; days are letter-tokens separated
# by spaces (e.g. "M W F" or "T R"). Cred is one digit (0 for labs).
ROW_RE = re.compile(
    r"^(?P<crn>\d{4,6})\s+CSCI\s+(?P<num>\d+[A-Z]*)\s+(?P<section>\w+)\s+"
    r"(?P<quad>\d+)\s+"
    r"(?P<rest>.+)$"
)
# In `rest`, split off the time/days tail. Time: "11:35 AM - 12:45 PM" or
# "TBA". After time, days are space-separated single letters.
TAIL_RE = re.compile(
    r"\s+(?P<credits>\d+)\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*[AP]M\s*-\s*\d{1,2}:\d{2}\s*[AP]M|TBA|ARR)\s+"
    r"(?P<days>(?:[MTWRF](?:\s|$))+|TBA|ARR)\s*"
    r"(?P<max>\d+)?\s*(?P<attrs>.*)$"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _format_meeting(days, time):
    days = _clean(days).replace(" ", "")
    return f"{days} {_clean(time)}".strip()


class WheatonILScraper(CourseScheduleScraper):
    college = College.WHEATON_IL
    terms = []  # discovery from the schedules index
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._index = None

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
            season = re.sub(r"\s+", " ", m.group("season").lower())
            term = SEASON_TERM.get(season)
            if term is None:
                continue
            year = int(m.group("year"))
            if season == "fall":
                ay = (year, year + 1)
            else:
                ay = (year - 1, year)
            url = urljoin(INDEX_URL, a["href"])
            out.append((ay, term, url))
        # Sort oldest first.
        out.sort(key=lambda r: (r[0], {"F": 0, "W": 1, "S": 2, "Su": 3}.get(r[1], 9)))
        self._index = out
        return out

    def scrape(self):
        rows = []
        for ay, term, url in self._discover():
            label = f"{ay[0]}-{ay[1] % 100:02d}/{term}"
            try:
                resp = requests.get(url, timeout=90)
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
        rows = []
        in_cs = False
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped == "Subject: Computer Science":
                in_cs = True
                continue
            if in_cs and stripped.startswith("Subject:"):
                break
            if not in_cs:
                continue
            # Skip the per-section column header.
            if stripped.startswith("CRN Subj Num"):
                continue
            m = ROW_RE.match(stripped)
            if not m:
                continue
            tail = TAIL_RE.search(m.group("rest"))
            if not tail:
                continue
            title = _clean(m.group("rest")[: tail.start()])
            time_str = _format_meeting(tail.group("days"), tail.group("time"))
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=f"CSCI {m.group('num')}",
                    section=m.group("section"),
                    course_name=title,
                    instructor="",
                    time=time_str,
                    url=url,
                )
            )
        return rows
