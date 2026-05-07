"""Amherst College course schedule scraper.

URL pattern: /academiclife/departments/computer_science/courses/{YYYYT}
where YYYY = the two-digit start year + two-digit end year (e.g. 2627 for AY
2026-27) and T is "F" (Fall) or "S" (Spring). Each page lists one term.

Each course is a `.coursehead` div containing one `.course-subj` heading
("CODE-NUM Course Name" linking to the detail page) and one or more
`.course-list-fac` rows of the form "<a>Instructor</a> (Section NN)". Meeting
times are not exposed on either the listing or the detail page (they live in
Workday), so we leave `time` empty.
"""

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

BASE_URL = "https://www.amherst.edu"
LIST_URL = BASE_URL + "/academiclife/departments/computer_science/courses/{code}"

# Heading text: "COSC-111 Introduction to Computer Science I". Code is the
# subject prefix + number (which may end in a letter, e.g. COSC-111L).
HEADING_RE = re.compile(r"^\s*(?P<code>[A-Z]+-\d+\w*)\s+(?P<name>.+?)\s*$")
# Faculty row text: "Myroslav Kryven (Section 01)" — we want "01".
SECTION_RE = re.compile(r"\(Section\s+(?P<section>\w+)\)", re.I)


class AmherstScraper(CourseScheduleScraper):
    college = College.AMHERST
    terms = ["F", "S"]
    wait_for = ".coursehead"

    def url_for(self, academic_year, term):
        start_yy = academic_year[0] % 100
        end_yy = academic_year[1] % 100
        return LIST_URL.format(code=f"{start_yy:02d}{end_yy:02d}{term}")

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for head in soup.select("div.coursehead"):
            subj = head.select_one(".course-subj")
            if subj is None:
                continue
            link = subj.find("a")
            heading = (link or subj).get_text(" ", strip=True)
            heading = re.sub(r"\s+", " ", heading)
            m = HEADING_RE.match(heading)
            if m:
                course_code = m.group("code")
                course_name = m.group("name")
            else:
                course_code, course_name = heading, ""

            href = link.get("href", "") if link else ""
            if href and not href.startswith("http"):
                href = BASE_URL + href

            # One row per faculty/section block. If none, emit a single row
            # with empty instructor/section.
            fac_blocks = head.select(".course-list-fac")
            if not fac_blocks:
                rows.append(
                    self.make_row(
                        academic_year,
                        term,
                        course_code=course_code,
                        course_name=course_name,
                        url=href,
                    )
                )
                continue

            for fac in fac_blocks:
                fac_text = re.sub(r"\s+", " ", fac.get_text(" ", strip=True)).strip()
                m_sec = SECTION_RE.search(fac_text)
                section = m_sec.group("section") if m_sec else ""

                fac_link = fac.find("a")
                if fac_link is not None:
                    instructor = re.sub(r"\s+", " ", fac_link.get_text(" ", strip=True)).strip()
                else:
                    # No link: drop any trailing parenthetical (e.g. section info).
                    instructor = re.sub(r"\s*\([^)]*\)\s*$", "", fac_text).strip()

                rows.append(
                    self.make_row(
                        academic_year,
                        term,
                        course_code=course_code,
                        section=section,
                        course_name=course_name,
                        instructor=instructor,
                        url=href,
                    )
                )
        return rows
