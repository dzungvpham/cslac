import pandas as pd
import time
from bs4 import BeautifulSoup
from faculty_scraper import create_selenium_driver, google_search_url
from pathlib import Path
from tqdm import tqdm

DATA_PATH = "../data/faculty_list.csv"
BASE_PATH = "../data/faculty_websites"

Path(BASE_PATH).mkdir(parents=True, exist_ok=True)

faculty = pd.read_csv(DATA_PATH)
faculty_with_urls = faculty[pd.notna(faculty["url"])]

driver = create_selenium_driver()
driver.implicitly_wait(10)

for _, row in tqdm(faculty_with_urls.iterrows(), total=faculty_with_urls.shape[0]):
    name = row["name"]
    college = row["college"]
    url = row["url"]
    college_path = f"{BASE_PATH}/{college}"
    Path(college_path).mkdir(parents=True, exist_ok=True)
    save_file = f"{college_path}/{name}.txt"
    if Path(save_file).is_file():
        continue

    try:
        driver.get(url)
        time.sleep(5)
    except Exception as e:
        print(f"{name} | {college}: Failed to get {url}: {e}")
        url = google_search_url(f"{name} Computer Science {college}", name)
        if url is not None:
            try:
                driver.get(url)
                faculty.loc[(faculty["name"] == name) & (faculty["college"] == college), "url"] = url
                print(f"Successfully retried with {url}")
            except Exception as e:
                print(f"{name} | {college}: Failed to get {url}: {e}")
                continue
        else:
            continue
    with open(save_file, 'w', encoding='utf-8') as file:
        soup = BeautifulSoup(driver.page_source, features="html.parser")
        file.write(soup.body.get_text("\n", strip=True))

driver.quit()
faculty.to_csv(DATA_PATH, index=False)