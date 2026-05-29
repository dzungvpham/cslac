# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research tool for scraping and analyzing CS faculty at liberal arts colleges (LACs). It produces a dataset of faculty names, titles, personal website URLs, Google Scholar profile URLs, and research fields/subfields.

## Setup

```bash
pip install -e .
```

## Running the Pipeline

All scripts are run from the `scraper/` directory. The faculty pipeline has eight stages:

```bash
cd scraper

# Stage 1: Scrape faculty lists from college department pages.
# Selenium is used automatically for colleges listed in `use_selenium_map`.
python faculty_scraper.py

# Stage 2: Find each faculty member's Google Scholar profile URL (Brave Search)
python faculty_scholar_url_scraper.py

# Stage 3: Fetch each Scholar profile and verify the match (Decodo proxy).
# Two-pass: re-running picks up rows flagged `rescrape` and skips `manual_approved`.
python faculty_scholar_profile_scraper.py

# Stage 4: Scrape each faculty member's personal website
python faculty_site_scraper.py

# Stage 5: Clean scraped website text (remove nav/footer boilerplate, trim to relevant sections)
python faculty_site_cleaner.py

# Stage 6: Use a local LLM to infer research fields and subfields
python faculty_site_analysis.py
# Resumable: re-running picks up where it left off by merging prior progress
# from data/faculty_list_with_field.csv.

# Stage 7: Scrape publication data from OpenAlex
python faculty_publication_scraper.py
# Append-only: re-running skips colleges already in the output.
# Use --overwrite to re-run from scratch, --college <name> for one college.

# Stage 8: Tag publication venues with CSRankings / ICORE / Scimago rankings
python faculty_publication_venue_tagger.py
# Reads faculty_publications.csv and writes back in-place with the new
# venue_acronym, venue_area, venue_in_csranking, venue_core_ranking,
# venue_core_url, venue_sjr_quartile, venue_issn, and venue_sjr_url columns.
```

A separate course-schedule pipeline lives under `scraper/course_schedule/`:

```bash
cd scraper
# Run all configured per-college course-schedule scrapers. By default each
# scraper only fetches (academic_year, term) pairs not already in the
# college's CSV (top-up mode for quarterly runs). Pass --force to re-scrape
# every configured pair; existing rows for a re-scraped pair are replaced
# wholesale, and terms absent from the new scrape are preserved.
python -m course_schedule.scrape_course_schedule [--force]
```

The Jupyter notebooks in `notebooks/` (`analyze_faculty.ipynb`, `create_taxonomy.ipynb`) are used for ad-hoc analysis and taxonomy construction — not part of the automated pipeline. The static dashboard in `docs/` (see below) is regenerated from the verified-profile CSV and is published via GitHub Pages (Settings → Pages → Deploy from a branch → `main` / `/docs`).

## Data Flow

```
data/colleges.csv                  → faculty_scraper.py                 → data/faculty_list.csv
data/faculty_list.csv              → faculty_scholar_url_scraper.py     → data/faculty_list_with_scholar_url.csv
data/faculty_list_with_scholar_url → faculty_scholar_profile_scraper.py → data/faculty_list_with_verified_profile.csv
data/faculty_list.csv              → faculty_site_scraper.py            → data/faculty_websites/<college>/<name>.txt
data/faculty_websites/             → faculty_site_cleaner.py            → data/faculty_websites_cleaned/<college>/<name>.txt
data/faculty_websites_cleaned/     → faculty_site_analysis.py           → data/faculty_list_with_field.csv
  (also merges in data/faculty_list.csv + data/faculty_list_with_verified_profile.csv as side-input)

data/faculty_list.csv + colleges.csv → faculty_publication_scraper.py        → data/faculty_publications.csv
data/faculty_publications.csv      → faculty_publication_venue_tagger.py  → data/faculty_publications.csv (in-place, adds venue_* columns)
  (also reads scraper/icore2026.csv, scraper/scimagojr.csv, scraper/scimagojr_math.csv)

data/colleges.csv                  → course_schedule.scrape_course_schedule → data/course_schedule/<College Name>.csv
```

`data/colleges.csv` is the source of truth for which colleges to include. Only rows with `Major == 1` are processed.

## Architecture

**`scraper/constants.py`** — Defines the `College` StrEnum with human-readable college names used as keys throughout the codebase.

**`scraper/faculty_scraper.py`** — Core scraping logic. Two scraping paths run per college:

1. **`auto_detect_scraper(soup)`** (primary) — heuristically infers the faculty-card pattern from page content. Stages: (1) score each candidate CSS class / structural tag (`tr`, `li`, `article`, `dt`) by how many valid `(name, title)` pairs it yields at various `name_line` offsets; (2) split `<hr>`- or `<br>`-separated sibling entries (e.g. New College of Florida, Coe); (3) walk up from each title leaf to find the smallest ancestor that yields a valid card. Title leaves are detected via the `TITLE_RE` regex. Helper passes: `_filter_descendants` collapses self-nesting classes to leaf cards but only when the descendant itself carries a title leaf (otherwise we'd lose real cards to e.g. inner "Message Perry" buttons or name-only divs); `filter_cards_by_heading` drops cards under section headings like "Emeriti" / "Affiliated"; `_maybe_subject_filter` falls back to a CS-subject-only filter when a page is clearly a full-school directory.

2. **`faculty_scraper_map`** (fallback) — a dict mapping `College` → hardcoded scraper function, used when the auto path returns nothing or when the privacy-filter ML model rejects every auto result for a college (`filter_non_human_rows`). Hardcoded scrapers are built from composable factories: `scrape_class_f(*classnames)`, `scrape_tag_f(tagname)`, `scrape_f(filter_fn)`. They are kept as a safety net but the auto path covers the great majority of colleges; many entries in the map are now stale (their CSS selectors have rotted) and only the auto path keeps those colleges working.

Each scraper returns a list of `{name, title, college, url}` dicts. A small number of colleges (Dickinson, Trinity C, Wesleyan) use API endpoints that return JSON — see `faculty_url_override_map`; auto cannot handle these, so their hardcoded entries call `json.loads()` directly. Colleges that block `requests` or require JS rendering are listed in `use_selenium_map`.

After scraping, `filter_non_human_rows` runs the `openai/privacy-filter` token-classification model on every name to drop non-human rows (e.g. "Apply Now", "Quick Links"). Rows with a URL slug matching the name are rescued (`url_matches_name`) to avoid dropping real-but-uncommon names the model misses. URL cleanup (`is_strange_url`, `fix_urls`) uses Google Search as a fallback when scraped URLs are missing or suspicious.

**`scraper/faculty_scholar_url_scraper.py`** — Uses the Brave Search API to find each faculty member's Google Scholar profile URL (`scholar.google.com/citations?user=...`). Queries are run asynchronously with a rate limiter (20 QPS) and exponential-backoff retries. Requires a `BRAVE_API_KEY` in a `.env` file. Outputs `data/faculty_list_with_scholar_url.csv`.

**`scraper/faculty_scholar_profile_scraper.py`** — Two-pass Scholar-profile verifier. Pass 1: for each row without a `scholar_match_status`, fetch the candidate profile through a Decodo residential proxy (requires `DECODO_USERNAME`/`DECODO_PASSWORD`/`DECODO_HOST`/`DECODO_PORT` in `.env`), parse out name + affiliation + citation/h-index stats, and classify the result as `matched`, `matched_name`, `matched_college`, `no_match`, `fetch_error`, or `no_url`. Manual step: edit the output CSV to mark rows `manual_approved` (locked) or `rescrape` (will be retried). Pass 2 — re-running the script — only touches rows whose status is empty or `rescrape`. Each retry rotates exit IPs to dodge Scholar's "not a robot" soft-block; uses 8 workers and `MAX_RETRIES = 8`. Output columns include `verified_affiliation`, `scholar_match_status`, and `scholar_*` citation metrics. Outputs `data/faculty_list_with_verified_profile.csv`.

**`scraper/faculty_site_scraper.py`** — Iterates through faculty with URLs, loads each page via Selenium, and saves the rendered body text to `data/faculty_websites/<college>/<name>.txt`. Skips already-saved files.

**`scraper/faculty_site_cleaner.py`** — Two-pass cleaning:
1. Removes shared header/footer boilerplate by comparing pages from the same college with the same URL base path
2. Keeps only lines near mentions of the faculty member's name or research-relevant keywords (research, interest, courses, publications, etc.)

**`scraper/faculty_site_analysis.py`** — Uses a local Ollama instance (`qwen3:30b-a3b-instruct-2507-q4_K_M` at `localhost:11434`) to extract research subfields from cleaned text, then classifies each faculty member into one of `ALLOWED_FIELDS = ["Computer Science", "Mathematics or Statistics", "Unknown", "Invalid"]`. Up to `MAX_SUBFIELDS = 5` CS subfields per row, drawn from the `CS_SUBFIELDS` taxonomy. Inputs: `data/faculty_list.csv` (base rows) merged with `data/faculty_list_with_verified_profile.csv` (so the prompt can see Scholar interests/affiliation), plus the per-faculty cleaned-text file under `data/faculty_websites_cleaned/<college>/<name>.txt`. Output: `data/faculty_list_with_field.csv` with `field` and pipe-separated `subfields` columns. Resumable — on restart it merges any existing output back in and only re-runs rows missing a `field`.

**`scraper/faculty_publication_scraper.py`** — Fetches CS publications per institution from OpenAlex (filtered by `topics.field.id:17`) using ROR IDs from `colleges.csv`. Each output row is a unique paper. For each work, matches authorships to the faculty list by `(last_name, first_initial)` and institution ROR; matched names are collected in the `matched_faculty` column. Remaining co-authors are classified as `student` (same institution, last name not in faculty list), `faculty` (same institution, last name matches), `other_lac` (institution name in our LAC set), or `external`. Deduplicates papers by normalized title, preferring journal/proceedings versions over preprints and merging matched faculty across duplicates. Output columns include `url` (DOI or landing page), `cited_by_count`, `topics`, `subfields`, and per-category co-author lists. Append-only by default (skips colleges already in the output); `--overwrite` re-runs from scratch, `--college <name>` re-runs a single college. Requires `OPENALEX_API_KEY` in `.env` (optional but recommended for higher rate limits). Outputs `data/faculty_publications.csv`.

**`scraper/faculty_publication_venue_tagger.py`** — Post-processing pass that tags each paper's venue with rankings from three sources, writing back to `data/faculty_publications.csv` in-place. (1) **CSRankings** — the 81 conferences across 27 areas at https://csrankings.org/ are matched via the hand-tuned `CSRANKINGS` regex table (include + exclude patterns) and populate `venue_acronym`, `venue_area`, `venue_in_csranking`. (2) **ICORE 2026** — scraped from `portal.core.edu.au` on first run and cached at `scraper/icore2026.csv`; matching is layered (CSRankings acronym → CORE acronym lookup, then parenthetical acronyms in the venue name, then a token-recall + Jaccard fuzzy match against CORE conference titles) and fills `venue_core_ranking` (`A*/A/B/C`) and `venue_core_url`. Also gives `Findings of ACL/EMNLP/NAACL` papers their parent conference's rank. (3) **Scimago (SJR)** — read from `scraper/scimagojr.csv` (CS-area filter) and `scraper/scimagojr_math.csv` (Math-area filter); journals are matched by normalized title with an ordered-subset fallback for naming drift (e.g. "IEEE/ACM Transactions on Networking" vs "IEEE Transactions on Networking"). A small `_CURATED_SJR` table fills in cross-disciplinary journals (Nature, Science, PRL, JAMA, etc.) that the CS/Math filters don't carry. Output columns: `venue_sjr_quartile` (`Q1`–`Q4`), `venue_issn`, `venue_sjr_url`.

**`scraper/openalex_subfield_map.py`** — Mapping from granular OpenAlex topic names (~4000 globally) to our 32-subfield CS taxonomy (`CS_SUBFIELDS` in `faculty_site_analysis.py`). Imported by `docs/generate_data.py` to derive per-paper `subfields` tags from OpenAlex `topics` strings, which the dashboard uses to gate paper visibility when the user clicks a subfield chip. Topics-only by design — OpenAlex's coarser `subfields` are too noisy (the docstring lists examples: software-testing → "Computer Networks", Cuban-drums → "Computer Vision"); the `openalex_subfields` argument is kept in the signature but ignored.

**`scraper/course_schedule/`** — Course-schedule scraping sub-package. The driver loop lives in `course_schedule_scraper.py` (`CourseScheduleScraper` base class): for each `(academic_year, term)` pair it calls `url_for(...)`, drives Selenium via `load(...)` (one fresh driver per page by default — many catalog SPAs only fetch on first navigation), and hands the rendered HTML to `parse_page(...)`. Subclasses set `college` (a `constants.College` value), `years_back` (default 5), and optionally `terms` (e.g. `["F", "S"]`; empty means one load per year for sites whose listing covers all terms). Per-school subclasses live alongside the base (`amherst.py`, `macalester.py`, `trinity.py`, `williams.py`, and many more — one module per non-platform school).

Four shared **platform-family modules** generate one class per `(College, base_url, subject)` config tuple, so adding a school on one of these platforms is a one-line change:

- **`selfservice.py`** — Ellucian **Colleague Self-Service** catalogs (`SELFSERVICE_COLLEGES`). Most live at `selfservice.<edu>`, but several deployments use custom subdomains (e.g. Emmanuel's `ecss.`, Grinnell's `colss-prod.ec.`, Luther's `norsehub.`, Meredith's `mcis.`, Westmont's `waypoint.`); the membership criterion is "Schedule Link contains `/Student/Courses/Search`." Self-Service exposes only currently registerable terms (last finished + current + next one or two), so the scraper captures whatever appears, not a fixed history; logged-in-only catalogs (Allegheny, Wooster) are detected via the `/Account/Login` redirect and produce empty results.
- **`banner9.py`** — Ellucian **Banner 9 Student Registration Self-Service** ("SSB") catalogs (`BANNER9_COLLEGES`). Hits the JSON API at `/StudentRegistrationSsb/ssb/...` directly with `requests` — no Selenium. Each school's Banner term codes vary (Lafayette uses 202610/202630, Dickinson 202670/202720, etc.), so terms are discovered at runtime from `getTerms` and mapped back to `(academic_year, term)` rather than hardcoded. A per-CRN `getFacultyMeetingTimes` hop is used when the list endpoint omits faculty data (e.g. Oberlin).
- **`powercampus.py`** — Ellucian **PowerCampus Self-Service** ("SELFSERV") catalogs (`POWERCAMPUS_COLLEGES`). Hits the React SPA's backing JSON endpoint at `/SELFSERV/Sections/Search` with `requests`. Two non-obvious requirements: the `X-Current-Page` header must be the base64 of `"SectionSearchId"`, and the session cookie from `/SELFSERV/Search/Section?eventId=<SUBJ>` must accompany the POST. Like Colleague Self-Service, only currently registerable terms appear.
- **`jenzabar_jics.py`** — Jenzabar **JICS Course_Schedules portlet** (`JENZABAR_JICS_COLLEGES`). ASP.NET WebForms page with a ~20 KB `__VIEWSTATE` and JS-driven postback search — driven via Selenium. Term descriptions vary across deployments (Claflin: `"Fall 2024-2025"`, Hendrix: `"2024-2025 - Fall Semester"`) and are parsed from the option text, not the opaque option value.

Two further consortium-specific scrapers live in **`hyperschedule.py`** (`HarveyMuddScraper`, `PomonaScraper`) — both Claremont Colleges schools, backed by the Hyperschedule API at `banana.hyperschedule.io` which returns the full 5C section list per term; a module-level cache keeps it at one API hit per term per process.

The runner `scrape_course_schedule.py` instantiates every scraper in `SCRAPERS`, including `*selfservice_scrapers()`, `*banner9_scrapers()`, `*jenzabar_jics_scrapers()`, and `*powercampus_scrapers()`. By default each scraper skips `(academic_year, term)` pairs already present in its CSV and only fetches new ones; `--force` re-scrapes every configured pair (replacing existing rows for that pair while preserving pairs absent from the new scrape). For scrapers with `terms = []` (one URL per year covering all terms, e.g. Williams), any row matching the academic year counts as coverage and the year is skipped. Output columns: `college, academic_year, term, course_code, section, course_name, instructor, time, url`.

**`docs/`** — Static dashboard for browsing the dataset, published as a GitHub Pages site. `index.html` is a single-page app (vanilla JS + IBM Plex fonts, light/dark themes); each expanded college panel has a Faculty / Courses / Publications toggle (Courses is hidden for colleges without schedule data, Publications for colleges with no matched papers). `generate_data.py` emits a single `data.json` keyed by college name, combining four sources:

- **Faculty** — merges four CSVs aligned by row order on `(name, title, college)`: `faculty_list.csv` (personal URL), `faculty_list_with_scholar_url.csv` (Scholar URL), `faculty_list_with_verified_profile.csv` (match status, citation/h-index metrics, scholar interests), and `faculty_list_with_field.csv` (LLM-inferred field + subfields). Only rows whose `field` is in `{Computer Science, Invalid}` are included; `scholar_match_status ∈ {matched, manual_approved}` counts as trusted (untrusted rows still appear but their `scholar_url` and citation metrics are suppressed). The `interests` field prefers LLM-inferred subfields, falling back to Scholar interests when the row is trusted. Each row's title is bucketed into `tenured | tenure_track | teaching | visiting | adjunct` via `categorize_title()`. The row-alignment check will fail loudly if the four faculty CSVs drift out of sync.
- **Links** — reads `data/colleges.csv` and folds `state` plus the four `*_url` fields into each college entry. Only colleges with `Major >= 1` are considered.
- **Courses** — reads every CSV under `data/course_schedule/` and adds per-college `terms` and `courses` with sorted term columns (year then F→W→S→Su) and `(code, name)`-deduplicated course rows, restricted to academic years ≥ 2021-22. Instructor strings are matched against the in-memory faculty list to produce per-cell initials + link.
- **Publications** — reads `data/faculty_publications.csv` (the venue-tagger-augmented version from Stage 8) and emits a per-college `publications` list. Each paper carries a `pub_type` (`conference | journal | workshop | preprint | book | other`), classified by venue name → `venue_type` → CORE/SJR rank in that priority order (workshops short-circuit on the venue name; OpenAlex `work_type=preprint` is overridden when the venue is a real conference/journal, since OpenAlex sometimes never re-types arXiv-first ingests). Conference papers get `venue_ranking` from ICORE 2026 (`A*/A/B/C`); journal papers get it from Scimago (`Q1`–`Q4`). Per-paper `subfields` come from `openalex_subfield_map.map_paper_to_cs_subfields(topics)`. A small skip list filters out OpenAlex noise rows like "Session details: …", "Math Counts", "Conversations: …".

Only colleges with at least one CS-faculty row are emitted. Regenerate after a pipeline run (`generate_data.py` also syncs the published date into `index.html`'s JSON-LD, `sitemap.xml`, and the footer string unless `--no-sync-dates` is passed).

## Selenium / ChromeDriver

ChromeDriver is managed automatically by Selenium Manager (Selenium 4.6+) — no manual setup needed. Requires Google Chrome to be installed in WSL (`google-chrome-stable`). The `--no-sandbox` and `--disable-dev-shm-usage` flags are set for WSL compatibility.

## Adding a New College

1. Add the college to `data/colleges.csv` with `Major = 1` and the correct `Faculty Link`
2. Add a `College.NEW_COLLEGE` entry to the `College` StrEnum in `scraper/constants.py`
3. Add an entry in `faculty_scraper_map` (a hardcoded fallback). In most cases the auto path will work without this, but the map is currently the gate that decides which colleges get processed
4. If the page requires Selenium, add to `use_selenium_map`; if it returns JSON instead of HTML, add to `faculty_url_override_map` (and write a JSON-aware hardcoded scraper, since auto can't handle JSON)
5. Verify auto handles the page (e.g. fetch the URL, run `auto_detect_scraper(soup)`, and inspect the output) before relying on the hardcoded fallback

## Adding a New Course-Schedule Scraper

1. Check whether the school runs one of the four supported platforms — if so, add a `(College.NAME, base_url, subject)` tuple to the platform's config list (no new file required):
   - **Ellucian Colleague Self-Service** (URL contains `/Student/Courses/Search`) → `SELFSERVICE_COLLEGES` in `selfservice.py`
   - **Ellucian Banner 9 SSB** (URL contains `/StudentRegistrationSsb/`) → `BANNER9_COLLEGES` in `banner9.py`
   - **Ellucian PowerCampus** (URL contains `/SELFSERV/Search/Section`) → `POWERCAMPUS_COLLEGES` in `powercampus.py`
   - **Jenzabar JICS** (URL contains `portlet=Course_Schedules`) → `JENZABAR_JICS_COLLEGES` in `jenzabar_jics.py`
2. Otherwise: create a new module under `scraper/course_schedule/` that subclasses `CourseScheduleScraper`, set `college`, and implement `url_for(academic_year, term)` and `parse_page(html, academic_year, term)`. Override `fetch_page(...)` if the schedule is gated behind a form/dropdown rather than reachable by URL.
3. If you created a new module (step 2), add the new class to `SCRAPERS` in `scraper/course_schedule/scrape_course_schedule.py`. Platform-family additions (step 1) are picked up automatically via the `*<platform>_scrapers()` splat.
