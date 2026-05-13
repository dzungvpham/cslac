"""Run all available course-schedule scrapers and write per-college CSVs.

To add a new school: implement a `CourseScheduleScraper` subclass in a new
module under this package, then add it to `SCRAPERS` below.

Re-running a scraper merges newly-scraped rows into any existing CSV
(deduped on the full row), so prior history is preserved. By default,
colleges with an existing CSV in `data/course_schedule/` are skipped to
avoid the cost of re-scraping; pass `--force` to re-scrape everything and
merge in any new rows.
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from course_schedule.amherst import AmherstScraper
from course_schedule.banner9 import banner9_scrapers
from course_schedule.barnard import BarnardScraper
from course_schedule.bowdoin import BowdoinScraper
from course_schedule.bryn_mawr import BrynMawrScraper
from course_schedule.bucknell import BucknellScraper
from course_schedule.carleton import CarletonScraper
from course_schedule.centre import CentreScraper
from course_schedule.colby import ColbyScraper
from course_schedule.colorado import ColoradoScraper
from course_schedule.davidson import DavidsonScraper
from course_schedule.drew import DrewScraper
from course_schedule.earlham import EarlhamScraper
from course_schedule.gettysburg import GettysburgScraper
from course_schedule.goucher import GoucherScraper
from course_schedule.hamilton import HamiltonScraper
from course_schedule.haverford import HaverfordScraper
from course_schedule.hyperschedule import HarveyMuddScraper, PomonaScraper
from course_schedule.macalester import MacalesterScraper
from course_schedule.middlebury import MiddleburyScraper
from course_schedule.mount_holyoke import MountHolyokeScraper
from course_schedule.occidental import OccidentalScraper
from course_schedule.randolph_macon import RandolphMaconScraper
from course_schedule.richmond import RichmondScraper
from course_schedule.selfservice import selfservice_scrapers
from course_schedule.smith import SmithScraper
from course_schedule.trinity import TrinityScraper
from course_schedule.unca import UNCAshevilleScraper
from course_schedule.vassar import VassarScraper
from course_schedule.wabash import WabashScraper
from course_schedule.wellesley import WellesleyScraper
from course_schedule.wesleyan import WesleyanScraper
from course_schedule.williams import WilliamsScraper

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "course_schedule"

SCRAPERS = [
    AmherstScraper,
    BarnardScraper,
    BowdoinScraper,
    BrynMawrScraper,
    BucknellScraper,
    CarletonScraper,
    CentreScraper,
    ColbyScraper,
    ColoradoScraper,
    DavidsonScraper,
    DrewScraper,
    EarlhamScraper,
    GettysburgScraper,
    GoucherScraper,
    HamiltonScraper,
    HaverfordScraper,
    HarveyMuddScraper,
    MacalesterScraper,
    MiddleburyScraper,
    MountHolyokeScraper,
    OccidentalScraper,
    PomonaScraper,
    RandolphMaconScraper,
    RichmondScraper,
    SmithScraper,
    TrinityScraper,
    UNCAshevilleScraper,
    VassarScraper,
    WabashScraper,
    WellesleyScraper,
    WesleyanScraper,
    WilliamsScraper,
    *selfservice_scrapers(),
    *banner9_scrapers(),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape colleges even if their CSV already exists; new rows are merged in.",
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
