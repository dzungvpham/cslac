"""Validate a freshly re-scraped data/faculty_list.csv against the committed
baseline (git HEAD) during a full refresh.

Flags colleges whose faculty count collapsed (broken scraper, not a real
departure) and lists added / dropped / moved faculty so you can reconcile.
Read-only. Run from scraper/ after `python faculty_scraper.py`.
"""
import csv, io, subprocess, collections, sys

NEW = "../data/faculty_list.csv"

def load_rows(text):
    return list(csv.DictReader(io.StringIO(text)))

def git_head(path="data/faculty_list.csv"):
    try:
        out = subprocess.run(["git", "show", f"HEAD:{path}"],
                             cwd="..", capture_output=True, text=True, check=True)
        return out.stdout
    except subprocess.CalledProcessError as e:
        sys.exit(f"could not read baseline from git HEAD: {e.stderr}")

old = load_rows(git_head())
with open(NEW, newline="") as f:
    new = list(csv.DictReader(f))

old_by = collections.defaultdict(list); new_by = collections.defaultdict(list)
for r in old: old_by[r["college"]].append(r["name"])
for r in new: new_by[r["college"]].append(r["name"])
cols = sorted(set(old_by) | set(new_by))

print(f"TOTAL: {len(old)} -> {len(new)} rows ({len(old_by)} -> {len(new_by)} colleges)\n")

print("=== SUSPICIOUS DROPS (likely broken scraper) ===")
susp = []
for c in cols:
    o, n = len(old_by[c]), len(new_by.get(c, []))
    if o >= 4 and n <= o * 0.5 or (o >= 1 and n == 0):
        susp.append((c, o, n))
for c, o, n in sorted(susp, key=lambda x: x[2]-x[1]):
    print(f"  ⚠️  {c}: {o} -> {n}")
print("  none" if not susp else "")

old_k = {(r["name"], r["college"]) for r in old}
new_k = {(r["name"], r["college"]) for r in new}
added, dropped = new_k - old_k, old_k - new_k

# moves: same name, different college
o_name = collections.defaultdict(set); n_name = collections.defaultdict(set)
for nm, c in old_k: o_name[nm].add(c)
for nm, c in new_k: n_name[nm].add(c)
moved = [(nm, sorted(o_name[nm]-n_name[nm])[0], c) for nm, c in added
         if nm in o_name and c not in o_name[nm] and (o_name[nm]-n_name[nm])]

print(f"\n=== ADDED ({len(added)}) ===")
mv_to = {(nm, c) for nm, _, c in moved}
for nm, c in sorted(added, key=lambda x: (x[1], x[0])):
    tag = f"  (MOVED from {[f for n,f,t in moved if n==nm and t==c][0]})" if (nm, c) in mv_to else ""
    print(f"  + {c}: {nm}{tag}")
print(f"\n=== DROPPED ({len(dropped)}) ===")
for nm, c in sorted(dropped, key=lambda x: (x[1], x[0])):
    print(f"  - {c}: {nm}")

print(f"\nSUMMARY: added {len(added)}, dropped {len(dropped)}, moved {len(moved)}, "
      f"suspicious colleges {len(susp)}")
if susp:
    print(">>> diagnose suspicious colleges (requests+Selenium probe) before proceeding <<<")
