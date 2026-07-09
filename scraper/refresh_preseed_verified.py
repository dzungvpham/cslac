"""Pre-seed data/faculty_list_with_verified_profile.csv for a data refresh.

Run AFTER Stage 1 (new faculty_list.csv) and BEFORE Stage 3
(faculty_scholar_profile_scraper.py).

Why this exists
---------------
The refresh must keep all five faculty CSVs row-aligned to the new
faculty_list.csv (generate_data.py hard-fails otherwise). Stage 3's own resume
logic keys reuse on (name, title, college) and APPENDS new/title-changed rows at
the end — which both breaks alignment and re-scrapes (losing `manual_approved`)
anyone who got promoted.

This script instead rebuilds the verified CSV in exact faculty_list.csv order,
carrying over every prior verified column + status by (name, college) — so a
faculty member who merely changed title keeps their verified profile AND their
manual_approved lock. Genuinely-new (name, college) rows are seeded with an
empty status so Stage 3 scrapes only them, and because every faculty_list
(name, college) is already present, Stage 3 appends nothing and order is
preserved.
"""
import csv

FACULTY_LIST = "../data/faculty_list.csv"
VERIFIED = "../data/faculty_list_with_verified_profile.csv"

VERIFIED_COLUMNS = [
    "verified_affiliation", "scholar_match_status",
    "scholar_citedby", "scholar_citedby5y",
    "scholar_hindex", "scholar_hindex5y",
    "scholar_i10index", "scholar_i10index5y",
    "scholar_interests", "scholar_cites_per_year",
]
OUT_COLUMNS = ["name", "title", "college"] + VERIFIED_COLUMNS


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    faculty = load(FACULTY_LIST)
    old = load(VERIFIED)

    # Prior verified data keyed by (name, college). Title deliberately excluded
    # so a promotion doesn't lose the reuse.
    prior = {}
    for r in old:
        prior[(r["name"], r["college"])] = r

    out_rows = []
    reused = new = reused_approved = 0
    for f in faculty:
        name, title, college = f["name"], f["title"], f["college"]
        row = {"name": name, "title": title, "college": college}
        p = prior.get((name, college))
        if p is not None:
            for c in VERIFIED_COLUMNS:
                row[c] = p.get(c, "")
            reused += 1
            if p.get("scholar_match_status") == "manual_approved":
                reused_approved += 1
        else:
            for c in VERIFIED_COLUMNS:
                row[c] = ""
            row["scholar_match_status"] = ""   # explicit → Stage 3 will scrape
            new += 1
        out_rows.append(row)

    with open(VERIFIED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Pre-seeded {VERIFIED}:")
    print(f"  {len(out_rows)} rows in faculty_list.csv order")
    print(f"  reused prior verified data for {reused} (name,college) "
          f"[{reused_approved} manual_approved preserved]")
    print(f"  {new} genuinely-new rows seeded empty (Stage 3 will scrape these)")

    # Sanity: verify order + key-set match faculty_list exactly.
    fl_keys = [(r["name"], r["title"], r["college"]) for r in faculty]
    out_keys = [(r["name"], r["title"], r["college"]) for r in out_rows]
    assert fl_keys == out_keys, "ALIGNMENT BUG: pre-seeded order != faculty_list"
    print("  alignment check vs faculty_list.csv: OK")


if __name__ == "__main__":
    main()
