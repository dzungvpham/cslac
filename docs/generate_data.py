#!/usr/bin/env python3
"""Generate data.json for the web dashboard.

Single merged output keyed by college name, combining three previously
separate JSONs:

  - faculty records — from four row-aligned CSVs under data/:
      faculty_list.csv                       → personal website url
      faculty_list_with_scholar_url.csv      → google scholar url
      faculty_list_with_verified_profile.csv → match status + citation metrics + interests
      faculty_list_with_field.csv            → inferred field + subfields
    Only rows whose `field` is "Computer Science" or "Invalid" are kept.
    `scholar_match_status ∈ {matched, manual_approved}` counts as trusted;
    untrusted rows still appear but their `scholar_url` and citation metrics
    are suppressed.

  - college metadata + links — from data/colleges.csv (state and the four
    department/catalog/schedule URLs).

  - course schedule — from data/course_schedule/<College>.csv; per-college
    sorted terms (year, F→W→S→Su) and dedup'd course rows restricted to
    academic years ≥ 2021-22. Instructor strings are matched against the
    college's faculty so each term cell can carry initials + link.

Only colleges with at least one CS/Invalid-field faculty row are emitted.
"""

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = Path(__file__).parent
DEFAULT_LIST     = ROOT / "data" / "faculty_list.csv"
DEFAULT_SCHOLAR  = ROOT / "data" / "faculty_list_with_scholar_url.csv"
DEFAULT_VERIFIED = ROOT / "data" / "faculty_list_with_verified_profile.csv"
DEFAULT_FIELD    = ROOT / "data" / "faculty_list_with_field.csv"
DEFAULT_COLLEGES = ROOT / "data" / "colleges.csv"
DEFAULT_COURSES  = ROOT / "data" / "course_schedule"
DEFAULT_PUBS     = ROOT / "data" / "faculty_publications.csv"
DEFAULT_OUTPUT   = DOCS / "data.json"
INDEX_HTML       = DOCS / "index.html"
SITEMAP_XML      = DOCS / "sitemap.xml"

TRUSTED_STATUSES = {"matched", "manual_approved"}
INCLUDED_FIELDS = {"Computer Science", "Invalid"}


# ── faculty ────────────────────────────────────────────────────────────────

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


def build_faculty(list_path: Path, scholar_path: Path, verified_path: Path, field_path: Path) -> dict[str, dict]:
    """Return {college_name: {faculty, total, matched, total_citations}}.
    Insertion order follows the CSV row order, matching the legacy output.
    """
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

    result: dict[str, dict] = {}
    for name, profs in colleges.items():
        trusted = [p for p in profs if p["status"] in TRUSTED_STATUSES]
        citations = [p["citedby"] for p in trusted if p["citedby"] is not None]
        result[name] = {
            "faculty": profs,
            "total": len(profs),
            "matched": len(trusted),
            "total_citations": sum(citations),
        }
    return result


# ── college links ──────────────────────────────────────────────────────────

def latest_schedule_url_overrides() -> dict[str, str]:
    """Map college name → latest-term schedule URL for scrapers whose URL
    rotates by term/year. Computed from each scraper's `latest_public_url()`;
    only scrapers that opt in (`public_url_template = True` or a custom
    `public_url_for`) contribute. If the scraper package can't be imported
    (e.g. missing optional deps), we silently return an empty map and fall
    back to the URLs in colleges.csv.
    """
    overrides: dict[str, str] = {}
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "scraper"))
    try:
        from course_schedule.scrape_course_schedule import SCRAPERS
    except Exception:
        return overrides
    for cls in SCRAPERS:
        try:
            url = cls.latest_public_url()
        except Exception:
            url = None
        if url:
            overrides[str(cls.college)] = url
    return overrides


def build_links(colleges_csv: Path, known: set[str]) -> dict[str, dict]:
    schedule_overrides = latest_schedule_url_overrides()
    result: dict[str, dict] = {}
    with open(colleges_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["Name"].strip()
            try:
                major = float(row["Major"] or 0)
            except ValueError:
                major = 0
            if major < 1 or name not in known:
                continue
            schedule_url = (
                schedule_overrides.get(name)
                or row.get("Schedule Link", "").strip()
                or None
            )
            result[name] = {
                "state":        row["State"].strip() or None,
                "program_url":  row["Program Link"].strip() or None,
                "faculty_url":  row.get("Faculty Link", "").strip() or None,
                "catalog_url":  row["Catalog Link"].strip() or None,
                "schedule_url": schedule_url,
            }
    return result


# ── course schedule ───────────────────────────────────────────────────────

# Course-name patterns to exclude (case-insensitive).
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
    r"\bcolloquium\b",
    r"\bsenior seminar\b",
    r"\bcapstone\b",
    r"\bresearch seminar\b",
    r"\bresearch sem\b",
    r"\bcollaborative research\b",
    r"\brsc research\b",
    r"\bindividual study\b",
    r"\bind study\b",
    r"\bindep(t|endent)? study\b",
    r"\bdir study\b",
    r"\badvanced study\b",
    r"\bnon-traditional study\b",
    r"\bprivate reading\b",
    r"\bind reading\b",
    r"\bindep(t|endent)? reading\b",
    r"\brecitation\b",
]
EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.IGNORECASE)

MIN_YEAR = "2021-22"
TERM_ORDER = {"F": 0, "W": 1, "S": 2, "Su": 3, "": 4}
ALLOWED_TERMS = {"F", "W", "S"}

_LAB_RE = re.compile(r"\blab(s|oratory)?\b", re.IGNORECASE)
_LAB_COMBINED_RE = re.compile(
    r"(?:\bw/|\bwith\s+|\band\s+|/)\s*lab(s|oratory)?\b",
    re.IGNORECASE,
)


def has_cs_code(code: str) -> bool:
    code = (code or "").lstrip()
    return bool(code) and code[:1].upper() == "C"


def is_excluded(name: str) -> bool:
    return bool(name) and EXCLUDE_RE.search(name) is not None


def is_lab_only(name: str) -> bool:
    if not name or not _LAB_RE.search(name):
        return False
    return _LAB_COMBINED_RE.search(name) is None


def term_label(year: str, term: str) -> str:
    start, end = year.split("-")
    yy = end[-2:] if term in ("W", "S", "Su") else start[-2:]
    if not term:
        return f"{start[-2:]}-{end[-2:]}"
    return f"{term}{yy}"


def natural_key(s: str) -> list:
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


# Instructor → faculty matching. Catalog scrapes use many formats:
# "First Last", "First M. Last", "Last, First", "Last,Initial", "D.Bunde",
# plus multi-instructor separators (`;`, `,`) and generic tokens like
# "Staff" / "TBA". Parse each row into (first, last) tuples and match
# against the college's faculty by last-token equality + first-name
# agreement.

_GENERIC_RE = re.compile(
    r"^("
    r"staff|tba|tbd|tba/tba|faculty|to be announced|unknown faculty|"
    r"instructor[\s\-]?tba|department staff|csb staff|"
    r"a&s|shss|full[\s\-]?time faculty|adjunct|"
    r"announced|instructor|none|n/a"
    r")$",
    re.IGNORECASE,
)
_INITIALS_LAST_RE = re.compile(r"^((?:[A-Z]\.\s*){1,3})([A-Z][a-z][A-Za-z'\-]+)$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _is_generic(s: str) -> bool:
    s = s.strip().rstrip(",").rstrip(".").strip()
    if not s:
        return True
    return bool(_GENERIC_RE.match(s))


def _split_no_semi(s: str) -> list[str]:
    s = s.strip()
    if not s:
        return []
    if "," not in s:
        return [] if _is_generic(s) else [s]
    parts = [p.strip() for p in s.split(",") if p.strip()]
    kept = [p for p in parts if not _is_generic(p)]
    if not kept:
        return []
    if len(kept) == 1:
        return kept
    if len(kept) == 2:
        if " " in kept[0] and " " in kept[1]:
            return kept
        return [", ".join(kept)]
    return kept


def split_instructors(raw: str) -> list[str]:
    s = raw.strip()
    if not s:
        return []
    if ";" in s:
        out: list[str] = []
        for p in s.split(";"):
            out.extend(_split_no_semi(p))
        return out
    return _split_no_semi(s)


def parse_instructor_name(s: str) -> tuple[str, str] | None:
    s = s.strip().strip(",").strip()
    if not s or _is_generic(s):
        return None
    m = _INITIALS_LAST_RE.match(s)
    if m:
        return (m.group(1).strip()[0].lower(), _norm(m.group(2)))
    if "," in s:
        last, _, rest = s.partition(",")
        last = _norm(last)
        rest_tokens = [t.rstrip(".") for t in rest.split() if t.strip()]
        if not last or not rest_tokens:
            return None
        return (_norm(rest_tokens[0]), last)
    tokens = [t for t in s.split() if t]
    if len(tokens) < 2:
        return None
    return (_norm(tokens[0].rstrip(".")), _norm(tokens[-1]))


def _parse_faculty_name(name: str) -> tuple[str, str] | None:
    tokens = [t for t in name.split() if t]
    if len(tokens) < 2:
        return None
    return (_norm(tokens[0]), _norm(tokens[-1]))


def _match_one(parsed, faculty_index: list[tuple[str, str, dict]]) -> dict | None:
    if not parsed:
        return None
    pfirst, plast = parsed
    plast_tok = plast.rsplit(" ", 1)[-1]
    cands: list[tuple[int, dict]] = []
    last_only: list[dict] = []
    for ffirst, flast, f in faculty_index:
        if flast != plast_tok:
            continue
        last_only.append(f)
        if pfirst == ffirst:
            cands.append((2, f))
        elif len(pfirst) == 1 and pfirst == ffirst[:1]:
            cands.append((1, f))
        elif len(ffirst) == 1 and ffirst == pfirst[:1]:
            cands.append((1, f))
    if cands:
        cands.sort(key=lambda x: -x[0])
        if len(cands) == 1 or cands[0][0] > cands[1][0]:
            return cands[0][1]
        return None
    if len(last_only) == 1:
        return last_only[0]
    return None


def faculty_match_index(faculty_by_college: dict[str, dict]) -> dict[str, list[dict]]:
    """Adapt the faculty map into the per-college list of matchable people
    (with initials label + best link) needed by instructor matching."""
    out: dict[str, list[dict]] = {}
    for college, entry in faculty_by_college.items():
        people = []
        for p in entry.get("faculty", []):
            url = p.get("url") or p.get("scholar_url") or None
            tokens = [t for t in p["name"].split() if t]
            if len(tokens) >= 2:
                label = (tokens[0][:1] + tokens[-1][:1]).upper()
            elif tokens:
                label = tokens[0][:2].upper()
            else:
                label = "?"
            people.append({"name": p["name"], "url": url, "label": label})
        out[college] = people
    return out


def match_instructors(raw: str, faculty: list[dict]) -> tuple[list[dict], bool]:
    if not faculty:
        return [], False
    pieces = split_instructors(raw)
    if not pieces:
        return [], False
    index = []
    for p in faculty:
        parsed = _parse_faculty_name(p["name"])
        if parsed:
            index.append((parsed[0], parsed[1], p))
    matched: list[dict] = []
    seen_names: set[str] = set()
    had_specific = False
    for piece in pieces:
        parsed = parse_instructor_name(piece)
        if parsed is None:
            continue
        had_specific = True
        m = _match_one(parsed, index)
        if m and m["name"] not in seen_names:
            seen_names.add(m["name"])
            matched.append(m)
    return matched, had_specific


def build_courses(input_dir: Path, faculty_by_college: dict[str, list[dict]]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    _stats = {"cells_total": 0, "cells_matched": 0, "instructors_matched": 0}

    csv_paths = sorted(input_dir.glob("*.csv"))

    # Global max academic year across every CSV — used to drop one-off
    # courses that haven't been taught in the latest 4 AYs.
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
        url_by_cell: dict[str, dict[tuple[str, str], str]] = defaultdict(dict)
        name_obs: dict[str, list[tuple[tuple[str, int], str, bool]]] = defaultdict(list)
        instr_strs: dict[str, dict[tuple[str, str], list[str]]] = defaultdict(lambda: defaultdict(list))

        for r in rows:
            year = r["academic_year"]
            term = r["term"]
            if year < MIN_YEAR or term not in ALLOWED_TERMS:
                continue
            code = (r["course_code"] or "").strip()
            name = (r["course_name"] or "").strip().strip('"')
            if not code or not has_cs_code(code) or is_excluded(name):
                continue
            all_terms.add((year, term))
            offered[code].add((year, term))
            url = (r.get("url") or "").strip()
            if url and (year, term) not in url_by_cell[code]:
                url_by_cell[code][(year, term)] = url
            if name:
                tkey = (year, TERM_ORDER.get(term, 99))
                name_obs[code].append((tkey, name, is_lab_only(name)))
            instructor = (r.get("instructor") or "").strip()
            if instructor:
                instr_strs[code][(year, term)].append(instructor)

        latest_name: dict[str, str] = {}
        codes_set = set(offered.keys())
        drop_codes: set[str] = {
            code for code in codes_set
            if len(code) > 1 and code.endswith("L") and code[:-1] in codes_set
        }
        for code in list(offered.keys()):
            obs = name_obs.get(code, [])
            non_lab = [o for o in obs if not o[2]]
            if non_lab:
                latest_name[code] = max(non_lab, key=lambda o: o[0])[1]
            elif obs:
                drop_codes.add(code)

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

        per_term_mode = any(
            len({u for u in url_by_cell.get(code, {}).values() if u}) >= 2
            for code in sorted_codes
        )
        course_url = {
            code: next(iter({u for u in url_by_cell.get(code, {}).values() if u}), None)
            for code in sorted_codes
        }
        college_unique_urls = {u for u in course_url.values() if u}
        drop_title_urls = (not per_term_mode) and len(college_unique_urls) <= 1

        college_faculty = faculty_by_college.get(college, [])

        courses_out = []
        for code in sorted_codes:
            cell_urls = url_by_cell.get(code, {})
            entry: dict = {"code": code, "name": latest_name.get(code, "")}
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

            if college_faculty:
                instr_col: list = []
                for (y, t) in sorted_terms:
                    if (y, t) not in offered[code]:
                        instr_col.append(None)
                        continue
                    raws = instr_strs.get(code, {}).get((y, t), [])
                    _stats["cells_total"] += 1
                    if not raws:
                        instr_col.append(None)
                        continue
                    matched_all: list[dict] = []
                    seen_names: set[str] = set()
                    had_specific = False
                    for raw in raws:
                        m, hs = match_instructors(raw, college_faculty)
                        had_specific = had_specific or hs
                        for f in m:
                            if f["name"] in seen_names:
                                continue
                            seen_names.add(f["name"])
                            matched_all.append(f)
                    if matched_all:
                        _stats["cells_matched"] += 1
                        _stats["instructors_matched"] += len(matched_all)
                        instr_col.append([
                            {"l": f["label"], "n": f["name"], "u": f.get("url")}
                            for f in matched_all
                        ])
                    else:
                        instr_col.append(None)
                if any(x is not None for x in instr_col):
                    entry["instructors"] = instr_col

            courses_out.append(entry)

        result[college] = {
            "terms": [
                {"year": y, "term": t, "label": term_label(y, t)}
                for (y, t) in sorted_terms
            ],
            "courses": courses_out,
        }

    if faculty_by_college and _stats["cells_total"]:
        pct = 100 * _stats["cells_matched"] / _stats["cells_total"]
        print(
            f"Instructor matching: {_stats['cells_matched']}/{_stats['cells_total']} "
            f"cells ({pct:.1f}%) with at least one matched instructor; "
            f"{_stats['instructors_matched']} total instructor links."
        )

    return result


# ── publications ─────────────────────────────────────────────────────────

EXCLUDED_VENUE_TYPES = {"book series", "ebook platform"}


def _split_pipe(s: str) -> list[str]:
    if not s:
        return []
    return [p.strip() for p in s.split("|") if p.strip()]


def _split_semi(s: str) -> list[str]:
    if not s:
        return []
    return [p.strip() for p in s.split(";") if p.strip()]


_REPO_VENUE_RE = re.compile(r"^(\w+)\s+\(.*\)$")


def _clean_venue(v: str) -> str | None:
    if not v:
        return None
    if "arxiv" in v.lower():
        return "arXiv"
    if "http" in v:
        return None
    m = _REPO_VENUE_RE.match(v)
    if m:
        v = m.group(1)
    return v.replace("&amp;", "&") or None


def build_publications(pubs_csv: Path) -> dict[str, dict]:
    """Return {college_name: {publications: [...]}}."""
    if not pubs_csv.exists():
        return {}

    rows = read_csv(pubs_csv)
    colleges: dict[str, list[dict]] = defaultdict(list)

    for r in rows:
        venue_type = (r.get("venue_type") or "").strip()
        if venue_type in EXCLUDED_VENUE_TYPES:
            continue

        college = (r.get("college") or "").strip()
        if not college:
            continue

        year_raw = (r.get("year") or "").strip()
        year = None
        if year_raw:
            try:
                year = int(float(year_raw))
            except (ValueError, TypeError):
                pass
        if year is None:
            continue

        core_rank = (r.get("venue_core_ranking") or "").strip() or None
        sjr_raw = (r.get("venue_sjr_quartile") or "").strip()
        sjr_quartile = sjr_raw if sjr_raw and sjr_raw != "-" else None
        venue_ranking = None
        venue_ranking_source = None
        if core_rank:
            venue_ranking = core_rank
            venue_ranking_source = "ICORE 2026 Ranking"
        elif sjr_quartile:
            venue_ranking = sjr_quartile
            venue_ranking_source = "Scimago 2025 Ranking"

        work_type = (r.get("work_type") or "").strip()
        venue_name = (r.get("venue") or "").strip()
        if core_rank:
            pub_type = "conference"
        elif sjr_quartile:
            pub_type = "journal"
        elif "workshop" in venue_name.lower():
            pub_type = "workshop"
        elif work_type == "preprint":
            pub_type = "preprint"
        elif work_type in ("book", "book-chapter"):
            pub_type = "book"
        else:
            pub_type = "other"

        cites_raw = (r.get("cited_by_count") or "").strip()
        cites = 0
        if cites_raw:
            try:
                cites = int(float(cites_raw))
            except (ValueError, TypeError):
                pass

        authors_raw = (r.get("authors") or "").strip()
        authors = []
        if authors_raw:
            try:
                for a in json.loads(authors_raw):
                    author = {"name": a.get("name", "")}
                    aid = a.get("id", "")
                    if aid:
                        author["url"] = f"https://openalex.org/authors/{aid}"
                    affs = a.get("affiliations", [])
                    if affs:
                        author["affiliation"] = affs[0]
                    authors.append(author)
            except (json.JSONDecodeError, TypeError):
                pass

        pub = {
            "title": (r.get("title") or "").strip(),
            "url": (r.get("url") or "").strip() or None,
            "year": year,
            "cites": cites,
            "venue": _clean_venue((r.get("venue") or "").strip()),
            "venue_url": (r.get("venue_url") or "").strip() or None,
            "venue_acronym": (r.get("venue_acronym") or "").strip() or None,
            "venue_ranking": venue_ranking,
            "venue_ranking_source": venue_ranking_source,
            "authors": authors,
            "pub_type": pub_type,
        }
        colleges[college].append(pub)

    result: dict[str, dict] = {}
    for name, pubs in colleges.items():
        result[name] = {"publications": pubs}
    return result


# ── merge + date sync ─────────────────────────────────────────────────────

def merge(faculty: dict[str, dict], links: dict[str, dict], courses: dict[str, dict], publications: dict[str, dict]) -> dict[str, dict]:
    """Combine the four per-college maps. Iteration follows the faculty map
    insertion order (CSV row order), preserving the legacy UI ordering."""
    out: dict[str, dict] = {}
    for name, fac in faculty.items():
        entry: dict = {}
        if name in links:
            entry.update(links[name])
        entry.update(fac)
        if name in courses:
            entry.update(courses[name])
        if name in publications:
            entry.update(publications[name])
        out[name] = entry
    return out


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _human_date(d: date) -> str:
    return f"{d.strftime('%B')} {_ordinal(d.day)} {d.year}"


def sync_dates(today: date) -> None:
    """Keep the published date in three SEO-relevant locations in sync:
    JSON-LD `dateModified`, sitemap.xml `<lastmod>`, and the human-readable
    "Data was last updated on …" line in the page footer."""
    iso = today.isoformat()
    human = _human_date(today)

    if INDEX_HTML.exists():
        html = INDEX_HTML.read_text(encoding="utf-8")
        new_html = re.sub(
            r'("dateModified":\s*")\d{4}-\d{2}-\d{2}(")',
            rf'\g<1>{iso}\g<2>',
            html,
            count=1,
        )
        new_html = re.sub(
            r'(Data was last updated on )[A-Za-z]+ \d{1,2}(?:st|nd|rd|th) \d{4}',
            rf'\g<1>{human}',
            new_html,
            count=1,
        )
        if new_html != html:
            INDEX_HTML.write_text(new_html, encoding="utf-8")

    if SITEMAP_XML.exists():
        xml = SITEMAP_XML.read_text(encoding="utf-8")
        new_xml = re.sub(
            r'(<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
            rf'\g<1>{iso}\g<2>',
            xml,
            count=1,
        )
        if new_xml != xml:
            SITEMAP_XML.write_text(new_xml, encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list",     type=Path, default=DEFAULT_LIST)
    p.add_argument("--scholar",  type=Path, default=DEFAULT_SCHOLAR)
    p.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    p.add_argument("--field",    type=Path, default=DEFAULT_FIELD)
    p.add_argument("--colleges", type=Path, default=DEFAULT_COLLEGES)
    p.add_argument("--courses-dir", type=Path, default=DEFAULT_COURSES)
    p.add_argument("--pubs",     type=Path, default=DEFAULT_PUBS)
    p.add_argument("--output",   type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--no-sync-dates", action="store_true",
                   help="Skip updating JSON-LD/sitemap/footer dates.")
    args = p.parse_args()

    faculty = build_faculty(args.list, args.scholar, args.verified, args.field)
    links = build_links(args.colleges, set(faculty.keys()))
    courses = build_courses(args.courses_dir, faculty_match_index(faculty))
    publications = build_publications(args.pubs)
    merged = merge(faculty, links, courses, publications)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    if not args.no_sync_dates:
        sync_dates(date.today())

    total_faculty = sum(c["total"] for c in merged.values())
    total_courses = sum(len(c.get("courses", [])) for c in merged.values())
    total_pubs = sum(len(c.get("publications", [])) for c in merged.values())
    pubs_colleges = sum(1 for c in merged.values() if c.get("publications"))
    print(f"Wrote {len(merged)} colleges, {total_faculty} faculty, "
          f"{total_courses} courses → {args.output}")
    print(f"{total_pubs} publications across {pubs_colleges} colleges")


if __name__ == "__main__":
    main()
