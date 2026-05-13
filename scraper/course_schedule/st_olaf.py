"""St. Olaf College course schedule scraper.

The public Class & Lab search at

    https://sis.stolaf.edu/sis/public-aclasslab.cfm

POSTs to ``public-acl-inez.cfm`` and returns an XML document of
``<course>`` records. We bypass the form and POST directly with
``searchyearterm`` + ``searchdepts=200`` (Computer Science).

Year-term codes are ``{start_year}{N}`` where ``N`` selects the term:
1=Fall, 2=January Term, 3=Spring, 4=Summer Session 1, 5=Summer
Session 2. All terms within an academic year share the same start
year prefix.
"""

import re
import sys
import warnings
from html import unescape
from pathlib import Path

import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

POST_URL = "https://sis.stolaf.edu/sis/public-acl-inez.cfm"
CS_DEPT_CODE = "200"

TERM_DIGIT = {"F": "1", "W": "2", "S": "3"}


class StOlafScraper(CourseScheduleScraper):
    college = College.ST_OLAF
    terms = ["F", "W", "S"]
    fresh_driver_per_load = False  # no Selenium needed

    def url_for(self, academic_year, term):
        start, _ = academic_year
        return f"{POST_URL}?searchyearterm={start}{TERM_DIGIT[term]}&searchdepts={CS_DEPT_CODE}"

    def fetch_page(self, academic_year, term):
        start, _ = academic_year
        yt = f"{start}{TERM_DIGIT[term]}"
        try:
            r = requests.post(
                POST_URL,
                data={
                    "searchyearterm": yt,
                    "searchdepts": CS_DEPT_CODE,
                    "searchbutton": "Search",
                },
                timeout=60,
            )
        except requests.RequestException:
            return None
        if r.status_code != 200 or "<course>" not in r.text:
            return None
        return r.text

    def parse_page(self, xml, academic_year, term):
        soup = BeautifulSoup(xml, "html.parser")
        rows = []
        for c in soup.find_all("course"):
            dept = _text(c, "deptname")
            num = _text(c, "coursenumber")
            section = _text(c, "coursesection")
            name = _text(c, "coursename")
            instr = _strip_html(_text(c, "instructors"))
            time_text = _clean(_text(c, "meetingtimes"))
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=f"{dept} {num}".strip(),
                    section=section,
                    course_name=name,
                    instructor=instr,
                    time=time_text,
                )
            )
        return rows


def _text(course, tag):
    el = course.find(tag)
    return _clean(el.get_text() if el is not None else "")


def _strip_html(raw):
    """Instructors / locations fields are CDATA-escaped HTML like
    ``<a ...>Hall-Holt, Olaf A.</a>``. Unescape, strip tags, and join
    multiple instructors with ``; ``.
    """
    if not raw:
        return ""
    text = unescape(raw)
    soup = BeautifulSoup(text, "html.parser")
    anchors = soup.find_all("a")
    if anchors:
        names = [_clean(a.get_text()) for a in anchors]
        return "; ".join(n for n in names if n)
    return _clean(soup.get_text(" ", strip=True))


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()
