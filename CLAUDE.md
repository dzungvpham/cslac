# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research tool for scraping and analyzing CS faculty at liberal arts colleges (LACs). It produces a dataset of faculty names, titles, personal website URLs, Google Scholar profile URLs, and research fields/subfields.

## Setup

```bash
pip install -e .
```

## Running the Pipeline

All scripts are run from the `scraper/` directory. The pipeline has four stages:

```bash
cd scraper

# Stage 1: Scrape faculty lists from college department pages.
# Selenium is used automatically for colleges listed in `use_selenium_map`.
python faculty_scraper.py

# Stage 2: Find each faculty member's Google Scholar profile URL
python faculty_scholar_url_scraper.py

# Stage 3: Scrape each faculty member's personal website
python faculty_site_scraper.py

# Stage 4: Clean scraped website text (remove nav/footer boilerplate, trim to relevant sections)
python faculty_site_cleaner.py

# Stage 5: Use a local LLM to infer research fields and subfields
python faculty_site_analysis.py
```

The Jupyter notebooks in `notebooks/` (`analyze_faculty.ipynb`, `create_taxonomy.ipynb`) are used for ad-hoc analysis and taxonomy construction — not part of the automated pipeline.

## Data Flow

```
data/colleges.csv              → faculty_scraper.py            → data/faculty_list.csv
data/faculty_list.csv          → faculty_scholar_url_scraper.py → data/faculty_list_with_scholar_url.csv
data/faculty_list.csv          → faculty_site_scraper.py       → data/faculty_websites/<college>/<name>.txt
data/faculty_websites/         → faculty_site_cleaner.py       → data/faculty_websites_cleaned/<college>/<name>.txt
data/faculty_websites_cleaned/ → faculty_site_analysis.py      → data/faculty_list_with_fields.csv
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

**`scraper/faculty_site_scraper.py`** — Iterates through faculty with URLs, loads each page via Selenium, and saves the rendered body text to `data/faculty_websites/<college>/<name>.txt`. Skips already-saved files.

**`scraper/faculty_site_cleaner.py`** — Two-pass cleaning:
1. Removes shared header/footer boilerplate by comparing pages from the same college with the same URL base path
2. Keeps only lines near mentions of the faculty member's name or research-relevant keywords (research, interest, courses, publications, etc.)

**`scraper/faculty_site_analysis.py`** — Uses a local Ollama instance (`llama3.1:8b-instruct-fp16` at `localhost:11434`) to extract research subfields from cleaned text, then classifies each faculty member into Computer Science / Mathematics / Statistics / Unknown.

## Selenium / ChromeDriver

ChromeDriver is managed automatically by Selenium Manager (Selenium 4.6+) — no manual setup needed. Requires Google Chrome to be installed in WSL (`google-chrome-stable`). The `--no-sandbox` and `--disable-dev-shm-usage` flags are set for WSL compatibility.

## Adding a New College

1. Add the college to `data/colleges.csv` with `Major = 1` and the correct `Faculty Link`
2. Add a `College.NEW_COLLEGE` entry to the `College` StrEnum in `scraper/constants.py`
3. Add an entry in `faculty_scraper_map` (a hardcoded fallback). In most cases the auto path will work without this, but the map is currently the gate that decides which colleges get processed
4. If the page requires Selenium, add to `use_selenium_map`; if it returns JSON instead of HTML, add to `faculty_url_override_map` (and write a JSON-aware hardcoded scraper, since auto can't handle JSON)
5. Verify auto handles the page (e.g. fetch the URL, run `auto_detect_scraper(soup)`, and inspect the output) before relying on the hardcoded fallback
