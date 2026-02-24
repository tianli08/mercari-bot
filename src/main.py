import asyncio
import discord_bot

def main():
    # TODO: Implement first pass as a user selection to send notifs or not.
    input("Press enter to start.")
    # Main Logic Loop
    asyncio.run(discord_bot.entry())
    
if __name__ == "__main__":
    main()

    # Selections should be made with a particular format
    # "https://jp.mercari.com/search?keyword=saint%20laurent%20jacket&sort=created_time&order=desc"
    # KW: Should be in JP if branded there unless artisanal
    # Sold out products should not be toggled out due to page refresh adding another product from following page.
