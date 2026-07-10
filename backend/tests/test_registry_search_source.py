"""Registry-backed scraper search source tests."""

from __future__ import annotations

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

from src import database, retrieve_utils  # noqa: E402
from src.alert_fanout import ScrapeResult  # noqa: E402
from src.constants import MERCARI_BASE_URL  # noqa: E402
from src.discord_bot import MercariSendBot, ScrapeWorker  # noqa: E402
from src.listings import ListingRecord  # noqa: E402

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

    async def fake_ensure_worker_driver(worker: ScrapeWorker) -> object:
        """Return a driver stand-in without opening Selenium."""
        return object()

    async def fake_scrape_search_listings(*_args: object) -> dict[str, object]:
        """Return zero listings after simulating a visited page."""
        return {}

    async def fake_fan_out_scrape_results(*_args: object) -> None:
        """Skip delivery for engine-path tests."""
        return None

    monkeypatch.setattr(cog, "_ensure_worker_driver", fake_ensure_worker_driver)
    monkeypatch.setattr(cog, "_scrape_search_listings", fake_scrape_search_listings)
    monkeypatch.setattr(cog, "_fan_out_scrape_results", fake_fan_out_scrape_results)

    await cog._process_search(worker, search)

    stamped_entry = await database.get_registry_entry("mercari", "rick owens")
    assert stamped_entry is not None
    assert stamped_entry.last_scraped_at is not None

    await fake_database.keyword_registry.delete_one({"_id": "mercari:rick owens"})

    await cog._process_search(worker, search)


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

    async def fake_fan_out_scrape_results(scrape_results: list[ScrapeResult], *_args: object) -> None:
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
