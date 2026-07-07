"""Keyword registry persistence tests."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_WEBHOOK", "https://discord.com/api/webhooks/123/test")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")

from src import database  # noqa: E402

pytestmark = pytest.mark.asyncio


class FakeDatabaseClient:
    """In-memory database client with the same collection attributes as production."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["keyword_registry_tests"]
        self.listings = self.db["marketplace_listings"]
        self.alerts = self.db["listing_alerts"]
        self.users = self.db["users"]
        self.watchlists = self.db["watchlists"]
        self.destinations = self.db["destinations"]
        self.keyword_registry = self.db["keyword_registry"]
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


async def test_subscribing_same_watchlist_is_idempotent(fake_database: FakeDatabaseClient) -> None:
    """Subscribing the same watchlist twice stores one subscriber."""
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-1", watchlist_id="watchlist-1")

    entry = await database.subscribe_keyword(
        "mercari",
        "rick owens",
        owner_id="owner-1",
        watchlist_id="watchlist-1",
    )

    assert entry.subscriber_count == 1
    assert [subscriber.watchlist_id for subscriber in entry.subscribers] == ["watchlist-1"]


async def test_unsubscribing_one_watchlist_leaves_other_subscriber(fake_database: FakeDatabaseClient) -> None:
    """Two watchlists share one registry entry and unsubscribe independently."""
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-2", watchlist_id="watchlist-2")

    entry = await database.get_registry_entry("mercari", "rick owens")
    assert entry is not None
    assert entry.subscriber_count == 2

    await database.unsubscribe_keyword("mercari", "rick owens", owner_id="owner-1", watchlist_id="watchlist-1")

    entry = await database.get_registry_entry("mercari", "rick owens")
    assert entry is not None
    assert entry.subscriber_count == 1
    assert [(subscriber.owner_id, subscriber.watchlist_id) for subscriber in entry.subscribers] == [
        ("owner-2", "watchlist-2")
    ]


async def test_unsubscribing_last_subscriber_deletes_entry(fake_database: FakeDatabaseClient) -> None:
    """Removing the last subscriber deletes the registry document."""
    await database.subscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")

    await database.unsubscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.unsubscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="missing")

    assert await database.get_registry_entry("mercari", "julius") is None


async def test_update_watchlist_keyword_edit_syncs_registry(fake_database: FakeDatabaseClient) -> None:
    """Updating watchlist keywords adds and removes registry subscriptions."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Designers",
        keywords=["rick owens", "julius"],
        destination_id="destination-1",
    )

    await database.update_watchlist(watchlist._id, keywords=["julius", "margiela"])

    assert await database.get_registry_entry("mercari", "rick owens") is None
    assert await database.get_registry_entry("mercari", "julius") is not None
    assert await database.get_registry_entry("mercari", "margiela") is not None


async def test_disable_and_reenable_watchlist_syncs_registry(fake_database: FakeDatabaseClient) -> None:
    """Disabling removes subscriptions and re-enabling restores them."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Archive",
        keywords=["rick owens", "julius"],
        destination_id="destination-1",
    )

    await database.set_watchlist_enabled(watchlist._id, False)
    assert await database.get_registry_entry("mercari", "rick owens") is None
    assert await database.get_registry_entry("mercari", "julius") is None

    await database.set_watchlist_enabled(watchlist._id, True)
    assert await database.get_registry_entry("mercari", "rick owens") is not None
    assert await database.get_registry_entry("mercari", "julius") is not None


async def test_delete_watchlist_removes_all_subscriptions(fake_database: FakeDatabaseClient) -> None:
    """Deleting a watchlist removes its registry subscriptions everywhere."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Cleanup",
        keywords=["rick owens"],
        destination_id="destination-1",
    )
    await database.subscribe_keyword(
        "mercari",
        "orphaned keyword",
        owner_id=watchlist.owner_id,
        watchlist_id=watchlist._id,
    )

    deleted = await database.delete_watchlist(watchlist._id)

    assert deleted is True
    assert await database.get_registry_entry("mercari", "rick owens") is None
    assert await database.get_registry_entry("mercari", "orphaned keyword") is None


async def test_list_active_registry_entries_orders_and_filters_stale_entries(
    fake_database: FakeDatabaseClient,
) -> None:
    """Active entries list never-scraped keywords first and filters stale timestamps."""
    await database.subscribe_keyword("mercari", "never", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.subscribe_keyword("mercari", "old", owner_id="owner-1", watchlist_id="watchlist-2")
    await database.subscribe_keyword("mercari", "new", owner_id="owner-1", watchlist_id="watchlist-3")
    old_timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    new_timestamp = datetime(2025, 1, 3, tzinfo=UTC)
    await database.mark_keyword_scraped("mercari", "old", old_timestamp)
    await database.mark_keyword_scraped("mercari", "new", new_timestamp)

    entries = await database.list_active_registry_entries("mercari")
    stale_entries = await database.list_active_registry_entries(
        "mercari",
        stale_before=datetime(2025, 1, 2, tzinfo=UTC),
    )

    assert [entry.keyword for entry in entries] == ["never", "old", "new"]
    assert [entry.keyword for entry in stale_entries] == ["never", "old"]


async def test_rebuild_keyword_registry_reconciles_projection(fake_database: FakeDatabaseClient) -> None:
    """Rebuilding restores desired entries, removes orphans, and preserves scrape history."""
    first_watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="First",
        keywords=["rick owens", "julius"],
        destination_id="destination-1",
    )
    second_watchlist = await database.create_watchlist(
        owner_id="owner-2",
        name="Second",
        keywords=["rick owens"],
        destination_id="destination-2",
    )

    await fake_database.keyword_registry.delete_many({})
    assert await database.rebuild_keyword_registry("mercari") == 2
    scraped_at = datetime(2025, 1, 1, tzinfo=UTC)
    await database.mark_keyword_scraped("mercari", "rick owens", scraped_at)
    await database.subscribe_keyword("mercari", "orphan", owner_id="owner-3", watchlist_id="watchlist-3")
    await fake_database.keyword_registry.update_one(
        {"_id": "mercari:rick owens"},
        {
            "$set": {
                "subscribers": [{"owner_id": first_watchlist.owner_id, "watchlist_id": first_watchlist._id}],
                "subscriber_count": 1,
            }
        },
    )

    assert await database.rebuild_keyword_registry("mercari") == 2

    rick_entry = await database.get_registry_entry("mercari", "rick owens")
    julius_entry = await database.get_registry_entry("mercari", "julius")
    assert rick_entry is not None
    assert julius_entry is not None
    assert rick_entry.subscriber_count == 2
    assert {subscriber.watchlist_id for subscriber in rick_entry.subscribers} == {
        first_watchlist._id,
        second_watchlist._id,
    }
    assert rick_entry.last_scraped_at == scraped_at
    assert await database.get_registry_entry("mercari", "orphan") is None


async def test_watchlist_keyword_normalization_matches_registry(fake_database: FakeDatabaseClient) -> None:
    """Watchlist keywords and direct registry keywords normalize to the same entry."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Spacing",
        keywords=["  Rick   Owens "],
        destination_id="destination-1",
    )
    await database.subscribe_keyword(
        "mercari",
        "rick owens",
        owner_id=watchlist.owner_id,
        watchlist_id=watchlist._id,
    )

    entry = await database.get_registry_entry("mercari", "rick owens")

    assert watchlist.keywords == ["rick owens"]
    assert entry is not None
    assert entry._id == "mercari:rick owens"
    assert entry.subscriber_count == 1
