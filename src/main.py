import time
from urllib.parse import urlencode

import discord
import retrieveUtils
from config import app_config
from constants import MERCARI_BASE_URL, SEARCH_URLS


def main():
    input("Press enter to start.")

    # can do something like this
    for filter_data in app_config.filters:
        for keyword in filter_data.keywords:
            params = {"keyword": keyword, "sort": "created_time", "order": "desc"}
            url = f"{MERCARI_BASE_URL}?{urlencode(params)}"
            print(url)

    ccp = retrieveUtils.mercariLink(SEARCH_URLS["Mihara"])

    while True:
        time.sleep(retrieveUtils.randomTime())
        newccp = retrieveUtils.mercariLink(SEARCH_URLS["Mihara"])
        newProduct = retrieveUtils.newProductCheck(ccp, newccp)
        if newProduct:
            ccp = newccp

            for key, value in newProduct.items():
                print("New product alert!: ", key)
                discord.sendWebhook(key)


if __name__ == "__main__":
    main()

    # Selections should be made with a particular format
    # "https://jp.mercari.com/search?keyword=saint%20laurent%20jacket&sort=created_time&order=desc"
    # KW: Should be in JP if branded there unless artisanal
    # Sold out products should not be toggled out due to page refresh adding another product from following page.
