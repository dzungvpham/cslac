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

    def scrape(self):
        rows = []
        for academic_year, term in self.schedule_pages():
            label = self._label(academic_year, term)
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

    def run(self, output_dir):
        """Scrape and write a CSV to `output_dir/<College Name>.csv`."""
        if not self.college:
            raise ValueError(f"{type(self).__name__}.college is not set")

        rows = sorted(self.scrape(), key=_row_sort_key)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.college}.csv"

        # Don't clobber existing data with an empty result — transient
        # failures (DNS, timeouts, an upstream redirect change) shouldn't
        # destroy a previously-good CSV. Re-runs with --force should still
        # overwrite when the scrape actually produced rows.
        if not rows and path.exists() and path.stat().st_size > 0:
            with open(path) as f:
                existing_rows = sum(1 for _ in f) - 1  # drop header
            if existing_rows > 0:
                print(
                    f"  scrape returned 0 rows; keeping existing {existing_rows}-row CSV at {path}",
                    flush=True,
                )
                return path, existing_rows

        df = pd.DataFrame(rows)
        for col in OUTPUT_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        df = df[OUTPUT_COLUMNS]
        df.to_csv(path, index=False)
        return path, len(df)

    # ---- helpers -------------------------------------------------------------

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


# Academic-calendar ordering: Fall, Winter/J-term, Spring, Summer.
# Empty/unknown terms sort last so they don't interleave with real ones.
_TERM_ORDER = {"F": 0, "W": 1, "S": 2, "Su": 3}


def _row_sort_key(row):
    return (
        row.get("academic_year", ""),
        _TERM_ORDER.get(row.get("term", ""), 99),
        row.get("course_code", ""),
        row.get("section", ""),
        row.get("instructor", ""),
        row.get("time", ""),
    )
