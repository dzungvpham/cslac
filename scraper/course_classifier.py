"""Classify each unique scraped course title into a CS subfield (or a meta
category) and write a ``category`` column back into every CSV under
``data/course_schedule/``.

The label space is the 32 CS subfields (mirrors ``CS_SUBFIELD_NAMES`` in
``faculty_site_analysis.py``, so the dashboard's existing subfield filter chips
can gate course visibility) plus four meta categories:

  * ``Core``    — generic, essential foundation courses (intro programming,
                  data structures, discrete math, computer organization, and
                  the standard algorithms course).
  * ``Misc``    — not a real lecture course (independent study, research,
                  thesis, capstone, internship, seminar, standalone lab).
  * ``Other``   — a computing/CS elective that fits none of the 32 subfields.
  * ``Unknown`` — not a Computer Science course at all (e.g. Calculus, Linear
                  Algebra, Statistics, Physics — math/other-department courses
                  that get swept up by cross-listings).

Classification is done by the ``claude`` CLI using Claude Sonnet 4.6 at low
effort. Titles are deduplicated across all colleges and terms by a normalized
key (NFKD + strip accents + collapse whitespace + lowercase) so each distinct
title is classified exactly once, then sent in batches of 50 to amortize the
fixed per-call context overhead. Results are cached in
``data/course_classification.json`` (keyed by the normalized title), making the
run resumable: a re-run only classifies titles missing from the cache and
re-writes the ``category`` column in every CSV.

Calls that never succeed (after in-call backoff and a few retry rounds) are
left *unclassified* — never fabricated — and reported, so re-running picks them
up.

Usage (from the ``scraper/`` directory)::

    python course_classifier.py                 # classify new titles, write CSVs
    python course_classifier.py --overwrite     # reclassify everything
    python course_classifier.py --no-write      # update cache only
"""

import argparse
import csv
import json
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
COURSE_DIR = ROOT / "data" / "course_schedule"
CACHE_PATH = ROOT / "data" / "course_classification.json"

# The 32 CS subfields — must stay in lock-step with CS_SUBFIELD_NAMES in
# scraper/faculty_site_analysis.py and CS_SUBFIELDS in docs/app.js so the
# category strings match the dashboard's filter-chip keys exactly.
CS_SUBFIELD_NAMES = [
    "Artificial intelligence", "Computer vision", "Machine learning",
    "Natural language processing", "Data science", "Information retrieval",
    "Computer architecture", "Computer networks", "Distributed systems",
    "Computer security & privacy", "Databases", "Design automation",
    "Embedded & real-time systems", "High-performance computing",
    "Mobile computing", "Measurement & performance analysis",
    "Operating systems", "Programming languages", "Software engineering",
    "Algorithms & complexity", "Quantum computing", "Cryptography",
    "Logic & verification", "Computational bio & bioinformatics",
    "Computer graphics", "Computer science education",
    "Economics & computation", "Human-computer interaction", "Robotics",
    "Visualization", "Computational social science", "Games & interactive art",
]
META_CATEGORIES = ["Core", "Misc", "Other", "Unknown"]
ALL_CATEGORIES = CS_SUBFIELD_NAMES + META_CATEGORIES

# Canonicalize a model-returned label back to one of ALL_CATEGORIES. Exact
# (case-insensitive) match plus the dashboard's short labels as aliases, so a
# stray "ML" or "HCI" still resolves.
_CANON = {c.lower(): c for c in ALL_CATEGORIES}
for _alias, _full in {
    "algo": "Algorithms & complexity", "ai": "Artificial intelligence",
    "comp. bio": "Computational bio & bioinformatics",
    "comp. social science": "Computational social science",
    "architecture": "Computer architecture", "graphics": "Computer graphics",
    "networks": "Computer networks", "cs ed": "Computer science education",
    "security": "Computer security & privacy", "cv": "Computer vision",
    "db": "Databases", "distributed": "Distributed systems",
    "games & art": "Games & interactive art",
    "embedded & real-time": "Embedded & real-time systems",
    "hpc": "High-performance computing", "hci": "Human-computer interaction",
    "ir": "Information retrieval", "ml": "Machine learning",
    "measurement": "Measurement & performance analysis",
    "mobicomp": "Mobile computing", "nlp": "Natural language processing",
    "os": "Operating systems", "pl": "Programming languages",
    "quantum": "Quantum computing", "swe": "Software engineering",
    "viz": "Visualization",
}.items():
    _CANON.setdefault(_alias, _full)

MODEL = "claude-sonnet-4-6"
EFFORT = "low"
# Disallowing the standard tools drops their definitions from the request,
# roughly halving the fixed per-call context (measured ~11.8k -> ~5.1k tokens).
DISALLOWED_TOOLS = (
    "Task Bash Glob Grep Read Edit Write NotebookEdit "
    "WebFetch WebSearch TodoWrite BashOutput KillBash"
)
SUBPROCESS_TIMEOUT = 240
CALL_ATTEMPTS = 5          # per-call retries (rate-limit / transient backoff)
BACKOFF_BASE = 5.0         # seconds; doubles each retry, capped at BACKOFF_MAX
BACKOFF_MAX = 90.0

SYSTEM_PROMPT = """\
You classify U.S. college course titles for a Computer Science dataset. For
each numbered title you are given, output the single best-fitting category,
using the EXACT strings below.

Meta categories:
- "Core": generic, essential CS foundation courses every major takes — intro
  programming (CS1/CS2/"Computer Science I/II"), data structures, discrete
  mathematics, computer organization, and the standard required algorithms
  course ("Algorithms", "Analysis of Algorithms", "Algorithm Design &
  Analysis"). Use Core only for these foundational courses, never for an
  advanced or specialized elective — "Advanced/Randomized/Applied Algorithms",
  a domain-specific "Algorithms for/on X", or "Theory of Computation" /
  "Computability" / "Automata" are NOT Core.
- "Misc": not a real lecture course — independent study, directed or
  undergraduate research, thesis, capstone, internship, practicum, seminar,
  colloquium, tutorial, or a standalone lab/recitation.
- "Other": a genuine COMPUTING/CS elective that fits none of the subfields
  below (e.g. "Computers and Society", "Computer Ethics", a broad "Special
  Topics in Computer Science", general "Topics in Computing").
- "Unknown": NOT a computer-science course — a math, statistics, science, or
  other-department course that was swept in by cross-listing (e.g. "Calculus",
  "Linear Algebra", "Probability", "Statistics", "General Physics",
  "Microeconomics", "Technical Writing").

Most titles you see ARE computer science and fit a subfield or Core — reach for
"Other" only when it is clearly a CS elective with no matching subfield, and
"Unknown" only when the subject is clearly not CS.

Subfields (prefer the most specific match):
Artificial intelligence; Computer vision; Machine learning; Natural language
processing; Data science; Information retrieval; Computer architecture;
Computer networks; Distributed systems; Computer security & privacy; Databases;
Design automation; Embedded & real-time systems; High-performance computing;
Mobile computing; Measurement & performance analysis; Operating systems;
Programming languages; Software engineering; Algorithms & complexity; Quantum
computing; Cryptography; Logic & verification; Computational bio &
bioinformatics; Computer graphics; Computer science education; Economics &
computation; Human-computer interaction; Robotics; Visualization; Computational
social science; Games & interactive art.

Guidance and examples (Title -> Category):
Intro to Computer Science / Programming I / Programming II -> Core; Data
Structures -> Core; Discrete Mathematics -> Core; Computer Organization -> Core;
Algorithms / Analysis of Algorithms / Algorithm Design and Analysis -> Core.
Advanced Algorithms / Randomized Algorithms / Applied Algorithms / Algorithms
for Data Science / Algorithms paired with a specialized topic (e.g. "Algorithms
and Visualization", "Algorithms and Concurrency") -> Algorithms & complexity;
Theory of Computation / Computability / Automata / Computational Complexity ->
Algorithms & complexity.
Artificial Intelligence -> Artificial intelligence; Machine Learning / Deep
Learning -> Machine learning; Computer Vision / Image Processing -> Computer
vision; Natural Language Processing -> Natural language processing; Data Science
/ Data Mining -> Data science; Information Retrieval / Recommender Systems ->
Information retrieval.
Operating Systems -> Operating systems; Computer Networks / Networking ->
Computer networks; Distributed Systems / Cloud Computing -> Distributed
systems; Computer Architecture -> Computer architecture; Embedded Systems /
Internet of Things -> Embedded & real-time systems; Parallel / High-Performance
Computing -> High-performance computing; Mobile App Development -> Mobile
computing; Performance Analysis -> Measurement & performance analysis.
Database Systems -> Databases; Programming Languages / Compilers -> Programming
languages; Software Engineering / Web Development / Software Design -> Software
engineering; Computer Security / Network Security -> Computer security &
privacy; Cryptography -> Cryptography; Formal Methods / Logic in CS -> Logic &
verification; VLSI / Digital Design Automation -> Design automation.
Quantum Computing -> Quantum computing; Bioinformatics / Computational Biology
-> Computational bio & bioinformatics; Computer Graphics -> Computer graphics;
Human-Computer Interaction / User Interface Design -> Human-computer
interaction; Robotics -> Robotics; Data / Information Visualization ->
Visualization; Computational Social Science / Social Network Analysis ->
Computational social science; Game Design / Game Development -> Games &
interactive art; Teaching of Computer Science -> Computer science education;
Algorithmic Game Theory / Mechanism Design -> Economics & computation.
Senior Thesis / Independent Study / CS Research / Internship / Capstone /
Seminar / Colloquium -> Misc.
Computers and Society / Computer Ethics / Special Topics in CS -> Other.
Calculus / Linear Algebra / Statistics / General Physics -> Unknown.

Output ONLY a JSON object mapping each title's number (as a string) to its
category string. No markdown, no prose, no trailing commentary."""


def norm_name(s: str) -> str:
    """Normalization key for deduping/caching a course title (NFKD, strip
    accents, collapse whitespace, lowercase, strip)."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def clean_name(s: str) -> str:
    return (s or "").strip().strip('"').strip()


def load_cache() -> dict:
    if CACHE_PATH.is_file():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"WARNING: cache at {CACHE_PATH} unreadable ({e}); starting fresh.")
    return {}


_cache_lock = threading.Lock()


def save_cache(cache: dict) -> None:
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=0, sort_keys=True), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def canonicalize(raw):
    if not isinstance(raw, str):
        return None
    key = raw.strip().strip(".\"'").lower()
    return _CANON.get(key)


def _extract_json_obj(text: str):
    """Pull a JSON object out of the model's text result (tolerates ``` fences)."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    i, j = text.find("{"), text.rfind("}")
    if i == -1 or j == -1 or j < i:
        return None
    try:
        return json.loads(text[i : j + 1])
    except json.JSONDecodeError:
        return None


_errors: list[str] = []
_errors_lock = threading.Lock()


def _record_error(msg: str) -> None:
    with _errors_lock:
        if len(_errors) < 8:
            _errors.append(msg)


def call_claude(user_prompt: str):
    """One claude CLI call with retry/backoff. Returns the parsed
    {index: label} dict, or None if every attempt failed."""
    cmd = [
        "claude", "-p", user_prompt,
        "--model", MODEL,
        "--effort", EFFORT,
        "--output-format", "json",
        "--system-prompt", SYSTEM_PROMPT,
        "--disallowedTools", DISALLOWED_TOOLS,
        "--strict-mcp-config",  # skip MCP-server startup (faster, avoids stalls)
    ]
    delay = BACKOFF_BASE
    last = "unknown error"
    for attempt in range(CALL_ATTEMPTS):
        try:
            # Run from a scratch dir so the repo's CLAUDE.md isn't auto-loaded.
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=SUBPROCESS_TIMEOUT, cwd=tempfile.gettempdir(),
            )
        except subprocess.TimeoutExpired:
            last = "timeout"
            proc = None
        except FileNotFoundError:
            sys.exit("ERROR: `claude` CLI not found on PATH.")

        if proc is not None:
            if proc.returncode == 0:
                try:
                    env = json.loads(proc.stdout)
                except json.JSONDecodeError:
                    env = None
                if env is not None and not env.get("is_error"):
                    obj = _extract_json_obj(env.get("result", "") or "")
                    if obj is not None:
                        return obj
                    last = "unparseable model result"
                else:
                    last = ((env or {}).get("result")
                            or proc.stderr.strip()[:160] or "error envelope")
            else:
                last = proc.stderr.strip()[:160] or f"exit {proc.returncode}"

        if attempt < CALL_ATTEMPTS - 1:
            time.sleep(delay + random.uniform(0, delay * 0.3))
            delay = min(delay * 2, BACKOFF_MAX)

    _record_error(last)
    return None


def classify_batch(batch):
    """batch = [(norm_key, display_title), ...]. Returns {norm_key: category}."""
    lines = "\n".join(f"{i + 1}. {title}" for i, (_, title) in enumerate(batch))
    prompt = f"Classify each course title:\n{lines}"
    obj = call_claude(prompt)
    out = {}
    if not isinstance(obj, dict):
        return out
    for i, (nk, _) in enumerate(batch):
        canon = canonicalize(obj.get(str(i + 1)))
        if canon:
            out[nk] = canon
    return out


def collect_titles():
    """Scan every CSV. Returns:

      titles  : {norm_key: display_title}  — one display string per unique title
      csv_meta: [csv_path, ...]            — non-empty CSVs to rewrite
    """
    titles: dict[str, str] = {}
    csv_meta = []
    for csv_path in sorted(COURSE_DIR.glob("*.csv")):
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        csv_meta.append(csv_path)
        for r in rows:
            name = clean_name(r.get("course_name", ""))
            if not name:
                continue
            titles.setdefault(norm_name(name), name)
    return titles, csv_meta


def chunked(seq, size):
    for x in range(0, len(seq), size):
        yield seq[x : x + size]


def write_csvs(csv_meta, cache):
    """Add/refresh the `category` column on every CSV from the cache."""
    n = 0
    for csv_path in csv_meta:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        if "category" not in fieldnames:
            fieldnames.append("category")
        for r in rows:
            name = clean_name(r.get("course_name", ""))
            r["category"] = cache.get(norm_name(name), "") if name else ""
        tmp = csv_path.with_suffix(".csv.tmp")
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(csv_path)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--overwrite", action="store_true",
                    help="reclassify every title, ignoring the cache")
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel claude calls (default 4; keep low to avoid "
                         "rate limits)")
    ap.add_argument("--batch-size", type=int, default=50,
                    help="titles per claude call (default 50)")
    ap.add_argument("--max-rounds", type=int, default=3,
                    help="retry rounds for titles that failed to classify")
    ap.add_argument("--no-write", action="store_true",
                    help="update the cache but do not touch the CSVs")
    args = ap.parse_args()

    titles, csv_meta = collect_titles()
    if not titles:
        sys.exit("No course titles found (check the data dir).")

    cache = {} if args.overwrite else load_cache()
    # Drop any cached labels that aren't valid categories (e.g. from an older
    # taxonomy) so they get reclassified.
    cache = {k: v for k, v in cache.items() if v in ALL_CATEGORIES}
    todo = [nk for nk in titles if nk not in cache]
    print(f"{len(titles)} unique titles across {len(csv_meta)} CSVs; "
          f"{len(todo)} to classify ({len(titles) - len(todo)} cached).")

    rnd = 0
    while todo and rnd < args.max_rounds:
        rnd += 1
        batches = [[(nk, titles[nk]) for nk in chunk]
                   for chunk in chunked(todo, args.batch_size)]
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(classify_batch, b) for b in batches]
            for fut in tqdm(as_completed(futs), total=len(futs),
                            desc=f"round {rnd} ({len(batches)} batches)"):
                res = fut.result()
                if res:
                    with _cache_lock:
                        cache.update(res)
                done += 1
                if done % 5 == 0:
                    save_cache(cache)
        save_cache(cache)
        todo = [nk for nk in titles if nk not in cache]
        if todo:
            print(f"  {len(todo)} titles still unclassified after round {rnd}.")

    save_cache(cache)

    dist = Counter(cache[nk] for nk in titles if nk in cache)
    print("\nCategory distribution (unique titles):")
    for cat, n in dist.most_common():
        print(f"  {n:5d}  {cat}")

    if todo:
        print(f"\n{len(todo)} titles could NOT be classified (left blank — re-run "
              f"to retry). Sample errors:")
        for e in _errors[:5]:
            print(f"  - {e}")
        print("  e.g. titles:", ", ".join(titles[nk] for nk in todo[:8]))

    if args.no_write:
        print("\n--no-write: cache updated, CSVs left untouched.")
        return
    n = write_csvs(csv_meta, cache)
    print(f"\nWrote `category` column into {n} CSV(s).")


if __name__ == "__main__":
    main()
