"""Pack every college logo into a single CSS sprite.

Outputs:
  docs/img/logo_sprite.webp  — square-cell grid of every logo
  docs/img/logo_sprite.css   — .college-logo base rule + per-college
                               --col/--row variables keyed by slug

The grid uses fixed CELL-sized cells at native resolution. The CSS scales
the whole sheet via the --cs custom property, so index.html can size logos
differently per breakpoint (e.g. 24px desktop, 16px mobile) without
regenerating the sprite.
"""
import math
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
LOGO_DIR = ROOT / "img" / "logo"
SPRITE_IMG = ROOT / "img" / "logo_sprite.webp"
SPRITE_CSS = ROOT / "img" / "logo_sprite.css"

CELL = 64  # native cell size — sources are already ≤64px on the long side

# Source-of-truth college → logo-file mapping. Mirror this list into
# index.html only via the generated CSS; the JS side derives the class
# name from the college name via collegeSlug() (matching slug() below).
COLLEGE_LOGOS = {
    "Albion College": "albion.png",
    "Albright College": "albright.png",
    "Allegheny College": "allegheny.png",
    "Amherst College": "amherst.png",
    "Augustana College": "augustana.png",
    "Austin College": "austin.png",
    "Bard College": "bard.png",
    "Barnard College": "barnard.png",
    "Beloit College": "beloit.png",
    "Berea College": "berea.webp",
    "Bethany College (WV)": "bethany.png",
    "Bethany Lutheran College": "bethany_lutheran.webp",
    "Bowdoin College": "bowdoin.webp",
    "Bridgewater College": "bridgewater.webp",
    "Bryn Athyn College": "bryn_athyn.png",
    "Bryn Mawr College": "bryn_mawr.png",
    "Bucknell University": "bucknell.png",
    "Carleton College": "carleton.webp",
    "Central College": "central.png",
    "Centre College": "centre.webp",
    "Claflin University": "claflin.png",
    "Coe College": "coe.png",
    "Colby College": "colby.png",
    "Colgate University": "colgate.webp",
    "College of St Benedict": "csbsju.webp",
    "College of the Holy Cross": "holy_cross.webp",
    "College of Wooster": "wooster.webp",
    "Colorado College": "colorado.png",
    "Concordia College": "concordia.webp",
    "Connecticut College": "connecticut.webp",
    "Cornell College": "cornell.webp",
    "Covenant College": "covenant.webp",
    "Davidson College": "davidson.png",
    "Denison University": "denison.webp",
    "DePauw University": "depauw.png",
    "Dickinson College": "dickinson.webp",
    "Drew University": "drew.png",
    "Earlham College": "earlham.webp",
    "East-West University": "east_west.png",
    "Eckerd College": "eckerd.png",
    "Franklin College": "franklin.webp",
    "Franklin & Marshall College": "franklin_marshall.png",
    "Furman University": "furman.webp",
    "Gettysburg College": "gettysburg.webp",
    "Gordon College": "gordon.webp",
    "Goucher College": "goucher.png",
    "Grinnell College": "grinnell.webp",
    "Gustavus Adolphus College": "gustavus.webp",
    "Hamilton College": "hamilton.webp",
    "Hampden-Sydney College": "hampden_sydney.webp",
    "Hanover College": "hanover.webp",
    "Hartwick College": "hartwick.webp",
    "Harvey Mudd College": "harvey_mudd.png",
    "Haverford College": "haverford.png",
    "Hendrix College": "hendrix.png",
    "Hobart and William Smith College": "hws.webp",
    "Hope College": "hope.png",
    "Houghton University": "houghton.png",
    "Illinois College": "illinois.png",
    "Juniata College": "juniata.png",
    "Kalamazoo College": "kalamazoo.webp",
    "Knox College": "knox.webp",
    "Lafayette College": "lafayette.png",
    "Lake Forest College": "lake_forest.png",
    "Lane College": "lane.png",
    "Lawrence University": "lawrence.png",
    "Lewis & Clark College": "lewis_clark.webp",
    "Linfield University": "linfield.webp",
    "Luther College": "luther.webp",
    "Lycoming College": "lycoming.png",
    "Lyon College": "lyon.webp",
    "Macalester College": "macalester.png",
    "Maryville College": "maryville.png",
    "Meredith College": "meredith.webp",
    "Middlebury College": "middlebury.png",
    "Monmouth College": "monmouth.png",
    "Mount Holyoke College": "mount_holyoke.webp",
    "Muhlenberg College": "muhlenberg.png",
    "New College of Florida": "new_college.webp",
    "Oberlin College": "oberlin.png",
    "Occidental College": "occidental.png",
    "Ohio Wesleyan University": "ohio_wesleyan.png",
    "Pomona College": "pomona.webp",
    "Presbyterian College": "presbyterian.png",
    "Randolph College": "randolph.webp",
    "Randolph-Macon College": "randolph_macon.webp",
    "Reed College": "reed.png",
    "Rhodes College": "rhodes.png",
    "Roanoke College": "roanoke.png",
    "Saint Anselm College": "saint_anselm.png",
    "Saint Michael's College": "saint_michaels.webp",
    "Skidmore College": "skidmore.webp",
    "Smith College": "smith.webp",
    "Southern Virginia University": "southern_virginia.webp",
    "Southwestern University": "southwestern.png",
    "St. Lawrence University": "st_lawrence.webp",
    "St. Mary's College of Maryland": "st_marys_md.webp",
    "St. Norbert College": "st_norbert.webp",
    "St. Olaf College": "st_olaf.webp",
    "Stonehill College": "stonehill.webp",
    "Susquehanna University": "susquehanna.webp",
    "Swarthmore College": "swarthmore.webp",
    "Tougaloo College": "tougaloo.png",
    "Transylvania University": "transylvania.png",
    "Trinity College": "trinity_college.webp",
    "Trinity University": "trinity_university.png",
    "Union College (NY)": "union.png",
    "University of Mary Washington": "umw.png",
    "University of Minnesota Morris": "umn_morris.webp",
    "University of North Carolina Asheville": "unca.png",
    "University of Puget Sound": "puget_sound.png",
    "University of Richmond": "richmond.png",
    "The University of the South": "sewanee.webp",
    "University of Virginia--Wise": "uva_wise.png",
    "Ursinus College": "ursinus.webp",
    "Vassar College": "vassar.webp",
    "Virginia Wesleyan University": "virginia_wesleyan.webp",
    "Wabash College": "wabash.png",
    "Wartburg College": "wartburg.png",
    "Washington and Lee University": "wash_lee.webp",
    "Washington College": "washington.webp",
    "Washington & Jefferson College": "wash_jeff.webp",
    "Wellesley College": "wellesley.png",
    "Wesleyan University": "wesleyan.webp",
    "Westminster College (PA)": "westminster.png",
    "Wheaton College (IL)": "wheaton_il.webp",
    "Wheaton College (MA)": "wheaton_ma.webp",
    "Whitman College": "whitman.webp",
    "Willamette University": "willamette.png",
    "Williams College": "williams.webp",
    "Wittenberg University": "wittenberg.png",
    "Wofford College": "wofford.webp",
}


def slug(name: str) -> str:
    """Match collegeSlug() in index.html. Lowercase, non-alphanumerics → '-',
    collapsed and trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> None:
    entries = sorted(COLLEGE_LOGOS.items(), key=lambda kv: kv[0])
    n = len(entries)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    sheet = Image.new("RGBA", (cols * CELL, rows * CELL), (0, 0, 0, 0))
    positions: dict[str, tuple[int, int]] = {}

    for i, (name, fname) in enumerate(entries):
        path = LOGO_DIR / fname
        with Image.open(path) as im:
            im = im.convert("RGBA")
            w, h = im.size
            scale = min(CELL / w, CELL / h)
            nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            col, row = i % cols, i // cols
            x = col * CELL + (CELL - nw) // 2
            y = row * CELL + (CELL - nh) // 2
            sheet.paste(im, (x, y), im)
            positions[name] = (col, row)

    SPRITE_IMG.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(SPRITE_IMG, format="WEBP", quality=90, method=6)

    lines = [
        "/* Generated by generate_logo_sprite.py — do not edit by hand. */\n",
        ".college-logo {\n"
        "  --cs: 24px;\n"
        f"  --cols: {cols};\n"
        f"  --rows: {rows};\n"
        "  display: inline-block;\n"
        "  flex-shrink: 0;\n"
        "  vertical-align: middle;\n"
        "  width: var(--cs);\n"
        "  height: var(--cs);\n"
        "  background-image: url(logo_sprite.webp);\n"
        "  background-repeat: no-repeat;\n"
        "  background-size: calc(var(--cs) * var(--cols)) calc(var(--cs) * var(--rows));\n"
        "  background-position: calc(var(--col, 0) * var(--cs) * -1) calc(var(--row, 0) * var(--cs) * -1);\n"
        "}\n",
    ]
    for name, (col, row) in sorted(positions.items()):
        lines.append(f".cl-{slug(name)} {{ --col: {col}; --row: {row}; }}\n")

    SPRITE_CSS.write_text("".join(lines))

    print(
        f"Sprite: {SPRITE_IMG.name} {SPRITE_IMG.stat().st_size/1024:.1f} KB "
        f"({cols}×{rows} cells, {n} logos)"
    )
    print(f"CSS:    {SPRITE_CSS.name} {SPRITE_CSS.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
