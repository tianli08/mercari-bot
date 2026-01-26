from selenium import webdriver
from selenium.webdriver.common.by import By
from collections import defaultdict
import random
import time

class MercariScraper:
    def __init__(self, driver):
        self.driver = driver

def mercariLink(link) -> dict: 
    # Returns dict <string, list> where string is link, and list has attributes [fullTitle, image, content]

    allItems = defaultdict(list)

    driver = webdriver.Chrome()
    driver.get(link)
    driver.implicitly_wait(5.5)
    # Items in mercari are sorted by <li data-testid="item-cell" class="">
        # Item ID located in <a-"data-location">
            # Item name and price in <div class="merItemThumbnail>
    totalItems = driver.find_elements(by = By.CSS_SELECTOR, value = '[data-testid="item-cell"]')
    # itemTest = driver.find_element(By.CSS_SELECTOR, '[data-testid="item-cell"]')

    print(f'Amount of items is {len(totalItems)}')

    for item in totalItems:
        content = item.text
        if not content.strip():
            continue
        # "Find the first anchor (link) tag inside this item"
        linkScrape = item.find_element(by=By.TAG_NAME, value="a")
        link = linkScrape.get_attribute("href")

        imageScrape = item.find_element(by=By.TAG_NAME, value="img")
        image = imageScrape.get_attribute("src")

        fullTitleScrape = item.find_element(By.CSS_SELECTOR, value = '.merItemThumbnail')
        fullTitle = fullTitleScrape.get_attribute("aria-label")

        # debugger

        # print(f"{content.replace('\n', ' ')}")
        # print(fullTitle)
        # print(link)
        # print(image)

        allItems[link] = (fullTitle, image, content)
    # time.sleep(2) 

    try:
        print(f"Page Title: {driver.title}")
        pass
    except:
        print("Driver crashed or closed.")

    driver.quit()

    return allItems


def newProductCheck(oldDict: dict, newDict: dict): # Returns new item/items if there are any, None if not.
    newItems = defaultdict(list)

    newItemLinks = newDict.keys() - oldDict.keys()

    for n in newItemLinks:
        itemData = newDict[n]

        newItems[n] = itemData
        
    return newItems

def randomTime(): # Returns a random time from 60s to 120s to prevent bot detection

    sleep_seconds = random.gauss(90, 15)
    final_time = max(60, sleep_seconds)
    return final_time