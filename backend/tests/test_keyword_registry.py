"""Keyword registry persistence tests."""

from __future__ import annotations

import asyncio
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
    assert entry.baselined_at is None
    assert [subscriber.watchlist_id for subscriber in entry.subscribers] == ["watchlist-1"]


async def test_unsubscribing_one_watchlist_leaves_other_subscriber(fake_database: FakeDatabaseClient) -> None:
    """Two watchlists share one registry entry and unsubscribe independently."""
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.subscribe_keyword("mercari", "rick owens", owner_id="owner-2", watchlist_id="watchlist-2")
    scraped_at = datetime(2025, 1, 1, tzinfo=UTC)
    baselined_at = datetime(2025, 1, 2, tzinfo=UTC)
    await database.mark_keyword_scraped("mercari", "rick owens", scraped_at)
    await database.mark_keyword_baselined("mercari", "rick owens", baselined_at)

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
    assert entry.last_scraped_at == scraped_at
    assert entry.baselined_at == baselined_at


async def test_unsubscribing_last_subscriber_deletes_entry(fake_database: FakeDatabaseClient) -> None:
    """Removing the last subscriber deletes the registry document."""
    await database.subscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")

    await database.unsubscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.unsubscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="missing")

    assert await database.get_registry_entry("mercari", "julius") is None
    leftover = await fake_database.keyword_registry.find({"keyword": "julius"}).to_list(length=None)
    assert leftover == []


async def test_resubscribing_after_deletion_creates_fresh_unbaselined_entry(
    fake_database: FakeDatabaseClient,
) -> None:
    """A registry entry deleted at zero subscribers gets a fresh baseline state when re-added."""
    await database.subscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")
    await database.mark_keyword_baselined("mercari", "julius")

    await database.unsubscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")
    entry = await database.subscribe_keyword(
        "mercari",
        "julius",
        owner_id="owner-1",
        watchlist_id="watchlist-1",
    )

    assert entry.baselined_at is None


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


async def test_mark_keyword_baselined_sets_stable_timestamp_and_updated_at(
    fake_database: FakeDatabaseClient,
) -> None:
    """The first baseline timestamp is persisted and later stamp attempts leave it unchanged."""
    await database.subscribe_keyword(
        "mercari",
        "rick owens",
        owner_id="owner-1",
        watchlist_id="watchlist-1",
    )
    old_updated_at = datetime(2024, 1, 1, tzinfo=UTC)
    await fake_database.keyword_registry.update_one(
        {"_id": "mercari:rick owens"},
        {"$set": {"updated_at": old_updated_at}},
    )
    first_baseline = datetime(2025, 1, 1, tzinfo=UTC)
    second_baseline = datetime(2025, 1, 2, tzinfo=UTC)

    marked_entry = await database.mark_keyword_baselined("mercari", "rick owens", first_baseline)
    repeated_entry = await database.mark_keyword_baselined("mercari", "rick owens", second_baseline)

    assert marked_entry.baselined_at == first_baseline
    assert marked_entry.updated_at > old_updated_at
    assert repeated_entry.baselined_at == first_baseline
    assert repeated_entry.updated_at == marked_entry.updated_at


async def test_mark_keyword_baselined_raises_for_missing_entry(fake_database: FakeDatabaseClient) -> None:
    """Baseline stamping distinguishes a missing entry from an already-stamped entry."""
    with pytest.raises(database.KeywordRegistryEntryNotFoundError):
        await database.mark_keyword_baselined("mercari", "missing")


async def test_registry_document_without_baseline_field_hydrates_as_unbaselined(
    fake_database: FakeDatabaseClient,
) -> None:
    """Legacy registry documents without the new field remain readable."""
    await database.subscribe_keyword("mercari", "legacy", owner_id="owner-1", watchlist_id="watchlist-1")
    await fake_database.keyword_registry.update_one(
        {"_id": "mercari:legacy"},
        {"$unset": {"baselined_at": ""}},
    )

    entry = await database.get_registry_entry("mercari", "legacy")

    assert entry is not None
    assert entry.baselined_at is None


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
    baselined_at = datetime(2025, 1, 2, tzinfo=UTC)
    await database.mark_keyword_scraped("mercari", "rick owens", scraped_at)
    await database.mark_keyword_baselined("mercari", "rick owens", baselined_at)
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
    assert rick_entry.baselined_at == baselined_at
    assert julius_entry.baselined_at is None
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


async def test_aborted_keyword_add_rolls_back_watchlist_and_registry(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed registry sync leaves the watchlist and registry at the pre-image."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Rollback Add",
        keywords=["keep"],
        destination_id="destination-1",
    )

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected registry failure")

    monkeypatch.setattr(database, "sync_watchlist_subscriptions", boom)

    with pytest.raises(RuntimeError, match="injected registry failure"):
        await database.add_watchlist_keywords_for_owner(watchlist._id, "owner-1", ["new"])

    stored = await database.get_watchlist_by_id(watchlist._id)
    assert stored is not None
    assert stored.keywords == ["keep"]
    assert await database.get_registry_entry("mercari", "keep") is not None
    assert await database.get_registry_entry("mercari", "new") is None


async def test_aborted_keyword_remove_leaves_subscriber_in_place(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed registry unsubscribe leaves both the keyword and subscriber visible."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Rollback Remove",
        keywords=["keep"],
        destination_id="destination-1",
    )

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected unsubscribe failure")

    monkeypatch.setattr(database, "sync_watchlist_subscriptions", boom)

    with pytest.raises(RuntimeError, match="injected unsubscribe failure"):
        await database.remove_watchlist_keyword_for_owner(watchlist._id, "owner-1", "keep")

    stored = await database.get_watchlist_by_id(watchlist._id)
    assert stored is not None
    assert stored.keywords == ["keep"]
    entry = await database.get_registry_entry("mercari", "keep")
    assert entry is not None
    assert entry.subscriber_count == 1


async def test_aborted_last_subscriber_remove_does_not_leave_empty_registry_document(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aborting prune after the occupancy update does not persist a zero-subscriber row."""
    await database.subscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected prune failure")

    monkeypatch.setattr(fake_database.keyword_registry, "delete_one", boom)

    with pytest.raises(RuntimeError, match="injected prune failure"):
        await database.unsubscribe_keyword("mercari", "julius", owner_id="owner-1", watchlist_id="watchlist-1")

    leftover = await fake_database.keyword_registry.find({"keyword": "julius"}).to_list(length=None)
    assert len(leftover) == 1
    assert leftover[0]["subscriber_count"] == 1
    assert leftover[0]["subscribers"] == [{"owner_id": "owner-1", "watchlist_id": "watchlist-1"}]


async def test_overlapping_shared_keyword_mutations_keep_occupancy_correct(
    fake_database: FakeDatabaseClient,
) -> None:
    """Concurrent add/remove on one keyword leaves exactly the surviving subscriber."""
    first = await database.create_watchlist(
        owner_id="owner-1",
        name="First",
        keywords=["shared"],
        destination_id="destination-1",
    )
    second = await database.create_watchlist(
        owner_id="owner-2",
        name="Second",
        keywords=[],
        destination_id="destination-2",
    )

    await asyncio.gather(
        database.add_watchlist_keywords_for_owner(second._id, "owner-2", ["shared"]),
        database.remove_watchlist_keyword_for_owner(first._id, "owner-1", "shared"),
    )

    first_stored = await database.get_watchlist_by_id(first._id)
    second_stored = await database.get_watchlist_by_id(second._id)
    entry = await database.get_registry_entry("mercari", "shared")
    assert first_stored is not None and first_stored.keywords == []
    assert second_stored is not None and second_stored.keywords == ["shared"]
    assert entry is not None
    assert entry.subscriber_count == 1
    assert [subscriber.watchlist_id for subscriber in entry.subscribers] == [second._id]
    active = await database.list_active_registry_entries("mercari")
    assert [item.keyword for item in active] == ["shared"]


async def test_concurrent_duplicate_adds_do_not_double_count_subscriber(
    fake_database: FakeDatabaseClient,
) -> None:
    """Two concurrent adds of the same watchlist/keyword pair end at count 1."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Duplicates",
        keywords=[],
        destination_id="destination-1",
    )

    await asyncio.gather(
        database.add_watchlist_keywords_for_owner(watchlist._id, "owner-1", ["same"]),
        database.add_watchlist_keywords_for_owner(watchlist._id, "owner-1", ["same"]),
    )

    stored = await database.get_watchlist_by_id(watchlist._id)
    entry = await database.get_registry_entry("mercari", "same")
    assert stored is not None and stored.keywords == ["same"]
    assert entry is not None
    assert entry.subscriber_count == 1
    assert [subscriber.watchlist_id for subscriber in entry.subscribers] == [watchlist._id]


async def test_disabled_watchlist_keyword_add_does_not_create_demand_until_enable(
    fake_database: FakeDatabaseClient,
) -> None:
    """Keywords stored while disabled occupy the registry only after an atomic enable."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Paused",
        keywords=[],
        destination_id="destination-1",
        enabled=False,
    )
    updated = await database.add_watchlist_keywords_for_owner(watchlist._id, "owner-1", ["later"])
    assert updated.keywords == ["later"]
    assert await database.get_registry_entry("mercari", "later") is None

    enabled = await database.set_watchlist_enabled(watchlist._id, True)
    assert enabled.enabled is True
    assert await database.get_registry_entry("mercari", "later") is not None


async def test_aborted_enable_does_not_subscribe_stored_keywords(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed enable rolls back both the flag and any registry occupancy."""
    watchlist = await database.create_watchlist(
        owner_id="owner-1",
        name="Paused Enable",
        keywords=["later"],
        destination_id="destination-1",
        enabled=False,
    )

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected enable failure")

    monkeypatch.setattr(database, "sync_watchlist_subscriptions", boom)

    with pytest.raises(RuntimeError, match="injected enable failure"):
        await database.set_watchlist_enabled(watchlist._id, True)

    stored = await database.get_watchlist_by_id(watchlist._id)
    assert stored is not None
    assert stored.enabled is False
    assert stored.keywords == ["later"]
    assert await database.get_registry_entry("mercari", "later") is None
    leftover = await fake_database.keyword_registry.find({"keyword": "later"}).to_list(length=None)
    assert leftover == []


async def test_duplicate_name_update_does_not_change_registry(
    fake_database: FakeDatabaseClient,
) -> None:
    """A duplicate-name error aborts before a partial registry update can commit."""
    first = await database.create_watchlist(
        owner_id="owner-1",
        name="Alpha",
        keywords=["keep"],
        destination_id="destination-1",
    )
    second = await database.create_watchlist(
        owner_id="owner-1",
        name="Beta",
        keywords=["other"],
        destination_id="destination-2",
    )

    with pytest.raises(database.WatchlistNameExistsError):
        await database.update_watchlist(second._id, name="Alpha", keywords=["changed"])

    stored = await database.get_watchlist_by_id(second._id)
    assert stored is not None
    assert stored.name == "Beta"
    assert stored.keywords == ["other"]
    stored_first = await database.get_watchlist_by_id(first._id)
    assert stored_first is not None
    assert stored_first.keywords == ["keep"]
    assert await database.get_registry_entry("mercari", "keep") is not None
    assert await database.get_registry_entry("mercari", "other") is not None
    assert await database.get_registry_entry("mercari", "changed") is None


async def test_keyword_mutations_fail_closed_without_transaction_support(
    fake_database: FakeDatabaseClient,
) -> None:
    """Standalone clients that cannot start transactions do not fall back to sequential writes."""

    class StandaloneClient:
        """Client without session support."""

    fake_database.client = StandaloneClient()
    with pytest.raises(database.KeywordMutationTransactionRequiredError):
        await database.create_watchlist(
            owner_id="owner-1",
            name="Standalone",
            keywords=["rick owens"],
            destination_id="destination-1",
        )
    assert await fake_database.watchlists.find_one({"name": "Standalone"}) is None
