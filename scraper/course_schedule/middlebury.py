"""Middlebury College course schedule scraper.

Middlebury's catalog runs at
``catalog.middlebury.edu/offerings/search/catalog-MCUG`` — a server-rendered
search form. We submit a GET with ``term=term-<TERMCODE>`` and
``department=topic-subject-CSCI``; results are paginated via ``page=N``.

Term codes are six digits, ``<calendar_year><season>``:

  * ``90`` = Fall (in the *start* year of the academic year)
  * ``10`` = Winter / J-term (end year)
  * ``20`` = Spring (end year)
  * ``65`` = Summer Study (end year)

E.g. AY 2025-26 -> ``202590`` (F25), ``202610`` (W26), ``202620`` (S26),
``202665`` (Su26 — appears in the dropdown the following spring).

Each ``<div class="catalog-result-card">`` is one section. The header link's
text encodes course + section + term shorthand (``CSCI0145A-F25``); a ``<dl>``
of ``<dt>`` / ``<dd>`` pairs holds Type, Term, Instructors, Location,
Schedule, etc. The schedule cell looks like
``"11:15am-12:30pm on Monday, Wednesday (Sep 8, 2025 to Dec 8, 2025)"``.

The site 403s plain ``requests`` (Cloudflare gate), and the gate also fires
on the second navigation within a single Selenium session — page=1 returns
results but page=2 in the same driver gets an interstitial. We work around
this by spawning a fresh driver per page (``fresh_driver_per_load = True``).
"""

import re
import sys
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://catalog.middlebury.edu/offerings/search/catalog-MCUG"

# All section types we want to include. The form defaults check only LCT and
# SEM; we want labs, discussions, etc. too so CS faculty teaching loads are
# captured.
OFFERING_TYPES = [
    "genera:offering-LCT",
    "genera:offering-LAB",
    "genera:offering-DSC",
    "genera:offering-DR1",
    "genera:offering-IND",
    "genera:offering-PE",
    "genera:offering-SCR",
    "genera:offering-SEM",
    "genera:offering-SNR",
    "genera:offering-SNZ",
]

# "CSCI0145A-F25" -> subject "CSCI", number "0145", section "A".
# Section is sometimes more than one letter; the trailing "-F25" is a term
# shorthand we ignore (we already know the term from the request).
COURSE_ID_RE = re.compile(
    r"^(?P<subject>[A-Z]+)(?P<num>\d+)(?P<sec>[A-Z0-9]*)-[A-Z]+\d{2}$"
)

# Schedule cell: "<time> on <days> (<date range>)". Date range is optional.
SCHEDULE_RE = re.compile(
    r"^(?P<time>.+?)\s+on\s+(?P<days>[^()]+?)(?:\s*\(.*\))?\s*$"
)

DAY_ABBREV = {
    "sunday": "Su",
    "monday": "M",
    "tuesday": "T",
    "wednesday": "W",
    "thursday": "Th",
    "friday": "F",
    "saturday": "Sa",
}


class MiddleburyScraper(CourseScheduleScraper):
    college = College.MIDDLEBURY
    terms = ["F", "W", "S", "Su"]
    fresh_driver_per_load = True
    post_load_sleep = 0.5

    # Hard cap so a runaway pagination loop can't spin forever.
    MAX_PAGES = 50

    def url_for(self, academic_year, term, page=1):
        code = self._term_code(academic_year, term)
        if code is None:
            return None
        # Two Middlebury-specific quirks force us to build the query string
        # by hand instead of using `urlencode`:
        #   1. The site's pagination uses indexed array syntax
        #      (`type[0]=...&type[1]=...`); the unindexed `type[]=...` form
        #      works on page 1 but returns zero results when combined with
        #      `page=N>1`.
        #   2. The values themselves contain a literal `:` (e.g.
        #      `genera:offering-LCT`) and the backend treats `genera%3A...`
        #      as a different value entirely. We have to leave `:` unencoded.
        params = [
            ("term", f"term-{code}"),
            ("department", "topic-subject-CSCI"),
            ("keywords", ""),
        ]
        for i, t in enumerate(OFFERING_TYPES):
            params.append((f"type[{i}]", t))
        params.append(("days_mode", "inclusive"))
        params.append(("level[0]", "topic-level-UG"))
        params.append(("search", "Search"))
        if page > 1:
            params.append(("page", str(page)))
        query = "&".join(f"{quote(k, safe='')}={quote(v, safe=':')}" for k, v in params)
        return f"{BASE_URL}?{query}"

    def fetch_page(self, academic_year, term):
        """Walk pagination, returning concatenated card HTML for the term.

        We extract just the result cards from each page and stitch them into
        a single synthetic document so the standard `parse_page` contract
        still applies (one HTML string in, one row list out).
        """
        first_url = self.url_for(academic_year, term)
        if first_url is None:
            return None
        html = self.load(first_url)
        soup = BeautifulSoup(html, "html.parser")
        max_page = _max_page(soup)
        all_cards = [str(c) for c in soup.select("div.catalog-result-card")]
        page = 2
        while page <= min(max_page, self.MAX_PAGES):
            html = self.load(self.url_for(academic_year, term, page=page))
            page_soup = BeautifulSoup(html, "html.parser")
            cards = page_soup.select("div.catalog-result-card")
            if not cards:
                break
            all_cards.extend(str(c) for c in cards)
            # In case max_page wasn't reachable from page 1 (large result
            # sets sometimes only show a windowed pagination range), keep
            # extending the bound from each page we visit.
            max_page = max(max_page, _max_page(page_soup))
            page += 1
        return "<html><body>" + "".join(all_cards) + "</body></html>"

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for card in soup.select("div.catalog-result-card"):
            row = self._parse_card(card, academic_year, term)
            if row is not None:
                rows.append(row)
        return rows

    def _parse_card(self, card, academic_year, term):
        link = card.select_one("p.f3 a")
        if link is None:
            return None
        link_text = _clean(link.get_text(" ", strip=True))
        course_code, section = _split_course_id(link_text)
        href = link.get("href", "")
        url = f"https://catalog.middlebury.edu{href}" if href.startswith("/") else href

        # Lab/sub sections render the H3 as two lines:
        #   "Introduction to Computing\nIntroduction to Computing Lab"
        # The second line is the more specific name; collapsing the H3 with
        # `get_text(" ")` would yield the duplicated string. Keep only the
        # last non-empty line.
        title_el = card.select_one("h3")
        course_name = ""
        if title_el is not None:
            lines = [
                _clean(line)
                for line in title_el.get_text("\n").splitlines()
                if _clean(line)
            ]
            course_name = lines[-1] if lines else ""

        info = {}
        for div in card.select("dl > div"):
            dt = div.find("dt")
            dd = div.find("dd")
            if dt is None or dd is None:
                continue
            key = _clean(dt.get_text(" ", strip=True)).rstrip(":")
            val = _clean(dd.get_text(" ", strip=True))
            info[key] = val

        instructor = info.get("Instructors", "")
        time_str = _format_schedule(info.get("Schedule", ""))

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
        start, end = academic_year
        if term == "F":
            return f"{start}90"
        if term == "W":
            return f"{end}10"
        if term == "S":
            return f"{end}20"
        if term == "Su":
            return f"{end}65"
        return None


# ---- helpers ---------------------------------------------------------------


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _max_page(soup):
    """Return the largest numbered page link in the pagination, or 1."""
    max_page = 1
    for a in soup.select(".pagination__link"):
        m = re.search(r"[?&]page=(\d+)", a.get("href", ""))
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def _split_course_id(text):
    """``CSCI0145A-F25`` -> (``"CSCI 0145"``, ``"A"``).

    Falls back to (raw text, "") if the pattern doesn't match — preserves
    whatever the catalog showed without losing the row.
    """
    m = COURSE_ID_RE.match(text or "")
    if not m:
        return text or "", ""
    return f"{m.group('subject')} {m.group('num')}", m.group("sec") or ""


def _format_schedule(raw):
    """``"11:15am-12:30pm on Monday, Wednesday (Sep 8, ...)"`` -> ``"MW 11:15am-12:30pm"``.

    Strips the date range (we already know the term). Returns the original
    string if it doesn't fit the expected shape.
    """
    if not raw:
        return ""
    m = SCHEDULE_RE.match(raw)
    if not m:
        return raw
    days_text = m.group("days")
    time_text = _clean(m.group("time"))
    abbrevs = []
    for part in re.split(r"\s*,\s*", days_text):
        key = part.strip().lower()
        if key in DAY_ABBREV:
            abbrevs.append(DAY_ABBREV[key])
    days = "".join(abbrevs)
    if days and time_text:
        return f"{days} {time_text}"
    return time_text or days
