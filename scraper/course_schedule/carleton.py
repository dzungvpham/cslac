"""Carleton College course schedule scraper.

Carleton's catalog search page accepts a comma-separated `term` query
parameter:

    /catalog/current/search/?subject=CS&term=25FA,26WI,26SP,26SU

Each term is encoded as ``YY`` + season (Carleton runs trimesters plus a
small summer term, so we see ``FA``, ``WI``, ``SP``, ``SU``). The endpoint
silently truncates to the first 16 terms it sees, so we batch one academic
year (4 terms) per request and aggregate.

Each rendered ``<li>`` of ``ul.courseSearchResults`` is one course
(`<h3 class="courseTitleBar">` with course code + title) containing one or
more ``<div class="course-section">`` blocks. Inside a section block:

  * ``<h4 class="courseSectionNumber">`` holds ``"CS 111.01"`` plus a
    nested ``<span class="sectionTerm">Fall 2025</span>``.
  * A ``<li>`` whose ``.meetingDay`` text is ``"Faculty:"`` lists the
    instructors, separated by ``·`` (and decorated with two emoji links
    per name that we strip).
  * Each ``<li class="classMeeting">`` carries one meeting: a
    ``.meetingDay`` cell ("M, W"), an optional location ``<a>``, and a
    ``<span class="meetingTimes">`` ("12:30pm-1:40pm").

Carleton's ``/catalog/current/`` always rewrites to the most-recent
academic-year catalog (currently ``current-2026``), and that one URL
serves history for all the terms it knows about — there is no separate
archived-year path.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper, NO_TERM

SEARCH_URL = "https://www.carleton.edu/catalog/current/search/"

# Mapping in both directions between Carleton's two-letter season codes
# and the canonical one-letter codes used in our CSVs.
CARLETON_TO_TERM = {"FA": "F", "WI": "W", "SP": "S", "SU": "Su"}
SECTION_TERM_RE = re.compile(r"^\s*(Fall|Winter|Spring|Summer)\s+(\d{4})\s*$", re.I)
SECTION_HEADER_RE = re.compile(
    r"^\s*(?P<code>[A-Z]+\s+[\w./]+?)\.(?P<section>[\w-]+)\s*$"
)


def _term_codes_for_ay(academic_year):
    """Return Carleton's `YY<season>` codes for one academic year.

    Fall is in the *start* calendar year; Winter/Spring/Summer are in the
    end year. Returned in academic-calendar order (F, W, S, Su).
    """
    start, end = academic_year
    return [
        f"{start % 100:02d}FA",
        f"{end % 100:02d}WI",
        f"{end % 100:02d}SP",
        f"{end % 100:02d}SU",
    ]


def _parse_section_term(text):
    """Map "Fall 2025" -> ((2025, 2026), "F"). Returns (None, None) on failure."""
    m = SECTION_TERM_RE.match(text or "")
    if not m:
        return None, None
    season_word = m.group(1).capitalize()
    year = int(m.group(2))
    code = {"Fall": "F", "Winter": "W", "Spring": "S", "Summer": "Su"}[season_word]
    if season_word == "Fall":
        ay = (year, year + 1)
    else:
        ay = (year - 1, year)
    return ay, code


class CarletonScraper(CourseScheduleScraper):
    college = College.CARLETON
    # We fetch each AY in one request; let the base loop yield a single
    # placeholder per year and parse_page emit per-section terms.
    terms = []
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        codes = ",".join(_term_codes_for_ay(academic_year))
        return f"{SEARCH_URL}?subject=CS&term={codes}"

    def fetch_page(self, academic_year, term):
        resp = requests.get(self.url_for(academic_year, term), timeout=self.page_load_timeout)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        # Restrict parsing to the AY we asked for — the catalog occasionally
        # leaks adjacent terms when our requested batch overlaps a course's
        # data-terms range. We trust the section-term label, not the request.
        rows = []
        for course_li in soup.select("ul.courseSearchResults > li"):
            title_bar = course_li.select_one("h3.courseTitleBar")
            course_title = ""
            if title_bar:
                title_el = title_bar.select_one(".courseTitle")
                if title_el:
                    course_title = _clean(title_el.get_text(" ", strip=True))
            for section in course_li.select("div.course-section"):
                row = self._parse_section(section, course_title)
                if row is None:
                    continue
                row_ay, row_term = row.pop("_term_meta")
                if row_ay != academic_year:
                    # Guard: keep only sections whose term lies in this AY.
                    continue
                row["academic_year"] = _format_ay(row_ay)
                row["term"] = row_term
                rows.append(row)
        return rows

    def _parse_section(self, section, course_title):
        header = section.select_one(".courseSectionNumber")
        if header is None:
            return None
        # The term lives in a nested span; pop it out before reading the
        # "CS 111.01"-style header text.
        sec_term_el = header.select_one(".sectionTerm")
        sec_term_text = ""
        if sec_term_el is not None:
            sec_term_text = sec_term_el.get_text(" ", strip=True)
            sec_term_el.extract()
        header_text = _clean(header.get_text(" ", strip=True))
        m = SECTION_HEADER_RE.match(header_text)
        if m:
            course_code = _clean(m.group("code"))
            section_num = m.group("section")
        else:
            course_code, section_num = header_text, ""

        ay, term_code = _parse_section_term(sec_term_text)
        if ay is None:
            return None

        instructor = ""
        meetings = []  # list of (days, time, location)
        for li in section.select("li"):
            label_el = li.select_one(".meetingDay")
            label_text = _clean(label_el.get_text(" ", strip=True)) if label_el else ""
            if label_text.rstrip(":").lower() == "faculty":
                instructor = _extract_faculty(li)
            elif "classMeeting" in (li.get("class") or []):
                meetings.append(_extract_meeting(li))

        time_str = _format_meetings(meetings)
        row = self.make_row(
            ay,
            term_code,
            course_code=course_code,
            section=section_num,
            course_name=course_title,
            instructor=instructor,
            time=time_str,
            url=SEARCH_URL,
        )
        # Stash the parsed (AY, term) for the caller to validate against
        # the AY this fetch was supposed to cover.
        row["_term_meta"] = (ay, term_code)
        return row


# ---- helpers ---------------------------------------------------------------


def _clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _format_ay(academic_year):
    start, end = academic_year
    return f"{start}-{str(end)[-2:]}"


def _extract_faculty(li):
    """Faculty rows look like:

        <li><span class="meetingDay">Faculty:</span>
          Anna Rafferty <a>🏫</a> <a>👤</a>
          ·
          Eric Alexander <a>🏫</a> <a>👤</a>
        </li>

    Strip the anchor decorations (each name has two), drop the "Faculty:"
    label, and split on the interpunct.
    """
    li_copy = BeautifulSoup(str(li), "html.parser").li
    for a in li_copy.find_all("a"):
        a.decompose()
    text = _clean(li_copy.get_text(" ", strip=True))
    text = re.sub(r"^Faculty:\s*", "", text, flags=re.I)
    # Split on middle dot (·) or interpunct variants. Some pages use a
    # leading interpunct on continuation lines; filter empties.
    parts = [p.strip() for p in re.split(r"\s*[·•]\s*", text) if p.strip()]
    seen = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return ", ".join(seen)


def _extract_meeting(li):
    """One ``li.classMeeting`` -> (days, time_range, location)."""
    days_el = li.select_one(".meetingDay")
    days_text = _clean(days_el.get_text(" ", strip=True)) if days_el else ""
    # "M, W" / "T, Th" -> "MW" / "TTh"
    days = "".join(p.strip() for p in days_text.split(","))
    time_el = li.select_one(".meetingTimes")
    time_range = _clean(time_el.get_text(" ", strip=True)) if time_el else ""
    # The location is whatever <a> sits between meetingDay and meetingTimes
    # (it links to a campus map). Skip the meetingDay span itself.
    location = ""
    for a in li.find_all("a"):
        href = a.get("href", "")
        if "/map/" in href or not href:
            location = _clean(a.get_text(" ", strip=True))
            break
    return days, time_range, location


def _format_meetings(meetings):
    """Same shape as banner9._format_meetings — group by (time, location)."""
    groups = {}
    order = []
    for days, time_range, location in meetings:
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
