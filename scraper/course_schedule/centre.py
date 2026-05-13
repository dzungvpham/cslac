"""Centre College course schedule scraper.

Centre publishes term schedules as PDFs under a Jenzabar (Centrenet)
file server. The public URL is

    https://centrenet.centre.edu/ICS/icsfs/mm/{sp|fa}{YY}.pdf

but Centrenet rejects the request without a per-file `target=<guid>`
query parameter — the unparameterized URL just renders the Centrenet
shell. The `target` GUID is randomly assigned per upload and is not
discoverable from the Centrenet UI without a login, so we look it up
via a web search for the bare URL: search results (Brave) include the
full URL with the right `target` value as their first hit.

Each resolved URL is cached in `centre_pdf_urls.json` next to the
output CSV so subsequent runs of any past term skip the network search
entirely. The PDF itself is parsed with `pdfplumber`: the relevant
section starts at a "Computer Science" header and ends at the next
department header. CSC rows look like

    CSC 170 Programming and Problem Solving 4 a D. Toth 8:00- 10:00AM -M-W-F- OLIN 208
    4 b W Bailey 1:50- 3:50PM -M-W-F- OLIN 208

The first form is a new course; the second is an additional section of
the prior course (credits + section letter, then instructor/time/days/
room). Lines lacking both a `CSC ###` prefix and a `<credits> <letter>`
prefix are additional meeting times for the prior section and are
folded into that row's `time` field.

CentreTerm (January) PDFs are formatted as free-form prose, not a
table; only fall/spring are scraped here.
"""

import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import pdfplumber
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

PDF_BASE = "https://centrenet.centre.edu/ICS/icsfs/mm/{code}.pdf"
SEARCH_URL = "https://search.brave.com/search"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CACHE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "course_schedule"
    / "centre_pdf_urls.json"
)

# Time can be "8:00-9:00AM", "12:40- 1:40PM" (stray space after the dash),
# or "TBA".
TIME_RE = re.compile(
    r"(?P<time>\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM)?|TBA)"
)
# Day mask: 7-position string of dashes and weekday letters
# (e.g. `-M-W-F-`, `--T-R--`, `-------`).
DAYS_RE = re.compile(r"(?P<days>(?:[-MTWRFSU]){5,8})")
NEW_COURSE_RE = re.compile(
    r"^(?P<code>CSC\s+\d+[A-Z]*)\s+(?P<name>.+?)\s+"
    r"(?P<credits>\d+)\s+(?P<section>[a-z])\s+(?P<rest>.+)$"
)
NEW_SECTION_RE = re.compile(
    r"^(?P<credits>\d+)\s+(?P<section>[a-z])\s+(?P<rest>.+)$"
)


class CentreScraper(CourseScheduleScraper):
    college = College.CENTRE
    terms = ["F", "S"]

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._cache = _load_cache()

    def _term_code(self, academic_year, term):
        start, end = academic_year
        if term == "F":
            return f"fa{start % 100:02d}"
        if term == "S":
            return f"sp{end % 100:02d}"
        raise ValueError(f"unsupported term: {term!r}")

    def url_for(self, academic_year, term):
        return PDF_BASE.format(code=self._term_code(academic_year, term))

    def _resolve_url(self, code):
        cached = self._cache.get(code)
        if cached:
            return cached
        bare_url = PDF_BASE.format(code=code)
        pat = re.compile(
            r"https?://centrenet\.centre\.edu/ICS/icsfs/mm/"
            + re.escape(code)
            + r"\.pdf\?target=[a-f0-9-]+"
        )
        # Brave rate-limits aggressively — give one polite retry on 429s
        # and otherwise rely on the cache to keep query volume tiny.
        for attempt in range(2):
            try:
                resp = requests.get(
                    SEARCH_URL,
                    params={"q": bare_url},
                    headers={"User-Agent": USER_AGENT},
                    timeout=15,
                )
            except requests.RequestException:
                time.sleep(5)
                continue
            if resp.status_code == 429:
                time.sleep(15)
                continue
            if resp.status_code != 200:
                return None
            m = pat.search(resp.text)
            if m:
                resolved = m.group(0)
                self._cache[code] = resolved
                _save_cache(self._cache)
                return resolved
            return None
        return None

    def fetch_page(self, academic_year, term):
        code = self._term_code(academic_year, term)
        url = self._resolve_url(code)
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
        except requests.RequestException:
            return None
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)

    def parse_page(self, text, academic_year, term):
        # Slice out the Computer Science section: from the standalone
        # "Computer Science" line until the next department header. CS at
        # Centre is short and always fits on one page.
        lines = text.splitlines()
        try:
            start = next(
                i for i, line in enumerate(lines)
                if line.strip() == "Computer Science"
            )
        except StopIteration:
            return []

        rows = []
        last_course_code = ""
        last_course_name = ""
        for line in lines[start + 1:]:
            stripped = line.strip()
            if not stripped:
                continue
            m = NEW_COURSE_RE.match(stripped)
            if m:
                last_course_code = _clean(m.group("code"))
                last_course_name = _clean(m.group("name"))
                row = _parse_rest(
                    self,
                    academic_year,
                    term,
                    last_course_code,
                    last_course_name,
                    m.group("section"),
                    m.group("rest"),
                )
                if row is not None:
                    rows.append(row)
                continue
            m = NEW_SECTION_RE.match(stripped)
            if m and last_course_code:
                row = _parse_rest(
                    self,
                    academic_year,
                    term,
                    last_course_code,
                    last_course_name,
                    m.group("section"),
                    m.group("rest"),
                )
                if row is not None:
                    rows.append(row)
                continue
            # Either an additional meeting time for the prior row (a line
            # that holds another instructor/time/days/room without a
            # credits prefix) or a line from the next department, signaling
            # the end of the CS section.
            if rows and _looks_like_meeting(stripped):
                meeting_time = _extract_time(stripped)
                if meeting_time:
                    rows[-1]["time"] = (
                        f"{rows[-1]['time']} / {meeting_time}".strip(" /")
                    )
                continue
            # Anything else: we've left the Computer Science section.
            break

        return rows


def _parse_rest(scraper, academic_year, term, course_code, course_name, section, rest):
    """Extract instructor/time/days from the trailing portion of a row."""
    rest = _clean(rest)
    time_m = TIME_RE.search(rest)
    if not time_m:
        return None
    instructor = _clean(rest[: time_m.start()])
    after_time = rest[time_m.end():].strip()
    days_m = DAYS_RE.match(after_time)
    days = _clean(days_m.group("days")) if days_m else ""
    meeting = _clean(f"{days} {time_m.group('time')}".strip())
    return scraper.make_row(
        academic_year,
        term,
        course_code=course_code,
        section=section,
        course_name=course_name,
        instructor=instructor,
        time=meeting,
    )


def _looks_like_meeting(line):
    return bool(TIME_RE.search(line))


def _extract_time(line):
    time_m = TIME_RE.search(line)
    if not time_m:
        return ""
    after_time = line[time_m.end():].strip()
    days_m = DAYS_RE.match(after_time)
    days = _clean(days_m.group("days")) if days_m else ""
    return _clean(f"{days} {time_m.group('time')}".strip())


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _load_cache():
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))
