"""Williams College course schedule scraper.

The catalog page lists every section for a whole academic year on one URL,
keyed by the two-digit ending year (`req_year=27` -> AY 2026-27). The page is
rendered client-side; we wait for `a.classinfo` to appear.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://catalog.williams.edu"
LIST_URL = BASE_URL + "/csci/list/?strm=9999&sbattr=&req_year={year}&offered=A"

# Course-code line example: "CSCI 102 - T1 (S)" or "CSCI 134 - 01 (F)" or
# "CSCI 23". Section may be alphanumeric (e.g. T1, 01); the term marker in
# parentheses is optional (F = Fall, S = Spring, W = Winter Study).
CODE_RE = re.compile(
    r"^(?P<code>[A-Z]+\s*\d+\w*)"
    r"(?:\s*-\s*(?P<section>\S+))?"
    r"\s*(?:\((?P<term>[A-Z])\))?"
    r"\s*$"
)


class WilliamsScraper(CourseScheduleScraper):
    college = College.WILLIAMS
    wait_for = "a.classinfo"
    public_url_template = True
    # The listing page covers all terms at once, so we leave `terms` empty
    # and ignore the `term` argument in `url_for` / `parse_page`.

    def url_for(self, academic_year, term):
        req_year = academic_year[1] % 100
        return LIST_URL.format(year=req_year)

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for li in soup.select("li[id]"):
            classes_div = li.select_one("div.classes")
            if classes_div is None:
                continue
            link = classes_div.select_one("a.classinfo")
            if link is None:
                continue

            code_text = link.get_text(" ", strip=True)
            m = CODE_RE.match(code_text)
            if m:
                course_code = re.sub(r"\s+", " ", m.group("code")).strip()
                section = (m.group("section") or "").strip()
                row_term = (m.group("term") or "").strip()
            else:
                course_code, section, row_term = code_text, "", ""

            # Course name = text in `div.classes` excluding the code link.
            name_parts = []
            for child in classes_div.children:
                if getattr(child, "name", None) == "a" and "classinfo" in (child.get("class") or []):
                    continue
                text = (
                    child.get_text(" ", strip=True)
                    if hasattr(child, "get_text")
                    else str(child).strip()
                )
                if text:
                    name_parts.append(text)
            course_name = re.sub(r"\s+", " ", " ".join(name_parts)).strip()

            instr_div = li.select_one("div.instructors")
            if instr_div and instr_div.find_all("a"):
                instructor = ", ".join(
                    re.sub(r"\s+", " ", a.get_text(" ", strip=True))
                    for a in instr_div.find_all("a")
                )
            else:
                instructor = instr_div.get_text(" ", strip=True) if instr_div else ""

            times_div = li.select_one("div.times")
            time_text = times_div.get_text(" ", strip=True) if times_div else ""

            href = link.get("href", "")
            if href and not href.startswith("http"):
                href = BASE_URL + href

            rows.append(
                self.make_row(
                    academic_year,
                    row_term,
                    course_code=course_code,
                    section=section,
                    course_name=course_name,
                    instructor=instructor,
                    time=time_text,
                    url=href,
                )
            )
        return rows
