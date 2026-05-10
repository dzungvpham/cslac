"""Smith College course schedule scraper.

Smith's course search lives in an iframe at
``https://www.smith.edu/apps/course_search/``. The form is GET-submitted with
``term=<code>&dept=CSC&csrf_token=<token>&op=Submit&...``; the CSRF token is
issued by the page on first load and is bound to the session cookie. One
token is good for many subsequent requests in the same session, so we fetch
the form once, scrape the token, then reuse it across all (year, term)
pages.

Term codes are six digits, ``<acad_year_end><season>``, e.g. for AY 2025-26:

  * ``202601`` = Fall 2025      (`F`)
  * ``202602`` = Interterm 2026 (`W` — Smith's J-term)
  * ``202603`` = Spring 2026    (`S`)
  * ``202604`` = Summer 2026    (`Su`)

Each ``<article class="course campus-course-search-result">`` is one section
with the section header (``course-dept``, ``course-course-num``,
``course-section-num``, ``course-section-title``, ``course-section-instructor``)
plus a collapsed details panel that's already in the DOM (``course-meeting``,
``course-type``, etc.) — no need to "click" each result, the data is
inlined. Cross-listed sections appear once per cross-listing in a `dept=CSC`
search; we dedupe by (course_code, section).
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

SEARCH_URL = "https://www.smith.edu/apps/course_search/"

# Day-name -> short code, matching the convention used elsewhere in this
# package (Carleton, Middlebury, Macalester).
DAY_ABBREV = {
    "sunday": "Su",
    "monday": "M",
    "tuesday": "T",
    "wednesday": "W",
    "thursday": "Th",
    "friday": "F",
    "saturday": "Sa",
}

# "Tuesday/Thursday | 1:20 PM - 2:35 PM / Sabin-Reed 106"
# Days, time, and location are all optional — TBA / async sections appear
# with just one or two of the three pieces present.
MEETING_RE = re.compile(
    r"^(?:(?P<days>[A-Za-z/, ]+?)\s*\|\s*)?"
    r"(?P<time>[\d: APMapm.\-–]+?)?"
    r"(?:\s*/\s*(?P<loc>.+))?$"
)


class SmithScraper(CourseScheduleScraper):
    college = College.SMITH
    terms = ["F", "W", "S", "Su"]

    # We hit Smith via plain `requests` and never spin up Selenium.
    # `fetch_page` is fully overridden below; the base class's Selenium
    # plumbing is unused.
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._session = None
        self._csrf = None

    def _ensure_session(self):
        if self._session is not None and self._csrf is not None:
            return
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
        r = self._session.get(SEARCH_URL, timeout=self.page_load_timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        token_el = soup.find("input", {"name": "csrf_token"})
        if token_el is None or not token_el.get("value"):
            raise RuntimeError("Smith course search: csrf_token not found on form page")
        self._csrf = token_el["value"]

    def url_for(self, academic_year, term):
        # Returned only for debugging/logging — `fetch_page` builds its own
        # request so the csrf_token doesn't leak into stale URLs.
        code = self._term_code(academic_year, term)
        if code is None:
            return None
        return f"{SEARCH_URL}?term={code}&dept=CSC"

    def fetch_page(self, academic_year, term):
        code = self._term_code(academic_year, term)
        if code is None:
            return None
        self._ensure_session()
        params = {
            "term": code,
            "dept": "CSC",
            "subject": "",
            "instructor": "",
            "instr_method": "",
            "credits": "",
            "course_number": "",
            "course_keyword": "",
            "csrf_token": self._csrf,
            "op": "Submit",
            "form_id": "campus_course_search_basic_search_form",
        }
        r = self._session.get(SEARCH_URL, params=params, timeout=self.page_load_timeout)
        r.raise_for_status()
        return r.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        seen = set()
        for art in soup.select("article.course.campus-course-search-result"):
            row = self._parse_article(art, academic_year, term)
            if row is None:
                continue
            key = (row["course_code"], row["section"])
            if key in seen:
                # Cross-listed sections show up once per cross-listing.
                continue
            seen.add(key)
            rows.append(row)
        return rows

    def _parse_article(self, art, academic_year, term):
        subj = _text(art.select_one(".course-course-subject")) or _text(
            art.select_one(".course-dept")
        )
        num = _text(art.select_one(".course-course-num"))
        if not subj or not num:
            return None
        course_code = f"{subj} {num}"

        section = _text(art.select_one(".course-section-num"))

        title_el = art.select_one(".course-section-title")
        course_name = ""
        url = ""
        if title_el is not None:
            course_name = _clean(title_el.get_text(" ", strip=True))
            link = title_el.find("a")
            if link is not None:
                href = link.get("href", "")
                if href.startswith("#"):
                    # In-page collapse anchor — append to the search base URL
                    # so the link points at the relevant fragment.
                    url = SEARCH_URL + href
                elif href:
                    url = href

        instructor = _text(art.select_one(".course-section-instructor"))

        meeting_el = art.select_one(".course-result-detail.course-meeting")
        time_str = _format_meeting(_extract_dd(meeting_el))

        return self.make_row(
            academic_year,
            term,
            course_code=course_code,
            section=section,
            course_name=course_name,
            instructor=instructor,
            time=time_str,
            url=url,
        )

    @staticmethod
    def _term_code(academic_year, term):
        _, end = academic_year
        if term == "F":
            return f"{end}01"
        if term == "W":
            return f"{end}02"
        if term == "S":
            return f"{end}03"
        if term == "Su":
            return f"{end}04"
        return None


# ---- helpers ---------------------------------------------------------------


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _text(el):
    return _clean(el.get_text(" ", strip=True)) if el is not None else ""


def _extract_dd(el):
    """The meeting span is ``<strong>Time/Location:</strong> <value>``;
    return just the value part.
    """
    if el is None:
        return ""
    text = _clean(el.get_text(" ", strip=True))
    return re.sub(r"^Time/Location:\s*", "", text, flags=re.I)


def _format_meeting(raw):
    """``"Tuesday/Thursday | 1:20 PM - 2:35 PM / Sabin-Reed 106"`` ->
    ``"TTh 1:20 PM-2:35 PM (Sabin-Reed 106)"``.

    Falls back to the raw string if it doesn't fit the expected shape — e.g.
    "TBA" / async sections show up with non-standard text and we'd rather
    surface the original than silently drop it.
    """
    if not raw:
        return ""
    m = MEETING_RE.match(raw)
    if not m:
        return raw
    days_text = (m.group("days") or "").strip()
    time_text = _clean((m.group("time") or "").replace(" - ", "-"))
    loc_text = _clean(m.group("loc") or "")

    abbrevs = []
    # Days come back as e.g. "Tuesday/Thursday" or "Monday, Wednesday".
    for part in re.split(r"[\s,/]+", days_text):
        key = part.strip().lower()
        if key in DAY_ABBREV:
            abbrevs.append(DAY_ABBREV[key])
    days = "".join(abbrevs)

    bits = []
    if days:
        bits.append(days)
    if time_text:
        bits.append(time_text)
    out = " ".join(bits)
    if loc_text:
        out = f"{out} ({loc_text})" if out else f"({loc_text})"
    return out or raw
