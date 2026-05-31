"""Fetch OpenAlex author metrics for faculty without a trusted Google Scholar
profile.

The OpenAlex author IDs come from `data/faculty_publications.csv`: for every
paper, `matched_faculty` names the LAC-faculty co-authors and `authors`
carries the per-author OpenAlex ID. The two name spellings don't always
agree — `matched_faculty` uses the canonical name from `faculty_list.csv`
while `authors` carries OpenAlex's `display_name` for the same person
(e.g. "Ike Lage" vs "Isaac Lage"). We bridge them with the same
`(last_name, first_initial)` key the publication scraper uses, restricted
to authors whose affiliations include the same college. We count, per
(college, canonical_name), how often each OA ID appears in their matched
papers and keep the dominant one (OpenAlex sometimes splits one person
across multiple unmerged author profiles). For the chosen ID we call the
OpenAlex Authors API and record `cited_by_count`, `summary_stats.h_index`,
and `summary_stats.i10_index`.

The output (`data/faculty_list_with_openalex_profile.csv`) is row-aligned
with `data/faculty_list.csv` so it can be zipped alongside the other
faculty CSVs in `docs/generate_data.py`. Faculty without any matched OA ID
are written with empty fields.

Resumable: re-running only refetches a row when the derived OA ID changed
or when metrics are missing. `--overwrite` refetches everything.

Usage:
    python faculty_openalex_profile_scraper.py
    python faculty_openalex_profile_scraper.py --overwrite
"""

import argparse
import csv
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

OPENALEX_API = "https://api.openalex.org"
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")

INPUT_FACULTY = "../data/faculty_list.csv"
INPUT_PUBS = "../data/faculty_publications.csv"
OUTPUT_CSV = "../data/faculty_list_with_openalex_profile.csv"

COLUMNS = [
    "name", "title", "college",
    "openalex_id",
    "openalex_citedby",
    "openalex_hindex",
    "openalex_i10index",
]

MAX_RETRIES = 6


def _name_key(name: str) -> tuple[str, str]:
    """(last_name, first_initial), lowercased. Matches the keying used by
    `_name_key` in faculty_publication_scraper.py."""
    parts = name.strip().split()
    if len(parts) < 2:
        return ("", "")
    return (parts[-1].lower(), parts[0][0].lower())


def build_oa_id_counts() -> dict[tuple[str, str], Counter]:
    """For each (college, canonical_faculty_name), count how often each
    OpenAlex author ID appears across their matched papers in
    faculty_publications.csv. Bridges the OpenAlex display_name in `authors`
    to the canonical name in `matched_faculty` via the (last_name,
    first_initial) key — the same bridge the publication scraper used to
    populate `matched_faculty` in the first place."""
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    with open(INPUT_PUBS, newline="") as f:
        for r in csv.DictReader(f):
            college = (r.get("college") or "").strip()
            matched_raw = (r.get("matched_faculty") or "").strip()
            if not college or not matched_raw:
                continue
            matched_by_key: dict[tuple[str, str], str] = {}
            for n in (s.strip() for s in matched_raw.split(";") if s.strip()):
                k = _name_key(n)
                if k != ("", ""):
                    matched_by_key[k] = n
            if not matched_by_key:
                continue
            authors_raw = r.get("authors") or ""
            try:
                authors = json.loads(authors_raw) if authors_raw else []
            except (json.JSONDecodeError, TypeError):
                continue
            for a in authors:
                name = (a.get("name") or "").strip()
                aid = (a.get("id") or "").strip()
                if not name or not aid:
                    continue
                # Mirror the publication scraper: only attribute an OA ID to a
                # matched_faculty if the author is affiliated with the same
                # college on this paper.
                if college not in (a.get("affiliations") or []):
                    continue
                canonical = matched_by_key.get(_name_key(name))
                if canonical:
                    counts[(college, canonical)][aid] += 1
    return counts


def pick_id(counter: Counter) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def fetch_author(session: requests.Session, oa_id: str) -> dict | None:
    """Return the author JSON, or None on permanent failure."""
    params = {}
    if OPENALEX_KEY:
        params["api_key"] = OPENALEX_KEY
    url = f"{OPENALEX_API}/authors/{oa_id}"
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            wait = min(5 * (2 ** attempt), 60)
            print(f"  [err] {oa_id}: {e}, retrying in {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 404:
            return None
        if resp.status_code == 429:
            wait = min(5 * (2 ** attempt), 60)
            print(f"  [429] {oa_id}: rate-limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"  [http] {oa_id}: {e}")
            return None
        return resp.json()
    print(f"  [fail] {oa_id}: exhausted retries")
    return None


def read_existing(output_path: Path) -> dict[tuple[str, str, str], dict]:
    if not output_path.exists():
        return {}
    out: dict[tuple[str, str, str], dict] = {}
    with open(output_path, newline="") as f:
        for row in csv.DictReader(f):
            out[(row["name"], row["title"], row["college"])] = row
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true",
                        help="Refetch every row instead of resuming.")
    args = parser.parse_args()

    oa_counts = build_oa_id_counts()
    print(f"Found OpenAlex author IDs for {len(oa_counts)} (college, faculty) keys")

    output_path = Path(OUTPUT_CSV)
    existing = {} if args.overwrite else read_existing(output_path)

    with open(INPUT_FACULTY, newline="") as f:
        base_rows = list(csv.DictReader(f))

    session = requests.Session()
    output_rows: list[dict] = []
    n_fetched = n_reused = n_no_id = 0

    for base in tqdm(base_rows, desc="Faculty"):
        name, title, college = base["name"], base["title"], base["college"]
        key = (name, title, college)
        chosen_id = pick_id(oa_counts.get((college, name), Counter()))

        prev = existing.get(key)
        if prev and prev.get("openalex_id", "") == chosen_id:
            if not chosen_id:
                output_rows.append(_blank_row(name, title, college))
                n_no_id += 1
                continue
            if (prev.get("openalex_citedby") or "") != "":
                output_rows.append({
                    "name": name, "title": title, "college": college,
                    "openalex_id": prev["openalex_id"],
                    "openalex_citedby": prev.get("openalex_citedby", ""),
                    "openalex_hindex": prev.get("openalex_hindex", ""),
                    "openalex_i10index": prev.get("openalex_i10index", ""),
                })
                n_reused += 1
                continue

        if not chosen_id:
            output_rows.append(_blank_row(name, title, college))
            n_no_id += 1
            continue

        data = fetch_author(session, chosen_id)
        row = _blank_row(name, title, college)
        row["openalex_id"] = chosen_id
        if data:
            row["openalex_citedby"] = data.get("cited_by_count", "") or 0
            stats = data.get("summary_stats") or {}
            row["openalex_hindex"] = stats.get("h_index", "") if stats.get("h_index") is not None else ""
            row["openalex_i10index"] = stats.get("i10_index", "") if stats.get("i10_index") is not None else ""
            n_fetched += 1
        output_rows.append(row)
        # Small courtesy gap; the polite-pool rate limit is generous.
        time.sleep(0.1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\nWrote {len(output_rows)} rows to {OUTPUT_CSV}")
    print(f"  fetched: {n_fetched}, reused: {n_reused}, no OA ID: {n_no_id}")


def _blank_row(name: str, title: str, college: str) -> dict:
    return {
        "name": name, "title": title, "college": college,
        "openalex_id": "", "openalex_citedby": "",
        "openalex_hindex": "", "openalex_i10index": "",
    }


if __name__ == "__main__":
    main()
