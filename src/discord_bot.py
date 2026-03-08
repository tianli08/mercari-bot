"""Discord bot worker for scraping and sending listing alerts."""

import asyncio
from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from . import retrieveUtils as retrieve_utils
from .config import settings
from .database import (
    discard_pending_alert_delivery,
    mark_alert_delivery_sent,
    reserve_alert_delivery,
    upsert_listing,
)
from .listings import ListingRecord

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


class View(discord.ui.View):
    """Persistent message actions for listing cards."""

    def __init__(self) -> None:
        """Create a persistent action row for listing messages."""
        super().__init__(timeout=None)

    @discord.ui.button(label="Save Item", emoji="\N{WHITE HEAVY CHECK MARK}")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Copy the current listing embed into the saved-items channel."""
        del button  # Callback signature requires this parameter.
        channel = interaction.client.get_channel(int(settings.saved_channel_id))
        embed = interaction.message.embeds[0]
        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message("Listing saved!", ephemeral=True)


class MercariSendBot(commands.Cog):
    """Continuously scrape Mercari and post newly discovered products."""

    def __init__(self, discord_bot: commands.Bot, send_initial_items: bool = True) -> None:
        """Initialize the scraping worker and start the polling loop."""
        self.bot = discord_bot
        self.send_initial_items = send_initial_items
        self.is_initial_scan = True
        self.driver: webdriver.Chrome | None = None
        self.searches = retrieve_utils.link_generator()
        self.send_product.start()

    @staticmethod
    def build_webdriver_options() -> Options:
        """Build Chrome options for the shared scraping session."""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        return options

    @staticmethod
    async def create_driver() -> webdriver.Chrome:
        """Create a Chrome webdriver without blocking the event loop."""
        options = MercariSendBot.build_webdriver_options()
        return await asyncio.to_thread(webdriver.Chrome, options=options)

    async def get_or_create_driver(self) -> webdriver.Chrome:
        """Create a single persistent driver and reuse it across cycles."""
        if self.driver is None:
            self.driver = await self.create_driver()
        return self.driver

    @staticmethod
    async def send_listing_message(
        channel: discord.abc.Messageable,
        item: ListingRecord,
    ) -> None:
        """Send a Discord embed for a single canonical listing."""
        proxy_link = retrieve_utils.link_crafter(item.url) if item.marketplace == "mercari" else None
        description_lines = [f"Marketplace: {item.marketplace.title()}"]

        if item.matched_filters:
            description_lines.append(f"Filters: {', '.join(sorted(item.matched_filters))}")
        if item.matched_keywords:
            description_lines.append(f"Keywords: {', '.join(sorted(item.matched_keywords))}")
        if item.price_text:
            description_lines.append(f"Price: {item.price_text}")
        if proxy_link:
            description_lines.append(f"Proxy: [Open listing]({proxy_link})")

        embed = discord.Embed(
            title=item.title,
            url=item.url,
            description="\n".join(description_lines),
        )
        if item.image_url:
            embed.set_image(url=item.image_url)
        embed.set_footer(text=f"ArchiveStatic | {item.canonical_id}")
        await channel.send(embed=embed, view=View())

    @tasks.loop(seconds=1)
    async def send_product(self) -> None:
        """Poll all searches, persist canonical listings, and send new alerts."""
        next_delay = retrieve_utils.random_time()
        self.send_product.change_interval(seconds=next_delay)
        channel = self.bot.get_channel(int(settings.designer_channel_id))
        if channel is None:
            print("Designer channel not found. Check designer_channel_id.")
            return

        driver = await self.get_or_create_driver()
        observed_at = datetime.now(UTC)
        aggregated_listings: dict[str, ListingRecord] = {}

        for search in self.searches:
            current_entries = await asyncio.to_thread(retrieve_utils.mercari_link, driver, search)
            retrieve_utils.merge_listing_results(aggregated_listings, current_entries)

        for listing in aggregated_listings.values():
            is_new_listing = await upsert_listing(listing, observed_at=observed_at)
            should_send_message = is_new_listing and (
                self.send_initial_items or not self.is_initial_scan
            )
            if not should_send_message:
                continue

            delivery_id = await reserve_alert_delivery(
                listing,
                channel_id=str(channel.id),
                observed_at=observed_at,
            )
            if delivery_id is None:
                continue

            try:
                await self.send_listing_message(channel, listing)
            except Exception:
                await discard_pending_alert_delivery(delivery_id)
                raise

            await mark_alert_delivery_sent(
                delivery_id,
                listing.canonical_id,
                delivered_at=observed_at,
            )
        self.is_initial_scan = False

    @send_product.before_loop
    async def wait_until_reg(self) -> None:
        """Wait for the Discord connection before starting the polling loop."""
        await self.bot.wait_until_ready()


async def entry(send_initial_items: bool = True) -> None:
    """Attach cogs and start the Discord client."""
    async with bot:
        await bot.add_cog(MercariSendBot(bot, send_initial_items=send_initial_items))
        await bot.start(settings.discord_key.get_secret_value())
