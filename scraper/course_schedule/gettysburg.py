"""Gettysburg College course schedule scraper.

Gettysburg runs Oracle PeopleSoft Campus Solutions ("Class Search") at
``psinfo1.gettysburg.edu/psc/SA8PROD/EMPLOYEE/HRMS/c/
GBC_STUDENT_RECORDS.GBC_GUEST_CLS_SRCH.GBL``. The page renders a single
HTML form whose POST submission returns server-rendered HTML — there is
no public JSON endpoint — so we use ``requests`` + BeautifulSoup.

Two-step flow per term:

  1. ``GET`` the search page once per session. Extract the ``ICSID``
     state token (PeopleSoft regenerates this per session; the POST is
     rejected without it) and the ``<select name="CLASS_SRCH_WRK2_STRM$35$">``
     term options, e.g. ``"2258" -> "Fall, 2025"``.
  2. For each ``(academic_year, term)``, ``POST`` back to the same URL
     with ``ICAction=CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH`` (the search
     button) and the subject set to ``CS``. The "Show Open Classes
     Only" checkbox is on by default — uncheck it by sending
     ``SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$3=N`` and omitting the
     checkbox itself (this is the standard PeopleSoft idiom).

The result page renders each course as a group container

    ``win0divSSR_CLSRSLT_WRK_GROUPBOX2GP$<G>``

whose heading is ``"CS 107 - Introduction to Scientific Computation"``,
followed by one ``MTG_*$<S>`` row per section (``$<S>`` is a global
counter across all groups, not nested under ``$<G>``). We walk the
document in order, tracking the current group heading, and assign each
section to it.
"""

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from constants import College  # noqa: E402

from course_schedule.course_schedule_scraper import CourseScheduleScraper

URL = (
    "https://psinfo1.gettysburg.edu/psc/SA8PROD/EMPLOYEE/HRMS/c/"
    "GBC_STUDENT_RECORDS.GBC_GUEST_CLS_SRCH.GBL"
)
SUBJECT = "CS"

# "Fall, 2025" / "Spring, 2026" / "Summer, 2025".
TERM_DESC_RE = re.compile(r"^\s*(?P<season>Fall|Spring|Summer)\s*,\s*(?P<year>\d{4})", re.I)

# "CS 107 - Introduction to Scientific Computation"
# "CS 220-NS - Database Systems"  (course numbers can carry a suffix)
HEADING_RE = re.compile(r"^\s*(?P<code>[A-Z]+\s+\d+\w*(?:-\w+)?)\s+-\s+(?P<name>.+?)\s*$")

# Days emitted by PeopleSoft as a single concatenated string:
# "MoWeFr", "TuTh", "Mo", "Sa", etc.
DAY_TOKENS = [
    ("Mo", "M"),
    ("Tu", "T"),
    ("We", "W"),
    ("Th", "Th"),
    ("Fr", "F"),
    ("Sa", "Sa"),
    ("Su", "Su"),
]


class GettysburgScraper(CourseScheduleScraper):
    college = College.GETTYSBURG
    terms = ["F", "S"]
    # Pure-HTML form, no Selenium needed.
    fresh_driver_per_load = False
    request_timeout = 60

    def __init__(self, driver=None):
        super().__init__(driver)
        self._session: requests.Session | None = None
        self._icsid: str | None = None
        self._term_codes: dict | None = None  # (ay, term) -> peoplesoft code

    def _ensure_session(self):
        if self._session is None:
            s = requests.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0 (cs-lac scraper)"})
            self._session = s
        return self._session

    def _discover_terms(self):
        if self._term_codes is not None:
            return self._term_codes
        s = self._ensure_session()
        resp = s.get(URL, timeout=self.request_timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        icsid_el = soup.find("input", attrs={"name": "ICSID"})
        if icsid_el is None or not icsid_el.get("value"):
            raise RuntimeError("Gettysburg: ICSID not present on Class Search page")
        self._icsid = icsid_el["value"]

        mapping = {}
        select = soup.find("select", attrs={"name": "CLASS_SRCH_WRK2_STRM$35$"})
        if select is not None:
            for opt in select.find_all("option"):
                code = (opt.get("value") or "").strip()
                desc = opt.get_text(" ", strip=True)
                m = TERM_DESC_RE.match(desc)
                if not code or not m:
                    continue
                year = int(m.group("year"))
                season = m.group("season").lower()
                if season == "fall":
                    ay, t = (year, year + 1), "F"
                elif season == "spring":
                    ay, t = (year - 1, year), "S"
                else:  # summer — skip; we only scrape F/S
                    continue
                mapping.setdefault((ay, t), code)
        self._term_codes = mapping
        return mapping

    def schedule_pages(self):
        mapping = self._discover_terms()
        for ay in self.past_academic_years(self.years_back):
            for t in self.terms:
                if (ay, t) in mapping:
                    yield ay, t

    def url_for(self, academic_year, term):
        return URL

    def fetch_page(self, academic_year, term):
        mapping = self._discover_terms()
        code = mapping.get((academic_year, term))
        if code is None:
            return None
        s = self._ensure_session()
        form_data = {
            "ICType": "Panel",
            "ICElementNum": "0",
            "ICStateNum": "1",
            "ICAction": "CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH",
            "ICModelCancel": "0",
            "ICXPos": "0",
            "ICYPos": "0",
            "ResponsetoDiffFrame": "-1",
            "TargetFrameName": "None",
            "FacetPath": "None",
            "ICFocus": "",
            "ICSaveWarningFilter": "0",
            "ICChanged": "-1",
            "ICSkipPending": "0",
            "ICAutoSave": "0",
            "ICResubmit": "0",
            "ICSID": self._icsid,
            "ICActionPrompt": "false",
            "ICBcDomData": "",
            "ICPanelName": "",
            "ICFind": "",
            "ICAddCount": "",
            "ICAppClsData": "",
            "CLASS_SRCH_WRK2_INSTITUTION$31$": "GBURG",
            "CLASS_SRCH_WRK2_STRM$35$": code,
            "SSR_CLSRCH_WRK_SUBJECT_SRCH$0": SUBJECT,
            "SSR_CLSRCH_WRK_SSR_EXACT_MATCH1$1": "E",
            "SSR_CLSRCH_WRK_CATALOG_NBR$1": "",
            "SSR_CLSRCH_WRK_ACAD_CAREER$2": "UGRD",
            # Uncheck "Show Open Classes Only" + "Open Entry/Exit Classes Only".
            # The PeopleSoft idiom: send the `$chk$` companion as N and omit
            # the checkbox value itself.
            "SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$3": "N",
            "SSR_CLSRCH_WRK_OEE_IND$chk$4": "N",
        }
        resp = s.post(
            URL,
            data=form_data,
            headers={"Referer": URL},
            timeout=self.request_timeout,
        )
        resp.raise_for_status()

        # If the result set is >50, PeopleSoft intercepts the response with a
        # confirmation dialog ("Your search will return over 50 classes,
        # would you like to continue?") instead of rendering results. Detect
        # it and post `ICAction=#ICSave` (the dialog's OK button) on the
        # updated ICSID/ICStateNum to confirm.
        if "return over 50 classes" in resp.text:
            soup = BeautifulSoup(resp.text, "html.parser")
            icsid2 = soup.find("input", attrs={"name": "ICSID"})
            state2 = soup.find("input", attrs={"name": "ICStateNum"})
            if icsid2 is None or state2 is None:
                return resp.text  # fall through; parser will produce 0 rows
            confirm = dict(form_data)
            confirm["ICSID"] = icsid2["value"]
            confirm["ICStateNum"] = state2["value"]
            confirm["ICAction"] = "#ICSave"
            resp = s.post(
                URL,
                data=confirm,
                headers={"Referer": URL},
                timeout=self.request_timeout,
            )
            resp.raise_for_status()
            # PeopleSoft answers the confirm-dialog action with an AJAX
            # partial-update envelope (text/xml) rather than a full HTML
            # page. The rendered results HTML lives inside
            # `<FIELD id='win0divPAGECONTAINER'><![CDATA[...]]></FIELD>`;
            # unwrap it so our normal HTML parser can find the result rows.
            m = re.search(
                r"<FIELD id='win0divPAGECONTAINER'[^>]*><!\[CDATA\[(.*?)\]\]></FIELD>",
                resp.text,
                re.S,
            )
            if m:
                return m.group(1)

        return resp.text

    def parse_page(self, html, academic_year, term):
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")

        # Walk the document in order. Each group container holds the heading
        # ("CS 107 - Introduction to Scientific Computation"); each MTG_CLASS_NBR
        # row that follows belongs to the most recently seen group, until the
        # next group container appears. Group `$<G>` and section `$<S>` indices
        # use separate sequences, so we can't pair them by id.
        rows = []
        current_code = ""
        current_name = ""
        seen_groups = set()
        seen_sections = set()
        for el in soup.find_all(id=True):
            elid = el.get("id", "")
            if elid.startswith("win0divSSR_CLSRSLT_WRK_GROUPBOX2GP$"):
                if elid in seen_groups:
                    continue
                seen_groups.add(elid)
                heading = _clean(el.get_text(" "))
                # The group container's text starts with the course heading
                # ("CS 107 - Introduction to Scientific Computation") and is
                # then followed by the section table text. Match against the
                # leading "<CODE> - <NAME>" portion only.
                m = HEADING_RE.match(heading.split("\n", 1)[0])
                if m:
                    current_code = _clean(m.group("code"))
                    current_name = _clean(m.group("name"))
                    # Drop everything after the first ' Class Section ...' tail
                    # that PeopleSoft glues onto the heading text.
                    current_name = re.split(r"\s+Class\s+Section\s+", current_name, 1)[0].strip()
                else:
                    current_code, current_name = "", heading
                continue
            if elid.startswith("MTG_CLASS_NBR$") and "$span$" not in elid:
                suffix = elid.rsplit("$", 1)[-1]
                if not suffix.isdigit() or suffix in seen_sections:
                    continue
                seen_sections.add(suffix)
                row = _build_row(soup, suffix, current_code, current_name)
                rows.append(
                    self.make_row(
                        academic_year,
                        term,
                        course_code=row["course_code"],
                        section=row["section"],
                        course_name=row["course_name"],
                        instructor=row["instructor"],
                        time=row["time"],
                        url=URL,
                    )
                )
        return rows

    def close(self):
        super().close()
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


def _build_row(soup, suffix, course_code, course_name):
    classname = _text(soup, f"MTG_CLASSNAME${suffix}")
    daytime = _text(soup, f"MTG_DAYTIME${suffix}")
    room = _text(soup, f"MTG_ROOM${suffix}")
    instr = _text(soup, f"MTG_INSTR${suffix}")
    # MTG_CLASSNAME looks like "A-LEC Regular": section letter + "-" + type.
    section = classname.split("-", 1)[0].strip() if "-" in classname else classname
    return {
        "course_code": course_code,
        "course_name": course_name,
        "section": section,
        "instructor": _format_instructor(instr),
        "time": _format_meeting(daytime, room),
    }


def _text(soup, eid):
    el = soup.find(id=eid)
    return _clean(el.get_text(" ")) if el is not None else ""


def _format_instructor(instr):
    if not instr or instr.lower() == "staff":
        return _clean(instr)
    # Multiple instructors come comma-separated.
    parts = [_clean(p) for p in instr.split(",") if _clean(p)]
    return ", ".join(parts)


def _format_meeting(daytime, room):
    """``"MoWeFr 9:00AM - 9:50AM"`` + room -> ``"MWF 09:00-09:50 (West 112)"``."""
    if not daytime:
        return f"({room})" if room else ""
    m = re.match(
        r"^\s*([A-Za-z]+)\s+(\d{1,2}:\d{2})\s*([AP]M)\s*-\s*(\d{1,2}:\d{2})\s*([AP]M)\s*$",
        daytime,
        re.I,
    )
    if not m:
        time_str = daytime
    else:
        days = _normalize_days(m.group(1))
        start = _to_24h(m.group(2), m.group(3))
        end = _to_24h(m.group(4), m.group(5))
        time_str = f"{days} {start}-{end}".strip()
    if room:
        return f"{time_str} ({room})" if time_str else f"({room})"
    return time_str


def _normalize_days(s):
    out = []
    remaining = s
    while remaining:
        for token, abbr in DAY_TOKENS:
            if remaining.startswith(token):
                out.append(abbr)
                remaining = remaining[len(token):]
                break
        else:
            # Unknown character — drop one and continue defensively.
            remaining = remaining[1:]
    return "".join(out)


def _to_24h(hhmm, ap):
    hh, mm = hhmm.split(":")
    h = int(hh) % 12
    if ap.upper() == "PM":
        h += 12
    return f"{h:02d}:{mm}"


def _clean(text):
    return re.sub(r"\s+", " ", str(text) if text is not None else "").strip()
