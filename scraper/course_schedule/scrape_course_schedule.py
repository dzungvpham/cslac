"""Run all available course-schedule scrapers and write per-college CSVs.

To add a new school: implement a `CourseScheduleScraper` subclass in a new
module under this package, then add it to `SCRAPERS` below.

By default, colleges with an existing CSV in `data/course_schedule/` are
skipped. Pass `--force` to re-scrape everything.
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from course_schedule.amherst import AmherstScraper
from course_schedule.trinity import TrinityScraper
from course_schedule.williams import WilliamsScraper

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "course_schedule"

SCRAPERS = [
    AmherstScraper,
    TrinityScraper,
    WilliamsScraper,
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape colleges even if their CSV already exists.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for cls in SCRAPERS:
        print(f"== {cls.__name__} ({cls.college}) ==", flush=True)
        existing = OUTPUT_DIR / f"{cls.college}.csv"
        if existing.exists() and not args.force:
            print(f"  -- already scraped ({existing}); pass --force to redo", flush=True)
            continue
        try:
            with cls() as scraper:
                path, n = scraper.run(OUTPUT_DIR)
                print(f"  -> wrote {n} rows to {path}", flush=True)
        except Exception:
            print(f"  !! {cls.__name__} failed:", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
