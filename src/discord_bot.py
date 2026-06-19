"""Discord bot worker for scraping and sending listing alerts."""

import asyncio
import os
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import discord
from discord.ext import commands
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
from .listings import ListingRecord, SearchDefinition
from .logging_utils import configure_logging, get_logger, log_exception
from .rate_limiter import AsyncRateLimiter

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
scraper_logger = get_logger("scraper")
dispatcher_logger = get_logger("dispatcher")
discord_logger = get_logger("discord")


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


def worker_logger(worker_id: int):
    """Return a logger bound to a worker component tag."""
    return get_logger(f"worker {worker_id}")


@dataclass(slots=True)
class ScrapeWorker:
    """Per-worker Selenium session state."""

    worker_id: int
    driver: webdriver.Chrome | None = None
    browser_profile: BrowserProfile | None = None
    search_count: int = 0


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
                discord_logger.warning(
                    "Saved-items channel is not available",
                    context={"channel_id": settings.saved_channel_id},
                )
                await interaction.followup.send("Saved-items channel not found.", ephemeral=True)
                return

            embed = interaction.message.embeds[0]
            try:
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                log_exception(
                    discord_logger,
                    "Failed to send listing embed to saved-items channel",
                    exc,
                    channel_id=settings.saved_channel_id,
                )
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
        """Initialize shared scraper state."""
        self.bot = discord_bot
        self.send_initial_items = send_initial_items
        self.is_initial_scan = True
        self.searches = retrieve_utils.link_generator()
        self.search_queue: asyncio.Queue[SearchDefinition] = asyncio.Queue()
        self.rate_limiter = AsyncRateLimiter(settings.max_requests_per_minute)
        self.workers: list[ScrapeWorker] = []
        self._launcher_task: asyncio.Task[None] | None = None
        self._dispatcher_task: asyncio.Task[None] | None = None
        self._worker_tasks: list[asyncio.Task[None]] = []

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
            log_exception(
                scraper_logger,
                "Failed to apply browser profile overrides",
                exc,
                platform=profile.platform,
                timezone=profile.timezone,
            )
        return driver, profile

    async def _ensure_worker_driver(self, worker: ScrapeWorker) -> webdriver.Chrome:
        """Create this worker's private webdriver if it does not already have one."""
        if worker.driver is None:
            logger = worker_logger(worker.worker_id)
            logger.info("Starting Chrome session")
            worker.driver, worker.browser_profile = await self.create_driver()
            worker.search_count = 0
            profile = worker.browser_profile
            logger.info(
                "Chrome session ready",
                context={
                    "platform": profile.platform,
                    "window": f"{profile.width}x{profile.height}",
                    "timezone": profile.timezone,
                },
            )
        return worker.driver

    async def _quit_worker_driver(self, worker: ScrapeWorker) -> None:
        """Quit this worker's private webdriver, if present."""
        if worker.driver is None:
            return

        driver = worker.driver
        worker.driver = None
        worker.browser_profile = None
        worker.search_count = 0
        logger = worker_logger(worker.worker_id)
        logger.info("Quitting Chrome session")
        try:
            await asyncio.to_thread(driver.quit)
        except Exception as exc:
            log_exception(logger, "Failed to quit Chrome session cleanly", exc)

    async def _restart_worker_driver(self, worker: ScrapeWorker, reason: str | None = None) -> None:
        """Restart this worker's webdriver after a failure or search-count limit."""
        worker_logger(worker.worker_id).info("Restarting Chrome session", context={"reason": reason})
        await self._quit_worker_driver(worker)

    def get_channel_for_filter(self, filter_name: str) -> discord.abc.Messageable | None:
        """Return the configured alert channel for a filter, falling back to the designer channel."""
        channel_id = FILTER_CHANNEL_IDS.get(filter_name) or settings.designer_channel_id
        channel = self.bot.get_channel(int(channel_id))
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

    async def cog_load(self) -> None:
        """Start the scraper pool after the cog is loaded."""
        self._launcher_task = asyncio.create_task(
            self._launch_scraper_pool(),
            name="mercari-scraper-launcher",
        )

    async def cog_unload(self) -> None:
        """Cancel scraper tasks and close all worker browsers."""
        tasks_to_cancel = [
            task
            for task in [self._launcher_task, self._dispatcher_task, *self._worker_tasks]
            if task is not None and not task.done()
        ]
        for task in tasks_to_cancel:
            task.cancel()
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

        if self.workers:
            await asyncio.gather(
                *(self._quit_worker_driver(worker) for worker in self.workers),
                return_exceptions=True,
            )

        self._launcher_task = None
        self._dispatcher_task = None
        self._worker_tasks.clear()
        self.workers.clear()

    async def _launch_scraper_pool(self) -> None:
        """Wait for Discord readiness, then launch the fixed scraper pool."""
        try:
            await self.bot.wait_until_ready()
            worker_count = min(max(1, settings.worker_pool_size), 6)
            if worker_count != settings.worker_pool_size:
                scraper_logger.warning(
                    "Adjusted worker pool size to supported range",
                    context={"configured": settings.worker_pool_size, "effective": worker_count},
                )

            scraper_logger.info(
                "Starting Mercari scraper pool",
                context={
                    "workers": worker_count,
                    "searches": len(self.searches),
                    "max_requests_per_minute": f"{settings.max_requests_per_minute:.2f}",
                },
            )
            self.workers = [ScrapeWorker(worker_id=worker_id) for worker_id in range(1, worker_count + 1)]

            startup_stagger = max(0.0, settings.worker_startup_stagger_seconds)
            for worker in self.workers:
                task = asyncio.create_task(
                    self._run_worker(worker),
                    name=f"mercari-scrape-worker-{worker.worker_id}",
                )
                self._worker_tasks.append(task)
                worker_logger(worker.worker_id).info("Worker task launched")
                if self.searches:
                    try:
                        await self._ensure_worker_driver(worker)
                    except Exception as exc:
                        log_exception(
                            worker_logger(worker.worker_id),
                            "Failed to prewarm Chrome session",
                            exc,
                        )
                        await self._restart_worker_driver(worker, reason="startup failure")
                if worker.worker_id < worker_count and startup_stagger > 0:
                    await asyncio.sleep(startup_stagger)

            self._dispatcher_task = asyncio.create_task(
                self._run_dispatcher(),
                name="mercari-scrape-dispatcher",
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_exception(scraper_logger, "Scraper pool launcher failed", exc)

    async def _run_dispatcher(self) -> None:
        """Refill the shared queue once per full scraping cycle."""
        cycle_number = 0
        try:
            while True:
                if not self.searches:
                    dispatcher_logger.warning("No searches configured; dispatcher is sleeping", context={"sleep": 60})
                    await asyncio.sleep(60)
                    continue

                cycle_number += 1
                cycle_started_at = time.monotonic()
                cycle_searches = list(self.searches)
                random.shuffle(cycle_searches)

                for search in cycle_searches:
                    await self.search_queue.put(search)

                dispatcher_logger.info(
                    "Scrape cycle queued",
                    context={
                        "cycle": cycle_number,
                        "searches": len(cycle_searches),
                        "queue_depth": self.search_queue.qsize(),
                    },
                )
                await self.search_queue.join()

                cycle_seconds = time.monotonic() - cycle_started_at
                if self.is_initial_scan:
                    self.is_initial_scan = False
                    dispatcher_logger.info("Initial scan complete; future new listings will be alerted")

                dispatcher_logger.info(
                    "Scrape cycle completed",
                    context={
                        "cycle": cycle_number,
                        "elapsed_seconds": f"{cycle_seconds:.2f}",
                        "pause_seconds": f"{settings.cycle_pause_seconds:.2f}",
                    },
                )
                await asyncio.sleep(max(0.0, settings.cycle_pause_seconds))
        except asyncio.CancelledError:
            dispatcher_logger.info("Dispatcher stopped")
            raise

    async def _run_worker(self, worker: ScrapeWorker) -> None:
        """Consume searches from the shared queue until cancelled."""
        logger = worker_logger(worker.worker_id)
        logger.info("Worker started")
        try:
            while True:
                search = await self.search_queue.get()
                try:
                    await self._process_search(worker, search)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log_exception(
                        logger,
                        "Search failed; worker will restart its Chrome session",
                        exc,
                        filter=search.filter_name,
                        keyword=search.keyword,
                        url=search.url,
                    )
                    await self._restart_worker_driver(worker, reason="search failure")
                finally:
                    self.search_queue.task_done()
        except asyncio.CancelledError:
            logger.info("Worker stopping")
            raise
        finally:
            await self._quit_worker_driver(worker)
            logger.info("Worker stopped")

    async def _process_search(self, worker: ScrapeWorker, search: SearchDefinition) -> None:
        """Scrape one search and process newly discovered listings."""
        logger = worker_logger(worker.worker_id)
        observed_at = datetime.now(UTC)
        channel = self.get_channel_for_filter(search.filter_name)
        if channel is None:
            channel_id = FILTER_CHANNEL_IDS.get(search.filter_name) or settings.designer_channel_id
            logger.warning(
                "Skipping search because alert channel is not available",
                context={"filter": search.filter_name, "keyword": search.keyword, "channel_id": channel_id},
            )
            return

        driver = await self._ensure_worker_driver(worker)
        search_started_at = time.monotonic()
        logger.info(
            "Search started",
            context={
                "filter": search.filter_name,
                "keyword": search.keyword,
                "queue_depth": self.search_queue.qsize(),
            },
        )
        await self.rate_limiter.acquire()
        logger.debug(
            "Requesting search page",
            context={"filter": search.filter_name, "keyword": search.keyword, "url": search.url},
        )
        current_entries = await asyncio.to_thread(retrieve_utils.mercari_link, driver, search)
        worker.search_count += 1
        if worker.search_count >= settings.driver_restart_after_searches:
            await self._restart_worker_driver(
                worker,
                reason=f"{worker.search_count} searches",
            )

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
                        log_exception(
                            logger,
                            "Failed to discard pending alert reservation",
                            discard_exc,
                            delivery_id=delivery_id,
                            listing_id=listing.canonical_id,
                        )
                log_exception(
                    logger,
                    "Skipping listing after processing error",
                    exc,
                    listing_id=listing.canonical_id,
                    filter=search.filter_name,
                    keyword=search.keyword,
                )

        search_seconds = time.monotonic() - search_started_at
        logger.info(
            "Search finished",
            context={
                "filter": search.filter_name,
                "keyword": search.keyword,
                "listings": len(aggregated_listings),
                "elapsed_seconds": f"{search_seconds:.2f}",
            },
        )


async def entry(send_initial_items: bool = True) -> None:
    """Attach cogs and start the Discord client."""
    configure_logging(settings.log_level)
    async with bot:
        await bot.add_cog(MercariSendBot(bot, send_initial_items=send_initial_items))
        await bot.start(settings.discord_key.get_secret_value())
