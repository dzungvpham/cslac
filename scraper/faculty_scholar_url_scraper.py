import os
import ast
import asyncio
import aiohttp
import pandas as pd
from dotenv import load_dotenv
from tqdm.asyncio import tqdm
import time

# Load env
load_dotenv()
API_KEY = os.getenv("BRAVE_API_KEY")

BASE_URL = "https://api.search.brave.com/res/v1/web/search"

HEADERS = {
    "Accept": "application/json",
    "X-Subscription-Token": API_KEY,
}

INPUT_CSV = "../data/faculty_list.csv"
OUTPUT_CSV = "../data/faculty_list_with_scholar_url.csv"


# ---- Rate limiter (50 QPS) ----
class RateLimiter:
    def __init__(self, rate_per_sec):
        self.rate = rate_per_sec
        self.tokens = rate_per_sec
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        while True: # Changed from recursion to a loop
            async with self.lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.tokens += elapsed * self.rate
                if self.tokens > self.rate:
                    self.tokens = self.rate
                self.last = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return

                wait_time = (1 - self.tokens) / self.rate

            await asyncio.sleep(wait_time)


rate_limiter = RateLimiter(20)  # <= 50 QPS
semaphore = asyncio.Semaphore(100)  # max concurrent requests


# ---- Core search function ----
async def fetch_scholar(session, name, college, max_retries=5):
    """Brave-search for a Scholar profile URL. Returns the first
    scholar.google.com/citations?user=... URL, or "" if none found."""
    query = f'{name} {college} site:scholar.google.com/citations'

    params = {
        "q": query,
        "count": 3,
        "search_lang": "en",
        "country": "us",
    }

    for attempt in range(max_retries):
        await rate_limiter.acquire()

        async with semaphore:
            try:
                async with session.get(BASE_URL, headers=HEADERS, params=params, timeout=10) as resp:

                    # ---- Handle rate limiting ----
                    if resp.status == 429:
                        wait = (2 ** attempt) + (0.1 * attempt)
                        await asyncio.sleep(wait)
                        continue

                    # ---- Handle server errors ----
                    if resp.status >= 500:
                        wait = (2 ** attempt)
                        await asyncio.sleep(wait)
                        continue

                    if resp.status != 200:
                        return ""

                    data = await resp.json()
                    results = data.get("web", {}).get("results", [])

                    for r in results:
                        url = r.get("url", "")
                        if "scholar.google.com/citations?user=" in url:
                            return url

                    return ""

            except asyncio.TimeoutError:
                await asyncio.sleep(2 ** attempt)
                continue

            except aiohttp.ClientError:
                await asyncio.sleep(2 ** attempt)
                continue

    # If all retries fail
    return ""


# ---- Main pipeline ----
async def search_rows(rows):
    """Run Brave search for the given list of (name, college) tuples.
    Returns a list of URL strings in the same order."""
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_scholar(session, name, college) for name, college in rows]
        return await tqdm.gather(*tasks)


def _parse_existing_url(raw):
    """Read a `google_scholar` cell from the old CSV. Handles two formats:
    - Old: a Python list literal like "['url1', 'url2', ...]" → returns first URL
    - New: a plain URL string → returns it
    Returns "" if missing/empty/unparseable."""
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


def main():
    df_new = pd.read_csv(INPUT_CSV)

    # Build lookup of existing URLs from the prior output, if any.
    existing: dict[tuple[str, str], str] = {}
    try:
        df_old = pd.read_csv(OUTPUT_CSV)
        for _, r in df_old.iterrows():
            url = _parse_existing_url(r.get("google_scholar"))
            if url:
                existing[(r["name"], r["college"])] = url
    except FileNotFoundError:
        pass

    # Partition: rows that already have a URL vs rows we need to search.
    needs_search: list[tuple[str, str]] = []
    for _, r in df_new.iterrows():
        key = (r["name"], r["college"])
        if key not in existing:
            needs_search.append(key)

    print(f"Reusing {len(existing)} existing URLs (rows already in {OUTPUT_CSV})")
    print(f"Brave-searching {len(needs_search)} new rows")

    if needs_search:
        results = asyncio.run(search_rows(needs_search))
        for key, url in zip(needs_search, results):
            existing[key] = url

    df_new["google_scholar"] = [
        existing.get((r["name"], r["college"]), "")
        for _, r in df_new.iterrows()
    ]
    df_new.to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {len(df_new)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
