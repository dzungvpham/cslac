#!/usr/bin/env python3
"""Generate faculty_data.json for the web dashboard.

Merges four CSVs (aligned by row order on (name, title, college)):
  - faculty_list.csv                       → personal website url
  - faculty_list_with_scholar_url.csv      → google scholar url
  - faculty_list_with_verified_profile.csv → scholar match status + metrics + interests
  - faculty_list_with_field.csv            → inferred field + subfields

Only includes faculty whose `field` is "Computer Science" or "Invalid".
The `interests` description prefers the LLM-inferred subfields; if absent and
the scholar profile is trusted, falls back to scholar interests. Both are
re-formatted to comma-separated.
"""

import csv
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_LIST       = ROOT / "data" / "faculty_list.csv"
DEFAULT_SCHOLAR    = ROOT / "data" / "faculty_list_with_scholar_url.csv"
DEFAULT_VERIFIED   = ROOT / "data" / "faculty_list_with_verified_profile.csv"
DEFAULT_FIELD      = ROOT / "data" / "faculty_list_with_field.csv"
DEFAULT_OUTPUT     = Path(__file__).parent / "faculty_data.json"

TRUSTED_STATUSES = {"matched", "manual_approved"}
INCLUDED_FIELDS = {"Computer Science", "Invalid"}


def to_int(v: str) -> int | None:
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def categorize_title(title: str) -> str:
    t = (title or "").lower()
    if t.startswith("visiting"):
        return "visiting"
    if t.startswith("adjunct"):
        return "adjunct"
    if any(k in t for k in ("lecturer", "instructor", "teaching", "practice")):
        return "teaching"
    if "assistant professor" in t:
        return "tenure_track"
    if "professor" in t:
        return "tenured"
    return "tenure_track"


def normalize_subfields(s: str) -> str | None:
    if not s:
        return None
    parts = [p.strip() for p in s.split("|") if p.strip()]
    return ", ".join(parts) if parts else None


def normalize_scholar_interests(s: str) -> str | None:
    if not s:
        return None
    parts = [p.strip() for p in s.split(";") if p.strip()]
    return ", ".join(parts) if parts else None


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_data(list_path: Path, scholar_path: Path, verified_path: Path, field_path: Path) -> list[dict]:
    list_rows     = read_csv(list_path)
    scholar_rows  = read_csv(scholar_path)
    verified_rows = read_csv(verified_path)
    field_rows    = read_csv(field_path)

    n = len(list_rows)
    if not (len(scholar_rows) == len(verified_rows) == len(field_rows) == n):
        raise ValueError("CSV row counts do not match — cannot align by row order")

    colleges: dict[str, list[dict]] = {}
    for base, sch, ver, fld in zip(list_rows, scholar_rows, verified_rows, field_rows):
        key = (base["name"], base["title"], base["college"])
        for other in (sch, ver, fld):
            if (other["name"], other["title"], other["college"]) != key:
                raise ValueError(f"Row alignment mismatch at {key} vs "
                                 f"{(other['name'], other['title'], other['college'])}")

        if fld.get("field") not in INCLUDED_FIELDS:
            continue

        trusted = ver["scholar_match_status"] in TRUSTED_STATUSES
        subfields_desc = normalize_subfields(fld.get("subfields", ""))
        scholar_desc = normalize_scholar_interests(ver.get("scholar_interests", "")) if trusted else None
        interests = subfields_desc or scholar_desc

        prof = {
            "name": base["name"],
            "title": base["title"],
            "category": categorize_title(base["title"]),
            "url": base.get("url") or None,
            "scholar_url": (sch.get("google_scholar") or None) if trusted else None,
            "status": ver["scholar_match_status"],
            "citedby":    to_int(ver.get("scholar_citedby"))    if trusted else None,
            "citedby5y":  to_int(ver.get("scholar_citedby5y"))  if trusted else None,
            "hindex":     to_int(ver.get("scholar_hindex"))     if trusted else None,
            "hindex5y":   to_int(ver.get("scholar_hindex5y"))   if trusted else None,
            "i10index":   to_int(ver.get("scholar_i10index"))   if trusted else None,
            "i10index5y": to_int(ver.get("scholar_i10index5y")) if trusted else None,
            "interests":  interests,
        }
        colleges.setdefault(base["college"], []).append(prof)

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
    parser.add_argument("--list",     type=Path, default=DEFAULT_LIST)
    parser.add_argument("--scholar",  type=Path, default=DEFAULT_SCHOLAR)
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--field",    type=Path, default=DEFAULT_FIELD)
    parser.add_argument("--output",   type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = build_data(args.list, args.scholar, args.verified, args.field)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    total_faculty = sum(c["total"] for c in data)
    print(f"Wrote {len(data)} colleges, {total_faculty} faculty → {args.output}")


if __name__ == "__main__":
    main()
