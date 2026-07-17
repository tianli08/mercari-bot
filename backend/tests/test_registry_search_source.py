"""Registry-backed scraper search source tests."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_WEBHOOK", "https://discord.com/api/webhooks/123/test")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "123")
os.environ.setdefault("SAVED_CHANNEL_ID", "456")

from src import database, discord_bot, retrieve_utils  # noqa: E402
from src.alert_fanout import ScrapeResult  # noqa: E402
from src.config import settings  # noqa: E402
from src.constants import MERCARI_BASE_URL  # noqa: E402
from src.discord_bot import MercariSendBot, ScrapeWorker  # noqa: E402
from src.listings import ListingRecord, SearchDefinition  # noqa: E402

pytestmark = pytest.mark.asyncio


class FakeDatabaseClient:
    """In-memory database client with the same collection attributes as production."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["registry_search_source_tests"]
        self.listings = self.db["marketplace_listings"]
        self.alerts = self.db["listing_alerts"]
        self.users = self.db["users"]
        self.watchlists = self.db["watchlists"]
        self.destinations = self.db["destinations"]
        self.keyword_registry = self.db["keyword_registry"]
        self.preset_keywords = self.db["preset_keywords"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the same indexes as the production client."""
        await database.DatabaseClient.ensure_indexes(self)


@pytest.fixture
def fake_database(monkeypatch: pytest.MonkeyPatch) -> FakeDatabaseClient:
    """Patch database access to use an in-memory MongoDB fake."""
    fake_client = FakeDatabaseClient()
    monkeypatch.setattr(database, "db_client", fake_client)
    return fake_client


async def _take_queued_searches(cog: MercariSendBot, count: int) -> list[SearchDefinition]:
    """Take a known dispatcher cycle from the queue with a deadlock timeout."""
    return [await asyncio.wait_for(cog.search_queue.get(), timeout=1) for _ in range(count)]


async def _stop_dispatcher(
    dispatcher_task: asyncio.Task[None],
    cog: MercariSendBot,
    pending_items: int,
) -> None:
    """Cancel a dispatcher test task and balance drained queue items."""
    dispatcher_task.cancel()
    for _ in range(pending_items):
        cog.search_queue.task_done()
    await asyncio.gather(dispatcher_task, return_exceptions=True)


async def test_registry_search_definitions_maps_active_entries_in_urgency_order(
    fake_database: FakeDatabaseClient,
) -> None:
    """Active registry entries become Mercari searches in stale-first order."""
    assert await retrieve_utils.registry_search_definitions() == []

    await database.subscribe_keyword("mercari", "never", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.subscribe_keyword("mercari", "old", owner_id="owner-1", watchlist_id="watchlist-2")
    await database.subscribe_keyword("mercari", "new", owner_id="owner-1", watchlist_id="watchlist-3")
    await database.mark_keyword_scraped("mercari", "old", datetime(2025, 1, 1, tzinfo=UTC))
    await database.mark_keyword_scraped("mercari", "new", datetime(2025, 1, 3, tzinfo=UTC))

    searches = await retrieve_utils.registry_search_definitions()

    assert [(search.marketplace, search.filter_name, search.keyword) for search in searches] == [
        ("mercari", "never", "never"),
        ("mercari", "old", "old"),
        ("mercari", "new", "new"),
    ]
    parsed_url = urlparse(searches[1].url)
    assert f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" == MERCARI_BASE_URL
    assert parse_qs(parsed_url.query) == {
        "keyword": ["old"],
        "sort": ["created_time"],
        "order": ["desc"],
    }


async def test_registry_search_definitions_excludes_fully_unsubscribed_entries(
    fake_database: FakeDatabaseClient,
) -> None:
    """Registry entries with no active subscribers are not returned as searches."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["rick owens"],
        destination_id="destination-1",
    )

    assert [search.keyword for search in await retrieve_utils.registry_search_definitions()] == ["rick owens"]

    await database.update_watchlist(watchlist._id, keywords=[])

    assert await retrieve_utils.registry_search_definitions() == []


async def test_process_search_stamps_registry_progress_and_ignores_deleted_entries(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine path stamps completed searches and tolerates entries removed mid-cycle."""
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-1", watchlist_id="watchlist-1")
    search = (await retrieve_utils.registry_search_definitions())[0]
    cog = MercariSendBot(discord_bot=object())
    worker = ScrapeWorker(worker_id=1)
    driver_requests = 0
    scrape_requests = 0

    async def fake_ensure_worker_driver(worker: ScrapeWorker) -> object:
        """Return a driver stand-in without opening Selenium."""
        nonlocal driver_requests
        driver_requests += 1
        return object()

    async def fake_scrape_search_listings(*_args: object) -> dict[str, object]:
        """Return zero listings after simulating a visited page."""
        nonlocal scrape_requests
        scrape_requests += 1
        return {}

    async def fake_fan_out_scrape_results(*_args: object, **_kwargs: object) -> None:
        """Skip delivery for engine-path tests."""
        return None

    monkeypatch.setattr(cog, "_ensure_worker_driver", fake_ensure_worker_driver)
    monkeypatch.setattr(cog, "_scrape_search_listings", fake_scrape_search_listings)
    monkeypatch.setattr(cog, "_fan_out_scrape_results", fake_fan_out_scrape_results)

    await cog._process_search(worker, search)

    stamped_entry = await database.get_registry_entry("mercari", "rick owens")
    assert stamped_entry is not None
    assert stamped_entry.last_scraped_at is not None
    assert stamped_entry.baselined_at is not None
    assert driver_requests == 1
    assert scrape_requests == 1

    first_baselined_at = stamped_entry.baselined_at
    await cog._process_search(worker, search)

    restamped_entry = await database.get_registry_entry("mercari", "rick owens")
    assert restamped_entry is not None
    assert restamped_entry.baselined_at == first_baselined_at
    assert driver_requests == 2
    assert scrape_requests == 2

    await fake_database.keyword_registry.delete_one({"_id": "mercari:rick owens"})
    mark_requests = 0

    async def fake_mark_keyword_scraped(_marketplace: str, _keyword: str) -> None:
        """Record any attempt to stamp the removed queued search."""
        nonlocal mark_requests
        mark_requests += 1

    monkeypatch.setattr(discord_bot, "mark_keyword_scraped", fake_mark_keyword_scraped)

    await cog._process_search(worker, search)

    assert driver_requests == 2
    assert scrape_requests == 2
    assert mark_requests == 0
    assert await database.get_registry_entry("mercari", "rick owens") is None


async def test_process_search_registry_check_fails_open(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient pre-scrape registry read failure does not suppress the scrape."""
    await database.subscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")
    search = (await retrieve_utils.registry_search_definitions())[0]
    cog = MercariSendBot(discord_bot=object())
    worker = ScrapeWorker(worker_id=1)
    scrape_requests = 0
    baseline_flags: list[bool] = []

    async def fail_registry_check(_marketplace: str, _keyword: str) -> None:
        """Simulate a transient registry lookup failure."""
        raise RuntimeError("registry unavailable")

    async def fake_ensure_worker_driver(worker: ScrapeWorker) -> object:
        """Return a driver stand-in without opening Selenium."""
        return object()

    async def fake_scrape_search_listings(*_args: object) -> dict[str, object]:
        """Record that scraping proceeded after the failed guard lookup."""
        nonlocal scrape_requests
        scrape_requests += 1
        return {}

    async def fake_fan_out_scrape_results(
        *_args: object,
        is_baseline_scan: bool,
    ) -> None:
        """Capture that a failed registry read does not suppress alerts."""
        baseline_flags.append(is_baseline_scan)

    monkeypatch.setattr(database, "get_registry_entry", fail_registry_check)
    monkeypatch.setattr(cog, "_ensure_worker_driver", fake_ensure_worker_driver)
    monkeypatch.setattr(cog, "_scrape_search_listings", fake_scrape_search_listings)
    monkeypatch.setattr(cog, "_fan_out_scrape_results", fake_fan_out_scrape_results)

    await cog._process_search(worker, search)

    assert scrape_requests == 1
    assert baseline_flags == [False]


async def test_process_search_persists_before_any_legacy_channel_resolution(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scrape persistence no longer depends on a legacy Discord channel being available."""
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-1", watchlist_id="watchlist-1")
    search = (await retrieve_utils.registry_search_definitions())[0]
    listing = ListingRecord(
        marketplace="mercari",
        item_id="m123",
        canonical_id="mercari:m123",
        url="https://jp.mercari.com/item/m123",
        title="Listing m123",
        image_url="https://example.com/image.jpg",
        raw_content="Listing body JPY 1200",
        price_text="JPY 1200",
        price_value=1200,
        currency="JPY",
        status="active",
        matched_filters={"rick owens"},
        matched_keywords={"rick owens"},
    )
    cog = MercariSendBot(discord_bot=object())
    worker = ScrapeWorker(worker_id=1)
    fanout_results: list[ScrapeResult] = []

    async def fake_ensure_worker_driver(worker: ScrapeWorker) -> object:
        """Return a driver stand-in without opening Selenium."""
        return object()

    async def fake_scrape_search_listings(*_args: object) -> dict[str, ListingRecord]:
        """Return one scraped listing."""
        return {listing.canonical_id: listing}

    async def fake_fan_out_scrape_results(
        scrape_results: list[ScrapeResult],
        *_args: object,
        **_kwargs: object,
    ) -> None:
        """Capture the post-persistence seam data."""
        fanout_results.extend(scrape_results)

    def fail_channel_resolution(_filter_name: str) -> None:
        raise AssertionError("legacy channel resolution should happen only inside fan-out fallback")

    monkeypatch.setattr(cog, "_ensure_worker_driver", fake_ensure_worker_driver)
    monkeypatch.setattr(cog, "_scrape_search_listings", fake_scrape_search_listings)
    monkeypatch.setattr(cog, "_fan_out_scrape_results", fake_fan_out_scrape_results)
    monkeypatch.setattr(cog, "get_channel_for_filter", fail_channel_resolution)

    await cog._process_search(worker, search)

    listing_document = await fake_database.listings.find_one({"_id": listing.canonical_id})
    assert listing_document is not None
    assert len(fanout_results) == 1
    assert fanout_results[0].is_new_listing is True


@pytest.mark.parametrize(
    ("send_initial_items", "is_new_listing", "is_baseline_scan", "expected"),
    [
        (False, True, True, False),
        (True, True, True, True),
        (False, True, False, True),
        (False, False, False, False),
        (True, False, True, False),
    ],
)
async def test_per_keyword_baseline_gate(
    send_initial_items: bool,
    is_new_listing: bool,
    is_baseline_scan: bool,
    expected: bool,
) -> None:
    """The listing gate combines global newness with the current keyword baseline phase."""
    cog = MercariSendBot(discord_bot=object(), send_initial_items=send_initial_items)

    assert (
        cog._should_send_listing_message(
            is_new_listing,
            is_baseline_scan=is_baseline_scan,
        )
        is expected
    )


async def test_vanished_registry_entry_during_baseline_stamp_logs_and_does_not_raise(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A keyword removed during its scrape cannot break the worker's baseline completion path."""
    await database.subscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")
    search = (await retrieve_utils.registry_search_definitions())[0]
    info_logs: list[tuple[str, dict[str, object]]] = []

    class RecordingLogger:
        """Minimal logger that records structured info calls."""

        def info(self, message: str, *, context: dict[str, object]) -> None:
            """Record one structured info log."""
            info_logs.append((message, context))

    async def fail_baseline_stamp(_marketplace: str, _keyword: str) -> None:
        """Simulate a registry entry disappearing between fan-out and baseline stamp."""
        raise database.KeywordRegistryEntryNotFoundError("mercari:julius")

    monkeypatch.setattr(discord_bot, "mark_keyword_baselined", fail_baseline_stamp)

    await MercariSendBot._mark_registry_search_baselined(
        search,
        RecordingLogger(),
        listings=0,
    )

    assert info_logs == [
        (
            "Registry entry disappeared before keyword baseline could be stamped",
            {"marketplace": "mercari", "keyword": "julius"},
        )
    ]


async def test_registry_search_definitions_reflects_watchlist_changes_between_fetches(
    fake_database: FakeDatabaseClient,
) -> None:
    """Watchlist edits change the next registry-backed search fetch without a restart."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["rick owens"],
        destination_id="destination-1",
    )

    assert [search.keyword for search in await retrieve_utils.registry_search_definitions()] == ["rick owens"]

    await database.update_watchlist(watchlist._id, keywords=["julius"])

    assert [search.keyword for search in await retrieve_utils.registry_search_definitions()] == ["julius"]


async def test_dispatcher_picks_up_registry_additions_across_cycles(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second dispatcher cycle enqueues keywords added after the first cycle."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["alpha"],
        destination_id="destination-1",
    )
    monkeypatch.setattr(settings, "cycle_pause_seconds", 0.0)
    change_logs: list[dict[str, object]] = []

    def capture_dispatcher_info(message: str, *, context: dict[str, object] | None = None) -> None:
        """Capture registry change logs while ignoring other dispatcher info messages."""
        if message == "Registry search set changed":
            change_logs.append(context or {})

    monkeypatch.setattr(discord_bot.dispatcher_logger, "info", capture_dispatcher_info)
    cog = MercariSendBot(discord_bot=object())
    dispatcher_task = asyncio.create_task(cog._run_dispatcher())
    pending_items = 0
    try:
        first_cycle = await _take_queued_searches(cog, 1)
        pending_items = len(first_cycle)
        assert [search.keyword for search in first_cycle] == ["alpha"]

        await database.update_watchlist(watchlist._id, keywords=["alpha", "beta"])
        for _ in range(pending_items):
            cog.search_queue.task_done()
        pending_items = 0

        second_cycle = await _take_queued_searches(cog, 2)
        pending_items = len(second_cycle)
        assert {search.keyword for search in second_cycle} == {"alpha", "beta"}
    finally:
        await _stop_dispatcher(dispatcher_task, cog, pending_items)

    assert change_logs == [
        {"cycle": 1, "added": ["alpha"], "removed": [], "total": 1},
        {"cycle": 2, "added": ["beta"], "removed": [], "total": 2},
    ]


async def test_dispatcher_drops_registry_removals_across_cycles(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second dispatcher cycle omits keywords removed after the first cycle."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["alpha", "beta"],
        destination_id="destination-1",
    )
    monkeypatch.setattr(settings, "cycle_pause_seconds", 0.0)
    change_logs: list[dict[str, object]] = []

    def capture_dispatcher_info(message: str, *, context: dict[str, object] | None = None) -> None:
        """Capture registry change logs while ignoring other dispatcher info messages."""
        if message == "Registry search set changed":
            change_logs.append(context or {})

    monkeypatch.setattr(discord_bot.dispatcher_logger, "info", capture_dispatcher_info)
    cog = MercariSendBot(discord_bot=object())
    dispatcher_task = asyncio.create_task(cog._run_dispatcher())
    pending_items = 0
    try:
        first_cycle = await _take_queued_searches(cog, 2)
        pending_items = len(first_cycle)
        assert {search.keyword for search in first_cycle} == {"alpha", "beta"}

        await database.update_watchlist(watchlist._id, keywords=["alpha"])
        for _ in range(pending_items):
            cog.search_queue.task_done()
        pending_items = 0

        second_cycle = await _take_queued_searches(cog, 1)
        pending_items = len(second_cycle)
        assert [search.keyword for search in second_cycle] == ["alpha"]
    finally:
        await _stop_dispatcher(dispatcher_task, cog, pending_items)

    assert change_logs == [
        {"cycle": 1, "added": ["alpha", "beta"], "removed": [], "total": 2},
        {"cycle": 2, "added": [], "removed": ["beta"], "total": 1},
    ]


async def test_dispatcher_reuses_previous_searches_after_refresh_failure(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed second registry read reuses the first cycle without a retry stall."""
    await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["alpha"],
        destination_id="destination-1",
    )
    monkeypatch.setattr(settings, "cycle_pause_seconds", 0.0)
    original_registry_search_definitions = retrieve_utils.registry_search_definitions
    refresh_count = 0
    refresh_failures: list[tuple[str, BaseException, dict[str, object]]] = []

    async def flaky_registry_search_definitions(marketplace: str = "mercari") -> list[SearchDefinition]:
        """Return one registry snapshot and fail the next refresh."""
        nonlocal refresh_count
        refresh_count += 1
        if refresh_count == 1:
            return await original_registry_search_definitions(marketplace)
        raise RuntimeError("registry unavailable")

    def capture_log_exception(
        _logger: object,
        message: str,
        exc: BaseException,
        **context: object,
    ) -> None:
        """Capture dispatcher exception logs for fallback assertions."""
        refresh_failures.append((message, exc, context))

    monkeypatch.setattr(retrieve_utils, "registry_search_definitions", flaky_registry_search_definitions)
    monkeypatch.setattr(discord_bot, "log_exception", capture_log_exception)
    cog = MercariSendBot(discord_bot=object())
    dispatcher_task = asyncio.create_task(cog._run_dispatcher())
    pending_items = 0
    try:
        first_cycle = await _take_queued_searches(cog, 1)
        pending_items = len(first_cycle)
        assert [search.keyword for search in first_cycle] == ["alpha"]

        for _ in range(pending_items):
            cog.search_queue.task_done()
        pending_items = 0

        second_cycle = await _take_queued_searches(cog, 1)
        pending_items = len(second_cycle)
        assert [search.keyword for search in second_cycle] == ["alpha"]
    finally:
        await _stop_dispatcher(dispatcher_task, cog, pending_items)

    assert refresh_count == 2
    assert len(refresh_failures) == 1
    message, exception, context = refresh_failures[0]
    assert message == "Registry refresh failed; reusing previous search set"
    assert isinstance(exception, RuntimeError)
    assert context == {"cycle": 2, "reused": 1}


async def test_successful_empty_refresh_replaces_previous_search_set(
    fake_database: FakeDatabaseClient,
) -> None:
    """An intentionally emptied registry is not mistaken for a transient refresh failure."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["alpha"],
        destination_id="destination-1",
    )
    cog = MercariSendBot(discord_bot=object())
    cog.searches = await retrieve_utils.registry_search_definitions()

    await database.update_watchlist(watchlist._id, keywords=[])

    assert await cog._load_cycle_searches(2) == []
    assert cog.searches == []
