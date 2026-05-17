"""Generic base class for college-specific course schedule scrapers.

A scraper for one school is built by subclassing `CourseScheduleScraper` and
implementing two hooks:

    url_for(academic_year, term)   -> the schedule URL for that page
    parse_page(html, academic_year, term) -> list of row dicts

The base class drives the loop: for each (academic_year, term) it computes
the URL, loads the page through Selenium, and asks the subclass to parse it.
The set of (academic_year, term) pairs to scrape is controlled by the
`years_back` and `terms` class attributes (overridable on subclasses).

Each row dict should contain (missing values as empty string, not None):

    college, academic_year, term, course_code, section, course_name,
    instructor, time, url

Selenium is always used. Many catalog SPAs only fetch data on the first
navigation per session, so by default each `load()` call uses a fresh driver
(see `fresh_driver_per_load`).
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from selenium.webdriver.support.ui import WebDriverWait

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from faculty_scraper import create_selenium_driver  # noqa: E402


OUTPUT_COLUMNS = [
    "college",
    "academic_year",
    "term",
    "course_code",
    "section",
    "course_name",
    "instructor",
    "time",
    "url",
]

# When `terms` is empty on a subclass, we issue a single load per academic
# year and pass this sentinel as the `term` argument to `url_for` /
# `parse_page`. Subclasses whose listing page covers all terms at once
# (e.g. Williams) leave `terms = []` and ignore the term argument.
NO_TERM = ""


class CourseScheduleScraper:
    """Base class for course-schedule scrapers.

    Subclass requirements:
        - set `college` to a `constants.College` value
        - implement `url_for(academic_year, term)` returning a URL string
        - implement `parse_page(html, academic_year, term)` returning row dicts

    Subclass tunables (class attributes):
        - `years_back`: how many academic years to scrape (default 5)
        - `terms`: list of term codes to iterate per year, e.g. ["F", "S"].
          Empty (the default) means a single load per year (the listing page
          covers all terms).
        - `wait_for`: CSS selector to await after page navigation (None means
          wait only for `document.readyState == 'complete'`).
        - `fresh_driver_per_load`: spin up a new driver for each `load()` call
          (default True; needed for SPA catalogs that don't re-fetch on
          subsequent same-origin navigations).
    """

    college: str = ""
    years_back: int = 5
    terms: list = []
    wait_for: str = None
    page_load_timeout: int = 30
    post_load_sleep: float = 1.0
    fresh_driver_per_load: bool = True
    # Set True on subclasses whose `url_for` produces a user-facing page (not
    # an API endpoint) so the dashboard can link straight to the latest-term
    # URL. Subclasses whose internal scraping URL differs from the public
    # one should override `public_url_for` instead.
    public_url_template: bool = False

    def __init__(self, driver=None):
        self._driver = driver
        self._owns_driver = driver is None

    # ---- driver management ---------------------------------------------------

    @property
    def driver(self):
        if self._driver is None:
            self._driver = create_selenium_driver()
        return self._driver

    def load(self, url, wait_for=None):
        """Navigate to `url`, wait until ready, return the rendered HTML.

        `wait_for` overrides the class-level `self.wait_for` for one call.
        """
        if self.fresh_driver_per_load and self._owns_driver:
            self.close()
        driver = self.driver
        driver.get(url)
        wait_selector = wait_for if wait_for is not None else self.wait_for
        if wait_selector:
            WebDriverWait(driver, self.page_load_timeout).until(
                lambda d: d.find_elements("css selector", wait_selector)
            )
        else:
            WebDriverWait(driver, self.page_load_timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        if self.post_load_sleep:
            time.sleep(self.post_load_sleep)
        return driver.page_source

    def close(self):
        if self._owns_driver and self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # ---- subclass hooks ------------------------------------------------------

    def url_for(self, academic_year, term):
        """Return the URL for one schedule page.

        `academic_year` is an `(start_year, end_year)` int tuple. `term` is
        whatever code the subclass put in `self.terms` (e.g. "F"); empty
        string when `self.terms` is empty.
        """
        raise NotImplementedError

    def parse_page(self, html, academic_year, term):
        """Return a list of row dicts parsed from `html`."""
        raise NotImplementedError

    def public_url_for(self, academic_year, term):
        """Return a user-facing URL the dashboard should link to for this
        (academic_year, term), or `None` to leave the colleges.csv URL
        untouched. Default: delegate to `url_for` when
        `public_url_template` is set, else `None`.
        """
        if self.public_url_template:
            return self.url_for(academic_year, term)
        return None

    @classmethod
    def latest_public_url(cls, today=None):
        """Build the user-facing URL for the most recent (academic_year, term)
        pair this scraper would target. Returns `None` if the subclass hasn't
        opted in via `public_url_template` / `public_url_for`.

        Term is picked from `cls.terms` based on the current month: July+
        prefers Fall, otherwise Spring (with a fallback to whatever term is
        actually configured). For scrapers with `terms = []` (one URL per
        academic year) the term argument is the empty string.
        """
        today = today or datetime.now()
        ay_list = cls.past_academic_years(1, today=today)
        if not ay_list:
            return None
        academic_year = ay_list[-1]
        if cls.terms:
            preferred = "F" if today.month >= 7 else "S"
            term = preferred if preferred in cls.terms else cls.terms[-1]
        else:
            term = NO_TERM
        try:
            inst = cls()
        except Exception:
            return None
        try:
            return inst.public_url_for(academic_year, term)
        except Exception:
            return None
        finally:
            try:
                inst.close()
            except Exception:
                pass

    def fetch_page(self, academic_year, term):
        """Return the rendered HTML for one (academic_year, term) page.

        Default: navigate to `url_for(academic_year, term)` and return the
        page source. Override for sites whose schedule lives behind a form
        (e.g. a term-selector dropdown + submit button) — your override is
        responsible for driving Selenium and returning the final HTML.

        Return `None` to signal that this (year, term) is not available
        (e.g. the term predates what the site exposes); the scrape loop
        will log it and move on.
        """
        return self.load(self.url_for(academic_year, term))

    # ---- driver loop ---------------------------------------------------------

    def schedule_pages(self):
        """Yield (academic_year, term) pairs to scrape, oldest first."""
        terms = self.terms or [NO_TERM]
        for academic_year in self.past_academic_years(self.years_back):
            for term in terms:
                yield academic_year, term

    def scrape(self, skip_pairs=None):
        skip_pairs = skip_pairs or set()
        rows = []
        for academic_year, term in self.schedule_pages():
            label = self._label(academic_year, term)
            if (format_academic_year(academic_year), term) in skip_pairs:
                print(f"  [{label}] already scraped, skipping (use --force to re-scrape)", flush=True)
                continue
            try:
                html = self.fetch_page(academic_year, term)
            except Exception as e:
                print(f"  [{label}] failed to load: {e}", flush=True)
                continue
            if html is None:
                print(f"  [{label}] not available", flush=True)
                continue
            page_rows = self.parse_page(html, academic_year, term)
            print(f"  [{label}] {len(page_rows)} sections", flush=True)
            rows.extend(page_rows)
        return rows

    def run(self, output_dir, force=False):
        """Scrape and merge results into `output_dir/<College Name>.csv`.

        Default (`force=False`): any `(academic_year, term)` pair already
        present in the existing CSV is skipped — only new pairs are fetched
        and appended. This is the quarterly top-up mode.

        With `force=True`: every configured pair is re-scraped. For each
        scraped pair, the existing CSV's rows for that pair are replaced
        wholesale with the new rows. Pairs absent from the new scrape are
        preserved untouched, so terms a school later removes from their
        public schedule stay in our history.
        """
        if not self.college:
            raise ValueError(f"{type(self).__name__}.college is not set")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.college}.csv"

        skip_pairs = set()
        if not force and path.exists() and path.stat().st_size > 0:
            skip_pairs = self._already_scraped_pairs(path)

        new_rows = self.scrape(skip_pairs=skip_pairs)

        new_df = pd.DataFrame(new_rows)
        for col in OUTPUT_COLUMNS:
            if col not in new_df.columns:
                new_df[col] = ""
        new_df = new_df[OUTPUT_COLUMNS]

        if path.exists() and path.stat().st_size > 0:
            existing_df = pd.read_csv(path, dtype=str, keep_default_na=False)
            for col in OUTPUT_COLUMNS:
                if col not in existing_df.columns:
                    existing_df[col] = ""
            existing_df = existing_df[OUTPUT_COLUMNS]
            before = len(existing_df)
            scraped_terms = set(
                map(tuple, new_df[["academic_year", "term"]].drop_duplicates().values.tolist())
            )
            existing_keys = list(zip(existing_df["academic_year"], existing_df["term"]))
            kept_mask = [key not in scraped_terms for key in existing_keys]
            kept_df = existing_df[kept_mask]
            replaced = before - len(kept_df)
            combined = pd.concat([kept_df, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=OUTPUT_COLUMNS, keep="first")
            print(
                f"  merged {len(new_df)} scraped rows into {before}-row CSV; "
                f"replaced {replaced} rows across {len(scraped_terms)} term(s), "
                f"kept {len(kept_df)} from prior terms",
                flush=True,
            )
        else:
            combined = new_df

        combined = combined.sort_values(
            by=["academic_year", "term", "course_code", "section", "instructor", "time"],
            key=lambda s: s.map(_TERM_ORDER) if s.name == "term" else s,
            kind="stable",
        ).reset_index(drop=True)

        combined.to_csv(path, index=False)
        return path, len(combined)

    # ---- helpers -------------------------------------------------------------

    def _already_scraped_pairs(self, path):
        """Return the set of `(academic_year_str, term)` iteration pairs from
        `self.schedule_pages()` that are already covered by the CSV at `path`.

        For scrapers with `terms = []` (one URL per year covering all terms),
        the iteration `term` is the empty string but stored rows carry real
        term codes ("F", "S", ...), so any row matching the academic year
        counts as coverage.
        """
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        seen_year_term = set(zip(df["academic_year"], df["term"]))
        seen_years = set(df["academic_year"])
        skip = set()
        for academic_year, term in self.schedule_pages():
            ay = format_academic_year(academic_year)
            if term == NO_TERM:
                if ay in seen_years:
                    skip.add((ay, term))
            elif (ay, term) in seen_year_term:
                skip.add((ay, term))
        return skip

    @staticmethod
    def past_academic_years(n=5, today=None):
        """Return the last `n` academic years as (start, end) int tuples,
        oldest first. The "current" academic year is the one whose fall
        semester has already begun (July onward).
        """
        today = today or datetime.now()
        current_start = today.year if today.month >= 7 else today.year - 1
        return [(current_start - i, current_start - i + 1) for i in range(n - 1, -1, -1)]

    def make_row(self, academic_year, term, **fields):
        """Build a row dict with the canonical column set pre-filled."""
        row = {
            "college": str(self.college),
            "academic_year": format_academic_year(academic_year),
            "term": term or "",
            "course_code": "",
            "section": "",
            "course_name": "",
            "instructor": "",
            "time": "",
            "url": "",
        }
        row.update({k: v for k, v in fields.items() if v is not None})
        return row

    def _label(self, academic_year, term):
        s = format_academic_year(academic_year)
        return f"{s}/{term}" if term else s


def format_academic_year(academic_year):
    """`(2025, 2026)` -> `'2025-26'`."""
    start, end = academic_year
    return f"{start}-{str(end)[-2:]}"


def format_meeting_slots(slots):
    """Render `(days, time_range, location)` triples as a meeting string.

    Triples sharing the same `(time_range, location)` are merged into a single
    weekday string (keeping the longer day string when they differ). Distinct
    slots are joined with `; `. Empty triples are skipped.

    Example: `[("MWF", "11:00-11:50", "DANA 137"), ("T", "13:00-15:50", "")]`
    -> `"MWF 11:00-11:50 (DANA 137); T 13:00-15:50"`.
    """
    groups = {}
    order = []
    for days, time_range, location in slots:
        if not days and not time_range and not location:
            continue
        key = (time_range, location)
        if key not in groups:
            groups[key] = days
            order.append(key)
        elif len(days) > len(groups[key]):
            groups[key] = days
    parts = []
    for key in order:
        time_range, location = key
        days = groups[key]
        bits = []
        if days:
            bits.append(days)
        if time_range:
            bits.append(time_range)
        s = " ".join(bits)
        if location:
            s = f"{s} ({location})" if s else f"({location})"
        if s:
            parts.append(s)
    return "; ".join(parts)


# Academic-calendar ordering: Fall, Winter/J-term, Spring, Summer.
# Empty/unknown terms sort last so they don't interleave with real ones.
_TERM_ORDER = {"F": 0, "W": 1, "S": 2, "Su": 3}
