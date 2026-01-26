import time
import retrieveUtils
import discord

def main():
    # ccp = retrieveUtils.mercariLink("https://jp.mercari.com/search?keyword=carol%20christian%20poell&sort=created_time&order=desc")
    # for key, value in ccp.items():
    #     print(key, value)

    input("Press enter to start.")
    ccp = retrieveUtils.mercariLink("https://jp.mercari.com/search?keyword=mihara&sort=created_time&order=desc")

    while True:
        time.sleep(retrieveUtils.randomTime())
        newccp = retrieveUtils.mercariLink("https://jp.mercari.com/search?keyword=mihara&sort=created_time&order=desc")
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
