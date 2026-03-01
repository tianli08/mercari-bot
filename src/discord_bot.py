import asyncio

import discord
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import retrieveUtils as retrieve_utils
from config import settings
from database import insert_links

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class View(discord.ui.View):
    """Persistent message actions for listing cards."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Save Item", emoji="\N{WHITE HEAVY CHECK MARK}")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        del button  # Callback signature requires this parameter.
        channel = interaction.client.get_channel(int(settings.saved_channel_id))
        embed = interaction.message.embeds[0]
        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message("Listing saved!", ephemeral=True)


class MercariSendBot(commands.Cog):
    """Continuously scrape Mercari and post newly discovered products."""

    def __init__(self, discord_bot: commands.Bot, send_initial_items: bool = True) -> None:
        self.bot = discord_bot
        self.send_initial_items = send_initial_items
        self.is_initial_scan = True
        self.driver: webdriver.Chrome | None = None
        self.all_urls = retrieve_utils.link_generator()
        self.send_product.start()

    @staticmethod
    def build_webdriver_options() -> Options:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        return options

    @staticmethod
    async def create_driver() -> webdriver.Chrome:
        options = MercariSendBot.build_webdriver_options()
        return await asyncio.to_thread(webdriver.Chrome, options=options)

    async def get_or_create_driver(self) -> webdriver.Chrome:
        """Create a single persistent driver and reuse it across cycles."""
        if self.driver is None:
            self.driver = await self.create_driver()
        return self.driver

    @staticmethod
    async def send_listing_message(
        channel: discord.abc.Messageable, link: str, brand: str, item: dict
    ) -> None:
        """Embed logic"""
        proxy_link = retrieve_utils.link_crafter(link)
        description = f"Brand is: {brand}"
        if proxy_link:
            description = f"{description}\nProxy: [Open listing]({proxy_link})"

        embed = discord.Embed(
            title=item["item_name"],
            url=link,
            description=description,
        )
        embed.set_image(url=item["image"])
        embed.set_footer(text="ArchiveStatic")
        await channel.send(embed=embed, view=View())

    @tasks.loop(seconds=1)
    async def send_product(self) -> None:
        next_delay = retrieve_utils.random_time()
        self.send_product.change_interval(seconds=next_delay)
        channel = self.bot.get_channel(int(settings.designer_channel_id))
        if channel is None:
            print("Designer channel not found. Check designer_channel_id.")
            return

        driver = await self.get_or_create_driver()
        for url, brand in self.all_urls.items():
            current_entries = await asyncio.to_thread(retrieve_utils.mercari_link, driver, url)
            for link, item in current_entries.items():
                is_new_listing = await insert_links(
                    {
                        "_id": link,
                        "item_name": item["item_name"],
                        "image": item["image"],
                    }
                )
                if is_new_listing:
                    should_send_message = self.send_initial_items or not self.is_initial_scan
                    if should_send_message:
                        await self.send_listing_message(channel, link, brand, item)
        self.is_initial_scan = False

    @send_product.before_loop
    async def wait_until_reg(self) -> None:
        await self.bot.wait_until_ready()


async def entry(send_initial_items: bool = True) -> None:
    """Attach cogs and start the Discord client."""
    async with bot:
        await bot.add_cog(MercariSendBot(bot, send_initial_items=send_initial_items))
        await bot.start(settings.discord_key.get_secret_value())
