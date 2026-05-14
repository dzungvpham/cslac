"""Randolph College course-schedule scraper.

Randolph publishes its course offerings via an ASP.NET WebForms page
(`inside.randolphcollege.edu/Course_Offerings.aspx`). The page exposes a
period dropdown — one entry per session, e.g. ``"2026 FALL (01)"``,
``"2026 FALL (02)"``, ``"2026 SPRING (03)"`` — and renders the course
list inline after a postback.

Randolph splits each 14-week semester into two 7-week sub-sessions
(``(01)/(02)`` for Fall, ``(03)/(04)`` for Spring), and a "(00)" /
``(1ST5WK)`` / ``(2ND5WK)`` set for Summer. A 14-week course typically
shows in both sub-sessions of its semester, so we collapse sub-sessions
into a single ``(academic_year, term)`` bucket and dedupe by
``(course_code, section)``.

We POST with the standard WebForms hidden fields (``__VIEWSTATE``,
``__VIEWSTATEGENERATOR``, ``__EVENTVALIDATION``) plus the period
selection. Parsing keys off ``div.courses_title`` (course header) and
the adjacent ``div.courses_content`` (period / credit / department /
days / time / location / instructor in a pair of small tables).
"""

from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

URL = "https://inside.randolphcollege.edu/Course_Offerings.aspx"

# Period label parser. The label is ``"YYYY <TERM> (<session>)"`` where
# ``<TERM>`` is FALL / SPRING / SUMMER (or the FALLGR/SPRINGGR/SUMMERGR
# graduate variants, which we drop), and ``<session>`` is the sub-session
# token (``01``, ``02``, ``03``, ``04``, ``00``, ``1ST5WK``, ``2ND5WK``).
PERIOD_RE = re.compile(r"^(?P<year>\d{4})\s+(?P<word>FALL|SPRING|SUMMER)(?P<gr>GR)?\s*\(")

# Course header parses to (course_code, section, title). The page renders
# the section as a single uppercase letter after the course number, e.g.
# ``"CSCI 2252 A - DATA STRUCTURES"``.
HEADER_RE = re.compile(
    r"^(?P<code>[A-Z]+(?:\s+[A-Z]+)?\s+\w+)\s+(?P<section>[A-Z0-9]+)\s+-\s+(?P<title>.+)$"
)

# Subject prefixes to keep (matches the per-college subject filtering used
# by the other scrapers). Randolph's CS courses use ``CSCI``.
SUBJECTS = ("CSCI",)


def _term_for_word(word):
    return {"FALL": "F", "SPRING": "S", "SUMMER": "Su"}.get(word)


def _academic_year_for(year, term_code):
    return (year, year + 1) if term_code == "F" else (year - 1, year)


def _parse_period(label):
    """Return ((start_year, end_year), term_code) for an undergrad period,
    or ``None`` for graduate or unparseable labels."""
    m = PERIOD_RE.match(label or "")
    if not m or m.group("gr"):
        return None
    year = int(m.group("year"))
    term = _term_for_word(m.group("word"))
    if term is None:
        return None
    return _academic_year_for(year, term), term


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def _kv_from_table(table):
    """Pull ``{label: value}`` from the small left/middle detail tables.

    Each row is ``<td>Label:</td><td>Value</td>``. Labels carry the
    trailing colon; we strip it.
    """
    out = {}
    if table is None:
        return out
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        label = _clean(tds[0].get_text(" ", strip=True)).rstrip(":")
        value = _clean(tds[1].get_text(" ", strip=True))
        if label:
            out[label] = value
    return out


class RandolphScraper(CourseScheduleScraper):
    college = College.RANDOLPH
    fresh_driver_per_load = False
    terms = []  # we discover the period list from the page itself
    request_timeout = 60

    def scrape(self):
        session = requests.Session()
        session.headers.update(
            {"User-Agent": "Mozilla/5.0 (cs-lac course-schedule scraper)"}
        )
        try:
            r = session.get(URL, timeout=self.request_timeout)
            r.raise_for_status()
        except Exception as e:
            print(f"  failed to load index: {e}", flush=True)
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        periods = self._extract_periods(soup)
        if not periods:
            print("  no periods found on the index page", flush=True)
            return []

        # ``(academic_year, term) -> {(code, section): row_dict}`` — dedupe
        # across sub-sessions so a 14-week course doesn't appear twice.
        buckets: dict = {}
        for period in periods:
            ay_term = _parse_period(period)
            if ay_term is None:
                continue
            academic_year, term = ay_term
            label = f"{academic_year[0]}-{str(academic_year[1])[-2:]}/{term} [{period}]"
            try:
                rows = self._fetch_period(session, period, academic_year, term)
            except Exception as e:
                print(f"  [{label}] failed: {e}", flush=True)
                continue
            bucket = buckets.setdefault((academic_year, term), OrderedDict())
            for row in rows:
                key = (row["course_code"], row["section"])
                bucket.setdefault(key, row)
            print(f"  [{label}] {len(rows)} sections", flush=True)

        out = []
        for bucket in buckets.values():
            out.extend(bucket.values())
        return out

    @staticmethod
    def _extract_periods(soup):
        select = soup.find("select", id=re.compile(r"DropDownList_Period$"))
        if select is None:
            return []
        periods = []
        for opt in select.find_all("option"):
            v = opt.get("value", "")
            # Skip the placeholder ("xxxxxxx") and "All Periods" ("%%").
            if v in ("xxxxxxx", "%%"):
                continue
            periods.append(v)
        return periods

    def _fetch_period(self, session, period, academic_year, term):
        # Re-fetch the index page to get a fresh viewstate for each
        # postback — the WebForms server validates that the viewstate
        # matches the request, and stale viewstates from a few minutes
        # ago start failing intermittently.
        r = session.get(URL, timeout=self.request_timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        def hidden(name):
            el = soup.find("input", {"name": name})
            return el.get("value", "") if el else ""

        form = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": hidden("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": hidden("__EVENTVALIDATION"),
            "ctl00$single_column_PH$course_offerings$TextBox_Search_Criteria": "",
            "ctl00$single_column_PH$course_offerings$DropDownList_Period": period,
            "ctl00$single_column_PH$course_offerings$Button_Search": "Search",
        }
        resp = session.post(URL, data=form, timeout=self.request_timeout)
        resp.raise_for_status()
        return self._parse_results(resp.text, period, academic_year, term)

    def _parse_results(self, html, period, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        # Each course renders as a ``courses_title`` block followed by a
        # sibling ``courses_content`` block holding the detail tables. We
        # walk the title blocks and look at the following ``courses_content``.
        for title_div in soup.select("div.courses_title"):
            header_el = title_div.select_one("div.course_list_title")
            if header_el is None:
                continue
            m = HEADER_RE.match(_clean(header_el.get_text(" ", strip=True)))
            if not m:
                continue
            course_code = _clean(m.group("code"))
            if not any(course_code.startswith(s) for s in SUBJECTS):
                continue
            section = m.group("section")
            title = _clean(m.group("title"))

            # The detail block is the next sibling whose class is
            # ``courses_content``. Two tables live underneath.
            detail = title_div.find_next_sibling(
                "div", class_="courses_content"
            )
            left, middle = {}, {}
            if detail is not None:
                tables = detail.find_all("table")
                if len(tables) >= 1:
                    left = _kv_from_table(tables[0])
                if len(tables) >= 2:
                    middle = _kv_from_table(tables[1])

            # Filter out graduate offerings that may slip through. The
            # period filter already excludes ``*GR`` periods, but the
            # ``Program`` field is a final safety net.
            program = left.get("Program", "")
            if program and "Und" not in program:
                continue

            instructor = middle.get("Instructor(s)", "")
            time_text = self._format_time(
                middle.get("Days"),
                middle.get("Time"),
                middle.get("Location"),
            )

            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=title,
                    instructor=instructor,
                    time=time_text,
                    url=URL,
                )
            )
        return rows

    @staticmethod
    def _format_time(days, time_range, location):
        days = _clean(days)
        time_range = _clean(time_range)
        location = _clean(location)
        parts = []
        if days:
            parts.append(days)
        if time_range:
            parts.append(time_range)
        s = " ".join(parts)
        if location:
            s = f"{s} ({location})" if s else f"({location})"
        return s
