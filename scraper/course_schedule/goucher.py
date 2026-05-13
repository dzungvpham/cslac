"""Goucher College course schedule scraper.

Goucher runs a newer (React-based) Ellucian Self-Service Course Search
at `/SelfService/Search/Section?department=CS`. The page lists every
section currently exposed (last finished term, current term, the next
one or two) and paginates them at five per page. There's no URL or UI
control to enlarge the page size, so we click the "Next page" button
until it's disabled.

Each card looks like:

    <button id="btnTitle_sectionCard_{idx}_{secId}" data-id="{secId}">
        CS 116: Intro to Computer Science
    </button>
    <p>Year: 2024 | Term: Fall | Session: UG Full Term</p>
    <p>Subtype: Lecture | Section: 001</p>
    <p>Type: Course | Credit type: Undergraduate Credit</p>
    <p>Duration: 8/22/2024 - 12/13/2024</p>
    <p>8:40 AM - 10:30 AM</p>
    <p>MonWed</p>
    <p>Goucher College, Julia Rogers, Room 128</p>
    ...
    <div id="avtInstructor_{secId}" title="Zimmerman, Jill">...</div>

We dedupe sections by `data-id` across pages just in case a section
appears twice during pagination transitions.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

LIST_URL = "https://hercules.goucher.edu/SelfService/Search/Section?&department=CS"

# Title-button text "CS 116: Intro to Computer Science" -> code + name.
TITLE_RE = re.compile(r"^(?P<code>[A-Z]+\s+\d+\w*):\s*(?P<name>.+)$")
YEAR_TERM_RE = re.compile(r"Year:\s*(?P<year>\d{4})\s*\|\s*Term:\s*(?P<term>\w+)")
SECTION_RE = re.compile(r"Section:\s*(?P<section>\w+)")

# "Fall" -> "F", "Spring" -> "S", etc.
TERM_CODE = {
    "fall": "F",
    "spring": "S",
    "summer": "Su",
    "winter": "W",
    "january": "W",
}


class GoucherScraper(CourseScheduleScraper):
    college = College.GOUCHER
    # Self-Service only exposes a moving window of terms; we discover them
    # at runtime from each card, so the base class's year×term loop doesn't
    # apply.
    terms = []
    wait_for = 'button[id^="btnTitle_sectionCard_"]'
    page_load_timeout = 60
    post_load_sleep = 2.0
    fresh_driver_per_load = False

    def url_for(self, academic_year, term):
        return LIST_URL

    def scrape(self):
        try:
            self.load(self.url_for(None, None))
        except TimeoutException:
            print("  [Goucher] page never rendered any section cards", flush=True)
            return []

        by_section_id = {}
        seen_pages = 0
        while True:
            self._wait_for_cards()
            html = self.driver.page_source
            page_rows = _parse_cards(self, html)
            for sec_id, row in page_rows:
                by_section_id.setdefault(sec_id, row)
            seen_pages += 1
            print(f"  [Goucher] page {seen_pages}: {len(page_rows)} sections", flush=True)
            if not self._click_next_page(html):
                break

        return list(by_section_id.values())

    def _wait_for_cards(self):
        WebDriverWait(self.driver, self.page_load_timeout).until(
            lambda d: d.find_elements(
                "css selector", 'button[id^="btnTitle_sectionCard_"]'
            )
        )

    def _click_next_page(self, prev_html):
        """Click the Next-page button. Return False when there is no next
        page (button disabled or missing)."""
        try:
            btn = self.driver.find_element(
                By.CSS_SELECTOR, 'button[aria-label="Next page"]'
            )
        except Exception:
            return False
        if btn.get_attribute("disabled") is not None:
            return False
        # Capture the first card's data-id so we can detect when the page
        # actually advances (URL/pagination state isn't reflected in the URL
        # bar).
        prev_first = _first_section_id(prev_html)
        try:
            btn.click()
        except StaleElementReferenceException:
            return False
        try:
            WebDriverWait(self.driver, self.page_load_timeout).until(
                lambda d: _first_section_id(d.page_source) not in (None, prev_first)
            )
        except TimeoutException:
            return False
        time.sleep(self.post_load_sleep)
        return True


def _first_section_id(html):
    m = re.search(r'btnTitle_sectionCard_\d+_(\d+)', html or "")
    return m.group(1) if m else None


def _parse_cards(scraper, html):
    """Return a list of (section_id, row_dict) tuples for the given page."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for btn in soup.select('button[id^="btnTitle_sectionCard_"]'):
        sec_id = btn.get("data-id") or ""
        title_text = _clean(btn.get_text(" ", strip=True))
        m = TITLE_RE.match(title_text)
        if m:
            course_code = _clean(m.group("code"))
            course_name = _clean(m.group("name"))
        else:
            course_code, course_name = title_text, ""

        # The card body is two levels above the title button; its
        # descendants include the five-to-seven meta `<p>` tags plus the
        # instructor avatar div.
        card = btn.parent.parent if btn.parent and btn.parent.parent else btn.parent
        if card is None:
            continue

        ps = [p.get_text(" ", strip=True) for p in card.find_all("p")]

        academic_year, term = _academic_year_and_term(ps)
        if academic_year is None:
            continue

        section = ""
        for line in ps:
            sm = SECTION_RE.search(line)
            if sm:
                section = sm.group("section")
                break

        time_text = _meeting_string(ps)
        instructor = _find_instructor(soup, sec_id)

        out.append(
            (
                sec_id,
                scraper.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                ),
            )
        )
    return out


def _academic_year_and_term(ps):
    for line in ps:
        m = YEAR_TERM_RE.search(line)
        if not m:
            continue
        year = int(m.group("year"))
        term_word = m.group("term").lower()
        code = TERM_CODE.get(term_word)
        if not code:
            return None, None
        if code == "F":
            return (year, year + 1), code
        return (year - 1, year), code
    return None, None


def _meeting_string(ps):
    """Pick out the time/days lines among the card paragraphs. We tag a
    line as a time line if it contains an `AM`/`PM` marker, and a days
    line if it's a concatenation of day abbreviations (`MonWed`,
    `TuesThur`, etc.). Anything else (year/section/duration/location) is
    ignored here."""
    time_line = ""
    days_line = ""
    for line in ps:
        s = line.strip()
        if re.match(r"\d{1,2}:\d{2}\s*(?:AM|PM)\s*-\s*\d{1,2}:\d{2}\s*(?:AM|PM)", s):
            time_line = _clean(s)
        elif re.fullmatch(
            r"(?:Mon|Tues|Wed|Thur|Fri|Sat|Sun)(?:Mon|Tues|Wed|Thur|Fri|Sat|Sun)*",
            s,
        ):
            days_line = _clean(s)
    if time_line and days_line:
        return f"{days_line} {time_line}"
    return time_line or days_line


def _find_instructor(soup, sec_id):
    if not sec_id:
        return ""
    el = soup.select_one(f'div[id="avtInstructor_{sec_id}"]')
    if el is None:
        return ""
    return _clean(el.get("title") or el.get("aria-label") or "")


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
