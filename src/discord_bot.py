import discord
from discord.ext import tasks, commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from config import settings
import retrieveUtils
from database import insert_links
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class View(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Save Item", emoji='\N{WHITE HEAVY CHECK MARK}')
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(int(settings.saved_channel_id))
        embed = interaction.message.embeds[0]
        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message("Listing saved!", ephemeral=True)
        
class MercariSendBot(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.send_product.start()
        self.all_urls = retrieveUtils.link_generator()

    @tasks.loop(seconds = 1)
    async def send_product(self):
        next_delay = retrieveUtils.random_time()
        self.send_product.change_interval(seconds=next_delay)
        channel = self.bot.get_channel(int(settings.designer_channel_id))
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        
        if channel:
            driver = await asyncio.to_thread(webdriver.Chrome, options=options)
            try:
                for url, brand in self.all_urls.items():  # Currently code only goes through all json keywords once.
                    curr_entry = await asyncio.to_thread(retrieveUtils.mercari_link, driver, url)
                    for link, desc in curr_entry.items():  # TODO: implement pydantic for db insertion
                        if await insert_links(
                            {
                                "_id": link,  # specific for mongodb hashing
                                "item_name": desc[0],
                                "image": desc[1],
                            }
                        ):
                            embed = discord.Embed(title=desc[0], url=link, description=f"Brand is: {brand}")
                            embed.set_image(url=desc[1])
                            embed.set_footer(text="ArchiveStatic")
                            view = View()
                            await channel.send(embed=embed, view=view)
            finally:
                driver.quit()
        else:
            print("Fail")

    @send_product.before_loop
    async def wait_until_reg(self):
        await self.bot.wait_until_ready()

class MercariReactionBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.send_product.start()

async def entry():
    async with bot:
        await bot.add_cog(MercariSendBot(bot))
        await bot.start(settings.discord_key.get_secret_value())
