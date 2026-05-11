"""Earlham College course schedule scraper.

Earlham runs the older Banner 8 Self-Service catalog
(``ssb.earlham.edu/frog/bwckschd.p_disp_dyn_sched``) rather than Banner 9,
so we can't reuse the JSON-based ``banner9.py`` base. The flow is plain
server-rendered HTML forms:

  1. ``GET  /frog/bwckschd.p_disp_dyn_sched``
       Returns the term-selector page. The ``<select name="p_term">``
       options list every term across all Earlham instances
       (undergraduate "EC", Seminary, MAT, M.ED, ...). We keep only those
       whose description starts with ``EC``.
  2. ``POST /frog/bwckschd.p_get_crse_unsec``
       The list-results endpoint. Banner 8 expects every ``sel_*`` filter
       to be passed twice — first as the literal value ``"dummy"`` (the
       hidden form fields), then as the real value (``"CS"`` for the
       subject; ``"%"`` for the unconstrained dropdowns). Posting without
       the dummies returns a 500.

The result HTML is a flat sequence of ``<th class="ddtitle">`` headings
("Course Title - CRN - SUBJ NNN - SECTION"), each immediately followed
by a ``<tr>`` whose body contains the metadata block plus a nested
``<table>`` of scheduled meeting times (one row per meeting pattern;
lecture + lab sections produce two).
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE = "https://ssb.earlham.edu/frog"
SUBJECT = "CS"

# "EC Fall Semester 2025-26", "EC Spring Semester 2024/25 (View only)", etc.
# Two years are always present; capture the start year, derive end from it.
TERM_DESC_RE = re.compile(
    r"^\s*EC\s+(?P<season>Fall|Spring)(?:\s+Semester)?\s+(?P<start>\d{4})\s*[-/]\s*\d{2,4}",
    re.I,
)

# Heading inside `<th class="ddtitle">`:
# "Programming & Problem Solving - 26204 - CS 128 - 0"
HEADING_RE = re.compile(
    r"^(?P<name>.+?)\s+-\s+(?P<crn>\w+)\s+-\s+"
    r"(?P<code>[A-Z]+\s+\d+\w*)\s+-\s+(?P<section>\w+)\s*$"
)

DAY_MAP = {"M": "M", "T": "T", "W": "W", "R": "Th", "F": "F", "S": "Sa", "U": "Su"}


class EarlhamScraper(CourseScheduleScraper):
    college = College.EARLHAM
    terms = ["F", "S"]
    # Pure-HTML endpoint, no Selenium needed.
    fresh_driver_per_load = False
    request_timeout = 30

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None
        self._term_codes: dict | None = None  # (ay, term) -> banner code

    def _ensure_session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0 (cs-lac scraper)"})
            self._session = s
        return self._session

    def _discover_terms(self):
        if self._term_codes is not None:
            return self._term_codes
        s = self._ensure_session()
        resp = s.get(f"{BASE}/bwckschd.p_disp_dyn_sched", timeout=self.request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        select = soup.find("select", attrs={"name": "p_term"})
        mapping = {}
        if select is None:
            self._term_codes = mapping
            return mapping
        for opt in select.find_all("option"):
            code = (opt.get("value") or "").strip()
            desc = opt.get_text(" ", strip=True)
            m = TERM_DESC_RE.match(desc)
            if not code or not m:
                continue
            start = int(m.group("start"))
            ay = (start, start + 1)
            t = "F" if m.group("season").lower() == "fall" else "S"
            # Earlham's option list is newest-first; keep the first occurrence
            # so the canonical (non-rerun) code wins if duplicates ever appear.
            mapping.setdefault((ay, t), code)
        self._term_codes = mapping
        return mapping

    def schedule_pages(self):
        mapping = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in self.terms:
                if (ay, t) in mapping:
                    yield ay, t

    def url_for(self, academic_year, term):
        return f"{BASE}/bwckschd.p_disp_dyn_sched"

    def fetch_page(self, academic_year, term):
        mapping = self._discover_terms()
        code = mapping.get((academic_year, term))
        if code is None:
            return None
        s = self._ensure_session()
        # Banner 8 requires the "dummy" placeholders before each real value
        # (they bind the hidden form fields). Order matters: dummies first.
        data = [
            ("term_in", code),
            ("sel_subj", "dummy"),
            ("sel_day", "dummy"),
            ("sel_schd", "dummy"),
            ("sel_insm", "dummy"),
            ("sel_camp", "dummy"),
            ("sel_levl", "dummy"),
            ("sel_sess", "dummy"),
            ("sel_instr", "dummy"),
            ("sel_ptrm", "dummy"),
            ("sel_attr", "dummy"),
            ("sel_subj", SUBJECT),
            ("sel_crse", ""),
            ("sel_title", ""),
            ("sel_schd", "%"),
            ("sel_from_cred", ""),
            ("sel_to_cred", ""),
            ("sel_ptrm", "%"),
            ("sel_instr", "%"),
            ("sel_sess", "%"),
            ("sel_attr", "%"),
            ("begin_hh", "0"),
            ("begin_mi", "0"),
            ("begin_ap", "a"),
            ("end_hh", "0"),
            ("end_mi", "0"),
            ("end_ap", "a"),
        ]
        resp = s.post(
            f"{BASE}/bwckschd.p_get_crse_unsec", data=data, timeout=self.request_timeout
        )
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        url = f"{BASE}/bwckschd.p_disp_dyn_sched"
        rows = []
        for title_th in soup.select("th.ddtitle"):
            heading = _clean(title_th.get_text(" "))
            m = HEADING_RE.match(heading)
            if m:
                course_name = m.group("name").strip()
                course_code = re.sub(r"\s+", " ", m.group("code").strip())
                section = m.group("section").strip()
            else:
                course_name, course_code, section = heading, "", ""

            detail_tr = title_th.find_parent("tr").find_next_sibling("tr")
            meetings = _parse_meetings(detail_tr) if detail_tr else []
            instructor = _format_instructors(meetings)
            time_str = _format_meetings(meetings)

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_str,
                    url=url,
                )
            )
        return rows

    def close(self):
        super().close()
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def _parse_meetings(detail_tr):
    """Extract the Scheduled Meeting Times sub-table rows.

    Returns a list of dicts with keys ``time``, ``days``, ``where``,
    ``instructors`` (skipping the header row).
    """
    table = detail_tr.find("table", class_="datadisplaytable")
    if table is None:
        return []
    out = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", class_="dddefault")
        if len(cells) < 7:
            # Header row uses <th>, skipped automatically.
            continue
        out.append(
            {
                "time": _clean(cells[1].get_text(" ")),
                "days": _clean(cells[2].get_text(" ")),
                "where": _clean(cells[3].get_text(" ")),
                "instructors": _extract_instructors(cells[6]),
            }
        )
    return out


def _extract_instructors(cell):
    """Strip the trailing `(P)` / `(S)` role markers and email icons.

    The cell looks like ``Name1 ( <abbr>P</abbr> )<a><img/></a>, Name2 (...)``.
    Decomposing the inner tags leaves stray ``( )`` shells around each name.
    """
    for tag in cell.find_all(["a", "abbr"]):
        tag.decompose()
    text = cell.get_text(" ", strip=True)
    text = re.sub(r"\(\s*\)", "", text)
    names = [_clean(n) for n in re.split(r",", text) if _clean(n)]
    return names


def _format_instructors(meetings):
    seen = []
    for m in meetings:
        for n in m["instructors"]:
            if n not in seen:
                seen.append(n)
    return ", ".join(seen)


def _format_meetings(meetings):
    """Render as ``"MWF 10:00-10:50 (CST 224); F 13:00-14:20 (CST 224)"``."""
    parts = []
    seen = set()
    for m in meetings:
        days = _normalize_days(m["days"])
        time_range = _normalize_time_range(m["time"])
        where = m["where"]
        if not (days or time_range or where):
            continue
        bits = [b for b in [days, time_range] if b]
        s = " ".join(bits)
        if where:
            s = f"{s} ({where})" if s else f"({where})"
        if s and s not in seen:
            seen.add(s)
            parts.append(s)
    return "; ".join(parts)


def _normalize_days(days):
    if not days:
        return ""
    return "".join(DAY_MAP.get(ch.upper(), "") for ch in days if not ch.isspace())


def _normalize_time_range(s):
    """``"10:00 am - 10:50 am"`` -> ``"10:00-10:50"`` (24h)."""
    if not s:
        return ""
    m = re.match(
        r"^\s*(\d{1,2}):(\d{2})\s*([ap]m)\s*-\s*(\d{1,2}):(\d{2})\s*([ap]m)\s*$",
        s,
        re.I,
    )
    if not m:
        return _clean(s)
    return f"{_to_24h(m.group(1), m.group(2), m.group(3))}-{_to_24h(m.group(4), m.group(5), m.group(6))}"


def _to_24h(hh, mm, ap):
    h = int(hh) % 12
    if ap.lower() == "pm":
        h += 12
    return f"{h:02d}:{mm}"


def _clean(text):
    return re.sub(r"\s+", " ", str(text) if text is not None else "").strip()
