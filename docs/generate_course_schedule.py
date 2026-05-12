#!/usr/bin/env python3
"""Generate course_schedule_data.json for the web dashboard.

Reads every CSV in data/course_schedule/ and emits a per-college map:

  {
    "<College>": {
      "terms":   [{"year": "2021-22", "term": "F", "label": "F'21"}, ...],
      "courses": [{"code": "CS 111", "name": "Intro to CS", "offered": [1, 0, 1, ...]}, ...]
    },
    ...
  }

Only academic years >= 2021-22 are included. Courses are deduplicated by
`course_code`; the displayed title is the most-recent non-empty title seen
for that code. Independent study, research, honors, thesis, internship,
tutorial, and directed-study entries are excluded.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT_DIR = ROOT / "data" / "course_schedule"
DEFAULT_OUTPUT = Path(__file__).parent / "course_schedule_data.json"

MIN_YEAR = "2021-22"
TERM_ORDER = {"F": 0, "W": 1, "S": 2, "Su": 3, "": 4}
ALLOWED_TERMS = {"F", "W", "S"}

# Course-name patterns to exclude (case-insensitive substrings).
EXCLUDE_PATTERNS = [
    r"\bindependent\b",
    r"\bhonors?\b",
    r"\bhon\b",
    r"\bthesis\b",
    r"\binternship\b",
    r"\btutorial\b",
    r"\bdirected (study|research|reading)\b",
    r"\bdirrdg\b",
    r"\bind st\b",
    r"\bindividualized study\b",
    r"\bsenior (project|research|capstone|honors)\b",
    r"\bcomp(uter)? sci(ence)? research\b",
    r"\bcs research\b",
    r"^research( -|:|$)",
    r"^research (- |in )",
    r"\bresearch study\b",
    r"\bstudent research\b",
    r"\bundergrad(uate)? research\b",
    r"\bgraduate research\b",
    r"\bresearch assistantship\b",
    # Seminars / colloquia / capstones — not regular taught courses.
    r"\bcolloquium\b",
    r"\bsenior seminar\b",
    r"\bcapstone\b",
    r"\bresearch seminar\b",
    r"\bresearch sem\b",
    r"\bcollaborative research\b",
    r"\brsc research\b",
    # Variants of "individual / independent / directed / advanced study" —
    # listed explicitly so we don't catch legitimate titles like
    # "Critical Study of Data and Algorithms".
    r"\bindividual study\b",
    r"\bind study\b",
    r"\bindep(t|endent)? study\b",
    r"\bdir study\b",
    r"\badvanced study\b",
    r"\bnon-traditional study\b",
    # Independent/private reading variants.
    r"\bprivate reading\b",
    r"\bind reading\b",
    r"\bindep(t|endent)? reading\b",
]
EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)


def has_cs_code(code: str) -> bool:
    """True if the course_code begins with a letter 'C' — used to drop
    cross-listed Math/Engineering/etc. entries that get pulled in by some
    catalog scrapers."""
    code = (code or "").lstrip()
    return bool(code) and code[:1].upper() == "C"


def is_excluded(name: str) -> bool:
    return bool(name) and EXCLUDE_RE.search(name) is not None


# Matches "lab" / "labs" / "laboratory" as a whole word.
_LAB_RE = re.compile(r"\blab(s|oratory)?\b", re.IGNORECASE)
# Matches a "combined-with-lab" marker: a connector token (w/, with, and, /)
# immediately before "lab" — i.e., the course is a lecture + lab combo rather
# than a stand-alone lab section. Comma is intentionally excluded: a title
# like "Computer Systems, Lab" is a lab-only entry, not a combined course.
_LAB_COMBINED_RE = re.compile(
    r"(?:\bw/|\bwith\s+|\band\s+|/)\s*lab(s|oratory)?\b",
    re.IGNORECASE,
)


def is_lab_only(name: str) -> bool:
    """A 'lab-only' entry is one that accompanies a separate lecture: e.g.
    'Lab for CSCI 203', 'Intro Computer Sci Lab', 'Laboratory'. Combined
    courses like 'Elementary Programming w/Lab' or 'Electronics and Lab'
    are kept.
    """
    if not name or not _LAB_RE.search(name):
        return False
    return _LAB_COMBINED_RE.search(name) is None


def term_label(year: str, term: str) -> str:
    # year is like "2021-22"; F maps to first half ('21), W/S/Su to second ('22).
    start, end = year.split("-")
    yy = end[-2:] if term in ("W", "S", "Su") else start[-2:]
    if not term:
        return f"{start[-2:]}-{end[-2:]}"
    return f"{term}{yy}"


def natural_key(s: str) -> list:
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


def build_data(input_dir: Path) -> dict:
    result: dict[str, dict] = {}

    csv_paths = sorted(input_dir.glob("*.csv"))

    # Global max academic year across every CSV — used to drop one-off
    # courses that haven't been taught in the latest 4 AYs. Using a global
    # cutoff means colleges with stale scraping data don't get a free pass
    # to keep showing 5-year-old singletons.
    global_max_year_start = 0
    for csv_path in csv_paths:
        with open(csv_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                y = (r.get("academic_year") or "").strip()
                if y >= MIN_YEAR and (r.get("term") or "").strip() in ALLOWED_TERMS:
                    try:
                        ys = int(y.split("-")[0])
                    except ValueError:
                        continue
                    if ys > global_max_year_start:
                        global_max_year_start = ys
    recent_cutoff = global_max_year_start - 3 if global_max_year_start else 0

    for csv_path in csv_paths:
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue

        college = rows[0]["college"]
        all_terms: set[tuple[str, str]] = set()
        offered: dict[str, set[tuple[str, str]]] = defaultdict(set)
        # url_by_cell[code][(year, term)] = first non-empty URL seen for that cell
        url_by_cell: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
        # name_obs[code] = list of (term_sort_key, name, is_lab_only); we delay
        # picking the display name until we've seen every row so we can prefer
        # a non-lab name when one exists.
        name_obs: dict[str, list[tuple[tuple[str, int], str, bool]]] = defaultdict(list)

        for r in rows:
            year = r["academic_year"]
            term = r["term"]
            if year < MIN_YEAR:
                continue
            if term not in ALLOWED_TERMS:
                continue
            code = (r["course_code"] or "").strip()
            name = (r["course_name"] or "").strip().strip('"')
            if not code or not has_cs_code(code):
                continue
            if is_excluded(name):
                continue
            all_terms.add((year, term))
            offered[code].add((year, term))
            url = (r.get("url") or "").strip()
            if url and (year, term) not in url_by_cell[code]:
                url_by_cell[code][(year, term)] = url
            if name:
                tkey = (year, TERM_ORDER.get(term, 99))
                name_obs[code].append((tkey, name, is_lab_only(name)))

        # Resolve display name per code; drop codes whose every observed name
        # is lab-only (those are stand-alone lab sections of another course).
        latest_name: dict[str, str] = {}
        drop_codes: set[str] = set()
        for code in list(offered.keys()):
            obs = name_obs.get(code, [])
            non_lab = [o for o in obs if not o[2]]
            if non_lab:
                latest_name[code] = max(non_lab, key=lambda o: o[0])[1]
            elif obs:
                # All observed names are lab-only → drop the code.
                drop_codes.add(code)
            # If no names ever observed, leave latest_name unset and keep code.

        # Drop a one-off course that hasn't been taught in the latest 4 AYs:
        # if it was offered exactly once and that single offering is older
        # than the global cutoff, it likely isn't a regular course anymore.
        if recent_cutoff:
            for code in list(offered.keys()):
                if code in drop_codes:
                    continue
                if len(offered[code]) != 1:
                    continue
                ((sole_year, _),) = tuple(offered[code])
                if int(sole_year.split("-")[0]) < recent_cutoff:
                    drop_codes.add(code)

        for code in drop_codes:
            offered.pop(code, None)
            url_by_cell.pop(code, None)

        if not offered:
            continue

        sorted_terms = sorted(all_terms, key=lambda yt: (yt[0], TERM_ORDER.get(yt[1], 99)))
        sorted_codes = sorted(offered.keys(), key=natural_key)

        # Decide link mode for the whole college: if any course has 2+ distinct
        # URLs across its term cells, the college uses per-term tick links;
        # otherwise links (if any) go on course titles. This keeps all courses
        # within a single college visually consistent.
        per_term_mode = any(
            len({u for u in url_by_cell.get(code, {}).values() if u}) >= 2
            for code in sorted_codes
        )
        # Course-level URL per code (only meaningful in non-per-term mode).
        course_url = {
            code: next(iter({u for u in url_by_cell.get(code, {}).values() if u}), None)
            for code in sorted_codes
        }
        # If every course in the college points to the same single URL, drop
        # the per-course title links — that URL is the college's schedule page
        # and is surfaced once via the schedule icon in the header instead.
        college_unique_urls = {u for u in course_url.values() if u}
        drop_title_urls = (not per_term_mode) and len(college_unique_urls) <= 1

        courses_out = []
        for code in sorted_codes:
            cell_urls = url_by_cell.get(code, {})
            entry: dict = {
                "code": code,
                "name": latest_name.get(code, ""),
            }
            if per_term_mode:
                entry["offered"] = [
                    (cell_urls.get((y, t), "") or 1) if (y, t) in offered[code] else 0
                    for (y, t) in sorted_terms
                ]
            else:
                entry["offered"] = [
                    1 if (y, t) in offered[code] else 0 for (y, t) in sorted_terms
                ]
                if course_url[code] and not drop_title_urls:
                    entry["url"] = course_url[code]
            courses_out.append(entry)

        result[college] = {
            "terms": [
                {"year": y, "term": t, "label": term_label(y, t)}
                for (y, t) in sorted_terms
            ],
            "courses": courses_out,
        }

    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = p.parse_args()

    data = build_data(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    total_courses = sum(len(c["courses"]) for c in data.values())
    print(f"Wrote {len(data)} colleges, {total_courses} courses → {args.output}")


if __name__ == "__main__":
    main()
