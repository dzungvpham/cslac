"""Wesleyan University course schedule scraper.

Each academic year is one URL on `owaprod-pub.wesleyan.edu/reg/!wesmaps_page.html`
with a `term` parameter. The returned page covers Fall, Winter, and Spring of
that academic year, delimited by `<a name="fall">`/`"winter"`/`"spring"`
anchors. Each course-section row is a `<TR>` with three `<TD>` cells:
course code (`COMP112-01`), title, and instructor + raw schedule.

The `term` parameter encodes the start year: `1{YY}9` where `YY` is the last
two digits of the start year (2025-26 -> 1259, 2024-25 -> 1249). Inside the
page, the Winter and Spring sections link to `term+1` and `term+2`
respectively, which we use to decide which season a `<TR>` belongs to.

The schedule cell encodes days as a 7-char `.MTWRF.` mask (positions
Sun-Sat); we strip the dots so meetings read e.g. "MW 02:50PM-04:10PM".
The page is plain HTML, so we use `requests` instead of Selenium.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

URL_TEMPLATE = (
    "https://owaprod-pub.wesleyan.edu/reg/!wesmaps_page.html"
    "?stuid=&facid=NONE&crse_list=COMP&term={term}&offered=Y"
)

# "COMP112-01" -> code "COMP112", section "01".
# Codes can have a letter suffix (COMP131F, COMP360A, COMP112Z).
COURSE_ID_RE = re.compile(r"^(?P<code>[A-Z]+\d+[A-Z]*)-(?P<section>\w+)$")

# 7-char day mask using `.MTWRF.` positional notation.
DAY_MASK_RE = re.compile(r"[.MTWRF]{7}")


class WesleyanScraper(CourseScheduleScraper):
    college = College.WESLEYAN
    # One URL per academic year covers F/W/S together. We don't iterate
    # terms; `parse_page` emits rows for all three.
    terms = []

    @staticmethod
    def _base_term(academic_year):
        start_year = academic_year[0]
        return 1009 + 10 * (start_year - 2000)

    def url_for(self, academic_year, term):
        return URL_TEMPLATE.format(term=self._base_term(academic_year))

    def fetch_page(self, academic_year, term):
        resp = requests.get(self.url_for(academic_year, term), timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse_page(self, html, academic_year, term):
        soup = BeautifulSoup(html, "html.parser")
        base = self._base_term(academic_year)
        term_for_code = {base: "F", base + 1: "W", base + 2: "S"}

        rows = []
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td", recursive=False)
            if len(cells) != 3:
                continue
            link = cells[0].find("a", href=True)
            if link is None:
                continue
            course_id = link.get_text(strip=True)
            m = COURSE_ID_RE.match(course_id)
            if not m:
                continue
            href = link["href"]
            term_match = re.search(r"term=(\d+)", href)
            if not term_match:
                continue
            term_code = int(term_match.group(1))
            term_letter = term_for_code.get(term_code)
            if term_letter is None:
                # Cross-listings sometimes link to other academic years; skip.
                continue

            course_name = _clean(cells[1].get_text(" ", strip=True))
            instructor_link = cells[2].find("a")
            instructor = _clean(instructor_link.get_text(" ", strip=True)) if instructor_link else ""
            schedule = _extract_schedule(cells[2])

            rows.append(
                self.make_row(
                    academic_year,
                    term_letter,
                    course_code=m.group("code"),
                    section=m.group("section"),
                    course_name=course_name,
                    instructor=instructor,
                    time=schedule,
                    url=f"https://owaprod-pub.wesleyan.edu/reg/{href}" if href.startswith("!") else href,
                )
            )
        return rows


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_schedule(cell):
    """Return the days+time string from the instructor cell.

    The cell looks like `<a>Name</a>&nbsp;...<br>..T.... 08:50AM-10:10AM;
    ....R.. 08:50AM-10:10AM;  SCIE121;  OLIN014;` — schedule is what comes
    after the `<br>`. We strip the 7-char day-mask dots so meetings read as
    e.g. `T` / `MWF` rather than `..T....` / `.M.W.F.`.
    """
    br = cell.find("br")
    if br is None:
        return ""
    raw = "".join(str(s) for s in br.next_siblings if isinstance(s, str))
    cleaned = DAY_MASK_RE.sub(lambda m: m.group(0).replace(".", ""), raw)
    return _clean(cleaned)
