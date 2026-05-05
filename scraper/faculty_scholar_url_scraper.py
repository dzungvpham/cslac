import os
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
                        return []

                    data = await resp.json()
                    results = data.get("web", {}).get("results", [])

                    links = []
                    for r in results:
                        url = r.get("url", "")
                        if "scholar.google.com/citations?user=" in url:
                            links.append(url)

                    return links

            except asyncio.TimeoutError:
                await asyncio.sleep(2 ** attempt)
                continue

            except aiohttp.ClientError:
                await asyncio.sleep(2 ** attempt)
                continue

    # If all retries fail
    return []


# ---- Main pipeline ----
async def process_dataframe(df):
    async with aiohttp.ClientSession() as session:
        # 1. Create a list of coroutines (not tasks yet)
        tasks = [
            fetch_scholar(session, row["name"], row["college"]) 
            for _, row in df.iterrows()
        ]

        # 2. Use tqdm.gather to track progress and keep order
        # This returns results in the exact same order as the 'tasks' list
        results = await tqdm.gather(*tasks)

    return results


def main():
    df = pd.read_csv("../data/faculty_list.csv")

    results = asyncio.run(process_dataframe(df))

    df["google_scholar"] = results
    df.to_csv("../data/faculty_list_with_scholar_url.csv", index=False)

    print("Finished.")


if __name__ == "__main__":
    main()