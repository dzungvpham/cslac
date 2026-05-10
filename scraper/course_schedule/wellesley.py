"""Wellesley College course schedule scraper.

Sources are mixed:

* The "current/upcoming" semester is rendered live by an iframe at
  ``webapps.wellesley.edu/class_schedule/classes.php?subject=cs&template=top3``
  embedded in ``/cs/curriculum/current``. We parse the iframe's table of
  ``<td class="specific_font">`` blocks (each holds one section's full
  details).
* Older semesters are posted as one PDF per term, linked from the same
  ``/cs/curriculum/current`` page. Most are plain text and yield directly
  to ``pdfplumber.extract_tables()``. Two are encoded with a private cipher
  font that pdfplumber surfaces as ``(cid:N)`` tokens — applying
  ``chr(N + 29)`` decodes them. The Spring 2022 PDF additionally writes
  glyphs in reversed character order, so each decoded line must be reversed.

The driver page is fetched once at scrape start to discover both the iframe
URL and every linked PDF (anchored by labels like "Fall 2023 CS Schedule"),
so newly posted PDFs are picked up without code changes.
"""

import io
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

MAIN_URL = "https://www.wellesley.edu/cs/curriculum/current"
WWW1_BASE = "https://www1.wellesley.edu"

# PDFs whose decoded text comes out reversed character-by-character (the
# glyph stream is written right-to-left). Detected by URL substring.
REVERSED_PDF_HINTS = ("spring_2022_course_schedule",)

CID_RE = re.compile(r"\(cid:(\d+)\)")
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
DAY_ABBREV = {
    "Monday": "M",
    "Tuesday": "T",
    "Wednesday": "W",
    "Thursday": "Th",
    "Friday": "F",
}

# Each course token in a calendar cell starts with "CS" + digits, optionally
# followed by an L (e.g. CS111L is the lab co-req). Use a *head* regex to
# split a possibly multi-course cell, then parse each chunk.
COURSE_HEAD_RE = re.compile(r"\bCS\d{3}L?\b")
# Section codes seen in the wild: 01..NN, L01 (lab), D01 (discussion),
# A1/B2-style letter+digit, single letter A..F (Spring 2020).
SECTION_RE = re.compile(r"^(?:L?\d{1,3}|D\d{1,2}|[A-Z]\d{1,2}|[A-F])$")
# Course-name legend lines look like:
#   "CS111 Computer Programming and Problem Solving"
# possibly with two columns concatenated on one line. Split on a CS-code
# boundary and trim.
LEGEND_ENTRY_RE = re.compile(r"\b(CS\d{3}L?)\b\s+([^\n]*?)(?=\s*\bCS\d{3}L?\b|$)")

# Iframe header: "<th>CS Courses for Fall 2026</h2>" (sic — invalid close tag)
IFRAME_HEADER_RE = re.compile(r"CS Courses for (Fall|Spring)\s+(\d{4})", re.I)
# Iframe course anchor text: "CS 110 01 - Sociotechnical Dimensions ..."
IFRAME_LINK_RE = re.compile(
    r"^\s*CS\s*(?P<num>\d+L?)\s+(?P<section>\S+)\s*-\s*(?P<name>.+?)\s*$"
)


def _decode_cell(text, reverse=False):
    """Decode `(cid:N)` tokens via the +29 cipher and optionally reverse."""
    if not text:
        return text or ""
    decoded = CID_RE.sub(lambda m: chr(int(m.group(1)) + 29), text)
    if reverse:
        decoded = "\n".join(line[::-1] for line in decoded.split("\n"))
    return decoded


def _decode_table(table, reverse=False):
    return [[_decode_cell(c, reverse=reverse) for c in row] for row in table]


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def _has_day_names(cells):
    """True if 4+ weekday names appear in *distinct* cells.

    Counting per-cell rather than per-substring-of-joined-text is what
    distinguishes the calendar header row from the legend block, which
    crams the same day names into a single multi-line cell.
    """
    found = 0
    for c in cells:
        text = _norm(c)
        if not text:
            continue
        for d in DAY_NAMES:
            if re.fullmatch(rf"(?:Time\s+)?{d}", text) or text == d:
                found += 1
                break
    return found >= 4


def _parse_course_chunk(chunk):
    """Parse one course chunk like "CS111 01, E Mustafaraj (L180)".

    Returns dict with code/section/instructor/room (any may be empty).
    """
    s = _norm(chunk)
    if not s:
        return None
    # Pull off the trailing room "(...)" if present.
    room = ""
    paren = re.search(r"\(([^()]*)\)\s*$", s)
    if paren:
        room = _norm(paren.group(1))
        s = s[: paren.start()].rstrip(", ")
    # First whitespace-separated token is the course code.
    parts = s.split(None, 1)
    code = parts[0].rstrip(",").upper()
    rest = parts[1] if len(parts) > 1 else ""
    # Optional section is the next token if it matches SECTION_RE.
    section = ""
    if rest:
        head, _, tail = rest.partition(" ")
        head = head.rstrip(",")
        if SECTION_RE.fullmatch(head):
            section = head
            rest = tail
    instructor = _norm(rest.lstrip(", "))
    return {"code": code, "section": section, "instructor": instructor, "room": room}


def _parse_cell(text):
    """Yield a list of course dicts parsed from one calendar cell."""
    text = (text or "").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    matches = list(COURSE_HEAD_RE.finditer(text))
    if not matches:
        return []
    chunks = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunks.append(text[m.start():end])
    out = []
    for c in chunks:
        parsed = _parse_course_chunk(c)
        if parsed is not None:
            out.append(parsed)
    return out


def _build_legend(tables):
    """Return a dict mapping course code -> course name from the legend table.

    Wellesley's PDFs put the per-course-code key in the first row of the
    grid table or in a small standalone block above it. We greedily search
    every cell for `CS<num> <Title>` pairs.
    """
    legend = {}
    for table in tables:
        for row in table:
            for cell in row:
                text = (cell or "").replace("\n", " ")
                # Skip cells that are mostly schedule entries (have parentheses
                # for rooms / instructors).
                if "(" in text:
                    continue
                for m in LEGEND_ENTRY_RE.finditer(text):
                    code = m.group(1).upper()
                    name = _norm(m.group(2))
                    # Drop trailing day-name / "Time" header leakage.
                    name = re.split(
                        r"\s+(?:Time|Monday|Tuesday|Wednesday|Thursday|Friday)\b",
                        name,
                    )[0].strip()
                    # Names that *are* day-axis labels are noise, not titles.
                    if not name or name in DAY_NAMES or name.lower() == "time":
                        continue
                    # Reject schedule-entry leakage: real legend titles are
                    # English words, not section codes ("L06 Mawhorter") or
                    # bare instructor lines.
                    first = name.split()[0]
                    if SECTION_RE.fullmatch(first):
                        continue
                    if code not in legend:
                        legend[code] = name
    return legend


def _select_grid(tables):
    """Pick the table that holds the calendar grid and report orientation.

    Returns (table, orientation, header_row_or_col_idx) where orientation is
    one of:
      * "rows-times": rows are time slots, columns are days (the common case).
      * "rows-days":  rows are days, columns are time slots (Spring 2022,
        whose glyph stream is reversed AND transposed in the grid).
    Returns (None, None, None) if no grid is found.
    """
    for table in tables:
        # Standard orientation: a row contains 4+ day names.
        for r_idx, row in enumerate(table):
            if _has_day_names(row):
                return table, "rows-times", r_idx
        # Transposed: a column contains 4+ day names.
        if not table:
            continue
        n_cols = max((len(r) for r in table), default=0)
        for c_idx in range(n_cols):
            col = [row[c_idx] if c_idx < len(row) else "" for row in table]
            if _has_day_names(col):
                return table, "rows-days", c_idx
    return None, None, None


def _walk_grid(table, orientation, header_idx):
    """Yield (cell_text, day, time) tuples for every body cell in the grid."""
    if orientation == "rows-times":
        header_row = [_norm(c) for c in table[header_idx]]
        # Column 0 of header_row is typically "Time"; the rest are day names.
        # Body rows are everything after `header_idx`.
        for row in table[header_idx + 1:]:
            time_label = _norm(row[0]) if row else ""
            for c_idx in range(1, min(len(row), len(header_row))):
                day = header_row[c_idx]
                if day not in DAY_NAMES:
                    continue
                yield row[c_idx], day, time_label
    else:  # rows-days
        # Columns are time slots; column `header_idx` holds day names. The
        # time labels live in the row whose day-column cell is "Time".
        n_cols = max((len(r) for r in table), default=0)
        time_row = None
        for row in table:
            if header_idx < len(row) and _norm(row[header_idx]).lower() == "time":
                time_row = row
                break
        time_labels = []
        for c_idx in range(n_cols):
            time_labels.append(_norm(time_row[c_idx]) if time_row and c_idx < len(time_row) else "")
        for row in table:
            day = _norm(row[header_idx]) if header_idx < len(row) else ""
            if day not in DAY_NAMES:
                continue
            for c_idx in range(len(row)):
                if c_idx == header_idx:
                    continue
                label = time_labels[c_idx] if c_idx < len(time_labels) else ""
                # In transposed mode, columns without a real time label sit
                # outside the schedule grid (legend strips, side margins) and
                # any course tokens there are stray references, not meetings.
                if not label:
                    continue
                yield row[c_idx], day, label


def _aggregate_meetings(meetings):
    """Collapse a list of (day, time, room) into a compact string.

    Groups meetings sharing the same (time, room) into a contiguous day
    string ("MTh 8:30-9:45 (L180)"). Distinct groups are joined with "; ".
    """
    # Preserve weekday ordering.
    day_order = {d: i for i, d in enumerate(DAY_NAMES)}

    groups = {}  # (time, room) -> ordered list of days
    for day, time, room in meetings:
        key = (time, room)
        groups.setdefault(key, [])
        if day not in groups[key]:
            groups[key].append(day)

    parts = []
    for (time, room), days in groups.items():
        days_sorted = sorted(days, key=lambda d: day_order.get(d, 99))
        day_str = "".join(DAY_ABBREV.get(d, d[0]) for d in days_sorted)
        bits = [day_str]
        if time:
            bits.append(time)
        s = " ".join(bits)
        if room:
            s += f" ({room})"
        parts.append(s)
    return "; ".join(parts)


class WellesleyScraper(CourseScheduleScraper):
    college = College.WELLESLEY
    terms = ["F", "S"]
    # Bumped past the default 5 because Wellesley's archive goes back to AY
    # 2019-20 (with a gap at 2020-21 and 2024-25, which we just skip).
    years_back = 7
    fresh_driver_per_load = False
    wait_for = "iframe"

    # Sentinel term for the live iframe page; replaced by the real term
    # parsed from the iframe header before rows are emitted.
    LIVE_TERM = "__LIVE__"

    def __init__(self, driver=None):
        super().__init__(driver)
        self._iframe_url = None
        self._pdf_urls = None  # dict: ((start, end), term) -> url

    # ---- discovery -----------------------------------------------------------

    def _discover(self):
        """Fetch the driver page once; populate iframe URL + PDF link map."""
        if self._pdf_urls is not None:
            return
        html = self.load(MAIN_URL, wait_for="iframe")
        soup = BeautifulSoup(html, "html.parser")

        iframe = soup.find("iframe", src=True)
        if iframe:
            src = iframe["src"]
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(MAIN_URL, src)
            self._iframe_url = src

        pdfs = {}
        for a in soup.select('a[href*=".pdf"]'):
            href = a.get("href", "")
            if href.startswith("/"):
                href = WWW1_BASE + href
            label = a.get_text(" ", strip=True)
            m = re.search(r"\b(Fall|Spring)\s+(\d{4})\b", label, re.I)
            if not m:
                continue
            term_word = m.group(1).capitalize()
            year = int(m.group(2))
            if term_word == "Fall":
                ay, term = (year, year + 1), "F"
            else:
                ay, term = (year - 1, year), "S"
            pdfs.setdefault((ay, term), href)
        self._pdf_urls = pdfs

    # ---- driver overrides ----------------------------------------------------

    def schedule_pages(self):
        self._discover()
        seen = set()
        for ay in self.past_academic_years(self.years_back):
            for t in self.terms:
                if (ay, t) in self._pdf_urls:
                    yield ay, t
                    seen.add((ay, t))
        # The iframe shows the upcoming/current semester, which (during the
        # spring or summer) is Fall of *next* AY. We yield a placeholder pair;
        # parse_page replaces it with whatever term the iframe header reports.
        today = datetime.now()
        current_start = today.year if today.month >= 7 else today.year - 1
        live_ay = (current_start + 1, current_start + 2)
        yield live_ay, self.LIVE_TERM

    def fetch_page(self, academic_year, term):
        self._discover()
        if (academic_year, term) in self._pdf_urls:
            url = self._pdf_urls[(academic_year, term)]
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return ("pdf", url, r.content)
        if term == self.LIVE_TERM:
            if not self._iframe_url:
                return None
            html = self.load(self._iframe_url, wait_for="td.specific_font")
            return ("html", self._iframe_url, html)
        return None

    def parse_page(self, payload, academic_year, term):
        if payload is None:
            return []
        kind, url, data = payload
        if kind == "pdf":
            return self._parse_pdf(data, url, academic_year, term)
        return self._parse_iframe(data, url)

    # ---- PDF parsing ---------------------------------------------------------

    def _parse_pdf(self, content, url, academic_year, term):
        reverse = any(hint in url for hint in REVERSED_PDF_HINTS)
        all_tables = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                for t in tables:
                    all_tables.append(_decode_table(t, reverse=reverse))

        if not all_tables:
            return []

        legend = _build_legend(all_tables)
        table, orientation, header_idx = _select_grid(all_tables)
        if table is None:
            return []

        # Aggregate per (code, section).
        agg = {}  # key -> {meetings: [(day,time,room)], instructors: set}
        for cell, day, time_label in _walk_grid(table, orientation, header_idx):
            for course in _parse_cell(cell):
                key = (course["code"], course["section"])
                slot = agg.setdefault(key, {"meetings": [], "instructors": []})
                slot["meetings"].append((day, time_label, course["room"]))
                if course["instructor"] and course["instructor"] not in slot["instructors"]:
                    slot["instructors"].append(course["instructor"])

        rows = []
        for (code, section), info in agg.items():
            instructor = ", ".join(info["instructors"])
            time_str = _aggregate_meetings(info["meetings"])
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=code,
                    section=section,
                    course_name=legend.get(code, ""),
                    instructor=instructor,
                    time=time_str,
                    url=url,
                )
            )
        return rows

    # ---- iframe parsing ------------------------------------------------------

    def _parse_iframe(self, html, url):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        # Walk the outer table row by row so a `<th>` term header can scope
        # the section blocks that follow it (the iframe currently shows one
        # term, but `template=top3` may grow back to three).
        current_year = None
        current_term = None
        for tr in soup.find_all("tr"):
            th = tr.find("th")
            if th is not None:
                m = IFRAME_HEADER_RE.search(th.get_text(" ", strip=True))
                if m:
                    word, year = m.group(1).capitalize(), int(m.group(2))
                    if word == "Fall":
                        current_year, current_term = (year, year + 1), "F"
                    else:
                        current_year, current_term = (year - 1, year), "S"
                    continue
            td = tr.find("td", class_="specific_font")
            if td is None or current_year is None:
                continue
            row = self._parse_iframe_section(td, current_year, current_term, url)
            if row is not None:
                rows.append(row)
        return rows

    def _parse_iframe_section(self, td, academic_year, term, url):
        # Anchor text holds "CS <num> <section> - <name>".
        link = td.find("a")
        if link is None:
            return None
        head = _norm(link.get_text(" ", strip=True))
        m = IFRAME_LINK_RE.match(head)
        if not m:
            return None
        course_code = "CS" + m.group("num")
        section = m.group("section")
        course_name = _norm(m.group("name"))

        details = {}
        # The hidden div holds <tr><th>Label:</th><td>Value</td></tr> rows.
        for sub_tr in td.select("div table tr"):
            sub_th = sub_tr.find("th")
            sub_td = sub_tr.find("td")
            if sub_th and sub_td:
                key = _norm(sub_th.get_text(" ", strip=True)).rstrip(":").lower()
                details[key] = _norm(sub_td.get_text(" ", strip=True))

        instructor = details.get("instructors", "")
        time_str = details.get("meeting time(s)", "")

        return self.make_row(
            academic_year,
            term,
            course_code=course_code,
            section=section,
            course_name=course_name,
            instructor=instructor,
            time=time_str,
            url=url,
        )
