"""Central College course schedule scraper.

Central runs a public searchable schedule at
``https://central.edu/academics/course-catalog/searchable-schedule/``.
The form on that page posts to ``https://central.edu/search/``, which
302-redirects to ``https://web.central.edu/registrar/searchcourse/`` —
where the response actually renders. We POST directly to the destination
to avoid the redirect dance.

The form's `Term` dropdown lists only currently-registerable terms
(typically the next 2-4 semesters; no historical archive). Term values
look like ``"26/SP"`` (Spring 2026, AY 2025-26) and ``"26/FA"`` (Fall
2026, AY 2026-27). Subject for CS is ``COSC``.

Each result row is one ``<tr>`` with cells:

    | <a>COSC-110-A</a>:<br>Title<p>flags</p> | credits | days time<br>room — instructor | enrolled/cap | status |

The cells are easy to address by index; the third cell stacks a meeting
line and a ``"<room> — <instructor>"`` line that we split on ``" — "``.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

FORM_URL = "https://central.edu/academics/course-catalog/searchable-schedule/"
POST_URL = "https://web.central.edu/registrar/searchcourse/"
SUBJECT = "COSC"

# Term option values: `"<YY>/<FA|SP|SU>"`. YY is the two-digit calendar year.
TERM_VALUE_RE = re.compile(r"^(?P<yy>\d{2})/(?P<season>FA|SP|SU)$")
SEASON_TERM = {"FA": "F", "SP": "S"}  # skip Summer

# Course-code cell: anchor text like "COSC-110-A".
COURSE_CODE_RE = re.compile(r"^([A-Z]+)-(\d+\w*)-(\w+)$")


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class CentralScraper(CourseScheduleScraper):
    college = College.CENTRAL
    terms = []
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._session = requests.Session()
        self._available = None  # (academic_year, term) -> form value

    def _discover_terms(self):
        if self._available is not None:
            return self._available
        resp = self._session.get(FORM_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        sel = soup.find("select", {"name": "Term"})
        if sel is None:
            self._available = {}
            return self._available
        out = {}
        for opt in sel.find_all("option"):
            value = (opt.get("value") or "").strip()
            m = TERM_VALUE_RE.match(value)
            if not m:
                continue
            season = m.group("season")
            term = SEASON_TERM.get(season)
            if term is None:
                continue
            year = 2000 + int(m.group("yy"))
            if term == "F":
                academic_year = (year, year + 1)
            else:  # Spring
                academic_year = (year - 1, year)
            out[(academic_year, term)] = value
        self._available = out
        return out

    def schedule_pages(self):
        available = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in ("F", "S"):
                if (ay, t) in available:
                    yield ay, t

    def fetch_page(self, academic_year, term):
        available = self._discover_terms()
        value = available.get((academic_year, term))
        if value is None:
            return None
        data = {
            "Term": value,
            "Subject": SUBJECT,
            "CoreReq": "",
            "Status": "",
            "MeetingTime": "",
        }
        resp = self._session.post(POST_URL, data=data, timeout=45)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for tr in soup.select("table.tableHover tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            link = cells[0].find("a")
            if link is None:
                continue
            code_text = _clean(link.get_text(" ", strip=True))
            m = COURSE_CODE_RE.match(code_text)
            if not m:
                continue
            course_code = f"{m.group(1)} {m.group(2)}"
            section = m.group(3)
            # Title: text in cell 0 after the anchor + trailing ":". The
            # `<br>` between the anchor and the title becomes a newline; the
            # bare ":" sometimes lives on its own line in between. Take the
            # first line that isn't the course code or a punctuation-only
            # fragment.
            title_text = cells[0].get_text("\n", strip=True)
            title_lines = [
                _clean(ln) for ln in title_text.split("\n")
                if _clean(ln) and _clean(ln) not in {":", code_text, code_text + ":"}
            ]
            course_name = title_lines[0] if title_lines else ""
            # Third cell stacks meeting time(s) + "<room> — <instructor>".
            # Some rows omit the meeting entirely and just print " — <instr>".
            meet_text = cells[2].get_text("\n", strip=True)
            meet_lines = [_clean(ln) for ln in meet_text.split("\n") if _clean(ln)]
            meeting = ""
            instructor = ""
            if meet_lines:
                last = meet_lines[-1]
                # Em-dash separates the room from the instructor. When the
                # meeting time is omitted the cell starts with a bare " — ",
                # so the split has to tolerate an empty left side.
                if "—" in last:
                    left, right = last.split("—", 1)
                    room = _clean(left)
                    instructor = _clean(right)
                    meeting_lines = meet_lines[:-1] + ([room] if room else [])
                else:
                    meeting_lines = meet_lines
                meeting = " / ".join(meeting_lines)
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=_clean(course_name),
                    instructor=_clean(instructor),
                    time=meeting,
                    url=FORM_URL,
                )
            )
        return rows
