"""University of Richmond course schedule scraper.

Richmond doesn't expose a queryable course catalog; the registrar publishes
class schedules as Excel sheets in a public Box folder:

    https://richmond.app.box.com/s/76rltos9mgu9pjnte2u669ex0ff24ejq

Layout inside the share:

    Class Schedules/
      2017-2018/
        Fall 2017.xlsx
        Spring 2018.xlsx
        Summer 2018.xlsx
      ...
      2024-2025/
        Fall 2024.xlsx
        ...
      2025-2026/
        Fall 2025/
          Undergraduate Arts & Sciences, Business, ..._Fall 2025.xlsx   <-- the one we want
          Law_Fall 2025.xlsx                                             <-- skip
          Graduate Business_Fall 2025.xlsx                               <-- skip
          School of Professional & Continuing Studies_Fall 2025.xlsx     <-- skip
        Spring 2026/...
        Summer 2026/...

Older AYs ship one xlsx per term directly in the AY folder; from 2025-26
onward each term gets a subfolder with one xlsx per school. We always pick
the file whose name starts with "Undergraduate Arts" (the only one whose
``CMSC`` rows are CS-department offerings — Law / Graduate Business /
SPCS don't carry CMSC).

Box doesn't let you list a public share via api.box.com without an OAuth
token, but the web UI's "Download" button hits a public endpoint that
streams the entire share as a single ~5 MB zip. We fetch that zip once at
scraper startup and pull each term's xlsx out of it in memory.

Each xlsx schema (1 row per (section, meeting_pattern, ATTR) tuple):

    CAMPUS, CRN, SUBJ, CRSE, SEC, TITLE, MAX, ACT, ATTR, CR,
    SUN, MON, TUE, WED, THU, FRI, SAT,   <-- day-of-week letter or NaN
    S TM, E TM, BLDG, RM, CODE, INSTRUCTOR, COMMENTS, START DATE, END DATE

A section with two meeting patterns (e.g. lecture M/W + lab F) shows up as
two rows; multi-attribute courses get one row per ATTR. We dedupe by
(CRN, days, start, end, BLDG, RM) and emit one row per section.
"""

import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

SHARE_NAME = "76rltos9mgu9pjnte2u669ex0ff24ejq"
SHARE_URL = f"https://richmond.app.box.com/s/{SHARE_NAME}"
ROOT_FOLDER_ID = "194952000490"  # "Class Schedules" — fixed for this share

# Box bulk-download endpoint: returns JSON pointing at the zipped share.
ZIP_INIT_URL = "https://richmond.app.box.com/index.php"

TERM_TO_SEASON = {"F": "Fall", "S": "Spring", "Su": "Summer"}

# Header column names in each xlsx.
DAY_COLUMNS = [
    ("SUN", "Su"),
    ("MON", "M"),
    ("TUE", "T"),
    ("WED", "W"),
    ("THU", "Th"),
    ("FRI", "F"),
    ("SAT", "Sa"),
]


class RichmondScraper(CourseScheduleScraper):
    college = College.RICHMOND
    terms = ["F", "S", "Su"]
    # We never use Selenium — the Box bulk-download endpoint is plain HTTP.
    fresh_driver_per_load = False

    def __init__(self, driver=None):
        super().__init__(driver=driver)
        self._zip = None

    # ---- Box zip download --------------------------------------------------

    def _ensure_zip(self):
        if self._zip is not None:
            return
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            }
        )
        # Step 1: load the share page to seed cookies + grab the request
        # token (Box's app-api endpoints reject calls without it).
        r = s.get(SHARE_URL, timeout=self.page_load_timeout)
        r.raise_for_status()
        m = re.search(r'requestToken":"([^"]+)"', r.text)
        if m is None:
            raise RuntimeError("Richmond/Box: requestToken not found on share page")
        token = m.group(1)
        api_hdrs = {
            "Request-Token": token,
            "X-Box-EndUser-API": f"sharedName={SHARE_NAME}",
            "Accept": "application/json",
            "Referer": SHARE_URL,
        }
        # Step 2: ask Box to prepare the zip; it answers JSON with the
        # actual signed download URL on dl.boxcloud.com.
        init = s.get(
            ZIP_INIT_URL,
            params={
                "folder_id": ROOT_FOLDER_ID,
                "q[shared_item][shared_name]": SHARE_NAME,
                "rm": "box_v2_zip_shared_folder",
            },
            headers=api_hdrs,
            timeout=self.page_load_timeout,
        )
        init.raise_for_status()
        info = init.json()
        if info.get("result") != "success" or not info.get("download_url"):
            raise RuntimeError(f"Richmond/Box: zip prepare failed: {info!r}")
        # Step 3: stream the zip into memory (~5 MB total).
        with s.get(info["download_url"], stream=True, timeout=300) as dl:
            dl.raise_for_status()
            buf = io.BytesIO()
            for chunk in dl.iter_content(chunk_size=64 * 1024):
                buf.write(chunk)
        buf.seek(0)
        self._zip = zipfile.ZipFile(buf)

    # ---- framework hooks ---------------------------------------------------

    def url_for(self, academic_year, term):
        # Used only for logging; the real fetch goes through `fetch_page`.
        return SHARE_URL

    def fetch_page(self, academic_year, term):
        self._ensure_zip()
        path = self._find_xlsx(academic_year, term)
        if path is None:
            return None  # signals "not available" to the base scrape loop
        with self._zip.open(path) as f:
            return f.read()

    def parse_page(self, xlsx_bytes, academic_year, term):
        df = pd.read_excel(io.BytesIO(xlsx_bytes))
        if "SUBJ" not in df.columns:
            return []
        cmsc = df[df["SUBJ"].astype(str).str.strip() == "CMSC"]
        rows = []
        for crn, grp in cmsc.groupby("CRN", sort=False):
            row = self._row_for_section(grp, academic_year, term)
            if row is not None:
                rows.append(row)
        return rows

    # ---- xlsx lookup -------------------------------------------------------

    def _find_xlsx(self, academic_year, term):
        """Return the zip path of the xlsx for this (AY, term), or None.

        Tries two layouts:
          1. ``Class Schedules/<start>-<end>/<Season> <year>.xlsx`` (older)
          2. ``Class Schedules/<start>-<end>/<Season> <year>/Undergraduate Arts*.xlsx``
        """
        season = TERM_TO_SEASON.get(term)
        if season is None:
            return None
        start, end = academic_year
        ay_dir = f"Class Schedules/{start}-{end}/"
        # Fall is in the start year; Winter/Spring/Summer are in the end year.
        cal_year = start if season == "Fall" else end
        term_label = f"{season} {cal_year}"

        names = [n for n in self._zip.namelist() if n.startswith(ay_dir)]
        # Layout 1: a single xlsx whose name is exactly "<Season> <year>.xlsx".
        flat_path = f"{ay_dir}{term_label}.xlsx"
        if flat_path in names:
            return flat_path
        # Layout 2: a subfolder "<Season> <year>/" with per-school xlsx files.
        sub_prefix = f"{ay_dir}{term_label}/"
        sub_files = [
            n
            for n in names
            if n.startswith(sub_prefix)
            and n.lower().endswith(".xlsx")
            and "/" not in n[len(sub_prefix) :]
        ]
        if not sub_files:
            return None
        # Pick the Undergraduate Arts & Sciences sheet (the one carrying CMSC
        # offerings). Box ships file names with both "Arts &" and "Art &"
        # spellings across terms, so match loosely.
        for n in sub_files:
            base = n[len(sub_prefix) :].lower()
            if base.startswith("undergraduate art"):
                return n
        # Fallback: take the alphabetically first xlsx (rare — only happens if
        # Box renames the file in a way that breaks the prefix check).
        return sorted(sub_files)[0]

    # ---- row aggregation ---------------------------------------------------

    def _row_for_section(self, grp, academic_year, term):
        """Collapse all rows for one CRN into a single section row."""
        first = grp.iloc[0]
        course_code = _format_course_code(first.get("SUBJ"), first.get("CRSE"))
        section = _format_section(first.get("SEC"))
        course_name = _str(first.get("TITLE"))
        instructor = _format_instructors(grp["INSTRUCTOR"])
        time_str = _format_meetings(grp)

        return self.make_row(
            academic_year,
            term,
            course_code=course_code,
            section=section,
            course_name=course_name,
            instructor=instructor,
            time=time_str,
            url=SHARE_URL,
        )


# ---- helpers ---------------------------------------------------------------


def _str(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


def _format_section(val):
    """Older xlsx stores SEC as int, newer as a zero-padded string. Normalize
    to ``"NN"`` (two-digit, zero-padded) for short numeric sections so the
    same section reads the same across years.
    """
    s = _str(val)
    if s.isdigit() and len(s) < 2:
        return s.zfill(2)
    return s


def _format_course_code(subj, crse):
    subj_s = _str(subj)
    if not subj_s:
        return ""
    if crse is None or (isinstance(crse, float) and pd.isna(crse)):
        return subj_s
    # CRSE comes as int; preserve it without a trailing ".0".
    if isinstance(crse, float):
        crse = int(crse)
    return f"{subj_s} {crse}"


def _format_instructors(series):
    """Last names, deduped, in the order they appear."""
    seen = []
    for v in series:
        name = _str(v)
        if name and name not in seen:
            seen.append(name)
    return ", ".join(seen)


def _format_meetings(grp):
    """Collapse the per-row meeting patterns for one CRN.

    Each row has at most one day-of-week column populated (Richmond emits
    one row per (meeting_pattern, ATTR), so a M/W lecture + F lab section
    shows up as 8 rows when there are 4 ATTR codes). We dedupe on
    (start, end, BLDG, RM) and merge the day letters across rows that share
    a (start, end, BLDG, RM) tuple.
    """
    # key -> set of day abbreviations (ordered by week order)
    groups = {}
    order = []
    for _, row in grp.iterrows():
        days = _row_days(row)
        start_t = _format_time(row.get("S TM"))
        end_t = _format_time(row.get("E TM"))
        bldg = _str(row.get("BLDG"))
        rm = _str(row.get("RM"))
        if not days and not start_t and not end_t and not bldg and not rm:
            continue
        location = " ".join(p for p in [bldg, rm] if p).strip()
        key = (start_t, end_t, location)
        if key not in groups:
            groups[key] = set()
            order.append(key)
        groups[key].update(days)

    parts = []
    for key in order:
        start_t, end_t, location = key
        days_sorted = "".join(
            abbr for _, abbr in DAY_COLUMNS if abbr in groups[key]
        )
        time_range = ""
        if start_t and end_t:
            time_range = f"{start_t}-{end_t}"
        elif start_t:
            time_range = start_t
        bits = []
        if days_sorted:
            bits.append(days_sorted)
        if time_range:
            bits.append(time_range)
        s = " ".join(bits)
        if location:
            s = f"{s} ({location})" if s else f"({location})"
        if s:
            parts.append(s)
    return "; ".join(parts)


def _row_days(row):
    """Yield the day abbreviations marked on this row."""
    days = []
    for col, abbr in DAY_COLUMNS:
        val = row.get(col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        if str(val).strip():
            days.append(abbr)
    return days


def _format_time(val):
    """Format a `datetime.time` (or NaT) as ``H:MMam`` / ``H:MMpm``.

    Richmond's xlsx stores times in 12-hour format with no AM/PM marker, so
    the cell ``1:30 PM`` round-trips as ``datetime.time(1, 30)`` — there's
    no way to recover the original period from the value alone. We infer
    using a college-schedule heuristic: hours 1-7 are afternoon/evening,
    hours 8-11 are morning, hour 12 is noon. (CS classes don't run at 1 AM.)
    """
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    try:
        h = val.hour
        m = val.minute
    except AttributeError:
        return _str(val)
    if h == 0 and m == 0:
        return ""
    suffix = "pm" if (h == 12 or h < 8) else "am"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d}{suffix}"
