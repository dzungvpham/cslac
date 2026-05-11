"""Randolph-Macon College course schedule scraper.

R-MC runs Jenzabar Mobile (`mymaconweb.rmc.edu/m/`) and exposes a public
course search at `/CourseSearch/SearchResults`. The page is plain
server-rendered HTML — no auth or JS required — so we use `requests`.

Term codes are `YYYY;NN`: `22` = Fall of `YYYY`, `42` = Spring of `YYYY+1`
(same academic year). E.g. `2025;22` = Fall 2025, `2025;42` = Spring 2026.

Each section is a `<div data-role="collapsible" data-coursekey="…">`
whose heading is `"CSCI NNN SS"` + course title, with sub-divs for the
instructor (`Taught by: …`), seat counts, and meeting time/location
(`Meets <span>DAYS TIME <br/> at ROOM on the CAMPUS</span>`).
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE = "https://mymaconweb.rmc.edu"
SEARCH_PATH = (
    "/m/d/m/5c62616e-9463-484d-8fd8-180250661411/CourseSearch/SearchResults"
)
SUBJECT = "CSCI"

# "CSCI 106 01" -> code="CSCI 106", section="01".
HEADING_RE = re.compile(r"^\s*(?P<code>[A-Z]+\s+\d+\w*)\s+(?P<section>\w+)\s*$")

# `data-coursekey` uses two spaces between course number and section
# (e.g. `"CSCI 106  01"`); we don't depend on that, but normalize whitespace.
TERM_SUFFIX = {"F": "22", "S": "42"}


class RandolphMaconScraper(CourseScheduleScraper):
    college = College.RANDOLPH_MACON
    terms = ["F", "S"]
    # Pure-HTML endpoint, no Selenium needed.
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None

    def _ensure_session(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "Mozilla/5.0 (cs-lac scraper)"})
        return self._session

    @staticmethod
    def _termcode(academic_year, term):
        start, _end = academic_year
        # Both F (Fall start_year) and S (Spring end_year) use start_year as
        # the prefix; the suffix distinguishes the term.
        return f"{start};{TERM_SUFFIX[term]}"

    def url_for(self, academic_year, term):
        # `openseats=OpenFull` returns all sections including filled ones.
        return (
            f"{BASE}{SEARCH_PATH}"
            f"?termcode={self._termcode(academic_year, term)}"
            f"&title=&code=&department={SUBJECT}"
            f"&faculty=&campus=&additional=&openseats=OpenFull&add=T"
        )

    def fetch_page(self, academic_year, term):
        s = self._ensure_session()
        resp = s.get(self.url_for(academic_year, term), timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for item in soup.select("div[data-coursekey]"):
            heading = item.select_one("h3 span.boldText")
            if heading is None:
                continue
            heading_text = _clean(heading.get_text(" "))
            m = HEADING_RE.match(heading_text)
            if m:
                course_code = m.group("code")
                section = m.group("section")
            else:
                course_code, section = heading_text, ""

            course_name = _course_name(item)
            instructor = _instructor(item)
            meeting = _meeting(item)
            url = ""
            link = item.select_one("a#details, a[href*=CourseDetails]")
            if link and link.get("href"):
                href = link["href"]
                url = href if href.startswith("http") else f"{BASE}{href}"

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=meeting,
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


def _course_name(item):
    # Title sits inside the same `<span class="center-classList">` as the
    # bold "CSCI 106 01" heading, as a NavigableString after the `<br>`.
    span = item.select_one("h3 span.center-classList")
    if span is None:
        return ""
    parts = [
        _clean(child) for child in span.children if isinstance(child, NavigableString)
    ]
    parts = [p for p in parts if p]
    return parts[0] if parts else ""


def _instructor(item):
    for div in item.select("div.center-classList.textWrapping"):
        text = div.get_text(" ", strip=True)
        if not text.startswith("Taught by"):
            continue
        names = [_clean(s.get_text(" ")) for s in div.find_all("span")]
        names = [n for n in names if n]
        if names:
            return ", ".join(names)
        # Fallback: strip the "Taught by:" prefix.
        return _clean(text[len("Taught by:") :])
    return ""


def _meeting(item):
    for div in item.select("div.center-classList.subtext"):
        text = div.get_text(" ", strip=True)
        if not text.startswith("Meets"):
            continue
        span = div.find("span")
        if span is None:
            return _clean(text[len("Meets") :])
        # Within the span: "<days/time> <br/> at <room> on the <campus>".
        # Render `<br>` as " — " to keep time and location readable.
        parts = []
        for child in span.children:
            if getattr(child, "name", None) == "br":
                parts.append(" — ")
            else:
                parts.append(child.get_text(" ") if hasattr(child, "get_text") else str(child))
        return _clean("".join(parts))
    return ""


def _clean(text):
    return re.sub(r"\s+", " ", str(text) if text is not None else "").strip()
