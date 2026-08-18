"""Alert delivery persistence tests."""

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
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")

from src import database  # noqa: E402
from src.listings import ListingRecord  # noqa: E402

pytestmark = pytest.mark.asyncio


class FakeDatabaseClient:
    """In-memory database client with the same collection attributes as production."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["alert_delivery_tests"]
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


def build_listing(item_id: str = "m123") -> ListingRecord:
    """Build a canonical listing for alert-delivery tests."""
    return ListingRecord(
        marketplace="mercari",
        item_id=item_id,
        canonical_id=f"mercari:{item_id}",
        url=f"https://jp.mercari.com/item/{item_id}",
        title=f"Listing {item_id}",
        image_url="https://example.com/image.jpg",
        raw_content="Listing body JPY 1200",
        price_text="JPY 1200",
        price_value=1200,
        currency="JPY",
        status="active",
        matched_filters={"designer"},
        matched_keywords={"rick owens"},
    )


async def test_reservation_is_per_destination(fake_database: FakeDatabaseClient) -> None:
    """The same canonical listing can be reserved once for each destination."""
    listing = build_listing()

    first_delivery_id = await database.reserve_alert_delivery(listing, destination_id="destination-1")
    second_delivery_id = await database.reserve_alert_delivery(listing, destination_id="destination-2")

    assert first_delivery_id == f"destination-1:{listing.canonical_id}"
    assert second_delivery_id == f"destination-2:{listing.canonical_id}"
    assert await fake_database.alerts.count_documents({"listing_id": listing.canonical_id}) == 2


async def test_dedupe_within_destination(fake_database: FakeDatabaseClient) -> None:
    """The same destination cannot reserve the same canonical listing twice."""
    listing = build_listing()

    first_delivery_id = await database.reserve_alert_delivery(listing, destination_id="destination-1")
    second_delivery_id = await database.reserve_alert_delivery(listing, destination_id="destination-1")

    assert first_delivery_id == f"destination-1:{listing.canonical_id}"
    assert second_delivery_id is None
    assert await fake_database.alerts.count_documents({"listing_id": listing.canonical_id}) == 1


async def test_owner_id_is_persisted(fake_database: FakeDatabaseClient) -> None:
    """Alert reservations store tenant ownership when provided and None for legacy calls."""
    listing = build_listing()

    tenant_delivery_id = await database.reserve_alert_delivery(
        listing,
        destination_id="destination-1",
        owner_id="tenant-1",
    )
    legacy_delivery_id = await database.reserve_alert_delivery(listing, destination_id="legacy-destination")

    tenant_document = await fake_database.alerts.find_one({"_id": tenant_delivery_id})
    legacy_document = await fake_database.alerts.find_one({"_id": legacy_delivery_id})
    assert tenant_document is not None
    assert legacy_document is not None
    assert tenant_document["owner_id"] == "tenant-1"
    assert legacy_document["owner_id"] is None


async def test_document_shape_uses_destination_id(fake_database: FakeDatabaseClient) -> None:
    """Alert documents use destination_id instead of the legacy channel_id field."""
    listing = build_listing()
    destination_id = "destination-1"

    delivery_id = await database.reserve_alert_delivery(listing, destination_id=destination_id)

    document = await fake_database.alerts.find_one({"_id": delivery_id})
    assert document is not None
    assert document["_id"] == f"{destination_id}:{listing.canonical_id}"
    assert document["destination_id"] == destination_id
    assert "channel_id" not in document


async def test_alert_lifecycle_still_works(fake_database: FakeDatabaseClient) -> None:
    """Sent and discard operations keep their existing alert lifecycle semantics."""
    listing = build_listing("m456")
    observed_at = datetime(2025, 1, 1, tzinfo=UTC)
    delivered_at = datetime(2025, 1, 2, tzinfo=UTC)
    await database.upsert_listing(listing, observed_at=observed_at)

    sent_delivery_id = await database.reserve_alert_delivery(
        listing,
        destination_id="sent-destination",
        observed_at=observed_at,
    )
    assert sent_delivery_id is not None
    await database.mark_alert_delivery_sent(sent_delivery_id, listing.canonical_id, delivered_at=delivered_at)

    sent_document = await fake_database.alerts.find_one({"_id": sent_delivery_id})
    listing_document = await fake_database.listings.find_one({"_id": listing.canonical_id})
    assert sent_document is not None
    assert listing_document is not None
    assert sent_document["status"] == "sent"
    assert listing_document["first_alerted_at"].replace(tzinfo=UTC) == delivered_at
    assert listing_document["last_alerted_at"].replace(tzinfo=UTC) == delivered_at

    await database.discard_pending_alert_delivery(sent_delivery_id)
    assert await fake_database.alerts.find_one({"_id": sent_delivery_id}) is not None

    pending_delivery_id = await database.reserve_alert_delivery(listing, destination_id="retry-destination")
    assert pending_delivery_id is not None
    await database.discard_pending_alert_delivery(pending_delivery_id)
    assert await fake_database.alerts.find_one({"_id": pending_delivery_id}) is None
    assert await database.reserve_alert_delivery(listing, destination_id="retry-destination") == pending_delivery_id
