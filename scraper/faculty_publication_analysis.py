"""Analyze faculty publication co-authorship patterns using OpenAlex.

Fetches CS publications per institution (topics.field.id:17), matches authors
to our faculty list, and classifies co-authorship patterns. ROR IDs are read
from colleges.csv (no institution search needed).

Output: faculty_publications.csv (per-paper detail with co-author lists).

Usage:
    python faculty_publication_analysis.py                   # full run (append-only)
    python faculty_publication_analysis.py --overwrite        # re-run from scratch
    python faculty_publication_analysis.py --college Williams # re-run one college
"""

import argparse
import csv
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

OPENALEX_API = "https://api.openalex.org"
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")
CS_FIELD_ID = "17"

FACULTY_CSV = "../data/faculty_list.csv"
COLLEGES_CSV = "../data/colleges.csv"
OUTPUT_PAPERS = "../data/faculty_publications.csv"

PAPER_FIELDS = [
    "name", "college", "openalex_author_id",
    "openalex_work_id", "title", "year", "venue",
    "topics", "subfields",
    "authors",
    "student_coauthors", "faculty_coauthors",
    "other_lac_coauthors", "external_coauthors",
]

MAX_RETRIES = 8


def _oa_id(raw):
    return (raw or "").rsplit("/", 1)[-1]


def _api_get(session, url, params):
    if OPENALEX_KEY:
        params = {**params, "api_key": OPENALEX_KEY}
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            wait = min(5 * (2 ** attempt), 120)
            print(f"  [err] {e}, retrying in {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code == 429:
            wait = min(5 * (2 ** attempt), 120)
            print(f"  [429] rate limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries: {url}")


def _get_venue(paper):
    loc = paper.get("primary_location")
    if not loc:
        return ""
    source = loc.get("source")
    if source and source.get("display_name"):
        return source["display_name"]
    return loc.get("raw_source_name", "")


def _name_key(name):
    parts = name.strip().split()
    if not parts:
        return ("", "")
    return (parts[-1].lower(), parts[0][0].lower())


VENUE_RANK = {"journal-article": 0, "proceedings-article": 0, "book-chapter": 1,
              "posted-content": 2, "dataset": 2}


def _norm_title(title):
    t = (title or "").replace("\\n", " ").replace("\\t", " ")
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def _dedup_papers(papers):
    groups = defaultdict(list)
    for p in papers:
        groups[_norm_title(p["title"])].append(p)
    deduped = []
    for group in groups.values():
        group.sort(key=lambda p: (VENUE_RANK.get(p.get("_raw_type", ""), 1),
                                  p.get("year") or 9999))
        deduped.append(group[0])
    return deduped


# ---- Data loading ----

def load_faculty_by_college():
    by_college = defaultdict(list)
    lnames = defaultdict(set)
    with open(FACULTY_CSV) as f:
        for row in csv.DictReader(f):
            by_college[row["college"]].append(row)
            lnames[row["college"]].add(row["name"].strip().split()[-1].lower())
    return by_college, lnames


def load_colleges():
    """Returns (lac_names set, {college: ror_url})."""
    names = set()
    rors = {}
    with open(COLLEGES_CSV) as f:
        for row in csv.DictReader(f):
            if float(row.get("Major", 0)) >= 1:
                name = row["Name"].strip()
                names.add(name)
                ror = row.get("ROR", "").strip()
                if ror:
                    rors[name] = f"https://ror.org/{ror}"
    return names, rors


# ---- OpenAlex queries ----

def fetch_cs_works(session, ror):
    works = []
    cursor = "*"
    while cursor:
        resp = _api_get(session, f"{OPENALEX_API}/works", params={
            "filter": f"authorships.institutions.ror:{ror},"
                      f"topics.field.id:{CS_FIELD_ID}",
            "select": "id,title,publication_year,authorships,primary_location,topics",
            "per_page": 200,
            "cursor": cursor,
        })
        data = resp.json()
        batch = data.get("results", [])
        works.extend(batch)
        cursor = data.get("meta", {}).get("next_cursor")
        if not batch:
            break
        time.sleep(0.2)
    return works


# ---- Classification ----

def process_college(session, college, inst_ror, faculty_list, faculty_lnames, lac_names):
    if not inst_ror:
        print(f"  [!] No ROR for {college}")
        return []

    works = fetch_cs_works(session, inst_ror)

    faculty_keys = {}
    for fac in faculty_list:
        faculty_keys[_name_key(fac["name"])] = fac["name"]

    all_papers = []

    for work in works:
        authorships = work.get("authorships") or []

        matched = []
        for auth in authorships:
            auth_name = (auth.get("author", {}).get("display_name") or "")
            auth_id = _oa_id(auth.get("author", {}).get("id", ""))
            auth_rors = {(i.get("ror") or "")
                        for i in (auth.get("institutions") or [])}
            if inst_ror and inst_ror in auth_rors:
                key = _name_key(auth_name)
                if key in faculty_keys:
                    matched.append((faculty_keys[key], auth_id))

        if not matched:
            continue

        authors_str = "; ".join(
            f"{(a.get('author', {}).get('display_name') or '')} "
            f"({_oa_id(a.get('author', {}).get('id', ''))})"
            for a in authorships
        )

        raw_topics = work.get("topics") or []
        topic_names = list(dict.fromkeys(
            t["display_name"] for t in raw_topics if t.get("display_name")
        ))
        subfields = list(dict.fromkeys(
            t["subfield"]["display_name"]
            for t in raw_topics if t.get("subfield", {}).get("display_name")
        ))

        for fac_name, fac_oa_id in matched:
            result = {
                "name": fac_name,
                "college": college,
                "openalex_author_id": fac_oa_id,
                "openalex_work_id": _oa_id(work.get("id", "")),
                "title": work.get("title", ""),
                "year": work.get("publication_year", ""),
                "venue": _get_venue(work),
                "topics": "; ".join(topic_names),
                "subfields": "; ".join(subfields),
                "authors": authors_str,
                "_raw_type": (work.get("primary_location") or {}).get(
                    "raw_type", ""),
            }

            coauthors = [a for a in authorships
                         if _oa_id(a.get("author", {}).get("id", "")) != fac_oa_id]

            students, faculty, other_lac, external = [], [], [], []
            for coauth in coauthors:
                name = (coauth.get("author", {}).get("display_name") or "")
                insts = coauth.get("institutions") or []
                rors = {(i.get("ror") or "") for i in insts}
                inst_names = {(i.get("display_name") or "").strip()
                              for i in insts}
                inst_names.discard("")

                if inst_ror and inst_ror in rors:
                    last = name.strip().split()[-1].lower() if name.strip() else ""
                    if last in faculty_lnames.get(college, set()):
                        faculty.append(name)
                    else:
                        students.append(name)
                elif inst_names & lac_names:
                    other_lac.append(name)
                else:
                    external.append(name)

            result.update(
                student_coauthors="; ".join(students),
                faculty_coauthors="; ".join(faculty),
                other_lac_coauthors="; ".join(other_lac),
                external_coauthors="; ".join(external),
            )
            all_papers.append(result)

    by_faculty = defaultdict(list)
    for p in all_papers:
        by_faculty[p["name"]].append(p)
    deduped = []
    for papers in by_faculty.values():
        deduped.extend(_dedup_papers(papers))
    for p in deduped:
        p.pop("_raw_type", None)

    return deduped


# ---- I/O ----

def _write_papers(papers):
    with open(OUTPUT_PAPERS, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(papers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--college", help="Re-run for a specific college")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing output instead of appending")
    args = parser.parse_args()

    faculty_by_college, faculty_lnames = load_faculty_by_college()
    lac_names, college_rors = load_colleges()
    colleges = sorted(faculty_by_college.keys())

    if args.college:
        colleges = [c for c in colleges if args.college.lower() in c.lower()]
        if not colleges:
            print(f"No college matching '{args.college}'")
            sys.exit(1)

    existing_papers = []
    done_colleges = set()
    output_path = Path(OUTPUT_PAPERS)
    if not args.overwrite and output_path.exists():
        with open(output_path) as f:
            existing_papers = list(csv.DictReader(f))
        if args.college:
            target_set = set(colleges)
            existing_papers = [r for r in existing_papers
                               if r["college"] not in target_set]
        else:
            done_colleges = {r["college"] for r in existing_papers}
            if done_colleges:
                print(f"Resuming: {len(done_colleges)} colleges already processed")

    remaining = [c for c in colleges if c not in done_colleges]
    session = requests.Session()
    all_papers = list(existing_papers)

    for i, college in enumerate(tqdm(remaining, desc="Colleges")):
        fac_list = faculty_by_college[college]
        ror = college_rors.get(college, "")
        papers = process_college(
            session, college, ror, fac_list, faculty_lnames, lac_names)
        all_papers.extend(papers)
        if (i + 1) % 5 == 0:
            _write_papers(all_papers)

    _write_papers(all_papers)

    if args.college:
        new_papers = [p for p in all_papers if p["college"] in set(remaining)]
        print(f"\nPer-paper details:")
        for p in new_papers:
            print(f"  {p['title']} ({p['year']}, {p['venue']})")
            if p.get("student_coauthors"):
                print(f"    Students: {p['student_coauthors']}")
            if p.get("faculty_coauthors"):
                print(f"    Faculty:  {p['faculty_coauthors']}")
            if p.get("other_lac_coauthors"):
                print(f"    LAC:      {p['other_lac_coauthors']}")
            if p.get("external_coauthors"):
                print(f"    External: {p['external_coauthors']}")

    print(f"\nWrote {len(all_papers)} papers to {OUTPUT_PAPERS}")


if __name__ == "__main__":
    main()
