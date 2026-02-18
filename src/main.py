import asyncio
import time
import retrieveUtils
from config import settings
from database import insert_links
import discord_bot


def main():
    input("Press enter to start.")

    all_urls = retrieveUtils.link_generator()

    new_items_only = 1
    # Runs through this once for new_items_only = 1 to avoid any old items
    if new_items_only:
        for url in all_urls:
            curr_entry = retrieveUtils.mercari_link(url)
            for link, desc in curr_entry.items():
                insert_links(
                    {
                        "_id": link,  # specific for mongodb hashing
                        "item_name": desc[0],
                        "image": desc[1],
                    }
                )
        time.sleep(retrieveUtils.random_time())
    asyncio.run(discord_bot.entry())
    


if __name__ == "__main__":
    main()

    # Selections should be made with a particular format
    # "https://jp.mercari.com/search?keyword=saint%20laurent%20jacket&sort=created_time&order=desc"
    # KW: Should be in JP if branded there unless artisanal
    # Sold out products should not be toggled out due to page refresh adding another product from following page.
