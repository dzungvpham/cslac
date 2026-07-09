"""Selenium-verify faculty that a refresh DROPPED, against each college's live
department listing, to separate scraper misses (still a real card on the page ->
RESTORE) from genuine departures (absent -> let go).

Departed faculty leave lingering individual profile pages and cached third-party
sites, so ONLY the rendered department LISTING is authoritative — this script
renders it with Selenium. Read-only.

Usage (from scraper/):
    python refresh_verify_drops.py                 # verify all drops
    python refresh_verify_drops.py "Denison,Reed"  # only these colleges
"""
import csv, io, re, subprocess, sys, warnings
warnings.filterwarnings("ignore")
from bs4 import BeautifulSoup
from faculty_scraper import create_selenium_driver, retry_with_selenium, TITLE_RE

def git_head(path):
    out = subprocess.run(["git", "show", f"HEAD:{path}"], cwd="..",
                         capture_output=True, text=True, check=True)
    return list(csv.DictReader(io.StringIO(out.stdout)))

old = git_head("data/faculty_list.csv")
with open("../data/faculty_list.csv", newline="") as f:
    new = list(csv.DictReader(f))
links = {r["Name"]: r["Faculty Link"] for r in csv.DictReader(open("../data/colleges.csv"))}

old_k = {(r["name"], r["college"]) for r in old}
new_k = {(r["name"], r["college"]) for r in new}
drops = sorted(old_k - new_k, key=lambda x: (x[1], x[0]))

only = set(a.strip() for a in sys.argv[1].split(",")) if len(sys.argv) > 1 else None
by_col = {}
for n, c in drops:
    if only and not any(o.lower() in c.lower() for o in only):
        continue
    by_col.setdefault(c, []).append(n)

def as_card(html, name):
    """CARD if the surname sits in a small block that also has a title."""
    soup = BeautifulSoup(html, "html.parser")
    surname = name.split()[-1]
    for tn in soup.find_all(string=re.compile(r"\b"+re.escape(surname)+r"\b", re.I)):
        cur = tn.parent
        for _ in range(5):
            if cur is None: break
            t = cur.get_text(" ", strip=True)
            if TITLE_RE.search(t or "") and all(p.lower() in t.lower()
                                                for p in name.split() if len(p) > 2):
                return True
            cur = cur.parent
    return False

d = create_selenium_driver()
restore, letgo = [], []
for col in sorted(by_col):
    try:
        html = retry_with_selenium(d, links.get(col, "")) or ""
    except Exception:
        html = ""
    tag = f"{len(html)//1000}KB" if html else "FETCH-FAIL"
    print(f"\n{col} [{tag}]")
    for n in by_col[col]:
        if html and as_card(html, n):
            restore.append((n, col)); v = "RESTORE (real card on listing = scraper miss)"
        elif not html:
            letgo.append((n, col)); v = "?? fetch failed — recheck manually"
        else:
            letgo.append((n, col)); v = "depart (absent from listing)"
        print(f"    {n:26} -> {v}")
d.quit()

print("\n" + "=" * 60)
print(f"RESTORE (scraper misses): {len(restore)}")
for n, c in restore: print(f"   + {c}: {n}")
print(f"Let go (departures): {len(letgo)}")
