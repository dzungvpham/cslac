import pandas as pd
import time
import threading
import concurrent.futures
import requests
from queue import Queue
from bs4 import BeautifulSoup
from faculty_scraper import create_selenium_driver, google_search_url
from pathlib import Path
from tqdm import tqdm

DATA_PATH = "../data/faculty_list.csv"
BASE_PATH = "../data/faculty_websites"

N_SELENIUM_WORKERS = 8
N_TOTAL_WORKERS = 32
REQUEST_TIMEOUT = 15
SELENIUM_SLEEP = 5

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# JS app root containers — page content is injected here at runtime
JS_ROOT_SELECTORS = ["div#root", "div#app", "div#__next", "div#gatsby-focus-wrapper"]

Path(BASE_PATH).mkdir(parents=True, exist_ok=True)

faculty = pd.read_csv(DATA_PATH)
faculty_with_urls = faculty[pd.notna(faculty["url"])].copy()
rows = list(faculty_with_urls.iterrows())

print(f"Starting {N_SELENIUM_WORKERS} Selenium drivers...")
driver_pool = Queue()
for _ in range(N_SELENIUM_WORKERS):
    driver_pool.put(create_selenium_driver())

url_updates = {}
url_updates_lock = threading.Lock()


def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    if soup.body is None:
        return None, soup
    return soup.body.get_text("\n", strip=True), soup


def needs_js(html):
    """Return True if the raw HTML looks like an unrendered JS app."""
    text, soup = extract_text(html)

    # Explicit JS-required messages in noscript tags
    for tag in soup.find_all("noscript"):
        content = tag.get_text().lower()
        if "javascript" in content or "enable" in content:
            return True

    # Empty JS framework root containers
    for selector in JS_ROOT_SELECTORS:
        tag, attr = selector.split("#")
        el = soup.find(tag, id=attr)
        if el is not None and not el.get_text(strip=True):
            return True

    # Many script tags but almost no visible text
    script_count = len(soup.find_all("script"))
    visible_text = text.strip() if text else ""
    if script_count >= 5 and len(visible_text) < 300:
        return True

    # Basically empty body
    if not visible_text or len(visible_text) < 200:
        return True

    return False


def fetch_with_requests(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code in (403, 429, 503):
            return None
        resp.raise_for_status()
        if needs_js(resp.text):
            return None
        text, _ = extract_text(resp.text)
        return text
    except Exception:
        return None


def fetch_with_selenium(url):
    driver = driver_pool.get()
    try:
        driver.get(url)
        time.sleep(SELENIUM_SLEEP)
        text, _ = extract_text(driver.page_source)
        return text
    except Exception as e:
        print(f"\nSelenium failed for {url}: {e}")
        return None
    finally:
        driver_pool.put(driver)


def process_row(idx_row):
    _, row = idx_row
    name = row["name"]
    college = row["college"]
    url = row["url"]

    college_path = Path(BASE_PATH) / college
    college_path.mkdir(parents=True, exist_ok=True)
    save_file = college_path / f"{name}.txt"

    if save_file.is_file():
        return

    text = fetch_with_requests(url)

    if text is None:
        text = fetch_with_selenium(url)

    if text is None:
        print(f"\n{name} | {college}: Both methods failed for {url}, trying Google search...")
        new_url = google_search_url(f"{name} Computer Science {college}", name)
        if new_url is not None:
            text = fetch_with_selenium(new_url)
            if text is not None:
                with url_updates_lock:
                    url_updates[(name, college)] = new_url
                print(f"\nSuccessfully retried {name} with {new_url}")

    if text is not None:
        save_file.write_text(text, encoding="utf-8")


try:
    with tqdm(total=len(rows), desc="Scraping faculty sites") as pbar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=N_TOTAL_WORKERS) as executor:
            futures = {executor.submit(process_row, r): r for r in rows}
            for future in concurrent.futures.as_completed(futures):
                pbar.update(1)
                try:
                    future.result()
                except Exception as e:
                    _, row = futures[future]
                    print(f"\nUnexpected error for {row['name']} | {row['college']}: {e}")
finally:
    while not driver_pool.empty():
        try:
            driver_pool.get_nowait().quit()
        except Exception:
            pass

for (name, college), new_url in url_updates.items():
    faculty.loc[(faculty["name"] == name) & (faculty["college"] == college), "url"] = new_url

faculty.to_csv(DATA_PATH, index=False)
print("Done.")
