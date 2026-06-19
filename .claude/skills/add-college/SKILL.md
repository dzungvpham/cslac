---
name: add-college
description: Add one new liberal arts college to the cslac CS-faculty dataset and run it through the full faculty pipeline incrementally — registration, Stages 1–9, IPEDS degree count, logo, and data.json — WITHOUT re-scraping the existing colleges. Use when asked to "add a college/school", "add <CollegeName>", "onboard a college", or expand the dataset with a new institution.
---

# Add a college to the cslac dataset

End-to-end routine for adding ONE college at a time. Complements the terse
"Adding a New College" section in `CLAUDE.md` (which only covers scraper
registration) by documenting the full **incremental** pipeline run.

All commands run from `scraper/` unless noted. Work on one college per run.

## ⚠️ Invariants — read first
1. **Never run `python faculty_scraper.py` with no args.** Its `main()` re-scrapes
   *every* college in `faculty_scraper_map` and overwrites `faculty_list.csv`.
   For one college you scrape it in isolation and **append**.
2. **The five faculty CSVs are row-aligned by position** and `docs/generate_data.py`
   asserts it (`name,title,college` must match across all five at every row).
   The five, in order:
   `faculty_list.csv`, `faculty_list_with_scholar_url.csv`,
   `faculty_list_with_verified_profile.csv`, `faculty_list_with_field.csv`,
   `faculty_list_with_openalex_profile.csv`.
   **Always append the new college's rows at the END of each**, in the same
   per-faculty order. Stages 2/3/9 rebuild their CSV aligned to `faculty_list.csv`
   automatically; only Stage 1 and Stage 6 need a manual append.
3. **Do not edit `auto_detect_scraper`** (the auto path) without asking the user.
   Adding a hardcoded entry to `faculty_scraper_map` is fine and expected.

## Prerequisites
- `.env`: `BRAVE_API_KEY` (Stage 2), `DECODO_*` (Stage 3). `OPENALEX_API_KEY`
  is optional (Stages 7/9 just run rate-limited without it).
- Google Chrome for Selenium (Stages 4, and Stage 1 fallback). Test with
  `create_selenium_driver()` before relying on it.
- Stage 6 wants a local Ollama; `faculty_site_analysis.py` auto-resolves the host
  (`$OLLAMA_HOST` → `localhost` → WSL Windows-host gateway, e.g. `172.22.96.1`),
  so it may work even when `localhost:11434` is refused. If unavailable, do the
  field analysis manually (see Stage 6).

## Step 0 — Research the college
Confirm it's a real LAC with a CS major (Carnegie `C21BASIC==21`; see
`data/degrees_awarded.csv` / the IPEDS finder). Gather:
- **Faculty Link** — the CS *department/area* page that lists faculty (prefer a
  CS-specific page over a school-wide directory). Verify it actually lists names.
- **ROR ID** — `https://api.ror.org/organizations?query=<College>` → the id after
  `ror.org/` (store the bare id, e.g. `01pq38j30`).
- **Program Link**, **City/State**, and whether the page is server-rendered or
  needs JS (fetch it and check the names are present in the raw HTML).

## Step 1 — Register the college
1. **`data/colleges.csv`** — append a row (current 9-col schema):
   `Name, City, State, ROR, Major, Minor/Concentration, Program Link, Faculty Link, Schedule Link`.
   `Major=1.0`. Insert in alphabetical position (or end; only the College enum +
   map gate matter functionally). Use pandas to preserve quoting.
2. **`scraper/constants.py`** — add `NAME = "Exact College Name"` to the `College`
   StrEnum (string must equal the `colleges.csv` Name exactly).
3. **`scraper/faculty_scraper.py` → `faculty_scraper_map`** — add an entry. This
   map is the *gate*: `main()`/`get_faculty_list` skip any college not in it.
   - First test whether the auto path handles the page:
     ```python
     import faculty_scraper as fs; from bs4 import BeautifulSoup
     soup = BeautifulSoup(fs.fetch_url("<faculty url>"), "html.parser")
     auto = fs.auto_detect_scraper(soup); print(auto and auto(soup))
     ```
   - If auto returns rows → still add a reasonable hardcoded fallback
     (`scrape_class_f("...")` etc.) as the map entry.
   - If auto returns `None`/garbage → write a custom `scrape_<college>(soup)`
     (model it on `scrape_macalester` / `scrape_bennington`) and reference it in
     the map. **Gotcha:** `clean_title()` returns `None` unless the text contains
     professor/lecturer/instructor/chair — schools that label people just
     "Faculty"/"Visiting Faculty" (e.g. Bennington, no tenure) need a custom
     scraper that supplies a title string. Titles flow into
     `categorize_title()` in `generate_data.py`
     (`visiting`/`adjunct`/`teaching`/`tenure_track`/`tenured`).
   - If the page needs JS, add the college to `use_selenium_map`; if it returns
     JSON, add to `faculty_url_override_map` + write a JSON-aware scraper.

## Stage 1 — scrape faculty → merge into `faculty_list.csv`
**Primary:** `python faculty_scraper.py --college "<Name>"` — scrapes only the
matching college via the full path (auto-detect → hardcoded fallback →
`openai/privacy-filter` ML drop → URL fixing) and merges into `faculty_list.csv`
(a new college is appended at the end; an existing college is replaced in place).
Needs Chrome + the ML model. The substring is matched case-insensitively against
`faculty_scraper_map` keys, so make it unique.

**Lightweight alternative** (skips the ML filter — fine when you wrote a clean
custom scraper and the page has no non-human noise):
```python
import csv, faculty_scraper as fs; from bs4 import BeautifulSoup
FAC = "<faculty url>"; COLLEGE = "<Exact Name>"
soup = BeautifulSoup(fs.fetch_url(FAC), "html.parser")   # or retry_with_selenium
rows = fs.faculty_scraper_map[COLLEGE](soup)             # or auto(soup)
with open("../data/faculty_list.csv", "a", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["name","title","college","url"])
    for r in rows:
        w.writerow({"name": r["name"], "title": r["title"], "college": COLLEGE,
                    "url": fs.get_full_faculty_url(FAC, r["url"])})
```

Verify the names/titles/URLs look right before continuing. (Re-running
`--college` for a college already in the file replaces its rows; if the row
count changed, re-run stages 2/3/6/9 so the sibling CSVs realign.)

## Stage 2 — Scholar URLs  ·  `python faculty_scholar_url_scraper.py`
Incremental: reuses existing URLs, Brave-searches only rows missing one, rewrites
the output aligned to `faculty_list.csv`. Empty result = no Scholar profile (fine).

## Stage 3 — verify Scholar profiles  ·  `python faculty_scholar_profile_scraper.py`
Adds the new rows with empty status and processes them via the Decodo proxy.
Rows with no Scholar URL short-circuit to `no_url` (no fetch, no manual step).
**Manual point:** for `matched_name`/`matched_college`/`no_match` you must eyeball
and set `manual_approved` (or fix the URL + `rescrape`) in the output CSV, then
re-run. Trusted = `matched`/`manual_approved`.

## Stage 4 — scrape sites  ·  `python faculty_site_scraper.py`
Skips already-saved files, so it only fetches the new college's pages →
`data/faculty_websites/<College>/<name>.txt`. Needs Chrome (8 drivers at startup).

## Stage 5 — clean  ·  `python faculty_site_cleaner.py`
Full-batch but deterministic/idempotent; regenerates `faculty_websites_cleaned/`.
Boilerplate dedup needs ≥2 faculty sharing a URL base path (true for most depts).

## Stage 6 — field + subfields → append to `faculty_list_with_field.csv`
Output cols: `name,title,college,field,subfields` (subfields `|`-joined).
- **If Ollama is up:** `python faculty_site_analysis.py`. It's resumable and
  **skips rows that already have a field**, so to (re)classify a specific college
  use `--overwrite` or clear its rows first.
- **If Ollama is down, do it yourself** (this is acceptable and was done for
  Bennington). Read each cleaned `.txt`, then classify per the rules/taxonomy in
  `faculty_site_analysis.py`: `field` ∈ `{Computer Science, Mathematics or
  Statistics, Unknown, Invalid}`; for CS, ≤5 subfields from `CS_SUBFIELD_NAMES`,
  only "strong"-evidence ones, exact canonical spelling. Validate names against
  `CS_SUBFIELD_NAMES` before appending. Show your reasoning to the user.

## Stage 7 — publications  ·  `python faculty_publication_scraper.py --college "<Name>"`
Append-only; splices the new college in (appended at end if new). Matches papers
to faculty by `(last_name, first_initial)` + the college's ROR, so **recent hires
/ visiting faculty whose work predates this affiliation can yield 0 papers** —
that's correct, not a bug. Sanity-check with a direct OpenAlex query
(`authorships.institutions.ror:<ror>,topics.field.id:17`).

## Stage 8 — venue tags  ·  `python faculty_publication_venue_tagger.py`
Run only if Stage 7 added papers; it re-tags `faculty_publications.csv` in place.
Skip if the college has 0 papers.

## Stage 9 — OpenAlex metrics  ·  `python faculty_openalex_profile_scraper.py`
Derives author IDs from `faculty_publications.csv`; row-aligned to `faculty_list.csv`.
0 matched papers → empty metrics (the faculty simply show no citation data).

## IPEDS degree count (optional, for the dashboard "majors" number)
Append one row to `data/degrees_awarded.csv`
(`college,UNITID,ipeds_name,cs_cip_codes,2021,2022,2023,2024`). Get the numbers
from the cached IPEDS files via `degrees_awarded_scraper`’s helpers
(`fetch_source`/`load_completions`, CS CIP set in `data/degrees_awarded/cip_reference.csv`)
or re-run `python degrees_awarded_scraper.py` (regenerates all from cache).

## Logo (optional)
1. Drop a source image at `docs/img/logo/<slug>.<ext>`.
2. **Normalize it to the 64px sprite cell.** The sprite packs every logo into a
   64px square, and all committed sources follow one convention: the **long side
   is 64** (a square logo is `64×64`; a non-square one keeps its aspect ratio
   with the long side at 64 — e.g. `colby.png` is `64×38`). So resize the source
   unless its long side is already 64 (most downloads are bigger — Bennington
   arrived as a 400×400 JPEG). This mirrors what `generate_logo_sprite.py` does
   at pack time (`scale = min(64/w, 64/h)`) and keeps source files tiny.
   ```python
   from PIL import Image
   p = "docs/img/logo/<slug>.<ext>"
   im = Image.open(p)
   w, h = im.size
   if max(w, h) != 64:                        # already cell-sized → skip
       s = 64 / max(w, h)
       im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
       # keep the same format/extension; for JPEG: im.convert("RGB").save(p, quality=90)
       im.save(p)
   ```
   (A square logo lands at `64×64`, i.e. *both* dimensions 64; non-square logos
   only ever hit 64 on the long side — don't upscale the short side to 64, that
   would distort and the packer would just shrink it back.)
3. Add `"Exact College Name": "<slug>.<ext>"` to the mapping in
   `docs/generate_logo_sprite.py`.
4. `python docs/generate_logo_sprite.py` to rebuild `logo_sprite.webp`/`.css`
   (the dashboard renders logos from the sprite, not the source files).

## Course schedule (optional)
Adds the dashboard's Courses toggle; independent of the faculty pipeline.

**First check for a supported platform** — if the school's schedule URL matches
one, it's a one-line config tuple, no new module (see `CLAUDE.md` → "Adding a
New Course-Schedule Scraper"):
- Colleague Self-Service (`/Student/Courses/Search`) → `SELFSERVICE_COLLEGES`
- Banner 9 SSB (`/StudentRegistrationSsb/`) → `BANNER9_COLLEGES`
- PowerCampus (`/SELFSERV/Search/Section`) → `POWERCAMPUS_COLLEGES`
- Jenzabar JICS (`portlet=Course_Schedules`) → `JENZABAR_JICS_COLLEGES`

**Otherwise write a custom subclass** (models: `course_schedule/bennington.py`,
`amherst.py`):
1. Create `scraper/course_schedule/<college>.py` subclassing
   `CourseScheduleScraper`; set `college`, `terms` (e.g. `["F", "S"]`; `[]` = one
   page per year that covers all terms), and implement `url_for(academic_year,
   term)` + `parse_page(html, academic_year, term)`. `academic_year` is an
   `(start, end)` int tuple (map Fall → start year, Spring → end year). Build
   rows with `self.make_row(...)`; fields: `course_code, section, course_name,
   instructor, time, url`.
2. Server-rendered page? Override `fetch_page` to use `requests` (skip Selenium —
   much faster). JS/SPA? Keep the default Selenium `load`, set `wait_for` to a
   content selector, and consider `fresh_driver_per_load` (see base docstring).
3. Set `public_url_template = True` when `url_for` is a user-facing page — the
   dashboard then auto-links the latest term via `latest_public_url()`, so you
   don't need to set the colleges.csv `Schedule Link`.
4. Register: import the class and add it to `SCRAPERS` in
   `scrape_course_schedule.py`.

**Run just this college** (the runner has no per-college flag):
```python
from course_schedule.scrape_course_schedule import OUTPUT_DIR
from course_schedule.<mod> import <Class>
with <Class>() as s:
    print(s.run(OUTPUT_DIR))   # writes data/course_schedule/<College>.csv
```
Re-runs top up only new `(year, term)` pairs; `run(OUTPUT_DIR, force=True)`
re-scrapes every configured pair.

**Classify categories** surgically, so you don't churn ~60 other CSVs:
```bash
python course_classifier.py --no-write     # classify new titles into the cache (uses the `claude` CLI)
```
then attach the column to only the new CSV:
```python
from course_classifier import load_cache, write_csvs
from pathlib import Path
write_csvs([Path("../data/course_schedule/<College>.csv")], load_cache())
```

**Gotchas**
- The dashboard renders only courses whose code passes `has_cs_code()` (CS
  subject prefixes); cross-listed MAT/PHY/etc. rows are dropped uniformly, so
  scraping a department's full area-of-study set is fine.
- Catalogs that expose only currently-registerable terms (Self-Service, and a
  brand-new program like Bennington's CS area) yield no back-history — coverage
  accrues across quarterly runs, not in one shot.
- Finding the URL: if a known schedule URL redirects/404s, search for where it
  moved (e.g. a `/curriculum/courses/` path on the main domain) before
  concluding the school has none.

## Build + verify  ·  `python docs/generate_data.py --no-sync-dates`
Use `--no-sync-dates` until you're actually publishing (the plain run also bumps
the published date in `index.html`/`sitemap.xml`/footer). The run **asserts the
5-CSV alignment** — success means everything lines up. Then confirm:
```python
import json; b = json.load(open("docs/data.json"))["<Exact Name>"]
print(len(b["faculty"]), b.get("majors"), [f["category"] for f in b["faculty"]])
```
Expect the right faculty count, the IPEDS `majors` number, and sensible
title categories. Only colleges with ≥1 CS-faculty row are emitted.

## Verification checklist
- [ ] All five faculty CSVs have the same row count and the college appears in each.
- [ ] `generate_data.py` ran without an alignment error.
- [ ] Faculty names/titles/subfields look right in `data.json`.
- [ ] Courses (if added): the college's CSV exists with categories attached, and
      `data.json` shows its `courses` + a rotating `schedule_url`.
- [ ] Flag to the user: any 0-publication / no-citation faculty and the
      `Minor/Concentration` guess.
