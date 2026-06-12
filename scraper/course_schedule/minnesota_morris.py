"""University of Minnesota Morris course schedule scraper.

The University of Minnesota system publishes a public Schedule Builder SPA at
``https://schedulebuilder.umn.edu/``, backed by a JSON API at ``/api.php``. We
call that API directly (no Selenium): the SPA renders only the first handful of
course cards and lazily loads the rest on scroll, so DOM scraping silently
dropped every upper-level course (e.g. CSCI 4555 in Spring 2026).

Schedule Builder exposes only currently-registerable terms (typically the
previous, current, and next one or two); the API rejects historical terms with
``{"error":true,"error_detail":"Invalid term."}``. The active-term list is read
from the home page, which embeds a literal ``terms = ["1263", "1265", ...]``
assignment. Each PeopleSoft ``strm`` code decodes as ``year = 1900 + strm // 10``
with a final digit of 3=Spring, 5=Summer, 9=Fall.

Flow per term (institution/campus = ``UMNMO``):

  1. POST ``type=param_search`` (subject=CSCI)
       -> ``[{id: crse_id, sections: [class_nbr, ...]}, ...]``
  2. GET  ``type=sections`` (all class_nbrs)
       -> section objects carrying ``title``, ``section_number``,
          ``component_short`` and ``meetings[]`` (each with ``pattern``, time
          strings, and nested ``instructors[]``).
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import (  # noqa: E402
    CourseScheduleScraper,
    _TERM_ORDER,
)

API_URL = "https://schedulebuilder.umn.edu/api.php"
HOME_URL = "https://schedulebuilder.umn.edu/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; cslac-course-scraper)"}

# Final digit of a PeopleSoft strm term code -> our term code. Fall belongs to
# the academic year it starts; Spring/Summer to the one they end.
_STRM_DIGIT = {3: "S", 5: "Su", 9: "F"}


class MinnesotaMorrisScraper(CourseScheduleScraper):
    college = College.MINNESOTA_MORRIS
    institution = "UMNMO"
    campus = "UMNMO"
    subject = "CSCI"

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session = requests.Session()
        self._session.headers.update(HEADERS)
        self._term_map = None  # (academic_year, term) -> strm, discovered once

    def close(self):
        super().close()
        try:
            self._session.close()
        except Exception:
            pass

    # ---- term discovery ------------------------------------------------------

    def _terms(self):
        """Map every currently-active term to its strm code, read from the home
        page's ``terms = [...]`` bootstrap. Cached per instance."""
        if self._term_map is None:
            self._term_map = {}
            html = self._get(HOME_URL).text
            m = re.search(r"terms\s*=\s*\[([^\]]*)\]", html)
            strms = (int(x) for x in re.findall(r"\d+", m.group(1))) if m else ()
            for strm in strms:
                parsed = _parse_strm(strm)
                if parsed is not None:
                    self._term_map[parsed] = strm
        return self._term_map

    def schedule_pages(self):
        yield from sorted(
            self._terms(), key=lambda p: (p[0], _TERM_ORDER.get(p[1], 9))
        )

    # ---- per-term fetch + parse ----------------------------------------------

    def fetch_page(self, academic_year, term):
        strm = self._terms().get((academic_year, term))
        if strm is None:
            return None
        courses = self._param_search(strm)
        class_nbrs = [cn for c in courses for cn in c.get("sections", [])]
        return self._sections(strm, class_nbrs)

    def parse_page(self, sections, academic_year, term):
        rows = []
        for sec in sections or []:
            row = self._section_row(sec, academic_year, term)
            if row is not None:
                rows.append(row)
        return rows

    def _section_row(self, sec, academic_year, term):
        code = f"{sec.get('subject', '')} {sec.get('catalog_nbr', '')}".strip()
        if not code:
            return None
        section = " ".join(
            p for p in (sec.get("section_number"), sec.get("component_short")) if p
        )
        return self.make_row(
            academic_year,
            term,
            course_code=code,
            section=section,
            course_name=_clean(sec.get("title")),
            instructor=_instructors(sec),
            time=_meeting_time(sec),
        )

    # ---- API calls -----------------------------------------------------------

    def _param_search(self, strm):
        """Return ``[{id, sections: [class_nbr, ...]}, ...]`` for the subject."""
        payload = [
            {
                "param": "subject",
                "value": self.subject,
                "token": "subject",
                "standalone": True,
                "start": 0,
                "end": len(self.subject) - 1,
                "raw_value": self.subject,
                "range": False,
                "multiple": False,
            }
        ]
        result = self._request(
            "POST",
            data={
                "type": "param_search",
                "institution": self.institution,
                "campus": self.campus,
                "term": strm,
                "json": json.dumps(payload),
            },
        )
        return result if isinstance(result, list) else []

    def _sections(self, strm, class_nbrs):
        out = []
        for i in range(0, len(class_nbrs), 100):
            chunk = class_nbrs[i : i + 100]
            result = self._request(
                "GET",
                params={
                    "type": "sections",
                    "institution": self.institution,
                    "campus": self.campus,
                    "term": strm,
                    "class_nbrs": ",".join(str(n) for n in chunk),
                },
            )
            if isinstance(result, list):
                out.extend(result)
        return out

    def _get(self, url):
        return self._with_retries(lambda: self._session.get(url, timeout=30))

    def _request(self, method, *, params=None, data=None):
        r = self._with_retries(
            lambda: self._session.request(
                method, API_URL, params=params, data=data, timeout=30
            )
        )
        return r.json()

    @staticmethod
    def _with_retries(call, attempts=3):
        for attempt in range(attempts):
            try:
                r = call()
                r.raise_for_status()
                return r
            except requests.RequestException:
                if attempt == attempts - 1:
                    raise
                time.sleep(2 * (attempt + 1))


def _parse_strm(strm):
    """`1263` -> `((2025, 2026), 'S')`. Returns None for unknown term digits."""
    term = _STRM_DIGIT.get(strm % 10)
    if term is None:
        return None
    year = 1900 + strm // 10
    academic_year = (year, year + 1) if term == "F" else (year - 1, year)
    return academic_year, term


def _meeting_time(sec):
    """Render ``meetings[]`` as e.g. ``"MWF 02:15 PM – 03:20 PM (65 min)"``,
    space-joining multiple blocks. Placeholder 00:00–00:00 meetings (used by
    directed-study sections with no real time) contribute nothing."""
    parts = []
    for m in sec.get("meetings") or []:
        zero = m.get("start_time") == 0 and m.get("end_time") == 0
        bits = []
        if m.get("pattern"):
            bits.append(m["pattern"])
        if not zero and m.get("start_time_string") and m.get("end_time_string"):
            bits.append(f"{m['start_time_string']} – {m['end_time_string']}")
            if m.get("duration_in_minutes"):
                bits.append(f"({m['duration_in_minutes']} min)")
        s = " ".join(bits)
        if s:
            parts.append(s)
    return " ".join(parts)


def _instructors(sec):
    seen, out = set(), []
    for m in sec.get("meetings") or []:
        for ins in m.get("instructors") or []:
            name = _clean(ins.get("label_name") or "")
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    return "; ".join(out)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
