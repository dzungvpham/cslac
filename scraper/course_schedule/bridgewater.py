"""Bridgewater College course schedule scraper.

Bridgewater publishes each academic year's master schedule as a single
Excel workbook hosted on Box, linked from the Registrar page

    https://www.bridgewater.edu/life-at-bridgewater/services-for-students/registrar/

The list entries on that page read like

    <li><a href="https://bridgewater.box.com/s/<hash>">
        2026-2027 Academic Year Schedule</a> – Includes separate tabs
    for 2026 Fall and 2027 Spring.</li>

Each workbook has one sheet per term (``"2026 Fall"``, ``"2027 Spring"``)
with columns ``Section Name | Short Title | Course Type | Days |
Start Time | End Time | Credits | Capacity | Comments``. Section names
look like ``CSCI-101-01``; instructor info is *not* in the file. The
Comments column occasionally carries cross-list / online tags.

Box share links resolve to a direct download at

    https://bridgewater.box.com/shared/static/<hash>.xlsx

so we skip the HTML viewer entirely. Bridgewater only keeps the current
and upcoming AY workbooks online — older years drop off — and the
registrar page is rewritten whenever a new one is posted, so the merge
logic in `CourseScheduleScraper.run` is what preserves prior terms.
"""

import re
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

REGISTRAR_URL = (
    "https://www.bridgewater.edu/life-at-bridgewater/services-for-students/registrar/"
)
DOWNLOAD_URL = "https://bridgewater.box.com/shared/static/{hash}.xlsx"

AY_LINK_RE = re.compile(
    r"^\s*(?P<start>\d{4})\s*-\s*(?P<end>\d{4})\s+Academic\s+Year\s+Schedule",
    re.I,
)
BOX_HASH_RE = re.compile(r"bridgewater\.box\.com/s/(?P<hash>[a-z0-9]+)", re.I)

# `"CSCI-101-01"` -> code `"CSCI 101"`, section `"01"`.
SECTION_RE = re.compile(
    r"^(?P<subject>[A-Z]+)-(?P<num>\d+\w*)-(?P<section>\w+)\s*$"
)

SHEET_TERM_RE = re.compile(
    r"^\s*(?P<year>\d{4})\s+(?P<season>Fall|Spring|Summer|Winter|May)\b",
    re.I,
)
SEASON_TERM = {
    "fall": "F",
    "winter": "W",
    "spring": "S",
    "summer": "Su",
    "may": "Su",  # May term — bucket with summer for sort order.
}

SUBJECTS = {"CSCI", "DSA"}  # Computer Science + Data Science & Analytics.


class BridgewaterScraper(CourseScheduleScraper):
    college = College.BRIDGEWATER
    # Discovery is "whatever AY workbooks are currently linked"; we don't
    # iterate over `past_academic_years`.
    terms = []
    fresh_driver_per_load = False

    def scrape(self):
        try:
            workbooks = self._discover_workbooks()
        except requests.RequestException as e:
            print(f"  registrar fetch failed: {e}", flush=True)
            return []
        if not workbooks:
            print("  no academic-year workbooks linked from registrar", flush=True)
            return []
        rows = []
        for academic_year, url in workbooks:
            label = f"{academic_year[0]}-{academic_year[1] % 100:02d}"
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  [{label}] download failed: {e}", flush=True)
                continue
            try:
                xl = pd.ExcelFile(BytesIO(resp.content))
            except Exception as e:
                print(f"  [{label}] excel open failed: {e}", flush=True)
                continue
            for sheet in xl.sheet_names:
                term = self._term_from_sheet(sheet)
                if term is None:
                    print(f"  [{label}/{sheet}] unrecognized sheet, skipping", flush=True)
                    continue
                try:
                    df = pd.read_excel(xl, sheet_name=sheet)
                except Exception as e:
                    print(f"  [{label}/{sheet}] parse failed: {e}", flush=True)
                    continue
                page_rows = self._parse_sheet(df, academic_year, term, url)
                print(f"  [{label}/{term}] {len(page_rows)} sections", flush=True)
                rows.extend(page_rows)
        return rows

    def _discover_workbooks(self):
        """Return ``[((start, end), download_url), ...]`` for each AY
        schedule currently linked from the registrar page.
        """
        resp = requests.get(REGISTRAR_URL, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        seen = set()
        out = []
        for a in soup.find_all("a", href=True):
            m = AY_LINK_RE.match(a.get_text(" ", strip=True))
            if not m:
                continue
            hm = BOX_HASH_RE.search(a["href"])
            if not hm:
                continue
            ay = (int(m.group("start")), int(m.group("end")))
            key = (ay, hm.group("hash"))
            if key in seen:
                continue
            seen.add(key)
            out.append((ay, DOWNLOAD_URL.format(hash=hm.group("hash"))))
        return out

    @staticmethod
    def _term_from_sheet(sheet_name):
        m = SHEET_TERM_RE.match(sheet_name)
        if not m:
            return None
        return SEASON_TERM.get(m.group("season").lower())

    def _parse_sheet(self, df, academic_year, term, url):
        rows = []
        for _, r in df.iterrows():
            section_name = str(r.get("Section Name", "")).strip()
            m = SECTION_RE.match(section_name)
            if not m:
                continue
            if m.group("subject") not in SUBJECTS:
                continue
            rows.append(
                self.make_row(
                    academic_year,
                    term,
                    course_code=f"{m.group('subject')} {m.group('num')}",
                    section=m.group("section"),
                    course_name=_clean(r.get("Short Title")),
                    instructor="",  # not present in the workbook
                    time=_meeting(r),
                    url=url,
                )
            )
        return rows


def _clean(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def _meeting(row):
    days = _clean(row.get("Days"))
    start = _fmt_time(row.get("Start Time"))
    end = _fmt_time(row.get("End Time"))
    parts = []
    if days:
        parts.append(days)
    if start and end:
        parts.append(f"{start}–{end}")
    elif start:
        parts.append(start)
    return " ".join(parts)


def _fmt_time(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    # Workbook cells are typed as datetime.time; render as "HH:MM".
    if hasattr(val, "strftime"):
        return val.strftime("%H:%M")
    s = str(val).strip()
    # `"09:00:00"` -> `"09:00"`.
    m = re.match(r"^(\d{1,2}:\d{2})(:\d{2})?$", s)
    return m.group(1) if m else s
