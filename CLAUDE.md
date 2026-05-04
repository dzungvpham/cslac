# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a research tool for scraping and analyzing CS faculty at liberal arts colleges (LACs). It produces a dataset of faculty names, titles, personal website URLs, and research fields/subfields.

## Setup

```bash
pip install -e .
```

## Running the Pipeline

All scripts are run from the `scraper/` directory. The pipeline has four stages:

```bash
cd scraper

# Stage 1: Scrape faculty lists from college department pages
python faculty_scraper.py
python faculty_scraper.py --selenium-backup  # also handle colleges that block requests

# Stage 2: Scrape each faculty member's personal website
python faculty_site_scraper.py

# Stage 3: Clean scraped website text (remove nav/footer boilerplate, trim to relevant sections)
python faculty_site_cleaner.py

# Stage 4: Use a local LLM to infer research fields and subfields
python faculty_site_analysis.py
```

The Jupyter notebooks in `notebooks/` (`analyze_faculty.ipynb`, `create_taxonomy.ipynb`) are used for ad-hoc analysis and taxonomy construction — not part of the automated pipeline.

## Data Flow

```
data/colleges.csv          → faculty_scraper.py    → data/faculty_list.csv
data/faculty_list.csv      → faculty_site_scraper.py → data/faculty_websites/<college>/<name>.txt
data/faculty_websites/     → faculty_site_cleaner.py → data/faculty_websites_cleaned/<college>/<name>.txt
data/faculty_websites_cleaned/ → faculty_site_analysis.py → data/faculty_list_with_fields.csv
```

`data/colleges.csv` is the source of truth for which colleges to include. Only rows with `Major == 1` are processed.

## Architecture

**`scraper/constants.py`** — Defines the `College` StrEnum with human-readable college names used as keys throughout the codebase.

**`scraper/faculty_scraper.py`** — Core scraping logic. The key data structure is `faculty_scraper_map`: a dict mapping `College` → scraper function. Most scrapers are built from composable factory functions:
- `scrape_class_f(*classnames)` — scrape elements matching all given CSS classes
- `scrape_tag_f(tagname)` — scrape by HTML tag
- `scrape_f(filter_fn)` — scrape using an arbitrary BeautifulSoup filter

Each scraper receives a `BeautifulSoup` object and returns a list of `{name, title, college, url}` dicts. A small number of colleges (Dickinson, Trinity C, Wesleyan) use API endpoints instead of HTML pages — see `faculty_url_override_map`. Colleges that block `requests` and require Selenium are listed in `use_selenium_map`.

URL cleanup (`is_strange_url`, `fix_urls`) uses Google Search as a fallback to find correct faculty profile URLs when scraped URLs are missing or suspicious.

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
3. Add a scraper entry in `faculty_scraper_map` in `scraper/faculty_scraper.py` using the appropriate factory function
4. If the page requires Selenium, add to `use_selenium_map`; if it uses an API endpoint, add to `faculty_url_override_map`
