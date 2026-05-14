"""Ellucian PowerCampus Self-Service course schedule scraper.

A small family of LACs runs Ellucian PowerCampus Self-Service ("SELFSERV"),
distinct from both Banner 9 SSB and Colleague Self-Service. The public
section search lives at:

    {base}/SELFSERV/Search/Section?eventId={SUBJECT}

The UI is a React SPA, but its data comes from a JSON endpoint we hit
directly with `requests` (no Selenium):

  1. ``GET  /SELFSERV/Search/Section?eventId=<SUBJ>``
       Establishes the ``.SelfService.Session`` cookie.
  2. ``POST /SELFSERV/Sections/Search``
       Body ``{"sectionSearchParameters":{"eventId":"<SUBJ>"},
              "startIndex":0,"length":500}`` returns
       ``{data: {overallCount, sections: [...]}}`` with every section
       across every currently-exposed term. The ``eventId`` parameter is a
       prefix filter, so passing ``"CSC"`` returns CSC141, CSC205, etc.

PowerCampus only exposes currently-registerable terms (typically the
current + next academic year), so we capture whatever appears rather than
iterating a fixed history. Each section's ``year`` + ``term`` fields tell
us where to bucket it.

Two non-obvious request requirements:
  - The ``X-Current-Page`` header must be set to the base64-encoded page
    identifier ``"SectionSearchId"`` → ``U2VjdGlvblNlYXJjaElk``. Without
    it the server 302s to ``/SELFSERV/Errors/Error403``.
  - The session cookie from step 1 must accompany step 2.

Each entry in ``POWERCAMPUS_COLLEGES`` is a ``(College, base_url, subject)``
tuple — adding a new school is a one-line change.
"""

import base64
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

# Same day-index convention used by the PowerCampus UI:
#   0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat.
DAY_ABBR = {0: "Su", 1: "M", 2: "T", 3: "W", 4: "Th", 5: "F", 6: "Sa"}
DAY_ORDER = [1, 2, 3, 4, 5, 6, 0]

# Maps PowerCampus `term` codes to our internal (academic_year_offset, code).
# `offset` is added to `year` to derive the academic-year start year:
#   FALL 2025  -> AY (2025, 2026), code "F"
#   SPRING 2026 -> AY (2025, 2026), code "S"
TERM_MAP = {
    "FALL":   (0,  "F"),
    "WINTER": (-1, "W"),
    "SPRING": (-1, "S"),
    "SUMMER": (-1, "Su"),
}

# OWU and a few other deployments split the summer into ``SUM1``/``SUM2``
# (and occasionally ``SP1``/``FA1`` mini-terms). Match by prefix so any
# numbered variant maps to the same internal code.
TERM_PREFIX_MAP = [
    ("SUM",  (-1, "Su")),
    ("FA",   (0,  "F")),   # FALL is caught by TERM_MAP first; FA1/FA2 fall here.
    ("SP",   (-1, "S")),   # SPRING is caught by TERM_MAP first.
    ("WIN",  (-1, "W")),
]

# The X-Current-Page header is required by the SELFSERV API. The value is
# base64("SectionSearchId").
SECTION_SEARCH_PAGE = base64.b64encode(b"SectionSearchId").decode("ascii")

PAGE_SIZE = 500


class PowerCampusScraper(CourseScheduleScraper):
    """Base scraper for any Ellucian PowerCampus Self-Service deployment.

    Subclass attributes:
        - ``base_url``: e.g. ``"https://selfservice.albright.edu"`` (no
          trailing slash, no ``/SELFSERV`` suffix).
        - ``subject``: course-code prefix to search, e.g. ``"CSC"``,
          ``"CS"``, ``"COMP"``. Used as a prefix filter on ``eventId``.
    """

    base_url: str = ""
    subject: str = ""
    # Path prefix between the host and ``/Search/Section`` / ``/Sections/Search``.
    # Most deployments live under ``/SELFSERV`` (uppercase), but Ohio Wesleyan's
    # campus.owu.edu instance uses lowercase ``/selfserv``.
    selfserv_path: str = "/SELFSERV"
    # PowerCampus returns every visible term in one response, so we don't
    # iterate (year, term) ourselves — `schedule_pages` yields a single
    # sentinel page and `fetch_page` fans the response back out by term.
    terms: list = []
    fresh_driver_per_load = False
    request_timeout = 30

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None
        self._sections_by_term: dict | None = None  # (ay, term) -> list[section]

    # ---- HTTP plumbing -------------------------------------------------------

    def _url(self, path):
        return f"{self.base_url}{self.selfserv_path}{path}"

    def _search_url(self):
        return self._url(f"/Search/Section?eventId={self.subject}")

    def _ensure_session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (cs-lac course-schedule scraper)",
                "Accept": "application/json, text/plain, */*",
                "Referer": self._search_url(),
            })
            s.get(self._search_url(), timeout=self.request_timeout)
            self._session = s
        return self._session

    def _fetch_all_sections(self):
        if self._sections_by_term is not None:
            return self._sections_by_term
        s = self._ensure_session()
        # Walk through every page reported by ``overallCount``. PowerCampus's
        # Sections/Search caps response size somewhere around 50 items per
        # call on some deployments (Ohio Wesleyan's catalog UI paginates 10
        # at a time), so we keep advancing ``startIndex`` until we've seen
        # ``overallCount`` results — `PAGE_SIZE = 500` is just the per-call
        # upper bound and the actual page size is whatever the server returns.
        sections: list = []
        start = 0
        overall = None
        page_calls = 0
        while True:
            resp = s.post(
                self._url("/Sections/Search"),
                json={
                    "sectionSearchParameters": {"eventId": self.subject},
                    "startIndex": start,
                    "length": PAGE_SIZE,
                },
                headers={"X-Current-Page": SECTION_SEARCH_PAGE},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            data = (resp.json() or {}).get("data", {}) or {}
            batch = data.get("sections") or []
            if overall is None:
                overall = int(data.get("overallCount") or 0)
            sections.extend(batch)
            if not batch:
                break
            start += len(batch)
            if start >= overall:
                break
            page_calls += 1
            if page_calls > 200:
                print(f"  pagination safety cap hit at {start}/{overall}", flush=True)
                break

        buckets: dict = {}
        for sec in sections:
            # OWU emits a parallel "dual requirement" row alongside every real
            # section (eventName like "QUANTITATIVE REQUIREMENT", same eventId
            # and section number as the actual class) — these are attribute
            # markers, not registrable sections, so drop them.
            if (sec.get("defaultCreditType") or "").upper() == "DUAL":
                continue
            key = _ay_term(sec)
            if key is None:
                continue
            buckets.setdefault(key, []).append(sec)
        self._sections_by_term = buckets
        return buckets

    # ---- driver overrides ----------------------------------------------------

    def schedule_pages(self):
        for key in sorted(self._fetch_all_sections().keys()):
            yield key

    def fetch_page(self, academic_year, term):
        return self._fetch_all_sections().get((academic_year, term))

    def parse_page(self, data, academic_year, term):
        if not data:
            return []
        url = self._search_url()
        rows = []
        for sec in data:
            event_id = (sec.get("eventId") or "").strip()
            course_code = _split_course_code(event_id)
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=(sec.get("section") or "").strip(),
                    course_name=(sec.get("eventName") or "").strip(),
                    instructor=_format_instructors(sec.get("instructors") or []),
                    time=_format_schedules(sec.get("schedules") or []),
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


# ---- formatting helpers ----------------------------------------------------


def _ay_term(section):
    """Return ((start_year, end_year), term_code) for a section, or None."""
    year = section.get("year")
    term = (section.get("term") or "").upper()
    if not year:
        return None
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    offset_code = TERM_MAP.get(term)
    if offset_code is None:
        for prefix, oc in TERM_PREFIX_MAP:
            if term.startswith(prefix):
                offset_code = oc
                break
    if offset_code is None:
        return None
    offset, code = offset_code
    start = y + offset
    return ((start, start + 1), code)


def _split_course_code(event_id):
    """Insert a space between the subject letters and the course number.

    PowerCampus returns ``"CSC141"``; we emit ``"CSC 141"`` for consistency
    with the other scrapers.
    """
    m = re.match(r"^([A-Za-z]+)\s*(.*)$", event_id)
    if not m:
        return event_id
    prefix, rest = m.group(1), m.group(2).strip()
    return f"{prefix} {rest}".strip()


def _format_instructors(instructors):
    seen = []
    for inst in instructors:
        name = (inst.get("fullName") or "").strip()
        if name and name not in seen:
            seen.append(name)
    return ", ".join(seen)


def _format_schedules(schedules):
    """Render the `schedules` array as `"MWF 10:35-11:25 (Roessner 200)"`.

    Multi-meeting sections (lecture + lab) are joined with `; `.
    """
    groups = {}
    order = []
    for sch in schedules:
        days = _format_days(sch.get("scheduledDays") or [])
        time_range = _format_time_range(sch.get("startTime"), sch.get("endTime"))
        location = _format_location(sch.get("bldgName"), sch.get("roomId"))
        if not days and not time_range and not location:
            continue
        key = (time_range, location)
        if key not in groups:
            groups[key] = days
            order.append(key)
        elif len(days) > len(groups[key]):
            groups[key] = days

    parts = []
    for key in order:
        time_range, location = key
        days = groups[key]
        bits = []
        if days:
            bits.append(days)
        if time_range:
            bits.append(time_range)
        s = " ".join(bits)
        if location:
            s = f"{s} ({location})" if s else f"({location})"
        if s:
            parts.append(s)
    return "; ".join(parts)


def _format_days(scheduled_days):
    present = set(int(d) for d in scheduled_days if d is not None)
    return "".join(DAY_ABBR[d] for d in DAY_ORDER if d in present)


def _format_time_range(start, end):
    s = _to_24h(start)
    e = _to_24h(end)
    if s and e:
        return f"{s}-{e}"
    return s or e or ""


def _to_24h(value):
    """Convert ``"11:00 AM"`` / ``"12:40 PM"`` to ``"11:00"`` / ``"12:40"``."""
    if not value:
        return ""
    s = str(value).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*([AaPp][Mm])?$", s)
    if not m:
        return s
    h = int(m.group(1))
    mm = m.group(2)
    suffix = (m.group(3) or "").upper()
    if suffix == "AM" and h == 12:
        h = 0
    elif suffix == "PM" and h != 12:
        h += 12
    return f"{h:02d}:{mm}"


def _format_location(building, room):
    building = (building or "").strip()
    room = (room or "").strip()
    # Building names like "Roessner Hall" are a little long; drop the
    # generic "Hall" suffix to match the compact style of other scrapers.
    building = re.sub(r"\s+Hall$", "", building, flags=re.I)
    return " ".join(x for x in [building, room] if x)


# ---- per-college configs ---------------------------------------------------

# Each entry is a dict with required keys `college`, `base_url`, `subject`:
#   - `base_url` has no trailing slash and no `/SELFSERV` suffix.
#   - `subject` is the course-code prefix (matched against `eventId`).
POWERCAMPUS_COLLEGES = [
    {"college": College.ALBRIGHT, "base_url": "https://selfservice.albright.edu", "subject": "CSC"},
    # Ohio Wesleyan hosts PowerCampus at a non-standard path (lowercase
    # `/selfserv`) and under campus.owu.edu rather than a selfservice.* host.
    {
        "college": College.OHIO_WESLEYAN,
        "base_url": "https://campus.owu.edu",
        "selfserv_path": "/selfserv",
        "subject": "CS",
    },
]


def _make_class(cfg):
    coll = cfg["college"]
    safe = re.sub(r"\W+", "", str(coll))
    attrs = {"college": coll}
    for key in ("base_url", "subject", "selfserv_path"):
        if key in cfg:
            attrs[key] = cfg[key]
    return type(f"{safe}PowerCampusScraper", (PowerCampusScraper,), attrs)


def powercampus_scrapers():
    """Return one scraper class per configured PowerCampus college."""
    return [_make_class(cfg) for cfg in POWERCAMPUS_COLLEGES]
