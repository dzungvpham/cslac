# CSLAC: Computer Science at Liberal Arts Colleges in the US

This repository contains the source code and data for the [cslac.org](https://cslac.org) website.
CSLAC collects data on Computer Science faculty and courses from almost all liberal arts colleges in the US.
We focus on faculty whose teaching and/or research are primarily in the field of Computer Science.
Math/Stats faculty within the same department are therefore currently not included.

## What's in the dataset

For each college we track:

- **Faculty** — name, title (professor, lecturer, visiting, etc.), personal website URL, Google Scholar profile URL, and inferred research subfields.
- **Citation metrics** — total citations, h-index, and i10-index pulled from each faculty member's verified Google Scholar profile.
- **Courses** — recent and upcoming CS course offerings (course code, name, instructor, term, meeting time) where the college publishes a public schedule.
- **Program info** — links to the program page, faculty list, course catalog, and schedule for each college.

The full source-of-truth CSVs live under [`data/`](data/). The website at [cslac.org](https://cslac.org) is a browsable view of the same data.

## How the data pipeline works

The pipeline starts from a single seed file, [`data/colleges.csv`](data/colleges.csv), which lists every college we cover along with the URLs to its CS department, faculty page, and course catalog. From there, data is built up in stages:

1. **Faculty discovery.** We crawl each college's faculty page and extract the name, title, and personal page URL for every CS faculty member. Because every college's site looks different, we use a heuristic auto-detector that infers the page's faculty-card pattern, with a small number of hand-written fallbacks for sites that need them.
2. **Scholar matching.** For each faculty member we search for a matching Google Scholar profile, then fetch that profile (through a residential proxy, since Scholar aggressively rate-limits) and verify it really belongs to the right person by checking the affiliation. Matches are labeled `matched`, `no_match`, or similar; ambiguous matches can be approved or rejected manually.
3. **Personal website scraping.** We use a headless browser to render each faculty member's personal page and save the visible text. The text is then cleaned by stripping shared header/footer boilerplate (detected by comparing pages from the same college) and trimming to lines near research-relevant keywords.
4. **Research field inference.** A local LLM reads the cleaned text plus the Scholar profile data and assigns each faculty member to a field (Computer Science, Math/Stats, etc.) along with up to five CS subfields drawn from a curated taxonomy.
5. **Course scraping.** A separate pipeline visits each college's course catalog and pulls every CS course offering for recent academic years. Different schools run very different catalog systems, so each school (or family of schools — e.g. the many that share Ellucian Self-Service) gets its own small scraper.
6. **Dashboard generation.** The CSVs from the steps above are merged into a single JSON file that powers the static dashboard published at cslac.org.

The pipeline is designed to be **incremental and resumable** — re-running any stage picks up where it left off and only reprocesses rows that need it.

## Using the data

The processed CSVs in [`data/`](data/) are the easiest entry point:

- [`data/colleges.csv`](data/colleges.csv) — list of colleges with program links and metadata.
- [`data/faculty_list.csv`](data/faculty_list.csv) — `name, title, college, url` for every CS faculty member.
- [`data/faculty_list_with_scholar_url.csv`](data/faculty_list_with_scholar_url.csv) — adds the Google Scholar URL.
- [`data/faculty_list_with_verified_profile.csv`](data/faculty_list_with_verified_profile.csv) — adds verified affiliation, match status, citation metrics, and Scholar research interests.
- [`data/faculty_list_with_field.csv`](data/faculty_list_with_field.csv) — adds the LLM-inferred field and CS subfields.
- [`data/course_schedule/<College Name>.csv`](data/course_schedule/) — one CSV per college with recent CS course offerings.

All four faculty CSVs are aligned by row order on `(name, title, college)` and can be joined directly.
We linked them together into a single `docs/data.json`, which is used to power [cslac.org](https://cslac.org).

## Running the code

The scraping pipeline is in [`scraper/`](scraper/). To set up:

```bash
pip install -e .
```

The faculty and course pipelines are each run as a sequence of Python scripts; see [`CLAUDE.md`](CLAUDE.md) for the exact commands, stage-by-stage data flow, and details on environment variables (a Brave Search API key for Scholar lookups, Decodo proxy credentials for profile fetching, and a local Ollama instance for field inference). Adding a new college means adding a row to `data/colleges.csv` and, if needed, a small entry in the scraper map.

## Citing

If you use this data or code, please cite it as follows:

```
@misc{pham2026cslac,
author = {Pham, Dzung},
month = jun,
title = {{CSLAC: Computer Science at Liberal Arts Colleges}},
url = {https://github.com/dzungvpham/cslac},
year = {2026}
}
```

## Disclaimer

CSLAC is an independent, non-commercial project and is not affiliated with, endorsed by, or sponsored by any of the colleges, universities, or individuals it covers. College and program names are used for identification purposes only.

The data is compiled from publicly available sources and is provided **"as is," without warranty of any kind**, express or implied, including warranties of accuracy, completeness, currency, or fitness for a particular purpose. Faculty rosters, titles, course offerings, and research interests change frequently; entries here may be incomplete, outdated, or incorrect. The data should not be relied on for hiring, admissions, accreditation, or any other consequential decision. We make no representation that any inferred research field or subfield reflects an individual's own characterization of their work.

All underlying rights — including in faculty biographies, course descriptions, citation metrics, and any third-party content — remain with their original owners. Excerpts and links are included under what we understand to be fair use for non-commercial research and educational purposes; if you are a rights holder and would like content attributed differently or removed, please open an issue.

Citation metrics (total citations, h-index, i10-index) and listed research interests are sourced from each faculty member's public Google Scholar profile and are reproduced here for non-commercial informational purposes. Google Scholar is a trademark of Google LLC; CSLAC is not affiliated with, endorsed by, or sponsored by Google. All Scholar-derived data remains the property of its respective owners, and the underlying profiles are authoritative — values shown here are point-in-time snapshots and may lag the live profile. Faculty who would like their Scholar-derived data suppressed in CSLAC can request this via an issue.

If you are a faculty member or institutional representative and would like an entry corrected, updated, or removed, please open an issue in this repository.

Use of this code or data is at your own risk. To the maximum extent permitted by law, the maintainers disclaim all liability for any loss or damage arising from its use.

## License

The source code is licensed under GPLv3 (see [`LICENSE`](LICENSE)).
