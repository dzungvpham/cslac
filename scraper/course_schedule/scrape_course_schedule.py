"""Run all available course-schedule scrapers and write per-college CSVs.

To add a new school: implement a `CourseScheduleScraper` subclass in a new
module under this package, then add it to `SCRAPERS` below.

By default, each scraper only fetches `(academic_year, term)` pairs that
are not already present in the college's CSV — designed for a quarterly
top-up run. Pass `--force` to re-scrape every configured pair; existing
rows for a re-scraped pair are replaced wholesale, and terms absent from
the new scrape are preserved.
"""

import argparse
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from course_schedule.amherst import AmherstScraper
from course_schedule.austin import AustinScraper
from course_schedule.banner9 import banner9_scrapers
from course_schedule.barnard import BarnardScraper
from course_schedule.bowdoin import BowdoinScraper
from course_schedule.bridgewater import BridgewaterScraper
from course_schedule.bryn_athyn import BrynAthynScraper
from course_schedule.bryn_mawr import BrynMawrScraper
from course_schedule.bucknell import BucknellScraper
from course_schedule.carleton import CarletonScraper
from course_schedule.central import CentralScraper
from course_schedule.centre import CentreScraper
from course_schedule.coe import CoeScraper
from course_schedule.colby import ColbyScraper
from course_schedule.colorado import ColoradoScraper
from course_schedule.covenant import CovenantScraper
from course_schedule.davidson import DavidsonScraper
from course_schedule.drew import DrewScraper
from course_schedule.earlham import EarlhamScraper
from course_schedule.gettysburg import GettysburgScraper
from course_schedule.gordon import GordonScraper
from course_schedule.goucher import GoucherScraper
from course_schedule.hamilton import HamiltonScraper
from course_schedule.haverford import HaverfordScraper
from course_schedule.holy_cross import HolyCrossScraper
from course_schedule.hope import HopeScraper
from course_schedule.houghton import HoughtonScraper
from course_schedule.hobart_william_smith import HobartWilliamSmithScraper
from course_schedule.knox import KnoxScraper
from course_schedule.hyperschedule import HarveyMuddScraper, PomonaScraper
from course_schedule.jenzabar_jics import jenzabar_jics_scrapers
from course_schedule.macalester import MacalesterScraper
from course_schedule.maryville import MaryvilleScraper
from course_schedule.middlebury import MiddleburyScraper
from course_schedule.minnesota_morris import MinnesotaMorrisScraper
from course_schedule.mount_holyoke import MountHolyokeScraper
from course_schedule.occidental import OccidentalScraper
from course_schedule.powercampus import powercampus_scrapers
from course_schedule.presbyterian import PresbyterianScraper
from course_schedule.puget_sound import PugetSoundScraper
from course_schedule.randolph import RandolphScraper
from course_schedule.randolph_macon import RandolphMaconScraper
from course_schedule.richmond import RichmondScraper
from course_schedule.selfservice import selfservice_scrapers
from course_schedule.sewanee import SewaneeScraper
from course_schedule.smith import SmithScraper
from course_schedule.st_mary_md import StMaryMdScraper
from course_schedule.st_olaf import StOlafScraper
from course_schedule.trinity import TrinityScraper
from course_schedule.unca import UNCAshevilleScraper
from course_schedule.vassar import VassarScraper
from course_schedule.wabash import WabashScraper
from course_schedule.washington_college import WashingtonCollegeScraper
from course_schedule.washington_lee import WashingtonLeeScraper
from course_schedule.wellesley import WellesleyScraper
from course_schedule.wesleyan import WesleyanScraper
from course_schedule.westminster_pa import WestminsterPAScraper
from course_schedule.wheaton_il import WheatonILScraper
from course_schedule.williams import WilliamsScraper
from course_schedule.wofford import WoffordScraper

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "course_schedule"

SCRAPERS = [
    AmherstScraper,
    AustinScraper,
    BarnardScraper,
    BowdoinScraper,
    BridgewaterScraper,
    BrynAthynScraper,
    BrynMawrScraper,
    BucknellScraper,
    CarletonScraper,
    CentralScraper,
    CentreScraper,
    CoeScraper,
    ColbyScraper,
    ColoradoScraper,
    CovenantScraper,
    DavidsonScraper,
    DrewScraper,
    EarlhamScraper,
    GettysburgScraper,
    GordonScraper,
    GoucherScraper,
    HamiltonScraper,
    HaverfordScraper,
    HolyCrossScraper,
    HopeScraper,
    HoughtonScraper,
    HobartWilliamSmithScraper,
    HarveyMuddScraper,
    KnoxScraper,
    MacalesterScraper,
    MaryvilleScraper,
    MiddleburyScraper,
    MinnesotaMorrisScraper,
    MountHolyokeScraper,
    OccidentalScraper,
    PomonaScraper,
    PresbyterianScraper,
    PugetSoundScraper,
    RandolphScraper,
    RandolphMaconScraper,
    RichmondScraper,
    SewaneeScraper,
    SmithScraper,
    StMaryMdScraper,
    StOlafScraper,
    TrinityScraper,
    UNCAshevilleScraper,
    VassarScraper,
    WabashScraper,
    WashingtonCollegeScraper,
    WashingtonLeeScraper,
    WellesleyScraper,
    WesleyanScraper,
    WestminsterPAScraper,
    WheatonILScraper,
    WilliamsScraper,
    WoffordScraper,
    *selfservice_scrapers(),
    *banner9_scrapers(),
    *jenzabar_jics_scrapers(),
    *powercampus_scrapers(),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape every configured (year, term) pair instead of only new ones; "
        "existing rows for re-scraped pairs are replaced.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for cls in SCRAPERS:
        print(f"== {cls.__name__} ({cls.college}) ==", flush=True)
        try:
            with cls() as scraper:
                path, n = scraper.run(OUTPUT_DIR, force=args.force)
                print(f"  -> wrote {n} rows to {path}", flush=True)
        except Exception:
            print(f"  !! {cls.__name__} failed:", flush=True)
            traceback.print_exc()


if __name__ == "__main__":
    main()
