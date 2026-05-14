"""Banner 9 Student Registration Self-Service course schedule scraper.

A second large family of LACs runs Ellucian Banner 9 Student Registration
Self-Service ("SSB"), reachable at

    {host}/StudentRegistrationSsb/ssb/term/termSelection?mode=search

The user-facing UI is a multi-step form (pick term → pick subject → search
→ paginate), but the same UI is backed by a clean JSON API that is
identical across deployments. We hit it directly with `requests` (no
Selenium needed):

  1. ``GET  /StudentRegistrationSsb/ssb/classSearch/classSearch``
       Establishes a JSESSIONID cookie.
  2. ``GET  /StudentRegistrationSsb/ssb/classSearch/getTerms``
       Lists every term the deployment exposes (description like
       "Fall 2026" / "Spring Semester 2026 (View Only)").
  3. ``POST /StudentRegistrationSsb/ssb/term/search?mode=search``
       with ``term=<TERMCODE>`` to bind the active term to the session.
  4. ``GET  /StudentRegistrationSsb/ssb/searchResults/searchResults``
       with ``txt_subject=<SUBJ>&txt_term=<TERMCODE>&pageOffset=...``
       returns ``{ success, totalCount, data: [...] }``. We page through
       until we've collected ``totalCount`` rows.
  5. ``GET  /StudentRegistrationSsb/ssb/searchResults/getFacultyMeetingTimes``
       per CRN, only when step 4 returns empty ``faculty`` /
       ``meetingsFaculty`` arrays. Some deployments (e.g. Oberlin) don't
       inline that data on the list endpoint — they require this extra
       hop to populate it.
  6. ``POST /StudentRegistrationSsb/ssb/classSearch/resetDataForm``
       clears the term binding before the next term in the same session.

Banner term codes vary wildly per institution (Lafayette uses
202610/202630, Berea 202611/202512, Dickinson 202670/202720, etc.), so we
discover them at runtime from ``getTerms`` and map descriptions back to
``(academic_year, term)`` pairs rather than hardcoding any formula.

Each entry in ``BANNER9_COLLEGES`` is a ``(College, base_url, subject)``
tuple — adding a new school is a one-line change.
"""

import html
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

# "Fall 2026", "Fall Semester 2026", "Spring 2026 (View Only)",
# "Winter Term 2027" (Lawrence trimester), etc.
TERM_DESC_RE = re.compile(
    r"^\s*(?P<season>Fall|Spring|Winter)(?:\s+(?:Semester|Term))?\s+(?P<year>\d{4})\b",
    re.I,
)

DAY_FLAGS = [
    ("monday", "M"),
    ("tuesday", "T"),
    ("wednesday", "W"),
    ("thursday", "Th"),
    ("friday", "F"),
    ("saturday", "Sa"),
    ("sunday", "Su"),
]

# Page size accepted by every Banner 9 deployment we've tested. CS course
# counts are always well under this, so a single page suffices in practice.
PAGE_SIZE = 500


class Banner9Scraper(CourseScheduleScraper):
    """Base scraper for any Banner 9 SSB deployment.

    Subclass attributes:
        - ``base_url``: e.g. ``"https://selfservice.lafayette.edu"`` (no
          trailing slash, no ``/StudentRegistrationSsb`` suffix).
        - ``subject``: Banner subject code, e.g. ``"CS"``, ``"CSCI"``,
          ``"COMP"``, ``"CPSC"``, ``"CSC"``.
    """

    base_url: str = ""
    # Banner subject code. May be a single string (``"CS"``) or a list of
    # codes (``["COP", "CAP", ...]``) for deployments whose CS curriculum
    # spans multiple Banner subjects (common at Florida public-system
    # schools using the SCNS three-letter prefix system).
    subject = ""
    # Some multi-tenant deployments (e.g. csbsju, which hosts both College
    # of St Benedict and Saint John's) require an institution / "MEP" code
    # on every request, or every endpoint returns
    # `errorMessage="No Institution code specified in the URL"` (HTTP 500).
    # Leave blank for single-tenant deployments.
    mep_code: str = ""
    # Path prefix for the Banner SSB app. Most deployments expose it as
    # `/StudentRegistrationSsb`; a few (e.g. Lawrence) use a custom prefix
    # like `/prod-StudentRegistrationSsb`. Leave the leading slash.
    ssb_path: str = "/StudentRegistrationSsb"
    terms = ["F", "S"]
    fresh_driver_per_load = False
    request_timeout = 30
    search_timeout = 60

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None
        self._term_codes: dict | None = None  # (ay, term) -> banner code

    # ---- HTTP plumbing -------------------------------------------------------

    def _ssb(self, path):
        return f"{self.base_url}{self.ssb_path}/ssb{path}"

    def _with_mep(self, params=None):
        params = dict(params or {})
        if self.mep_code:
            params.setdefault("mepCode", self.mep_code)
        return params

    def _ensure_session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (cs-lac course-schedule scraper)",
                "Accept": "application/json, text/plain, */*",
            })
            # Establishes JSESSIONID and any per-deployment cookies.
            s.get(
                self._ssb("/classSearch/classSearch"),
                params=self._with_mep(),
                timeout=self.request_timeout,
                allow_redirects=True,
            )
            self._session = s
        return self._session

    def _discover_terms(self):
        if self._term_codes is not None:
            return self._term_codes
        s = self._ensure_session()
        # max=50 spans well over five academic years' worth of Fall/Spring/Summer/Interim.
        resp = s.get(
            self._ssb("/classSearch/getTerms"),
            params=self._with_mep({"searchTerm": "", "offset": 1, "max": 50}),
            timeout=self.request_timeout,
        )
        resp.raise_for_status()
        mapping = {}
        for entry in resp.json():
            code = (entry.get("code") or "").strip()
            desc = (entry.get("description") or "").strip()
            m = TERM_DESC_RE.match(desc)
            if not m or not code:
                continue
            season = m.group("season").capitalize()
            year = int(m.group("year"))
            if season == "Fall":
                ay, t = (year, year + 1), "F"
            elif season == "Winter":
                # Trimester schools (e.g. Lawrence) put Winter in the
                # middle of the academic year (Winter 2027 = AY 2026-27).
                ay, t = (year - 1, year), "W"
            else:  # Spring
                ay, t = (year - 1, year), "S"
            # If a description appears twice (rare), keep the first which is
            # usually the most recent / canonical entry.
            mapping.setdefault((ay, t), code)
        self._term_codes = mapping
        return mapping

    # ---- driver overrides ----------------------------------------------------

    def schedule_pages(self):
        mapping = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in self.terms:
                if (ay, t) in mapping:
                    yield ay, t

    def fetch_page(self, academic_year, term):
        mapping = self._discover_terms()
        code = mapping.get((academic_year, term))
        if code is None:
            return None
        s = self._ensure_session()

        subjects = [self.subject] if isinstance(self.subject, str) else list(self.subject)
        all_rows = []
        for subj in subjects:
            # Reset + re-bind the term before each subject query. Banner
            # caches the first search per binding and would otherwise return
            # the first subject's results for every subsequent subject in
            # the same binding (observed on NCF). Single-subject deployments
            # pay a tiny extra cost but stay correct.
            self._reset_form(s)
            s.post(
                self._ssb("/term/search"),
                params=self._with_mep({"mode": "search"}),
                data={
                    "term": code,
                    "studyPath": "",
                    "studyPathText": "",
                    "startDatepicker": "",
                    "endDatepicker": "",
                },
                timeout=self.request_timeout,
            ).raise_for_status()
            collected = 0
            offset = 0
            while True:
                resp = s.get(
                    self._ssb("/searchResults/searchResults"),
                    params=self._with_mep({
                        "txt_subject": subj,
                        "txt_term": code,
                        "startDatepicker": "",
                        "endDatepicker": "",
                        "pageOffset": offset,
                        "pageMaxSize": PAGE_SIZE,
                        "sortColumn": "subjectDescription",
                        "sortDirection": "asc",
                    }),
                    timeout=self.search_timeout,
                )
                resp.raise_for_status()
                payload = resp.json()
                rows = payload.get("data") or []
                all_rows.extend(rows)
                collected += len(rows)
                total = payload.get("totalCount") or 0
                if not rows or collected >= total:
                    break
                offset += PAGE_SIZE

        # Some deployments (Oberlin, etc.) leave faculty / meetingsFaculty
        # empty on the list endpoint and require a per-CRN hop. Hydrate
        # those rows individually; deployments that already inline the data
        # incur zero extra calls.
        for row in all_rows:
            if (row.get("faculty") or row.get("meetingsFaculty")):
                continue
            crn = row.get("courseReferenceNumber")
            if not crn:
                continue
            try:
                fr = s.get(
                    self._ssb("/searchResults/getFacultyMeetingTimes"),
                    params=self._with_mep({"term": code, "courseReferenceNumber": crn}),
                    timeout=self.request_timeout,
                )
                fr.raise_for_status()
            except requests.RequestException:
                continue
            try:
                fmt = (fr.json() or {}).get("fmt") or []
            except ValueError:
                continue
            row["meetingsFaculty"] = fmt
            # `fmt` entries each carry a `faculty` array; flatten to the
            # top-level `faculty` field for uniform downstream handling.
            faculty = []
            for entry in fmt:
                for f in entry.get("faculty") or []:
                    faculty.append(f)
            row["faculty"] = faculty

        # Clear the term binding so the next iteration starts clean. Some
        # deployments otherwise leak state across term/search posts.
        self._reset_form(s)

        return all_rows

    def _reset_form(self, s):
        try:
            s.post(
                self._ssb("/classSearch/resetDataForm"),
                params=self._with_mep(),
                timeout=self.request_timeout,
            )
        except requests.RequestException:
            pass

    def parse_page(self, data, academic_year, term):
        if not data:
            return []
        url = self._ssb("/classSearch/classSearch")
        rows = []
        for entry in data:
            subject = (entry.get("subject") or "").strip()
            number = (entry.get("courseNumber") or "").strip()
            if subject and number:
                course_code = f"{subject} {number}"
            else:
                course_code = (entry.get("subjectCourse") or "").strip()
            section = (entry.get("sequenceNumber") or "").strip()
            course_name = _clean(entry.get("courseTitle"))
            instructor = _format_faculty(entry.get("faculty") or [])
            time_str = _format_meetings(entry.get("meetingsFaculty") or [])
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


# ---- formatting helpers ----------------------------------------------------


def _clean(text):
    """HTML-unescape and collapse whitespace; Banner emits raw entities."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _format_faculty(faculty):
    primary = []
    others = []
    for f in faculty:
        name = _clean(f.get("displayName"))
        if not name:
            continue
        (primary if f.get("primaryIndicator") else others).append(name)
    seen = []
    for n in primary + others:
        if n not in seen:
            seen.append(n)
    return ", ".join(seen)


def _format_meetings(meetings_faculty):
    """Render a `meetingsFaculty` array as `"MWF 10:35-11:25 (RISC 362)"`.

    Multi-meeting sections (e.g. lecture + lab) are joined with `; `.
    """
    groups = {}  # (time_range, location) -> day string
    order = []
    for m in meetings_faculty:
        mt = m.get("meetingTime") or {}
        days = "".join(abbr for k, abbr in DAY_FLAGS if mt.get(k))
        time_range = _format_time_range(mt.get("beginTime"), mt.get("endTime"))
        building = _clean(mt.get("building"))
        room = _clean(mt.get("room"))
        location = " ".join(x for x in [building, room] if x)
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


def _format_time_range(start, end):
    s = _format_hhmm(start)
    e = _format_hhmm(end)
    if s and e:
        return f"{s}-{e}"
    return s or e or ""


def _format_hhmm(value):
    if not value:
        return ""
    s = str(value).strip()
    if len(s) == 4 and s.isdigit():
        return f"{s[:2]}:{s[2:]}"
    return s


# ---- per-college configs ---------------------------------------------------

# Each entry is a dict with required keys `college`, `base_url`, `subject`
# and optional `mep_code`, `ssb_path`, `terms`:
#   - `base_url` has no trailing slash and no `/StudentRegistrationSsb` suffix.
#   - `mep_code` is only set for multi-tenant deployments that require an
#     institution code on every request (e.g. csbsju, which hosts both
#     College of St Benedict and Saint John's).
#   - `ssb_path` defaults to `"/StudentRegistrationSsb"`; override for hosts
#     that put the SSB app under a different path (e.g. Lawrence's
#     `/prod-StudentRegistrationSsb`).
#   - `terms` defaults to `["F", "S"]`; trimester schools like Lawrence
#     add `"W"`.
BANNER9_COLLEGES = [
    {"college": College.ALBION, "base_url": "https://adminpagesprod02.albion.edu:7443", "subject": "CS"},
    {"college": College.BEREA, "base_url": "https://b9student-prod.berea.edu:8444", "subject": "CSC"},
    {"college": College.CONCORDIA, "base_url": "https://banner.cord.edu", "subject": "CSC"},
    {"college": College.CONNECTICUT, "base_url": "https://reg-prod.ec.conncoll.edu", "subject": "COM"},
    {"college": College.DENISON, "base_url": "https://banner.denison.edu", "subject": "CS"},
    {"college": College.DICKINSON, "base_url": "https://bannercprod.dickinson.edu", "subject": "COMP"},
    {"college": College.ECKERD, "base_url": "https://regssb-prod.ban.eckerd.edu", "subject": "CS"},
    {"college": College.LAFAYETTE, "base_url": "https://selfservice.lafayette.edu", "subject": "CS"},
    {"college": College.LAWRENCE, "base_url": "https://bannerweb.lawrence.edu", "subject": "CMSC",
     "ssb_path": "/prod-StudentRegistrationSsb", "terms": ["F", "W", "S"]},
    {"college": College.MARY_WASHINGTON, "base_url": "https://reg-prod.ec.umw.edu", "subject": "CPSC"},
    # NCF switched from local CSCI/DATA prefixes to FL state SCNS three-letter
    # codes (CAI/CAP/CDA/CEN/CIS/COP/COT) around Fall 2025; we keep both to
    # span the full multi-year history.
    {"college": College.NEW_FLORIDA, "base_url": "https://banapps02.ncf.edu",
     "subject": ["CAI", "CAP", "CDA", "CEN", "CIS", "COP", "COT", "CSCI", "DATA"]},
    {"college": College.OBERLIN, "base_url": "https://banner.cc.oberlin.edu", "subject": "CSCI"},
    {"college": College.SKIDMORE, "base_url": "https://bannerxe.skidmore.edu", "subject": "CS"},
    {"college": College.ST_BENEDICT, "base_url": "https://registration.csbsju.edu", "subject": "CSCI", "mep_code": "B"},
    {"college": College.STONEHILL, "base_url": "https://xessb.stonehill.edu", "subject": "CSC"},
    {"college": College.SWARTHMORE, "base_url": "https://studentregistration.swarthmore.edu", "subject": "CPSC"},
    {"college": College.WHEATON_MA, "base_url": "https://banprodselfservice.wheatonma.edu:7341", "subject": "COMP"},
]


def _make_class(cfg):
    coll = cfg["college"]
    safe = re.sub(r"\W+", "", str(coll))
    attrs = {"college": coll}
    for key in ("base_url", "subject", "mep_code", "ssb_path", "terms"):
        if key in cfg:
            attrs[key] = cfg[key]
    return type(f"{safe}Banner9Scraper", (Banner9Scraper,), attrs)


def banner9_scrapers():
    """Return one scraper class per configured Banner 9 college."""
    return [_make_class(cfg) for cfg in BANNER9_COLLEGES]
