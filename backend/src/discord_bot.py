"""Discord bot worker for scraping and sending listing alerts."""

import asyncio
import contextlib
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import discord
from discord.ext import commands
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from . import retrieve_utils, webdriver_utils
from .browser_profile import BrowserProfile
from .config import get_legacy_app_config, settings
from .database import (
    discard_pending_alert_delivery,
    mark_alert_delivery_sent,
    reserve_alert_delivery,
    upsert_listing,
)
from .discord_messages import View as View
from .discord_messages import send_listing_message as send_discord_listing_message
from .listings import ListingRecord, SearchDefinition
from .logging_utils import ContextLoggerAdapter, configure_logging, get_logger, log_exception
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
    for filter_data in get_legacy_app_config().filters:
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
SELENIUM_CONNECTION_LOGGER = "urllib3.connectionpool"


def worker_logger(worker_id: int):
    """Return a logger bound to a worker component tag."""
    return get_logger(f"worker {worker_id}")


@contextlib.contextmanager
def quiet_selenium_shutdown_warnings():
    """Suppress Selenium connection retries while a browser session is being torn down."""
    logger = logging.getLogger(SELENIUM_CONNECTION_LOGGER)
    previous_level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous_level)


@dataclass(slots=True)
class ScrapeWorker:
    """Per-worker Selenium session state."""

    worker_id: int
    driver: webdriver.Chrome | None = None
    browser_profile: BrowserProfile | None = None
    search_count: int = 0


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
        return webdriver_utils.build_webdriver_options(profile)

    @staticmethod
    def apply_browser_profile(driver: webdriver.Chrome, profile: BrowserProfile) -> None:
        """Apply stealth-oriented browser overrides to a new session."""
        webdriver_utils.apply_browser_profile(driver, profile)

    @staticmethod
    async def create_driver() -> tuple[webdriver.Chrome, BrowserProfile]:
        """Create a Chrome webdriver without blocking the event loop."""
        return await webdriver_utils.create_driver()

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
            with quiet_selenium_shutdown_warnings():
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
        await send_discord_listing_message(channel, item)

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
        self._log_search_started(logger, search, self.search_queue.qsize())
        aggregated_listings = await self._scrape_search_listings(worker, driver, search, logger)
        await self._process_listing_alerts(channel, aggregated_listings, observed_at, search, logger)
        self._log_search_finished(logger, search, aggregated_listings, search_started_at)

    @staticmethod
    def _log_search_started(logger: ContextLoggerAdapter, search: SearchDefinition, queue_depth: int) -> None:
        """Log the beginning of a queued search."""
        logger.info(
            "Search started",
            context={
                "filter": search.filter_name,
                "keyword": search.keyword,
                "queue_depth": queue_depth,
            },
        )

    async def _scrape_search_listings(
        self,
        worker: ScrapeWorker,
        driver: webdriver.Chrome,
        search: SearchDefinition,
        logger: ContextLoggerAdapter,
    ) -> dict[str, ListingRecord]:
        """Request a search page and return merged listing records."""
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

        return self._aggregate_listing_results(current_entries)

    @staticmethod
    def _aggregate_listing_results(current_entries: list[ListingRecord]) -> dict[str, ListingRecord]:
        """Merge duplicate listings from a scrape into canonical records."""
        aggregated_listings: dict[str, ListingRecord] = {}
        retrieve_utils.merge_listing_results(aggregated_listings, current_entries)
        return aggregated_listings

    async def _process_listing_alerts(
        self,
        channel: discord.abc.Messageable,
        aggregated_listings: dict[str, ListingRecord],
        observed_at: datetime,
        search: SearchDefinition,
        logger: ContextLoggerAdapter,
    ) -> None:
        """Upsert scraped listings and deliver any required Discord alerts."""
        for listing in aggregated_listings.values():
            await self._process_listing_alert(channel, listing, observed_at, search, logger)

    async def _process_listing_alert(
        self,
        channel: discord.abc.Messageable,
        listing: ListingRecord,
        observed_at: datetime,
        search: SearchDefinition,
        logger: ContextLoggerAdapter,
    ) -> None:
        """Apply dedupe rules for a single listing and send its alert when needed."""
        delivery_id = None
        message_sent = False
        try:
            is_new_listing = await upsert_listing(listing, observed_at=observed_at)
            should_send_message = self._should_send_listing_message(is_new_listing)
            if not should_send_message:
                return

            delivery_id = await reserve_alert_delivery(
                listing,
                destination_id=str(channel.id),
                observed_at=observed_at,
            )
            if delivery_id is None:
                return

            await self.send_listing_message(channel, listing)
            message_sent = True

            await mark_alert_delivery_sent(
                delivery_id,
                listing.canonical_id,
                delivered_at=observed_at,
            )
        except Exception as exc:
            if delivery_id is not None and not message_sent:
                await self._discard_pending_alert_delivery(delivery_id, listing, logger)
            log_exception(
                logger,
                "Skipping listing after processing error",
                exc,
                listing_id=listing.canonical_id,
                filter=search.filter_name,
                keyword=search.keyword,
            )

    def _should_send_listing_message(self, is_new_listing: bool) -> bool:
        """Return whether a new listing should be sent for the current scan phase."""
        return is_new_listing and (self.send_initial_items or not self.is_initial_scan)

    @staticmethod
    async def _discard_pending_alert_delivery(
        delivery_id: str,
        listing: ListingRecord,
        logger: ContextLoggerAdapter,
    ) -> None:
        """Discard a pending delivery reservation after a failed Discord send."""
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

    @staticmethod
    def _log_search_finished(
        logger: ContextLoggerAdapter,
        search: SearchDefinition,
        aggregated_listings: dict[str, ListingRecord],
        search_started_at: float,
    ) -> None:
        """Log the end of a completed search."""
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
