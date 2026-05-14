"""Course-schedule scraper for Washington College (Chestertown, MD).

Washington College publishes term schedules only as PDFs on the
registrar page. We scrape the index for PDF links, download each
one, find the "Subject - Computer Science" page, and extract the
CSI rows from pdfplumber's table extractor.

The schedule PDFs have variable column counts depending on which
optional columns (Currently Enrolled, W2/W3/Honors flags, crosslist
names) are present, so each row is parsed by locating the cell
matching a "HH:MM[AP]M - HH:MM[AP]M" time pattern and reading the
instructor / location / days from the three cells to its left.

Selenium is bypassed: the index page and PDFs are static, so we
fetch them with `requests` and parse with `BeautifulSoup` and
`pdfplumber`.
"""

import io
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

INDEX_URL = (
    "https://www.washcoll.edu/people_departments/offices/registrar/"
    "course-schedule.php"
)

# "Fall 2026 Course Schedule" / "FALL 2026 COURSE SCHEDULE" / "Spring 2025 Course Schedule".
LABEL_RE = re.compile(
    r"\b(?P<season>Fall|Spring)\s+(?P<year>\d{4})\b\s*-?\s*(?:Course\s+Schedule)?",
    re.I,
)
SEASON_TERM = {"fall": "F", "spring": "S"}

# Course-code cell like "CSI*111*10" -> ("CSI 111", "10").
COURSE_CODE_RE = re.compile(r"^(?P<subj>[A-Z]+)\*(?P<num>\d+\w*)\*(?P<section>\w+)$")

# Time cell like "8:30AM - 9:20AM" or "11:30AM - 12:45PM".
TIME_RE = re.compile(r"\d{1,2}:\d{2}\s*[AP]M\s*-\s*\d{1,2}:\d{2}\s*[AP]M")


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("\n", " ")).strip()


def parse_label(label):
    """Return ((start_year, end_year), term) or (None, None) for a link label
    like ``"FALL 2026 COURSE SCHEDULE"`` / ``"Spring 2025 Course Schedule"``.
    """
    m = LABEL_RE.search(label or "")
    if not m:
        return None, None
    year = int(m.group("year"))
    term = SEASON_TERM.get(m.group("season").lower())
    if term is None:
        return None, None
    if term == "F":
        return (year, year + 1), term
    return (year - 1, year), term


def _parse_row(row, source_url):
    """Convert one pdfplumber table row into a (cells) dict, or None.

    Variable column counts (because pdfplumber compresses blank columns
    between optional fields) mean we can't index columns positionally;
    instead, anchor on the cell matching `TIME_RE` and read the three
    cells immediately to its left as instructor / location / days.
    """
    if not row or len(row) < 3:
        return None
    code_cell = _clean(row[0])
    m = COURSE_CODE_RE.match(code_cell)
    if not m:
        return None
    course_code = f"{m.group('subj')} {m.group('num')}"
    section = m.group("section")
    title = _clean(row[1]) if len(row) > 1 else ""

    time_idx = None
    for i in range(2, len(row)):
        cell = row[i] or ""
        if TIME_RE.search(cell):
            time_idx = i
            break

    instructor, days, time_text, location = "", "", "", ""
    if time_idx is not None:
        time_text = _clean(row[time_idx])
        if time_idx - 1 >= 2:
            days = _clean(row[time_idx - 1])
        if time_idx - 2 >= 2:
            location = _clean(row[time_idx - 2])
        if time_idx - 3 >= 2:
            instructor = _clean(row[time_idx - 3])

    schedule_parts = []
    if days and time_text:
        schedule_parts.append(f"{days} {time_text}")
    elif time_text:
        schedule_parts.append(time_text)
    if location:
        schedule_parts.append(location)
    schedule = "; ".join(schedule_parts)

    return dict(
        course_code=course_code,
        section=section,
        course_name=title,
        instructor=instructor,
        time=schedule,
        url=source_url,
    )


class WashingtonCollegeScraper(CourseScheduleScraper):
    """Scrape Washington College's per-term PDF schedules for CSI courses."""

    college = College.WASHINGTON
    subject = "CSI"

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; cslac-scraper/1.0)"
        )

    def close(self):
        try:
            self._session.close()
        except Exception:
            pass
        super().close()

    def scrape(self):
        # Override the year/term loop: we don't know which terms are available
        # until we read the index, and there's a single PDF per term.
        try:
            resp = self._session.get(INDEX_URL, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  failed to load index: {e}", flush=True)
            return []

        wanted = set(self.past_academic_years(self.years_back))
        links = []  # [(academic_year, term, url, label)]
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href.lower().endswith(".pdf"):
                continue
            # The registrar lists Final-Exam PDFs alongside course-schedule
            # PDFs and both share the season+year prefix in the link text.
            # Restrict to URLs under the `course-schedule/` subdirectory so
            # we don't grab an exam schedule for the term's slot.
            if "course-schedule/" not in href.lower():
                continue
            label = _clean(a.get_text(" ", strip=True))
            academic_year, term = parse_label(label)
            if academic_year is None or term is None:
                continue
            if academic_year not in wanted:
                continue
            key = (academic_year, term)
            if key in seen:
                continue
            seen.add(key)
            links.append((academic_year, term, urljoin(INDEX_URL, href), label))

        if not links:
            print("  no usable PDF links found", flush=True)
            return []

        links.sort(key=lambda x: (x[0], {"F": 0, "S": 1}.get(x[1], 9)))
        rows = []
        for academic_year, term, url, label in links:
            tag = f"{academic_year[0]}-{str(academic_year[1])[-2:]}/{term}"
            try:
                page_rows = self._scrape_pdf(url, academic_year, term)
            except Exception as e:
                print(f"  [{tag}] failed: {e}", flush=True)
                continue
            print(f"  [{tag}] {len(page_rows)} sections ({label})", flush=True)
            rows.extend(page_rows)
        return rows

    def _scrape_pdf(self, url, academic_year, term):
        resp = self._session.get(url, timeout=60)
        resp.raise_for_status()
        rows = []
        seen = set()
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if f"Subject - {self._subject_full_name()}" not in text:
                    continue
                for table in page.extract_tables():
                    if not table:
                        continue
                    header = " ".join(c for c in (table[0] or []) if c)
                    if "Course" not in header or "Section Title" not in header:
                        continue
                    for raw_row in table[1:]:
                        parsed = _parse_row(raw_row, url)
                        if parsed is None:
                            continue
                        key = (parsed["course_code"], parsed["section"])
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(
                            self.make_row(academic_year, term, **parsed)
                        )
        return rows

    @staticmethod
    def _subject_full_name():
        return "Computer Science"
