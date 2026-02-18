import random
from collections import defaultdict
from urllib.parse import urlencode

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from config import app_config
from constants import MERCARI_BASE_URL


def mercari_link(link) -> dict:
    '''
     Returns dict <string, tuple> where string is link, and tuple has attributes (fullTitle, image, content)
    '''
    all_items = {}
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(link)
    driver.implicitly_wait(7)
    # Items in mercari are sorted by <li data-testid="item-cell" class="">
    # Item ID located in <a-"data-location">
    # Item name and price in <div class="merItemThumbnail>
    total_items = driver.find_elements(by=By.CSS_SELECTOR, value='[data-testid="item-cell"]')
    # itemTest = driver.find_element(By.CSS_SELECTOR, '[data-testid="item-cell"]')

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

        all_items[link] = (full_title, image, content)
    # time.sleep(2)

    try:
        print(f"Page Title: {driver.title}")
        pass
    except :
        print("Driver crashed or closed.")

    driver.quit()

    return all_items


def new_product_check(old_dict: dict, new_dict: dict):  # Returns new item/items if there are any, None if not.
    new_items = defaultdict(list)

    new_item_links = new_dict.keys() - old_dict.keys()

    for n in new_item_links:
        item_data = new_dict[n]

        new_items[n] = item_data

    return new_items


def random_time():  # Returns a random time from 60s to 120s to prevent bot detection
    sleep_seconds = random.gauss(90, 15)
    final_time = max(60, sleep_seconds)
    return final_time


def link_generator() -> dict[str]:  # Moved to over here, generates all the links with brand name as keys.
    all_urls = {}
    for filter_data in app_config.filters:
        for keyword in filter_data.keywords:
            params = {"keyword": keyword, "sort": "created_time", "order": "desc"}
            url = f"{MERCARI_BASE_URL}?{urlencode(params)}"
            all_urls[url] = filter_data.name
    return all_urls