"""Drew University course schedule scraper.

Drew runs the classic Banner 8 self-service catalog at
`/prod/bwckctlg.p_disp_dyn_ctlg`. It is *not* compatible with the Banner 9
JSON API used by `selfservice.py`; pages are server-rendered HTML and the
section list requires three requests:

  1. ``POST /prod/bwckctlg.p_display_courses``
     with `term_in`, `sel_subj=CSCI`, and a pile of `sel_*=dummy` placeholders
     (the form always submits a hidden `dummy` value before the real one) —
     returns a catalog page that lists every CSCI course and, for those
     actually offered that term, hyperlinks to a per-(course, schedule-type)
     section listing.
  2. ``GET  /prod/bwckctlg.p_disp_listcrse?term_in=...&subj_in=CSCI&crse_in=N&schd_in=X``
     for each unique `(crse_in, schd_in)` pair found in step 1 — returns the
     "Sections Found" page with section headers and a nested
     "Scheduled Meeting Times" table per section.

Banner 8 term codes at Drew share the same `{end_year}` prefix across the
whole academic year (the Banner AY is the year containing Spring):
    Fall     -> `{end_year}10`   e.g. 2025-26 -> 202610
    January  -> `{end_year}20`   ("W" in our term ordering)
    Spring   -> `{end_year}30`
    Summer   -> `{end_year}40`

We include all four; terms a given AY didn't offer simply return zero
sections.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE = "https://selfservice.drew.edu"
CATALOG_POST = f"{BASE}/prod/bwckctlg.p_display_courses"
LISTCRSE = f"{BASE}/prod/bwckctlg.p_disp_listcrse"
SECTION_DETAIL = f"{BASE}/prod/bwckschd.p_disp_detail_sched"

SUBJECT = "CSCI"

TERM_SUFFIX = {"F": "10", "W": "20", "S": "30", "Su": "40"}

LISTCRSE_RE = re.compile(
    r"/prod/bwckctlg\.p_disp_listcrse\?term_in=(\d+)"
    r"&(?:amp;)?subj_in=([A-Z]+)"
    r"&(?:amp;)?crse_in=(\w+)"
    r"&(?:amp;)?schd_in=(\w+)",
    re.I,
)

# Section header text looks like:
#   "Introduction to Computer Science in Python - 10137 - CSCI 150 - 001"
# We rsplit `" - "` 3 times so an em-dashed title remains intact.
HEADER_TAIL_RE = re.compile(r"^(.*) - (\w+) - ([A-Z]+ \w+) - (\w+)$")

PRIMARY_FLAG_RE = re.compile(r"\(\s*P(?:rimary)?\s*\)", re.I)


class DrewScraper(CourseScheduleScraper):
    college = College.DREW
    terms = ["F", "W", "S", "Su"]

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None

    def _ensure_session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "Mozilla/5.0 (cs-lac scraper)"})
        return self._session

    @staticmethod
    def _term_code(academic_year, term):
        # Drew's Banner academic year is "the year containing Spring", so all
        # four terms (Fall of start_year, Jan/Spring/Summer of end_year) share
        # `end_year` as the prefix. E.g. AY 2025-26 -> 2026{10,20,30,40}.
        _, end_year = academic_year
        return f"{end_year}{TERM_SUFFIX[term]}"

    def url_for(self, academic_year, term):
        return f"{CATALOG_POST}?term_in={self._term_code(academic_year, term)}"

    def fetch_page(self, academic_year, term):
        s = self._ensure_session()
        code = self._term_code(academic_year, term)
        # Banner 8 forms always submit a hidden `dummy` value as the first
        # entry of each `sel_*` multi-select before the real selection.
        data = [
            ("term_in", code),
            ("call_proc_in", "bwckctlg.p_disp_dyn_ctlg"),
            ("sel_subj", "dummy"), ("sel_subj", SUBJECT),
            ("sel_levl", "dummy"),
            ("sel_schd", "dummy"),
            ("sel_coll", "dummy"),
            ("sel_divs", "dummy"),
            ("sel_dept", "dummy"),
            ("sel_attr", "dummy"),
            ("sel_crse_strt", ""), ("sel_crse_end", ""),
            ("sel_title", ""),
            ("sel_from_cred", ""), ("sel_to_cred", ""),
        ]
        resp = s.post(CATALOG_POST, data=data, timeout=60)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        code = self._term_code(academic_year, term)
        # Find every distinct (crse_in, schd_in) link in the catalog page.
        seen = set()
        targets = []
        for term_in, subj_in, crse_in, schd_in in LISTCRSE_RE.findall(html):
            if subj_in != SUBJECT or term_in != code:
                continue
            key = (crse_in, schd_in)
            if key in seen:
                continue
            seen.add(key)
            targets.append(key)

        s = self._ensure_session()
        rows = []
        for crse_in, schd_in in targets:
            try:
                resp = s.get(
                    LISTCRSE,
                    params={
                        "term_in": code,
                        "subj_in": SUBJECT,
                        "crse_in": crse_in,
                        "schd_in": schd_in,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
            except requests.RequestException:
                continue
            rows.extend(self._parse_sections(resp.text, academic_year, term, code))
        return rows

    def _parse_sections(self, html, academic_year, term, term_code):
        soup = BeautifulSoup(html, "html.parser")
        outer = _find_sections_table(soup)
        if outer is None:
            return []

        out = []
        current = None
        for tr in outer.find_all("tr", recursive=False):
            th = tr.find("th", class_="ddtitle")
            if th:
                if current:
                    out.append(self._finalize_section(current, academic_year, term))
                current = _parse_section_header(th, term_code)
                continue
            if current is None:
                continue
            inner = tr.find("table", class_="datadisplaytable")
            if inner is None:
                continue
            for mrow in inner.find_all("tr"):
                cells = mrow.find_all("td", recursive=False)
                if len(cells) != 7:
                    continue
                meeting_type = _clean(cells[0].get_text(" "))
                if meeting_type.lower().startswith("final exam"):
                    continue
                time_text = _clean(cells[1].get_text(" "))
                days = _clean(cells[2].get_text(" "))
                where = _clean(cells[3].get_text(" "))
                instructor = _format_instructor(cells[6])
                current["meetings"].append((days, time_text, where))
                if instructor and instructor not in current["instructors"]:
                    current["instructors"].append(instructor)

        if current:
            out.append(self._finalize_section(current, academic_year, term))
        return out

    def _finalize_section(self, current, academic_year, term):
        meetings = "; ".join(
            _format_meeting(d, t, w) for d, t, w in current["meetings"] if (d or t or w)
        )
        return self.make_row(
            academic_year,
            term,
            course_code=current["course_code"],
            section=current["section"],
            course_name=current["course_name"],
            instructor=", ".join(current["instructors"]),
            time=meetings,
            url=current["url"],
        )

    def close(self):
        super().close()
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def _find_sections_table(soup):
    for t in soup.find_all("table", class_="datadisplaytable"):
        cap = t.find("caption")
        if cap and "Sections Found" in cap.get_text():
            return t
    return None


def _parse_section_header(th, term_code):
    text = _clean(th.get_text(" "))
    m = HEADER_TAIL_RE.match(text)
    url = ""
    link = th.find("a", href=True)
    if link:
        href = link["href"]
        if href.startswith("/"):
            url = BASE + href
        else:
            url = href
    if m:
        course_name = _clean(m.group(1))
        crn = m.group(2)
        course_code = m.group(3)
        section = m.group(4)
    else:
        course_name, crn, course_code, section = text, "", "", ""
        _ = crn  # unused, retained for clarity
    if not url:
        url = f"{SECTION_DETAIL}?term_in={term_code}&crn_in={crn}"
    return {
        "course_code": course_code,
        "section": section,
        "course_name": course_name,
        "meetings": [],
        "instructors": [],
        "url": url,
    }


def _format_meeting(days, time_text, where):
    bits = [b for b in (days, time_text) if b]
    s = " ".join(bits)
    if where:
        s = f"{s} ({where})" if s else f"({where})"
    return s


def _format_instructor(cell):
    # Cell content: "Diane   Liporace ( P )<email-icon>", possibly with
    # multiple instructors joined by commas/`<br>`s.
    text = cell.get_text(" ", strip=True)
    text = PRIMARY_FLAG_RE.sub("", text)
    return _clean(text)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
