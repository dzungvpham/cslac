"""Austin College course schedule scraper.

Austin runs its public course search on WebAdvisor at
``https://hopper.austincollege.edu/hlive/webhopper?CONSTITUENCY=WBAP&type=P
&pid=ST-XWEBS006``. The page is JS-rendered, so we drive it with
Selenium: pick a term (`VAR1`) and a subject (`LIST.VAR1_1` = `"CS"`),
submit, and read the "Sections" results table.

Term option values look like ``"25/FA"`` (Fall 2025), ``"25/SP"`` (Spring
2026, i.e. spring of academic year 25-26), and ``"25/JT"`` (January 2026
J-term). The form lists every term going back ~10 years; we restrict to
the past 5 academic years' fall/spring pairs and skip Summer / May Term.

Each result row's "Section Name" cell reads like ``"CS*110*A"`` — we
split that on ``*`` for the course code, number, and section.
"""

import re
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

SEARCH_URL = (
    "https://hopper.austincollege.edu/hlive/webhopper"
    "?CONSTITUENCY=WBAP&type=P&pid=ST-XWEBS006"
)
SUBJECT = "CS"

# Term option values: `YY/FA`, `YY/SP`, `YY/JT`, `YY/SU`, `YY/SU1`. The
# two-digit year is the academic-year start. Spring/J-term/Summer fall
# in the second half of the academic year.
TERM_VALUE_RE = re.compile(r"^(?P<yy>\d{2})/(?P<season>FA|SP|JT|SU|SU1)$")
SEASON_TERM = {"FA": "F", "SP": "S", "JT": "W"}  # Summer skipped


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


class AustinScraper(CourseScheduleScraper):
    college = College.AUSTIN
    fresh_driver_per_load = False
    page_load_timeout = 60
    post_load_sleep = 3.0
    terms = []  # term iteration happens via `schedule_pages`

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._available = None  # (academic_year, term) -> option_value

    def _load_form(self):
        d = self.driver
        d.get(SEARCH_URL)
        # WebAdvisor renders the form after a JS bootstrap; wait for the
        # term selector to appear.
        WebDriverWait(d, self.page_load_timeout).until(
            lambda x: x.find_elements(By.NAME, "VAR1")
            and x.find_elements(By.NAME, "LIST.VAR1_1")
        )

    def _discover_terms(self):
        if self._available is not None:
            return self._available
        self._load_form()
        out = {}
        for opt in self.driver.find_elements(
            By.CSS_SELECTOR, "select[name='VAR1'] option"
        ):
            value = (opt.get_attribute("value") or "").strip()
            m = TERM_VALUE_RE.match(value)
            if not m:
                continue
            season = m.group("season")
            term = SEASON_TERM.get(season)
            if term is None:
                continue
            yy = int(m.group("yy"))
            year = 2000 + yy
            if season == "FA":
                ay = (year, year + 1)
            else:
                ay = (year, year + 1)  # value `25/SP` = spring of AY 25-26
            out[(ay, term)] = value
        self._available = out
        return out

    def schedule_pages(self):
        available = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in ("F", "S"):
                if (ay, t) in available:
                    yield ay, t

    def fetch_page(self, academic_year, term):
        available = self._discover_terms()
        value = available.get((academic_year, term))
        if value is None:
            return None
        # WebAdvisor accumulates state across postbacks, so reload the form
        # before every search.
        self._load_form()
        d = self.driver
        Select(d.find_element(By.NAME, "VAR1")).select_by_value(value)
        Select(d.find_element(By.NAME, "LIST.VAR1_1")).select_by_value(SUBJECT)
        d.find_element(By.NAME, "SUBMIT2").click()
        try:
            WebDriverWait(d, self.page_load_timeout).until(
                lambda x: "Course Schedule" in (x.title or "")
                or x.find_elements(By.ID, "GROUP_Grp_WSS_COURSE_SECTIONS")
            )
        except TimeoutException:
            print("  timed out waiting for results", flush=True)
            return None
        time.sleep(self.post_load_sleep)
        return d.page_source

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        sections_group = soup.find(id="GROUP_Grp_WSS_COURSE_SECTIONS")
        if sections_group is None:
            return []
        # The Sections table is the inner one with a "Sections" groupTitle.
        target = None
        for table in sections_group.find_all("table"):
            head = table.find("th", class_="groupTitle")
            if head and "Section" in head.get_text():
                target = table
                break
        if target is None:
            return []

        # Columns (after the leading windowIdx <th>):
        #   Term | Status | Available/Capacity | IC | Req Code | S/D/U
        #     | Zap No/Synonym | Section Name | Course Info | Faculty | Room
        #     | Meet Times | Comments
        rows = []
        for tr in target.find_all("tr"):
            cells = tr.find_all("td")
            # Each data row leads with a row-index cell and has 14 total.
            if len(cells) < 14:
                continue
            section_name = _clean(cells[8].get_text(" ", strip=True))
            m = re.match(r"^([A-Z]+)\*(\d+\w*)\*(\w+)$", section_name)
            if not m:
                continue
            course_code = f"{m.group(1)} {m.group(2)}"
            section = m.group(3)
            course_name = _clean(cells[9].get_text(" ", strip=True))
            instructor = _clean(cells[10].get_text(" ", strip=True))
            room = _clean(cells[11].get_text(" ", strip=True))
            meet = _clean(cells[12].get_text(" ", strip=True))
            time_str = f"{meet} ({room})" if room and meet else meet or ""
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_str,
                    url=SEARCH_URL,
                )
            )
        return rows
