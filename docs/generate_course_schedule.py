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
]
EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)


def is_excluded(name: str) -> bool:
    return bool(name) and EXCLUDE_RE.search(name) is not None


def term_label(year: str, term: str) -> str:
    # year is like "2021-22"; F maps to first half ('21), W/S/Su to second ('22).
    start, end = year.split("-")
    yy = end[-2:] if term in ("W", "S", "Su") else start[-2:]
    if not term:
        return f"{start[-2:]}–{end}"
    return f"{term} '{yy}"


def natural_key(s: str) -> list:
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


def build_data(input_dir: Path) -> dict:
    result: dict[str, dict] = {}

    for csv_path in sorted(input_dir.glob("*.csv")):
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue

        college = rows[0]["college"]
        all_terms: set[tuple[str, str]] = set()
        offered: dict[str, set[tuple[str, str]]] = defaultdict(set)
        # latest_name[code] = (term_sort_key, name)
        latest_name: dict[str, tuple[tuple[str, int], str]] = {}

        for r in rows:
            year = r["academic_year"]
            term = r["term"]
            if year < MIN_YEAR:
                continue
            code = (r["course_code"] or "").strip()
            name = (r["course_name"] or "").strip().strip('"')
            if not code:
                continue
            if is_excluded(name):
                continue
            all_terms.add((year, term))
            offered[code].add((year, term))
            if name:
                tkey = (year, TERM_ORDER.get(term, 99))
                cur = latest_name.get(code)
                if cur is None or tkey >= cur[0]:
                    latest_name[code] = (tkey, name)

        if not offered:
            continue

        sorted_terms = sorted(all_terms, key=lambda yt: (yt[0], TERM_ORDER.get(yt[1], 99)))
        sorted_codes = sorted(offered.keys(), key=natural_key)

        result[college] = {
            "terms": [
                {"year": y, "term": t, "label": term_label(y, t)}
                for (y, t) in sorted_terms
            ],
            "courses": [
                {
                    "code": code,
                    "name": latest_name.get(code, ((None, 0), ""))[1],
                    "offered": [1 if (y, t) in offered[code] else 0
                                for (y, t) in sorted_terms],
                }
                for code in sorted_codes
            ],
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
