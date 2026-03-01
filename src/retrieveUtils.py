import random
from collections import defaultdict
from typing import TypedDict
from urllib.parse import urlencode
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from config import app_config
from constants import MERCARI_BASE_URL, BUYEE_LINK


class ListingData(TypedDict):
    item_name: str
    image: str
    content: str


def mercari_link(driver, link: str) -> dict[str, ListingData]:
    """Scrape a Mercari search page and return listings keyed by URL."""
    all_items: dict[str, ListingData] = {}
    driver.get(link)
    try:
        WebDriverWait(driver, 7).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="item-cell"]'))
        )
    except TimeoutException:
        print(f"No item cells found before timeout: {link}")
        return all_items

    total_items = driver.find_elements(by=By.CSS_SELECTOR, value='[data-testid="item-cell"]')

    print(f"Amount of items is {len(total_items)}")

    for item in total_items:
        content = item.text
        if not content.strip():
            continue
        # "Find the first anchor (link) tag inside this item"
        link_scrape = item.find_element(by=By.TAG_NAME, value="a")
        link = link_scrape.get_attribute("href")

        image_scrape = item.find_element(by=By.TAG_NAME, value="img")
        image = image_scrape.get_attribute("src")

        full_title_scrape = item.find_element(By.CSS_SELECTOR, value=".merItemThumbnail")
        full_title = full_title_scrape.get_attribute("aria-label")

        all_items[link] = {
            "item_name": full_title,
            "image": image,
            "content": content,
        }

    try:
        print(f"Page Title: {driver.title}")
    except Exception:
        print("Driver crashed or closed.")

    return all_items


def new_product_check(old_dict: dict, new_dict: dict) -> dict:
    """Return only products present in new_dict but not old_dict."""
    new_items: dict = defaultdict(list)

    new_item_links = new_dict.keys() - old_dict.keys()

    for n in new_item_links:
        item_data = new_dict[n]

        new_items[n] = item_data

    return dict(new_items)


def random_time() -> float:
    """Return random delay (>=60s) to reduce scraping predictability."""
    sleep_seconds = random.gauss(90, 15)
    final_time = max(60, sleep_seconds)
    print(f"Next iteration sleeping for {final_time} seconds")
    return final_time


def link_generator() -> dict[str, str]:
    """Generate Mercari search URLs mapped to their filter/brand name."""
    all_urls: dict[str, str] = {}
    for filter_data in app_config.filters:
        for keyword in filter_data.keywords:
            params = {"keyword": keyword, "sort": "created_time", "order": "desc"}
            url = f"{MERCARI_BASE_URL}?{urlencode(params)}"
            all_urls[url] = filter_data.name
    return all_urls

def link_crafter(mercari_link: str) -> str | None:
    """Build a Buyee listing URL from a Mercari item URL."""
    if "/item/" not in mercari_link:
        return None

    item_id = mercari_link.split("/item/", maxsplit=1)[1].split("/", maxsplit=1)[0]
    item_id = item_id.split("?", maxsplit=1)[0].strip()
    if not item_id:
        return None

    return f"{BUYEE_LINK}{item_id}"