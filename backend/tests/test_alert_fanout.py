"""Tenant fan-out delivery tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "123")
os.environ.setdefault("SAVED_CHANNEL_ID", "456")

from src import alert_fanout, database  # noqa: E402
from src.destinations import DestinationRecord  # noqa: E402
from src.listings import ListingRecord  # noqa: E402
from src.watchlists import WatchlistRecord  # noqa: E402

pytestmark = pytest.mark.asyncio

OBSERVED_AT = datetime(2025, 1, 1, tzinfo=UTC)


class FakeDatabaseClient:
    """In-memory database client with the same collection attributes as production."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["alert_fanout_tests"]
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


class RecordingDestinationSender:
    """Destination sender test double that records attempts and can fail selected destinations."""

    def __init__(self, failing_destination_ids: set[str] | None = None) -> None:
        """Initialize the recording sender."""
        self.failing_destination_ids = failing_destination_ids or set()
        self.attempts: list[tuple[str, str]] = []
        self.sent: list[tuple[str, str]] = []

    async def __call__(self, destination: DestinationRecord, listing: ListingRecord) -> None:
        """Record or fail one destination delivery attempt."""
        self.attempts.append((destination._id, listing.canonical_id))
        if destination._id in self.failing_destination_ids:
            raise RuntimeError(f"send failed for {destination._id}")
        self.sent.append((destination._id, listing.canonical_id))


@pytest.fixture
def fake_database(monkeypatch: pytest.MonkeyPatch) -> FakeDatabaseClient:
    """Patch database access to use an in-memory MongoDB fake."""
    fake_client = FakeDatabaseClient()
    monkeypatch.setattr(database, "db_client", fake_client)
    return fake_client


def build_listing(item_id: str = "m123", *, price_value: int = 1200) -> ListingRecord:
    """Build a canonical listing for fan-out tests."""
    return ListingRecord(
        marketplace="mercari",
        item_id=item_id,
        canonical_id=f"mercari:{item_id}",
        url=f"https://jp.mercari.com/item/{item_id}",
        title=f"Listing {item_id}",
        image_url="https://example.com/image.jpg",
        raw_content=f"Listing body JPY {price_value}",
        price_text=f"JPY {price_value}",
        price_value=price_value,
        currency="JPY",
        status="active",
        matched_filters={"rick owens"},
        matched_keywords={"rick owens"},
    )


async def run_fanout(
    listing: ListingRecord,
    sender: RecordingDestinationSender,
    *,
    keyword: str = "rick owens",
    is_new_listing: bool = True,
    should_send_listing: Callable[[bool], bool] | None = None,
    legacy_alerts_enabled: bool = True,
    legacy_target_factory: Callable[[], alert_fanout.LegacyDeliveryTarget | None] | None = None,
) -> None:
    """Run tenant fan-out with test defaults."""
    should_send = should_send_listing if should_send_listing is not None else lambda is_new: is_new
    await alert_fanout.fan_out_listing_alerts(
        marketplace="mercari",
        keyword=keyword,
        scrape_results=[alert_fanout.ScrapeResult(listing=listing, is_new_listing=is_new_listing)],
        should_send_listing=should_send,
        observed_at=OBSERVED_AT,
        destination_sender=sender,
        legacy_alerts_enabled=legacy_alerts_enabled,
        legacy_target_factory=legacy_target_factory,
    )


async def create_destination(owner_id: str, label: str) -> DestinationRecord:
    """Create a valid Discord webhook destination for tests."""
    return await database.create_destination(
        owner_id=owner_id,
        webhook_url=f"https://discord.com/api/webhooks/123/{owner_id}-{label}",
        label=label,
    )


async def test_fanout_delivers_to_each_matching_destination_with_owner_metadata(
    fake_database: FakeDatabaseClient,
) -> None:
    """A new listing fans out to every enabled matching subscriber destination."""
    first_destination = await create_destination("owner-1", "main")
    second_destination = await create_destination("owner-2", "main")
    await database.create_watchlist(
        owner_id="owner-1",
        name="First",
        keywords=["rick owens"],
        destination_id=first_destination._id,
    )
    await database.create_watchlist(
        owner_id="owner-2",
        name="Second",
        keywords=["rick owens"],
        destination_id=second_destination._id,
    )
    listing = build_listing()
    sender = RecordingDestinationSender()

    await run_fanout(listing, sender)

    assert set(sender.sent) == {
        (first_destination._id, listing.canonical_id),
        (second_destination._id, listing.canonical_id),
    }
    documents = await fake_database.alerts.find({}).to_list(length=None)
    assert {
        (document["destination_id"], document["owner_id"], document["listing_id"], document["status"])
        for document in documents
    } == {
        (first_destination._id, "owner-1", listing.canonical_id, "sent"),
        (second_destination._id, "owner-2", listing.canonical_id, "sent"),
    }


async def test_price_filter_skip_for_one_watchlist_does_not_block_another(
    fake_database: FakeDatabaseClient,
) -> None:
    """A listing that fails one watchlist filter can still deliver to another watchlist."""
    low_price_destination = await create_destination("owner-1", "low")
    matching_destination = await create_destination("owner-2", "match")
    await database.create_watchlist(
        owner_id="owner-1",
        name="Too Low",
        keywords=["rick owens"],
        filters={"max_price": 1000},
        destination_id=low_price_destination._id,
    )
    await database.create_watchlist(
        owner_id="owner-2",
        name="Matches",
        keywords=["rick owens"],
        filters={"max_price": 2000},
        destination_id=matching_destination._id,
    )
    listing = build_listing(price_value=1200)
    sender = RecordingDestinationSender()

    await run_fanout(listing, sender)

    assert sender.sent == [(matching_destination._id, listing.canonical_id)]
    assert await fake_database.alerts.count_documents({}) == 1


async def test_duplicate_destination_across_watchlists_sends_once(
    fake_database: FakeDatabaseClient,
) -> None:
    """Two matching watchlists pointing at one destination produce one reserved send."""
    destination = await create_destination("owner-1", "main")
    await database.create_watchlist(
        owner_id="owner-1",
        name="First",
        keywords=["rick owens"],
        destination_id=destination._id,
    )
    await database.create_watchlist(
        owner_id="owner-1",
        name="Second",
        keywords=["rick owens"],
        destination_id=destination._id,
    )
    listing = build_listing()
    sender = RecordingDestinationSender()

    await run_fanout(listing, sender)

    assert sender.sent == [(destination._id, listing.canonical_id)]
    assert await fake_database.alerts.count_documents({}) == 1


async def test_duplicate_destination_failure_is_not_retried_in_same_fanout(
    fake_database: FakeDatabaseClient,
) -> None:
    """A failed shared destination is retried in a later cycle, not by duplicate routes."""
    destination = await create_destination("owner-1", "main")
    await database.create_watchlist(
        owner_id="owner-1",
        name="First",
        keywords=["rick owens"],
        destination_id=destination._id,
    )
    await database.create_watchlist(
        owner_id="owner-1",
        name="Second",
        keywords=["rick owens"],
        destination_id=destination._id,
    )
    listing = build_listing()
    sender = RecordingDestinationSender(failing_destination_ids={destination._id})

    await run_fanout(listing, sender)

    assert sender.attempts == [(destination._id, listing.canonical_id)]
    assert await fake_database.alerts.count_documents({}) == 0


async def test_send_failure_discards_reservation_and_continues_to_next_destination(
    fake_database: FakeDatabaseClient,
) -> None:
    """A failing destination does not prevent later destinations from receiving the listing."""
    failing_destination = await create_destination("owner-1", "failing")
    healthy_destination = await create_destination("owner-2", "healthy")
    await database.create_watchlist(
        owner_id="owner-1",
        name="Failing",
        keywords=["rick owens"],
        destination_id=failing_destination._id,
    )
    await database.create_watchlist(
        owner_id="owner-2",
        name="Healthy",
        keywords=["rick owens"],
        destination_id=healthy_destination._id,
    )
    listing = build_listing()
    sender = RecordingDestinationSender(failing_destination_ids={failing_destination._id})

    await run_fanout(listing, sender)

    assert sender.attempts == [
        (failing_destination._id, listing.canonical_id),
        (healthy_destination._id, listing.canonical_id),
    ]
    assert sender.sent == [(healthy_destination._id, listing.canonical_id)]
    assert await fake_database.alerts.find_one({"destination_id": failing_destination._id}) is None
    healthy_document = await fake_database.alerts.find_one({"destination_id": healthy_destination._id})
    assert healthy_document is not None
    assert healthy_document["status"] == "sent"


async def test_disabled_watchlists_and_missing_destinations_are_skipped(
    fake_database: FakeDatabaseClient,
) -> None:
    """Stale disabled subscribers and missing destinations are skipped without reserving alerts."""
    disabled_destination = await create_destination("owner-1", "disabled")
    disabled_watchlist = WatchlistRecord.new(
        owner_id="owner-1",
        name="Disabled",
        keywords=["rick owens"],
        destination_id=disabled_destination._id,
        enabled=False,
    )
    await fake_database.watchlists.insert_one(disabled_watchlist.to_document())
    await database.subscribe_keyword(
        "mercari",
        "rick owens",
        owner_id=disabled_watchlist.owner_id,
        watchlist_id=disabled_watchlist._id,
    )
    await database.create_watchlist(
        owner_id="owner-2",
        name="Missing Destination",
        keywords=["rick owens"],
        destination_id="missing-destination",
    )
    listing = build_listing()
    sender = RecordingDestinationSender()

    await run_fanout(listing, sender)

    assert sender.attempts == []
    assert await fake_database.alerts.count_documents({}) == 0


async def test_legacy_fallback_only_runs_for_zero_subscribers_when_enabled(
    fake_database: FakeDatabaseClient,
) -> None:
    """Legacy bot-channel delivery is gated to keywords with no registry subscribers."""
    legacy_sent: list[str] = []

    async def send_legacy(listing: ListingRecord) -> None:
        """Record a legacy channel send."""
        legacy_sent.append(listing.canonical_id)

    def legacy_target_factory() -> alert_fanout.LegacyDeliveryTarget:
        """Return a legacy channel target for fallback delivery."""
        return alert_fanout.LegacyDeliveryTarget(
            destination_id="legacy-channel-123",
            send_listing=send_legacy,
        )

    sender = RecordingDestinationSender()
    listing = build_listing("m-legacy")

    await run_fanout(
        listing,
        sender,
        keyword="orphan keyword",
        legacy_target_factory=legacy_target_factory,
    )

    assert legacy_sent == [listing.canonical_id]
    legacy_document = await fake_database.alerts.find_one({"destination_id": "legacy-channel-123"})
    assert legacy_document is not None
    assert legacy_document["owner_id"] is None

    await run_fanout(
        build_listing("m-disabled-legacy"),
        sender,
        keyword="another orphan",
        legacy_alerts_enabled=False,
        legacy_target_factory=legacy_target_factory,
    )
    assert legacy_sent == [listing.canonical_id]

    await database.subscribe_keyword(
        "mercari",
        "subscribed keyword",
        owner_id="owner-1",
        watchlist_id="missing-watchlist",
    )
    await run_fanout(
        build_listing("m-subscribed"),
        sender,
        keyword="subscribed keyword",
        legacy_target_factory=legacy_target_factory,
    )
    assert legacy_sent == [listing.canonical_id]


async def test_keyword_baseline_gate_suppresses_first_pass_then_delivers(
    fake_database: FakeDatabaseClient,
) -> None:
    """A keyword baseline pass writes no delivery before a later pass alerts."""
    destination = await create_destination("owner-1", "main")
    await database.create_watchlist(
        owner_id="owner-1",
        name="First",
        keywords=["rick owens"],
        destination_id=destination._id,
    )
    listing = build_listing("m-gated")
    sender = RecordingDestinationSender()

    def should_alert(is_new_listing: bool, *, is_baseline_scan: bool) -> bool:
        """Apply the per-keyword baseline gate used by the worker."""
        return is_new_listing and not is_baseline_scan

    await run_fanout(
        listing,
        sender,
        should_send_listing=lambda is_new: should_alert(is_new, is_baseline_scan=True),
    )
    assert sender.sent == []
    assert await fake_database.alerts.count_documents({}) == 0

    await run_fanout(
        listing,
        sender,
        should_send_listing=lambda is_new: should_alert(is_new, is_baseline_scan=False),
    )
    assert sender.sent == [(destination._id, listing.canonical_id)]
    assert await fake_database.alerts.count_documents({}) == 1
