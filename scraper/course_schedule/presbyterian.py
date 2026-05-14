"""Presbyterian College course schedule scraper.

Presbyterian runs the older Banner 8 ``hzskschd`` web app rather than the
Banner 9 SSB that powers most of `banner9.py`. The schedule is served as
plain HTML tables — no JavaScript, no JSON. Two endpoints:

  1. ``GET  /prod/hzskschd.P_SelectSubject``
       Returns the search form, including a ``<select name="validterm">``
       whose options enumerate the currently viewable terms (the only
       history exposed publicly — older terms 404 with "not available
       for viewing").
  2. ``POST /prod/hzskschd.P_ViewSchedule``
       Body ``validterm=<TERMCODE>&subjcode=<SUBJ>&openclasses=N`` returns
       a one-section-per-row HTML table.

Term codes are ``<yyyy><mm>`` where ``yyyy`` is the academic-year start
year (``202601`` = Fall 2026 = AY 2026-27) and ``mm`` is a season code
(``01`` Fall, ``02`` Spring, ``04``/``05`` Summer; ``03`` Maymester and
``21``+ graduate Phys Asst terms are ignored).
"""

import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import (  # noqa: E402
    CourseScheduleScraper,
    format_academic_year,
)

BASE_URL = "https://banners.presby.edu/prod"
SELECT_URL = f"{BASE_URL}/hzskschd.P_SelectSubject"
VIEW_URL = f"{BASE_URL}/hzskschd.P_ViewSchedule"

# Map Banner 8 month-suffix (last 2 chars of term code) to our internal term.
TERM_SUFFIX_MAP = {
    "01": "F",
    "02": "S",
    "04": "Su",
    "05": "Su",
}

# Day cells appear in 6 columns in this order. Banner uses "R" for Thursday.
DAY_COLS = ["M", "T", "W", "Th", "F", "Sa"]
DAY_LETTERS = {"M": "M", "T": "T", "W": "W", "R": "Th", "F": "F", "S": "Sa"}

REQUEST_TIMEOUT = 30


class PresbyterianScraper(CourseScheduleScraper):
    college = College.PRESBYTERIAN
    subject = "CSC"
    # The page enumerates only currently-viewable terms; we discover them at
    # runtime rather than iterating a fixed history.
    terms: list = []
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None

    def _ensure_session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (cs-lac course-schedule scraper)",
            })
            self._session = s
        return self._session

    def _discover_terms(self):
        """Return {(academic_year, term): term_code} for visible undergrad terms."""
        s = self._ensure_session()
        resp = s.get(SELECT_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        select = re.search(
            r'<select name="validterm"[^>]*>(.*?)</select>', resp.text, re.S | re.I
        )
        if not select:
            return {}
        mapping = {}
        for opt in re.finditer(
            r'<option[^>]+value="([^"]+)"[^>]*>([^<]+)',
            select.group(1),
            re.I,
        ):
            code = opt.group(1).strip()
            if len(code) != 6 or not code.isdigit():
                continue
            term_suffix = code[4:]
            if term_suffix not in TERM_SUFFIX_MAP:
                continue
            year = int(code[:4])
            mapping[((year, year + 1), TERM_SUFFIX_MAP[term_suffix])] = code
        return mapping

    def scrape(self):
        s = self._ensure_session()
        mapping = self._discover_terms()
        if not mapping:
            print("  no viewable terms found", flush=True)
            return []
        rows = []
        for (ay, t), code in sorted(mapping.items()):
            try:
                resp = s.post(
                    VIEW_URL,
                    data={"validterm": code, "subjcode": self.subject, "openclasses": "N"},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{format_academic_year(ay)}/{t}] failed: {e}", flush=True)
                continue
            page_rows = self._parse_html(resp.text, ay, t)
            print(f"  [{format_academic_year(ay)}/{t}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def _parse_html(self, html, academic_year, term):
        rows = []
        for tr_chunk in re.split(r"<tr[^>]*>", html, flags=re.I)[1:]:
            body = tr_chunk.split("</tr>", 1)[0]
            cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S | re.I)
            if len(cells) != 14:
                continue
            cleaned = [_clean(c) for c in cells]
            course_raw = cleaned[1]
            if not course_raw.startswith(self.subject):
                continue
            course_code, section = _split_code(course_raw)
            day_cells = cleaned[5:11]
            time_str = _format_time(day_cells, cleaned[11], cleaned[12])
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=cleaned[3],
                    instructor=cleaned[4],
                    time=time_str,
                    url=SELECT_URL,
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


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    # Banner 8 sometimes emits unterminated `&nbsp` entities.
    text = text.replace("\xa0", " ")
    text = re.sub(r"&nbsp;?", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_code(raw):
    """``"CSC 1235 K"`` -> ``("CSC 1235", "K")``."""
    m = re.match(r"^([A-Za-z]+\s*\d+[A-Za-z]?)\s+([A-Za-z0-9]+)$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw, ""


def _format_time(day_cells, time_raw, location):
    """Render Banner 8's six day cells + time + room as ``"MWF 13:00-14:15 (H-P 212)"``.

    ``day_cells`` is a list of six strings, each either a Banner day letter
    (M T W R F S) or empty/&nbsp.
    """
    days = "".join(
        DAY_LETTERS[c.strip()]
        for c in day_cells
        if c.strip() in DAY_LETTERS
    )
    time_str = _compact_time_range(time_raw)
    # The "TBA" placeholder Banner uses for online/internship slots is
    # "00:00-00:01am" — strip those (they're not real meeting times).
    if time_str.startswith("00:00-00:01"):
        time_str = ""
    parts = [p for p in (days, time_str) if p]
    s = " ".join(parts)
    location = (location or "").strip()
    if location:
        s = f"{s} ({location})" if s else f"({location})"
    return s


def _compact_time_range(raw):
    """``"3:00-4:15pm"`` / ``"11:30-12:20pm"`` -> ``"15:00-16:15"`` / ``"11:30-12:20"``.

    Banner 8 typically only emits the AM/PM suffix on the end time. We
    propagate it back to the start, but if doing so would produce an
    inverted range (e.g. ``"11:30-12:20pm"`` naively becoming 23:30-12:20)
    we flip the start to the opposite half of the day, which handles the
    common case of a class spanning the noon boundary.
    """
    if not raw:
        return ""
    m = re.match(
        r"^(\d{1,2}:\d{2})(am|pm)?\s*-\s*(\d{1,2}:\d{2})(am|pm)?$",
        raw,
        re.I,
    )
    if not m:
        return raw
    start_hhmm, start_sfx, end_hhmm, end_sfx = m.groups()
    end_sfx = (end_sfx or "").upper()
    start_sfx = (start_sfx or end_sfx).upper()
    start_24 = _to_24h(start_hhmm, start_sfx)
    end_24 = _to_24h(end_hhmm, end_sfx)
    if not start_sfx_was_explicit(start_sfx, raw) and start_24 > end_24 and start_sfx in ("AM", "PM"):
        flipped = "AM" if start_sfx == "PM" else "PM"
        start_24 = _to_24h(start_hhmm, flipped)
    return f"{start_24}-{end_24}"


def start_sfx_was_explicit(suffix, raw):
    """True iff the start endpoint had its own AM/PM marker in the input."""
    return bool(re.match(r"^\d{1,2}:\d{2}(am|pm)", raw, re.I))


def _to_24h(hhmm, suffix):
    h, mm = hhmm.split(":")
    h = int(h)
    if suffix == "AM" and h == 12:
        h = 0
    elif suffix == "PM" and h != 12:
        h += 12
    return f"{h:02d}:{mm}"
