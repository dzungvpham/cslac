#!/usr/bin/env python3
"""Generate college_links.json from colleges.csv.

Includes only colleges where Major >= 1 AND the college appears in the
faculty input CSV (so the website only shows links for colleges with data).
"""

import csv
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_COLLEGES  = ROOT / "data" / "colleges.csv"
DEFAULT_FACULTY   = ROOT / "data" / "faculty_list_with_verified_profile.csv"
DEFAULT_OUTPUT    = Path(__file__).parent / "college_links.json"


def faculty_colleges(faculty_csv: Path) -> set[str]:
    with open(faculty_csv, newline="", encoding="utf-8") as f:
        return {row["college"] for row in csv.DictReader(f)}


def build_links(colleges_csv: Path, known_colleges: set[str]) -> dict:
    result = {}
    with open(colleges_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["Name"].strip()
            try:
                major = float(row["Major"] or 0)
            except ValueError:
                major = 0

            if major < 1:
                continue
            if name not in known_colleges:
                continue

            result[name] = {
                "state":        row["State"].strip() or None,
                "program_url":  row["Program Link"].strip() or None,
                "catalog_url":  row["Catalog Link"].strip() or None,
                "schedule_url": row.get("Schedule Link", "").strip() or None,
            }

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--colleges", type=Path, default=DEFAULT_COLLEGES)
    parser.add_argument("--faculty",  type=Path, default=DEFAULT_FACULTY)
    parser.add_argument("--output",   type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    known = faculty_colleges(args.faculty)
    links = build_links(args.colleges, known)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2)

    print(f"Wrote {len(links)} colleges → {args.output}")


if __name__ == "__main__":
    main()
