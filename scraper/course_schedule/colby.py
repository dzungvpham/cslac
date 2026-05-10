"""Colby College course schedule scraper.

Colby's CS department doesn't publish a structured course feed; courses for
the *current* academic year are listed on https://cs.colby.edu/index.php
(department home), and past + future years live on
https://cs.colby.edu/courses.php. The official registrar tool at
https://www.colby.edu/registrar/CWcurricq.html only goes through 2024-25,
so we fall back to the department pages for both current and historical
data.

Both pages are static HTML with the same per-term shape::

    <h3>Fall 2024</h3>
    <p><ul>
      <li>CS 231: Data Structures and Algorithms (Lectures: Harper, Al Madi)
                                                  (Labs: Lage, Harper)</li>
      <li>CS 333: <a href="...">Programming Languages</a></li>
      ...
    </ul></p>

`courses.php` adds an ``<h2>YYYY-YYYY Academic Year</h2>`` wrapper around
each year. `index.php` does not — the only AY-level grouping is the
"Current Courses" h2 — so we trust the *season* from each h3 and assign all
of them to the current AY (Colby occasionally typos the J-term year, e.g.
listing "January 2025" under what is really AY 2025-26).

Time, section, and meeting info are not on these pages — those columns are
left empty. Instructor info appears in parens but is irregular: it can be
missing entirely, prefixed with ``Lectures:`` / ``Labs:``, or interleaved
with non-instructor notes like ``(prerequisite: ...)`` or
``(sequence course 1)``.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

INDEX_URL = "https://cs.colby.edu/index.php"
COURSES_URL = "https://cs.colby.edu/courses.php"

TERM_FROM_SEASON = {"Fall": "F", "January": "W", "Spring": "S"}

TERM_HEADING_RE = re.compile(
    r"^(?P<season>Fall|January|Spring)\s+(?P<year>\d{4})$", re.I
)
AY_HEADING_RE = re.compile(
    r"^(?P<start>\d{4})-(?P<end>\d{4})\s+Academic\s+Year$", re.I
)
COURSE_LI_RE = re.compile(r"^\s*(?P<code>[A-Z]{2,4}\s*\d+\w*)\s*:\s*(?P<rest>.*)$")

# Paren groups that should *not* be parsed as instructor lists.
NON_INSTRUCTOR_RE = re.compile(
    r"prerequisite|sequence course|note\s*:|this does count|"
    r"for students with|cross[- ]?list",
    re.I,
)
# A name token: capitalized word, optionally with apostrophes/hyphens, and
# optionally followed by 1-2 more capitalized words ("Al Madi", "Frank Bolton").
INSTRUCTOR_NAME_RE = re.compile(r"^[A-Z][a-zA-Z'-]+(?:\s+[A-Z][a-zA-Z'-]+){0,2}$")


class ColbyScraper(CourseScheduleScraper):
    college = College.COLBY
    # Both pages cover whole AYs at once; we issue one fetch per AY and
    # emit per-term rows from `parse_page`.
    terms = []
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._index_html = None
        self._courses_html = None

    def url_for(self, academic_year, term):
        return INDEX_URL if self._is_current_ay(academic_year) else COURSES_URL

    def fetch_page(self, academic_year, term):
        if self._is_current_ay(academic_year):
            if self._index_html is None:
                self._index_html = self.load(INDEX_URL)
            return self._index_html
        if self._courses_html is None:
            self._courses_html = self.load(COURSES_URL)
        return self._courses_html

    def parse_page(self, html, academic_year, term):
        if self._is_current_ay(academic_year):
            return self._parse_index(html, academic_year)
        return self._parse_courses(html, academic_year)

    def _is_current_ay(self, academic_year):
        return academic_year == self.past_academic_years(1)[0]

    # ---- index.php ---------------------------------------------------------

    def _parse_index(self, html, academic_year):
        """Walk h3 headings under the "Current Courses" section.

        Trusts the season but not the year on each h3 — the page lists only
        the current year's terms, so all h3s belong to `academic_year`.
        """
        soup = BeautifulSoup(html, "html.parser")
        section = soup.find(
            lambda t: t.name in ("h2", "h3") and "Current Courses" in t.get_text()
        )
        if section is None:
            return []
        rows = []
        for h3 in _siblings_until(section, "h2"):
            if getattr(h3, "name", "") != "h3":
                continue
            m = TERM_HEADING_RE.match(_clean(h3.get_text(strip=True)))
            if not m:
                continue
            term = TERM_FROM_SEASON.get(m.group("season").capitalize())
            if term is None:
                continue
            rows.extend(_rows_after(h3, academic_year, term, INDEX_URL))
        return rows

    # ---- courses.php -------------------------------------------------------

    def _parse_courses(self, html, academic_year):
        """Pick the `<h2>YYYY-YYYY Academic Year</h2>` matching `academic_year`
        and walk its h3 children. Skips `<h2>Archive</h2>` (purely a visual
        divider on the page — it isn't an AY heading).
        """
        soup = BeautifulSoup(html, "html.parser")
        target_h2 = None
        for h2 in soup.find_all("h2"):
            m = AY_HEADING_RE.match(_clean(h2.get_text(strip=True)))
            if not m:
                continue
            if (int(m.group("start")), int(m.group("end"))) == academic_year:
                target_h2 = h2
                break
        if target_h2 is None:
            return []
        rows = []
        for sib in _siblings_until(target_h2, "h2"):
            if getattr(sib, "name", "") != "h3":
                continue
            m = TERM_HEADING_RE.match(_clean(sib.get_text(strip=True)))
            if not m:
                continue
            term = TERM_FROM_SEASON.get(m.group("season").capitalize())
            if term is None:
                continue
            rows.extend(_rows_after(sib, academic_year, term, COURSES_URL))
        return rows


# ---- helpers ---------------------------------------------------------------


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _siblings_until(start, stop_tag):
    """Yield siblings of `start` until a tag of `stop_tag` is reached."""
    node = start
    while True:
        node = node.next_sibling
        if node is None:
            return
        if getattr(node, "name", "") == stop_tag:
            return
        yield node


def _rows_after(h3, academic_year, term, url):
    """Find the first `<ul>` after this h3 (it may be wrapped in a `<p>`)
    and emit one row per `<li>`.
    """
    ul = None
    for sib in _siblings_until(h3, "h3"):
        name = getattr(sib, "name", "")
        if name == "ul":
            ul = sib
            break
        if name in ("p", "div"):
            inner = sib.find("ul")
            if inner is not None:
                ul = inner
                break
    rows = []
    if ul is None:
        return rows
    for li in ul.find_all("li", recursive=False):
        row = _parse_li(li, academic_year, term, url)
        if row is not None:
            rows.append(row)
    return rows


def _parse_li(li, academic_year, term, url):
    text = _clean(li.get_text(" ", strip=True))
    m = COURSE_LI_RE.match(text)
    if not m:
        return None
    course_code = re.sub(r"\s+", " ", m.group("code")).strip()
    # Normalize "CS231" -> "CS 231".
    course_code = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", course_code)
    course_name, instructor = _split_name_and_instructor(m.group("rest"))
    return {
        "college": str(College.COLBY),
        "academic_year": _format_ay(academic_year),
        "term": term,
        "course_code": course_code,
        "section": "",
        "course_name": course_name,
        "instructor": instructor,
        "time": "",
        "url": url,
    }


def _format_ay(academic_year):
    start, end = academic_year
    return f"{start}-{str(end)[-2:]}"


def _split_name_and_instructor(rest):
    """Parse the part of a list item *after* "CS NNN: ".

    Returns ``(name, instructors_joined_by_comma)``.

    Strategy: collect top-level paren groups separately from non-paren text.
    The course name is the non-paren text; each paren group is then triaged
    as instructor info or a non-instructor annotation (prereq, sequence
    note, crosslist, etc.).
    """
    name_chars = []
    paren_groups = []
    depth = 0
    paren_buf = []
    for ch in rest:
        if ch == "(":
            if depth == 0:
                paren_buf = []
            else:
                paren_buf.append(ch)
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
            if depth == 0:
                paren_groups.append("".join(paren_buf))
            else:
                paren_buf.append(ch)
        else:
            (name_chars if depth == 0 else paren_buf).append(ch)
    name = _clean("".join(name_chars))
    # Some entries put the role labels *outside* parens, e.g.
    # "Computer Organization: Lectures, Labs (Li, Taylor)". Strip the
    # dangling ":<role>(, <role>)*" tail so the title is just the title.
    name = re.sub(
        r"\s*:\s*(?:Lectures?|Labs?|Projects?)"
        r"(?:\s*[,/]\s*(?:Lectures?|Labs?|Projects?))*\s*$",
        "",
        name,
        flags=re.I,
    )

    instructors = []
    for group in paren_groups:
        for n in _extract_names(group):
            if n not in instructors:
                instructors.append(n)
    return name, ", ".join(instructors)


def _extract_names(group):
    """Pull instructor surnames out of one paren group.

    Skips groups that are clearly non-instructor annotations. Strips
    "Lectures:" / "Labs:" / "Projects:" labels that decorate names.
    """
    if NON_INSTRUCTOR_RE.search(group):
        return []
    text = _clean(group)
    # Strip leading/embedded role labels.
    text = re.sub(
        r"\b(Lectures?|Labs?|Projects?)\s*[:,]\s*", "", text, flags=re.I
    )
    parts = [p.strip() for p in re.split(r"\s*,\s*", text) if p.strip()]
    names = []
    for p in parts:
        if INSTRUCTOR_NAME_RE.match(p):
            names.append(p)
    return names
