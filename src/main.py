
import retrieveUtils
from config import settings
from database import insert_links
from discord import send_webhook


def main():
    input("Press enter to start.")

    all_urls = retrieveUtils.link_generator()

    # db concept:
    # if link not in db, return the new product, else continue.

    for url in all_urls:  # Currently code only goes through all json keywords once.
        curr_entry = retrieveUtils.mercari_link(url)
        for link, desc in curr_entry.items():  # TODO: implement pydantic for db insertion
            if insert_links(
                {
                    "_id": link,  # specific for mongodb hashing
                    "item_name": desc[0],
                    "image": desc[1],
                }
            ):
                send_webhook(link, desc, settings.designer_webhook)
                # TODO: need to implment a potential faster way of checking items already sent, 15 item limit refresh is slow.


if __name__ == "__main__":
    main()

    # Selections should be made with a particular format
    # "https://jp.mercari.com/search?keyword=saint%20laurent%20jacket&sort=created_time&order=desc"
    # KW: Should be in JP if branded there unless artisanal
    # Sold out products should not be toggled out due to page refresh adding another product from following page.
