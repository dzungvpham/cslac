#!/usr/bin/env python3
"""Generate faculty_data.json for the web dashboard from the verified profile CSV."""

import csv
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = ROOT / "data" / "faculty_list_with_verified_profile.csv"
DEFAULT_OUTPUT = Path(__file__).parent / "faculty_data.json"


def to_int(v: str) -> int | None:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


TRUSTED_STATUSES = {"matched", "manual_approved"}


def categorize_title(title: str) -> str:
    t = (title or "").lower()
    if t.startswith("visiting"):
        return "visiting"
    if t.startswith("adjunct"):
        return "adjunct"
    if any(k in t for k in ("lecturer", "instructor", "teaching", "practice")):
        return "teaching"
    return "tenure_track"


def build_data(input_path: Path) -> list[dict]:
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    colleges: dict[str, list[dict]] = {}
    for row in rows:
        college = row["college"]
        trusted = row["scholar_match_status"] in TRUSTED_STATUSES
        prof = {
            "name": row["name"],
            "title": row["title"],
            "category": categorize_title(row["title"]),
            "url": row["url"] or None,
            "scholar_url": (row["google_scholar"] or None) if trusted else None,
            "status": row["scholar_match_status"],
            "citedby":    to_int(row["scholar_citedby"])    if trusted else None,
            "citedby5y":  to_int(row["scholar_citedby5y"])  if trusted else None,
            "hindex":     to_int(row["scholar_hindex"])     if trusted else None,
            "hindex5y":   to_int(row["scholar_hindex5y"])   if trusted else None,
            "i10index":   to_int(row["scholar_i10index"])   if trusted else None,
            "i10index5y": to_int(row["scholar_i10index5y"]) if trusted else None,
            "interests":  (row["scholar_interests"] or None) if trusted else None,
        }
        colleges.setdefault(college, []).append(prof)

    result = []
    for name, profs in colleges.items():
        trusted = [p for p in profs if p["status"] in TRUSTED_STATUSES]
        citations = [p["citedby"] for p in trusted if p["citedby"] is not None]
        hindices = [p["hindex"] for p in trusted if p["hindex"] is not None]
        result.append(
            {
                "name": name,
                "faculty": profs,
                "total": len(profs),
                "matched": len(trusted),
                "total_citations": sum(citations),
                "max_hindex": max(hindices) if hindices else None,
            }
        )

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = build_data(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {len(data)} colleges → {args.output}")


if __name__ == "__main__":
    main()
