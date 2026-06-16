"""Discord bot worker for scraping and sending listing alerts."""

import asyncio
import os
import traceback
from datetime import UTC, datetime

import discord
from discord.ext import commands, tasks
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from . import retrieveUtils as retrieve_utils
from .browser_profile import BrowserProfile, build_fingerprint_script, pick_browser_profile
from .config import app_config, settings
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


def configured_filter_channels() -> dict[str, str]:
    """Return filter-name to channel-id mappings from config and environment."""
    channels: dict[str, str] = {}
    extra_settings = settings.model_extra or {}
    for filter_data in app_config.filters:
        if filter_data.channel_id:
            channels[filter_data.name] = filter_data.channel_id
            continue
        if filter_data.channel_id_env:
            setting_name = filter_data.channel_id_env.lower()
            channel_id = (
                os.getenv(filter_data.channel_id_env)
                or getattr(settings, setting_name, None)
                or extra_settings.get(setting_name)
                or extra_settings.get(filter_data.channel_id_env)
            )
            if channel_id:
                channels[filter_data.name] = str(channel_id)
    return channels


FILTER_CHANNEL_IDS = configured_filter_channels()


def print_error(message: str, exc: BaseException) -> None:
    """Print exception details for long-running terminal monitoring."""
    print(f"{message}: {type(exc).__name__}: {exc}")
    traceback.print_exception(type(exc), exc, exc.__traceback__)


class View(discord.ui.View):
    """Persistent message actions for listing cards."""

    def __init__(self) -> None:
        """Create a persistent action row for listing messages."""
        super().__init__(timeout=None)
        self.is_saved = False
        self.save_lock = asyncio.Lock()

    def disable_save_actions(self) -> None:
        """Disable interactive controls after a listing has been saved."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Save Item", emoji="\N{WHITE HEAVY CHECK MARK}")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Copy the current listing embed into the saved-items channel once."""
        await interaction.response.defer(ephemeral=True, thinking=False)

        if interaction.message is None or not interaction.message.embeds:
            await interaction.followup.send("This listing message is missing its embed.", ephemeral=True)
            return

        async with self.save_lock:
            if self.is_saved:
                self.disable_save_actions()
                await interaction.message.edit(view=self)
                await interaction.followup.send("Listing already saved.", ephemeral=True)
                return

            channel = interaction.client.get_channel(int(settings.saved_channel_id))
            if channel is None:
                await interaction.followup.send("Saved-items channel not found.", ephemeral=True)
                return

            embed = interaction.message.embeds[0]
            try:
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                print_error("Failed to save listing embed to saved-items channel", exc)
                await interaction.followup.send("Saving failed. Try again.", ephemeral=True)
                return

            self.is_saved = True
            self.disable_save_actions()
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.followup.send("Listing saved!", ephemeral=True)


class MercariSendBot(commands.Cog):
    """Continuously scrape Mercari and post newly discovered products."""

    def __init__(self, discord_bot: commands.Bot, send_initial_items: bool = True) -> None:
        """Initialize the scraping worker and start the polling loop."""
        self.bot = discord_bot
        self.send_initial_items = send_initial_items
        self.is_initial_scan = True
        self.driver: webdriver.Chrome | None = None
        self.browser_profile: BrowserProfile | None = None
        self.driver_search_count = 0
        self.searches = retrieve_utils.link_generator()
        self.next_search_index = 0
        self.query_interval_seconds = retrieve_utils.query_interval(len(self.searches))
        self.send_product.start()

    @staticmethod
    def build_webdriver_options(profile: BrowserProfile) -> Options:
        """Build Chrome options for the shared scraping session."""
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument(f"--window-size={profile.width},{profile.height}")
        options.add_argument(f"--lang={profile.locale}")
        options.add_argument(f"--user-agent={profile.user_agent}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option(
            "prefs",
            {"intl.accept_languages": profile.accept_language},
        )
        return options

    @staticmethod
    def apply_browser_profile(driver: webdriver.Chrome, profile: BrowserProfile) -> None:
        """Apply stealth-oriented browser overrides to a new session."""
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": profile.user_agent,
                "acceptLanguage": profile.accept_language,
                "platform": profile.platform,
            },
        )
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": profile.width,
                "height": profile.height,
                "deviceScaleFactor": profile.device_scale_factor,
                "mobile": False,
            },
        )
        driver.execute_cdp_cmd(
            "Emulation.setTimezoneOverride",
            {"timezoneId": profile.timezone},
        )
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": build_fingerprint_script(profile)},
        )

    @staticmethod
    async def create_driver() -> tuple[webdriver.Chrome, BrowserProfile]:
        """Create a Chrome webdriver without blocking the event loop."""
        profile = pick_browser_profile()
        options = MercariSendBot.build_webdriver_options(profile)
        driver = await asyncio.to_thread(webdriver.Chrome, options=options)
        await asyncio.to_thread(driver.set_page_load_timeout, settings.selenium_page_load_timeout_seconds)
        await asyncio.to_thread(driver.set_script_timeout, settings.selenium_script_timeout_seconds)
        try:
            await asyncio.to_thread(MercariSendBot.apply_browser_profile, driver, profile)
        except Exception as exc:
            print_error("Failed to apply browser profile overrides", exc)
        print(
            "Started Chrome session with "
            f"{profile.platform}, {profile.width}x{profile.height}, {profile.timezone}"
        )
        return driver, profile

    async def get_or_create_driver(self) -> webdriver.Chrome:
        """Create a single persistent driver and reuse it across cycles."""
        if self.driver is None:
            self.driver, self.browser_profile = await self.create_driver()
            self.driver_search_count = 0
        return self.driver

    async def restart_driver(self) -> None:
        """Restart the Selenium driver after failures or long-running sessions."""
        if self.driver is not None:
            try:
                await asyncio.to_thread(self.driver.quit)
            except Exception as exc:
                print_error("Failed to quit Chrome session cleanly", exc)
        self.driver = None
        self.browser_profile = None
        self.driver_search_count = 0

    def advance_search(self) -> None:
        """Move to the next configured search and refresh the next delay."""
        self.next_search_index = (self.next_search_index + 1) % len(self.searches)
        if self.next_search_index == 0:
            self.is_initial_scan = False
        self.query_interval_seconds = retrieve_utils.query_interval(len(self.searches))
        self.send_product.change_interval(seconds=self.query_interval_seconds)

    def get_channel_for_filter(self, filter_name: str) -> discord.abc.Messageable | None:
        """Return the configured alert channel for a filter, falling back to the designer channel."""
        channel_id = FILTER_CHANNEL_IDS.get(filter_name) or settings.designer_channel_id
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            print(f"Alert channel not found for {filter_name}. Check channel id {channel_id}.")
        return channel

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
        if not self.searches:
            print("No searches configured. Sleeping for 60 seconds.")
            self.send_product.change_interval(seconds=60)
            return

        observed_at = datetime.now(UTC)
        search = self.searches[self.next_search_index]
        channel = self.get_channel_for_filter(search.filter_name)
        if channel is None:
            self.advance_search()
            return

        try:
            driver = await self.get_or_create_driver()
        except Exception as exc:
            print_error(f"Failed to start Chrome for {search.filter_name} [{search.keyword}]", exc)
            await self.restart_driver()
            self.advance_search()
            return

        print(
            "Checking search "
            f"{self.next_search_index + 1}/{len(self.searches)}: "
            f"{search.filter_name} [{search.keyword}]"
        )
        try:
            current_entries = await asyncio.to_thread(retrieve_utils.mercari_link, driver, search)
        except Exception as exc:
            print_error(f"Search failed for {search.filter_name} [{search.keyword}]", exc)
            await self.restart_driver()
            current_entries = []
        else:
            self.driver_search_count += 1
            if self.driver_search_count >= settings.driver_restart_after_searches:
                print(f"Restarting Chrome after {self.driver_search_count} searches.")
                await self.restart_driver()
        aggregated_listings: dict[str, ListingRecord] = {}
        retrieve_utils.merge_listing_results(aggregated_listings, current_entries)

        for listing in aggregated_listings.values():
            delivery_id = None
            message_sent = False
            try:
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

                await self.send_listing_message(channel, listing)
                message_sent = True

                await mark_alert_delivery_sent(
                    delivery_id,
                    listing.canonical_id,
                    delivered_at=observed_at,
                )
            except Exception as exc:
                if delivery_id is not None and not message_sent:
                    try:
                        await discard_pending_alert_delivery(delivery_id)
                    except Exception as discard_exc:
                        print_error(f"Failed to discard pending alert {delivery_id}", discard_exc)
                print_error(f"Skipping listing {listing.canonical_id} after error", exc)

        self.advance_search()

    @send_product.error
    async def send_product_error(self, error: BaseException) -> None:
        """Log unexpected task-level failures."""
        print_error("send_product task crashed", error)

    @send_product.before_loop
    async def wait_until_reg(self) -> None:
        """Wait for the Discord connection before starting the polling loop."""
        await self.bot.wait_until_ready()


async def entry(send_initial_items: bool = True) -> None:
    """Attach cogs and start the Discord client."""
    async with bot:
        await bot.add_cog(MercariSendBot(bot, send_initial_items=send_initial_items))
        await bot.start(settings.discord_key.get_secret_value())
