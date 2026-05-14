"""Course-schedule scraper for The University of the South (Sewanee).

The Sewanee registrar exposes a fully server-rendered schedule at
``https://registrar.sewanee.edu/schedule/`` with the term, school,
subject, and an optional General-Education track selected via query
parameters. We fetch one URL per term and parse the accordion of
"{CRN} – {SUBJ NUM SECTION} – {TITLE}" course cards.

Sewanee uses ecclesiastical-calendar names: *Advent* is the fall
semester, *Easter* the spring; we map "Advent Semester YYYY" to
academic year (YYYY, YYYY+1)/F and "Easter Semester YYYY" to
(YYYY-1, YYYY)/S, and skip Summer.

The term ``<select>`` only advertises a rolling window of terms (the
last few finished + current + next one or two), so we scrape whatever
appears there rather than a fixed N-year history.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://registrar.sewanee.edu/schedule/"
SCHOOL = "college-of-arts-sciences-2"
SUBJECT = "computer-science"

# "Advent Semester 2026" / "Easter Semester 2025" — Summer terms are skipped.
TERM_LABEL_RE = re.compile(
    r"^(?P<season>Advent|Easter)\s+Semester\s+(?P<year>\d{4})\s*$",
    re.I,
)
SEASON_TERM = {"advent": "F", "easter": "S"}

# Course heading like "91101 – CSCI 157 A – Introduction to Modeling and Programming".
# The separators are en-dashes (U+2013).
COURSE_HEADING_RE = re.compile(
    r"^\s*\d+\s*[–-]\s*"
    r"(?P<subj>[A-Z]+)\s+(?P<num>\d+\w*)\s+(?P<section>\w+)"
    r"\s*[–-]\s*(?P<title>.+?)\s*$"
)


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_term_label(label):
    """Return ((start_year, end_year), term) or (None, None)."""
    m = TERM_LABEL_RE.match(_clean(label))
    if not m:
        return None, None
    year = int(m.group("year"))
    season = m.group("season").lower()
    term = SEASON_TERM.get(season)
    if term is None:
        return None, None
    if term == "F":
        return (year, year + 1), term
    return (year - 1, year), term


class SewaneeScraper(CourseScheduleScraper):
    college = College.SOUTH
    fresh_driver_per_load = False
    post_load_sleep = 1.0
    terms = []  # discovered at runtime; base loop is overridden

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._term_slugs = None  # {(ay, t): slug}

    def _build_url(self, slug):
        return (
            f"{BASE_URL}?term={slug}"
            f"&school={SCHOOL}&subject={SUBJECT}&track="
        )

    def _discover_terms(self):
        if self._term_slugs is not None:
            return self._term_slugs
        html = self.load(self._build_url(""))
        soup = BeautifulSoup(html, "html.parser")
        select = soup.find("select", attrs={"name": "term"})
        out = {}
        if select is None:
            self._term_slugs = out
            return out
        for opt in select.find_all("option"):
            slug = (opt.get("value") or "").strip()
            label = _clean(opt.get_text(" ", strip=True))
            if not slug:
                continue
            academic_year, term = parse_term_label(label)
            if academic_year is None or term is None:
                continue
            out.setdefault((academic_year, term), slug)
        self._term_slugs = out
        return out

    def schedule_pages(self):
        terms = self._discover_terms()
        wanted = set(self.past_academic_years(self.years_back))
        # Yield discovered terms; oldest first.
        pairs = sorted(terms.keys(), key=lambda k: (k[0], {"F": 0, "S": 1}.get(k[1], 9)))
        for academic_year, term in pairs:
            if academic_year in wanted:
                yield academic_year, term

    def url_for(self, academic_year, term):
        slug = (self._term_slugs or {}).get((academic_year, term), "")
        return self._build_url(slug)

    def fetch_page(self, academic_year, term):
        slug = self._discover_terms().get((academic_year, term))
        if not slug:
            return None
        return self.load(self._build_url(slug))

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        seen = set()
        for item in soup.select("li.accordion_item, div.accordion_item, .course_schedule_items > *"):
            heading = item.select_one(".accordion_item_heading_inner.course_heading_inner")
            if heading is None:
                continue
            m = COURSE_HEADING_RE.match(_clean(heading.get_text(" ", strip=True)))
            if not m:
                continue
            course_code = f"{m.group('subj')} {m.group('num')}"
            section = m.group("section")
            course_name = _clean(m.group("title"))

            time_text = ""
            time_el = item.select_one(".course_times .course_info")
            if time_el is not None:
                time_text = _clean(time_el.get_text(" ", strip=True))
            location = ""
            loc_el = item.select_one(".course_location .course_info")
            if loc_el is not None:
                location = _clean(loc_el.get_text(" ", strip=True))
            if time_text and location:
                time_text = f"{time_text}; {location}"
            elif location and not time_text:
                time_text = location

            instructor = ""
            instr_el = item.select_one(".course_instructor .course_info")
            if instr_el is not None:
                instructor = _clean(instr_el.get_text(" ", strip=True))

            key = (course_code, section)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                    url=self._build_url(self._term_slugs.get((academic_year, term), "")),
                )
            )
        return rows
