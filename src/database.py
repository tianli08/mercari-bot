"""MongoDB persistence for canonical listings and alert deliveries."""

from __future__ import annotations

from datetime import UTC, datetime

import motor.motor_asyncio
from pymongo import ASCENDING

from .config import settings
from .listings import ListingRecord


class DatabaseClient:
    """Lazily initialized singleton wrapper for MongoDB access."""

    _instance: "DatabaseClient | None" = None

    def __new__(cls) -> "DatabaseClient":
        """Return a shared database client instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize MongoDB collections once."""
        if hasattr(self, "db"):
            return
        connection_string = settings.mongo_uri.get_secret_value()
        self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        self.db = self.client[settings.mongo_database_name]
        self.listings = self.db[settings.mongo_listings_collection_name]
        self.alerts = self.db[settings.mongo_alerts_collection_name]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the indexes needed for canonical listings and alert dedupe."""
        if self._indexes_ready:
            return

        await self.listings.create_index(
            [("marketplace", ASCENDING), ("item_id", ASCENDING)],
            unique=True,
            name="marketplace_item_id_unique",
        )
        await self.listings.create_index("last_seen_at", name="last_seen_at_idx")
        await self.listings.create_index("matched_filters", name="matched_filters_idx")
        await self.alerts.create_index(
            [("listing_id", ASCENDING), ("channel_id", ASCENDING)],
            unique=True,
            name="listing_channel_unique",
        )
        await self.alerts.create_index("status", name="alert_status_idx")
        self._indexes_ready = True


db_client = DatabaseClient()


async def upsert_listing(listing: ListingRecord, observed_at: datetime | None = None) -> bool:
    """Upsert a canonical listing document and return whether it was new."""
    await db_client.ensure_indexes()

    timestamp = observed_at or datetime.now(UTC)
    listing_document = listing.to_document(observed_at=timestamp)
    listing_id = listing_document["_id"]
    mutable_document = {key: value for key, value in listing_document.items() if key != "_id"}

    result = await db_client.listings.update_one(
        {"_id": listing_id},
        {
            "$setOnInsert": {
                "_id": listing_id,
                "first_seen_at": timestamp,
                "created_at": timestamp,
            },
            "$set": mutable_document,
        },
        upsert=True,
    )
    return result.upserted_id is not None


async def reserve_alert_delivery(
    listing: ListingRecord,
    channel_id: str,
    observed_at: datetime | None = None,
) -> str | None:
    """Reserve a delivery slot and return its id if this alert is new."""
    await db_client.ensure_indexes()

    timestamp = observed_at or datetime.now(UTC)
    delivery_id = f"{channel_id}:{listing.canonical_id}"
    result = await db_client.alerts.update_one(
        {"_id": delivery_id},
        {
            "$setOnInsert": {
                "_id": delivery_id,
                "listing_id": listing.canonical_id,
                "channel_id": channel_id,
                "marketplace": listing.marketplace,
                "item_id": listing.item_id,
                "canonical_url": listing.url,
                "title": listing.title,
                "matched_filters": sorted(listing.matched_filters),
                "matched_keywords": sorted(listing.matched_keywords),
                "status": "pending",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        },
        upsert=True,
    )
    if result.upserted_id is None:
        return None
    return delivery_id


async def mark_alert_delivery_sent(
    delivery_id: str,
    listing_id: str,
    delivered_at: datetime | None = None,
) -> None:
    """Mark an alert as sent and update listing-level alert timestamps."""
    await db_client.ensure_indexes()

    timestamp = delivered_at or datetime.now(UTC)
    await db_client.alerts.update_one(
        {"_id": delivery_id},
        {
            "$set": {
                "status": "sent",
                "delivered_at": timestamp,
                "updated_at": timestamp,
            }
        },
    )
    await db_client.listings.update_one(
        {"_id": listing_id, "first_alerted_at": {"$exists": False}},
        {"$set": {"first_alerted_at": timestamp}},
    )
    await db_client.listings.update_one(
        {"_id": listing_id},
        {"$set": {"last_alerted_at": timestamp}},
    )


async def discard_pending_alert_delivery(delivery_id: str) -> None:
    """Delete a reserved alert if Discord delivery fails."""
    await db_client.ensure_indexes()
    await db_client.alerts.delete_one({"_id": delivery_id, "status": "pending"})
