"""Two-pass Google Scholar profile scraper.

Pass 1 (automatic): for each faculty row with no `scholar_match_status`, fetch
their Scholar profile via the Decodo proxy and classify the result as one of:
  matched, matched_name, matched_college, no_match, fetch_error, no_url

Manual step (you, in the output CSV):
  - For `fetch_error` rows whose URL is stale: replace the URL in
    `google_scholar` and set `scholar_match_status` to `rescrape`.
  - For `matched_name` / `matched_college` / `no_match` rows you've eyeballed
    and confirmed: set `scholar_match_status` to `manual_approved`.
  - Anything left untouched stays as-is on the next run.

Pass 2 (automatic): re-running the script picks up any row whose status is
empty *or* `rescrape` and re-fetches it. `manual_approved` rows are never
touched again.
"""

import os
import re
import ast
import random
import shutil
import threading
import unicodedata
import concurrent.futures
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

INPUT_CSV = "../data/faculty_list_with_scholar_url.csv"
OUTPUT_CSV = "../data/faculty_list_with_verified_profile.csv"

PROXY_URL = (
    f"http://{os.environ['DECODO_USERNAME']}:{os.environ['DECODO_PASSWORD']}"
    f"@{os.environ['DECODO_HOST']}:{os.environ['DECODO_PORT']}"
)
PROXIES = {"http": PROXY_URL, "https": PROXY_URL}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
]

REQUEST_TIMEOUT = 60
N_WORKERS = 8
# Each retry rotates to a fresh Decodo exit IP. Roughly half of exit IPs hit
# Scholar's "show you're not a robot" soft-block, so we need a generous retry
# budget to make all-fail vanishingly unlikely (8 retries → ~0.4%).
MAX_RETRIES = 8
CHECKPOINT_EVERY = 25  # rewrite output CSV after this many completions

# Statuses that mean "do not touch this row" on subsequent runs.
TERMINAL_STATUSES = {
    "matched", "matched_name", "matched_college",
    "no_match", "fetch_error", "no_url",
    "manual_approved",
}
# Statuses that should be (re)processed when the script runs.
PROCESSABLE_STATUSES = {"", "rescrape"}

VERIFIED_COLUMNS = [
    "verified_affiliation",
    "scholar_match_status",
    "scholar_citedby",
    "scholar_citedby5y",
    "scholar_hindex",
    "scholar_hindex5y",
    "scholar_i10index",
    "scholar_i10index5y",
    "scholar_interests",
    "scholar_cites_per_year",
]


def _make_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def _is_subsequence(s: str, t: str) -> bool:
    it = iter(t)
    return all(c in it for c in s)


def _match_level(name: str, college: str, scholar_name: str, affiliation: str) -> str:
    n1, n2 = _normalize(name), _normalize(scholar_name)
    aff = _normalize(affiliation)
    col = _normalize(college)
    name_match = bool(n1 and n2 and (_is_subsequence(n1, n2) or _is_subsequence(n2, n1)))
    college_match = bool(col and aff and (_is_subsequence(col, aff) or _is_subsequence(aff, col)))
    if name_match and college_match:
        return "matched"
    if name_match:
        return "matched_name"
    if college_match:
        return "matched_college"
    return "no_match"


def _extract_scholar_id(url: str) -> str | None:
    m = re.search(r"user=([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def _parse_url(raw) -> str:
    """Read a `google_scholar` cell. Handles two formats for back-compat:
    plain URL string (current) and Python list literal "[url, ...]" (legacy)."""
    if pd.isna(raw):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if s.startswith("["):
        try:
            urls = ast.literal_eval(s)
            return urls[0] if urls else ""
        except Exception:
            return ""
    return s


_SOFT_BLOCK_MARKERS = (
    "show you&#39;re not a robot", "show you're not a robot",
    "verify that you&#39;re not a robot", "verify that you're not a robot",
)


def _is_soft_block(html: str) -> bool:
    return any(m in html for m in _SOFT_BLOCK_MARKERS)


def _fetch_html(url: str) -> str | None:
    """Fetch a Scholar URL through the Decodo rotating proxy. Each retry gets
    a fresh exit IP and a fresh random User-Agent. Returns the HTML on a clean
    200, or None for any failure (404, soft-block, timeout, etc.)."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(
                url,
                headers=_make_headers(),
                proxies=PROXIES,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if r.status_code == 200 and not _is_soft_block(r.text):
                return r.text
        except requests.RequestException:
            pass
        # Cap backoff at 4s — the bottleneck is rotating past bad exit IPs,
        # not waiting out a rate limit, so long sleeps don't help.
        time.sleep(min(2 ** attempt, 4) + random.uniform(0, 1))
    return None


def _parse_profile(html: str) -> dict | None:
    """Parse a Scholar profile page. Returns None if the page has no profile
    (e.g. invalid Scholar ID returning an empty 200)."""
    soup = BeautifulSoup(html, "html.parser")
    name_el = soup.find(id="gsc_prf_in")
    if not name_el or not name_el.get_text(strip=True):
        return None

    aff_els = soup.select(".gsc_prf_il")
    affiliation = aff_els[0].get_text(strip=True) if aff_els else ""

    interests = [a.get_text(strip=True) for a in soup.select("#gsc_prf_int .gsc_prf_inta")]

    stats: dict[str, str] = {}
    for tr in soup.select("#gsc_rsb_st tbody tr"):
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue
        label = cells[0].get_text(strip=True).lower()
        all_time, five_y = cells[1].get_text(strip=True), cells[2].get_text(strip=True)
        if "citation" in label:
            stats["citedby"], stats["citedby5y"] = all_time, five_y
        elif "h-index" in label:
            stats["hindex"], stats["hindex5y"] = all_time, five_y
        elif "i10-index" in label:
            stats["i10index"], stats["i10index5y"] = all_time, five_y

    years = [s.get_text(strip=True) for s in soup.select(".gsc_g_t")]
    cites = [s.get_text(strip=True) for s in soup.select(".gsc_g_al")]
    cites_per_year = {y: int(c) for y, c in zip(years, cites) if c.isdigit()}

    return {
        "name": name_el.get_text(strip=True),
        "affiliation": affiliation,
        "interests": interests,
        "citedby": stats.get("citedby", ""),
        "citedby5y": stats.get("citedby5y", ""),
        "hindex": stats.get("hindex", ""),
        "hindex5y": stats.get("hindex5y", ""),
        "i10index": stats.get("i10index", ""),
        "i10index5y": stats.get("i10index5y", ""),
        "cites_per_year": cites_per_year,
    }


def _empty_verified(status: str) -> dict:
    return {
        "verified_affiliation": "",
        "scholar_match_status": status,
        "scholar_citedby": "",
        "scholar_citedby5y": "",
        "scholar_hindex": "",
        "scholar_hindex5y": "",
        "scholar_i10index": "",
        "scholar_i10index5y": "",
        "scholar_interests": "",
        "scholar_cites_per_year": "",
    }


def _process_row(name: str, college: str, raw_url) -> dict:
    """Fetch and classify one row. Returns the verified_* fields only."""
    url = _parse_url(raw_url)
    if not url:
        return _empty_verified("no_url")

    scholar_id = _extract_scholar_id(url)
    if not scholar_id:
        return _empty_verified("no_url")

    full_url = f"https://scholar.google.com/citations?hl=en&user={scholar_id}"
    html = _fetch_html(full_url)
    if html is None:
        return _empty_verified("fetch_error")

    profile = _parse_profile(html)
    if profile is None:
        return _empty_verified("no_match")

    status = _match_level(name, college, profile["name"], profile["affiliation"])
    # Partial matches (matched_name, matched_college) and no_match are
    # treated as unverified — citation data is unreliable until a human
    # promotes them to manual_approved.
    if status != "matched":
        result = _empty_verified(status)
        if status != "no_match":
            result["verified_affiliation"] = profile["affiliation"]
        return result
    return {
        "verified_affiliation": profile["affiliation"],
        "scholar_match_status": status,
        "scholar_citedby": profile["citedby"],
        "scholar_citedby5y": profile["citedby5y"],
        "scholar_hindex": profile["hindex"],
        "scholar_hindex5y": profile["hindex5y"],
        "scholar_i10index": profile["i10index"],
        "scholar_i10index5y": profile["i10index5y"],
        "scholar_interests": "; ".join(profile["interests"]),
        "scholar_cites_per_year": str(profile["cites_per_year"]),
    }


def _load_or_init_output(input_path: str, output_path: str) -> pd.DataFrame:
    """Load the output CSV if it exists. Otherwise seed it from the input CSV
    with empty verified_* columns. If the output exists but the input has new
    rows (matched on name+college), the new rows are appended with empty
    status so the next run picks them up."""
    input_df = pd.read_csv(input_path)
    if not os.path.exists(output_path):
        out = input_df.copy()
        for col in VERIFIED_COLUMNS:
            out[col] = ""
        return out

    out = pd.read_csv(output_path)
    for col in VERIFIED_COLUMNS:
        if col not in out.columns:
            out[col] = ""
        # Force object dtype: empty cells get inferred as float64/NaN, which
        # then refuses string/int assignments during pass 2 rescrapes.
        out[col] = out[col].astype(object).where(out[col].notna(), "")
    out["scholar_match_status"] = out["scholar_match_status"].astype(str)

    existing = set(zip(out["name"], out["college"]))
    new_rows = input_df[~input_df.apply(
        lambda r: (r["name"], r["college"]) in existing, axis=1
    )]
    if len(new_rows):
        added = new_rows.copy()
        for col in VERIFIED_COLUMNS:
            added[col] = ""
        out = pd.concat([out, added], ignore_index=True)
        print(f"{len(added)} new row(s) added from input CSV")
    return out


def _atomic_write(df: pd.DataFrame, path: str) -> None:
    tmp = f"{path}.tmp"
    df.to_csv(tmp, index=False)
    shutil.move(tmp, path)


def main():
    df = _load_or_init_output(INPUT_CSV, OUTPUT_CSV)
    df["scholar_match_status"] = df["scholar_match_status"].fillna("").astype(str)

    todo_idx = [i for i, s in df["scholar_match_status"].items()
                if s.strip() in PROCESSABLE_STATUSES]

    if not todo_idx:
        print("Nothing to process — all rows have terminal statuses.")
        _atomic_write(df, OUTPUT_CSV)
        return

    status_counts = df.loc[todo_idx, "scholar_match_status"].value_counts(dropna=False)
    summary = ", ".join(
        f"{(s or 'empty')}={n}" for s, n in status_counts.items()
    )
    print(f"{len(todo_idx)} row(s) to process ({summary}); "
          f"{len(df) - len(todo_idx)} row(s) skipped (terminal status).")

    write_lock = threading.Lock()
    completed_since_checkpoint = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
        future_to_idx = {
            executor.submit(
                _process_row,
                df.at[i, "name"],
                df.at[i, "college"],
                df.at[i, "google_scholar"],
            ): i
            for i in todo_idx
        }
        for future in tqdm(
            concurrent.futures.as_completed(future_to_idx),
            total=len(future_to_idx),
            desc="Verifying Scholar profiles",
        ):
            i = future_to_idx[future]
            try:
                result = future.result()
            except Exception as e:
                print(f"\nError on row {i} "
                      f"({df.at[i, 'name']} / {df.at[i, 'college']}): {e}")
                result = _empty_verified("fetch_error")

            with write_lock:
                for col, val in result.items():
                    df.at[i, col] = val
                completed_since_checkpoint += 1
                if completed_since_checkpoint >= CHECKPOINT_EVERY:
                    _atomic_write(df, OUTPUT_CSV)
                    completed_since_checkpoint = 0

    _atomic_write(df, OUTPUT_CSV)
    print("Done. Output written to", OUTPUT_CSV)


if __name__ == "__main__":
    main()
