"""Haverford College course schedule scraper.

Haverford publishes a unified course search at
``/academics/results``. Filters are passed as array query parameters:

    semester[0]=fall_2024
    department[0]=Computer Science
    college[0]=haverford
    page=1
    per_page=200

The page is Drupal-rendered HTML behind Cloudflare's anti-bot challenge,
so Selenium is required (`requests` is rejected with 403). Results live
in a single `table.footable` with columns:

    Registration-ID | Course Name | Instructor | Misc | Days and Times | Location

The Registration-ID concatenates the course code and section, e.g.
``CMSCH105A001`` = course ``CMSCH105A`` + section ``001``; lab/recitation
sections use letters in the last position (``00A``, ``00B``, ...). The
first column also links to a per-section detail page.

Each Cloudflare challenge has to be solved per session, so we let the
base class spin up a fresh driver per page load (the default).
"""

import re
import sys
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://www.haverford.edu"
RESULTS_PATH = "/academics/results"

# Section is the trailing 2 digits + 1 digit-or-letter (e.g. 001, 002, 00A).
REGID_RE = re.compile(r"^(?P<code>.+?)(?P<section>\d{2}[0-9A-Z])$")


class HaverfordScraper(CourseScheduleScraper):
    college = College.HAVERFORD
    terms = ["F", "S"]
    page_load_timeout = 60

    @staticmethod
    def _semester(academic_year, term):
        start, end = academic_year
        if term == "F":
            return f"fall_{start}"
        if term == "S":
            return f"spring_{end}"
        raise ValueError(f"unknown term {term!r}")

    def url_for(self, academic_year, term):
        sem = self._semester(academic_year, term)
        # per_page=200 fits any single-department term in one request.
        params = (
            f"semester%5B0%5D={sem}"
            f"&department%5B0%5D={quote('Computer Science')}"
            f"&college%5B0%5D=haverford"
            f"&page=1&per_page=200"
        )
        return f"{BASE_URL}{RESULTS_PATH}?{params}"

    def fetch_page(self, academic_year, term):
        # Override `load()` flow so we can wait on either the results table
        # or the "No results found" alert — a single CSS selector can't catch
        # both, and the Cloudflare challenge often takes 10-20s to clear.
        if self.fresh_driver_per_load and self._owns_driver:
            self.close()
        driver = self.driver
        driver.get(self.url_for(academic_year, term))
        WebDriverWait(driver, self.page_load_timeout).until(
            lambda d: "Listed " in d.page_source or "No results found" in d.page_source
        )
        return driver.page_source

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="footable")
        if table is None:
            return []

        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td"], recursive=False)
            if len(cells) < 6:
                continue
            regid_cell, name_cell, inst_cell, _misc, time_cell, loc_cell = cells[:6]
            regid = _clean(regid_cell.get_text(" "))
            if not regid:
                continue
            course_code, section = _split_regid(regid)
            course_name = _clean(name_cell.get_text(" "))
            instructor = _format_instructor(inst_cell)
            time_text = _clean(time_cell.get_text(" "))
            location = _clean(loc_cell.get_text(" "))
            if location:
                time_text = f"{time_text} ({location})" if time_text else f"({location})"
            url = ""
            link = regid_cell.find("a", href=True)
            if link:
                href = link["href"]
                url = href if href.startswith("http") else f"{BASE_URL}{href}"
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                    url=url,
                )
            )
        return rows


def _split_regid(regid):
    m = REGID_RE.match(regid)
    if m:
        return m.group("code"), m.group("section")
    return regid, ""


def _format_instructor(cell):
    # Instructors are rendered as one or more `<a href="mailto:...">Last,First</a>`
    # links, possibly separated by `;` or `<br>`. Strip mailto noise.
    parts = []
    for a in cell.find_all("a"):
        name = _clean(a.get_text(" "))
        if name and name not in parts:
            parts.append(name)
    if parts:
        return ", ".join(parts)
    return _clean(cell.get_text(" "))


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
