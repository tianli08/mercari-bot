"""MongoDB persistence for listings, alert deliveries, tenant users, watchlists, and destinations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import motor.motor_asyncio
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from .config import settings
from .destinations import (
    DestinationLabelExistsError,
    DestinationNotFoundError,
    DestinationRecord,
    DestinationType,
    encrypt_webhook_url,
    normalize_label,
    validate_webhook_url,
)
from .listings import ListingRecord
from .users import EmailAlreadyExistsError, UserPlan, UserRecord, UserStatus, normalize_email
from .watchlists import (
    WatchlistFilters,
    WatchlistNameExistsError,
    WatchlistNotFoundError,
    WatchlistRecord,
    normalize_keywords,
    normalize_watchlist_name,
)


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
        self.users = self.db[settings.mongo_users_collection_name]
        self.watchlists = self.db[settings.mongo_watchlists_collection_name]
        self.destinations = self.db[settings.mongo_destinations_collection_name]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the indexes needed for listings, alert dedupe, users, watchlists, and destinations."""
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
        await self.users.create_index("email", unique=True, name="users_email_unique")
        await self.users.create_index("status", name="users_status_idx")
        await self.watchlists.create_index("owner_id", name="watchlists_owner_idx")
        await self.watchlists.create_index(
            [("owner_id", ASCENDING), ("name", ASCENDING)],
            unique=True,
            name="watchlists_owner_name_unique",
        )
        await self.watchlists.create_index("enabled", name="watchlists_enabled_idx")
        await self.destinations.create_index("owner_id", name="destinations_owner_idx")
        await self.destinations.create_index(
            [("owner_id", ASCENDING), ("label", ASCENDING)],
            unique=True,
            name="destinations_owner_label_unique",
        )
        self._indexes_ready = True


db_client = DatabaseClient()


async def create_user(
    email: str,
    password_hash: str,
    *,
    status: UserStatus | str = UserStatus.ACTIVE,
    plan: UserPlan | str = UserPlan.FREE,
    created_at: datetime | None = None,
) -> UserRecord:
    """Create a tenant user and return the inserted record."""
    await db_client.ensure_indexes()

    user = UserRecord.new(
        email=email,
        password_hash=password_hash,
        status=status,
        plan=plan,
        created_at=created_at,
    )
    try:
        await db_client.users.insert_one(user.to_document())
    except DuplicateKeyError as exc:
        raise EmailAlreadyExistsError(normalize_email(email)) from exc
    return user


async def get_user_by_id(tenant_id: str) -> UserRecord | None:
    """Return a tenant user by stable tenant id."""
    await db_client.ensure_indexes()

    document = await db_client.users.find_one({"_id": tenant_id})
    if document is None:
        return None
    return _document_to_user(document)


async def get_user_by_email(email: str) -> UserRecord | None:
    """Return a tenant user by normalized email address."""
    await db_client.ensure_indexes()

    document = await db_client.users.find_one({"email": normalize_email(email)})
    if document is None:
        return None
    return _document_to_user(document)


async def create_watchlist(
    owner_id: str,
    name: str,
    keywords: list[str],
    *,
    filters: WatchlistFilters | dict[str, Any] | None = None,
    destination_id: str,
    enabled: bool = True,
    created_at: datetime | None = None,
) -> WatchlistRecord:
    """Create a tenant watchlist and return the inserted record."""
    await db_client.ensure_indexes()

    watchlist = WatchlistRecord.new(
        owner_id=owner_id,
        name=name,
        keywords=keywords,
        filters=filters,
        destination_id=destination_id,
        enabled=enabled,
        created_at=created_at,
    )
    try:
        await db_client.watchlists.insert_one(watchlist.to_document())
    except DuplicateKeyError as exc:
        raise WatchlistNameExistsError("watchlist name already exists for this owner") from exc
    return watchlist


async def get_watchlist_by_id(watchlist_id: str) -> WatchlistRecord | None:
    """Return a watchlist by id."""
    await db_client.ensure_indexes()

    document = await db_client.watchlists.find_one({"_id": watchlist_id})
    if document is None:
        return None
    return _document_to_watchlist(document)


async def list_watchlists_for_owner(owner_id: str, *, enabled_only: bool = False) -> list[WatchlistRecord]:
    """Return all watchlists owned by a tenant."""
    await db_client.ensure_indexes()

    query: dict[str, Any] = {"owner_id": owner_id}
    if enabled_only:
        query["enabled"] = True
    documents = await db_client.watchlists.find(query).to_list(length=None)
    return [_document_to_watchlist(document) for document in documents]


async def update_watchlist(
    watchlist_id: str,
    *,
    name: str | None = None,
    keywords: list[str] | None = None,
    filters: WatchlistFilters | dict[str, Any] | None = None,
    destination_id: str | None = None,
    enabled: bool | None = None,
) -> WatchlistRecord:
    """Update mutable watchlist fields and return the updated record."""
    await db_client.ensure_indexes()

    update_document: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if name is not None:
        update_document["name"] = normalize_watchlist_name(name)
    if keywords is not None:
        update_document["keywords"] = normalize_keywords(keywords)
    if filters is not None:
        update_document["filters"] = _coerce_watchlist_filters(filters).to_document()
    if destination_id is not None:
        update_document["destination_id"] = destination_id
    if enabled is not None:
        update_document["enabled"] = enabled

    try:
        document = await db_client.watchlists.find_one_and_update(
            {"_id": watchlist_id},
            {"$set": update_document},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError as exc:
        raise WatchlistNameExistsError("watchlist name already exists for this owner") from exc
    if document is None:
        raise WatchlistNotFoundError(watchlist_id)
    return _document_to_watchlist(document)


async def set_watchlist_enabled(watchlist_id: str, enabled: bool) -> WatchlistRecord:
    """Set a watchlist's enabled flag and return the updated record."""
    await db_client.ensure_indexes()

    document = await db_client.watchlists.find_one_and_update(
        {"_id": watchlist_id},
        {"$set": {"enabled": enabled, "updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise WatchlistNotFoundError(watchlist_id)
    return _document_to_watchlist(document)


async def delete_watchlist(watchlist_id: str) -> bool:
    """Delete a watchlist and return whether a document was removed."""
    await db_client.ensure_indexes()

    result = await db_client.watchlists.delete_one({"_id": watchlist_id})
    return result.deleted_count > 0


async def create_destination(
    owner_id: str,
    webhook_url: str,
    label: str,
    *,
    type: DestinationType | str = DestinationType.DISCORD_WEBHOOK,
    created_at: datetime | None = None,
) -> DestinationRecord:
    """Create a tenant destination and return the inserted record."""
    await db_client.ensure_indexes()

    destination = DestinationRecord.new(
        owner_id=owner_id,
        webhook_url=webhook_url,
        label=label,
        type=type,
        created_at=created_at,
    )
    try:
        await db_client.destinations.insert_one(destination.to_document())
    except DuplicateKeyError as exc:
        raise DestinationLabelExistsError("destination label already exists for this owner") from exc
    return destination


async def get_destination_by_id(destination_id: str) -> DestinationRecord | None:
    """Return a destination by id."""
    await db_client.ensure_indexes()

    document = await db_client.destinations.find_one({"_id": destination_id})
    if document is None:
        return None
    return _document_to_destination(document)


async def list_destinations_for_owner(owner_id: str) -> list[DestinationRecord]:
    """Return all destinations owned by a tenant."""
    await db_client.ensure_indexes()

    documents = await db_client.destinations.find({"owner_id": owner_id}).to_list(length=None)
    return [_document_to_destination(document) for document in documents]


async def update_destination(
    destination_id: str,
    *,
    label: str | None = None,
    webhook_url: str | None = None,
) -> DestinationRecord:
    """Update mutable destination fields and return the updated record."""
    await db_client.ensure_indexes()

    update_document: dict[str, Any] = {"updated_at": datetime.now(UTC)}
    if label is not None:
        update_document["label"] = normalize_label(label)
    if webhook_url is not None:
        update_document["webhook_url_encrypted"] = encrypt_webhook_url(validate_webhook_url(webhook_url))
        update_document["verified_at"] = None

    try:
        document = await db_client.destinations.find_one_and_update(
            {"_id": destination_id},
            {"$set": update_document},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError as exc:
        raise DestinationLabelExistsError("destination label already exists for this owner") from exc
    if document is None:
        raise DestinationNotFoundError(destination_id)
    return _document_to_destination(document)


async def mark_destination_verified(
    destination_id: str,
    verified_at: datetime | None = None,
) -> DestinationRecord:
    """Set a destination's verification timestamp and return the updated record."""
    await db_client.ensure_indexes()

    timestamp = datetime.now(UTC)
    verification_timestamp = _as_utc(verified_at) if verified_at is not None else timestamp
    document = await db_client.destinations.find_one_and_update(
        {"_id": destination_id},
        {"$set": {"verified_at": verification_timestamp, "updated_at": timestamp}},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise DestinationNotFoundError(destination_id)
    return _document_to_destination(document)


async def delete_destination(destination_id: str) -> bool:
    """Delete a destination and return whether a document was removed."""
    await db_client.ensure_indexes()

    # Watchlist reference integrity is enforced by the API layer in a later phase.
    result = await db_client.destinations.delete_one({"_id": destination_id})
    return result.deleted_count > 0


async def upsert_listing(listing: ListingRecord, observed_at: datetime | None = None) -> bool:
    """Upsert a canonical listing document and return whether it was new."""
    await db_client.ensure_indexes()

    timestamp = observed_at or datetime.now(UTC)
    listing_document = listing.to_document(observed_at=timestamp)
    listing_id = listing_document["_id"]
    mutable_document = {
        "listing_id": listing_document["listing_id"],
        "marketplace": listing_document["marketplace"],
        "item_id": listing_document["item_id"],
        "canonical_url": listing_document["canonical_url"],
        "url": listing_document["url"],
        "title": listing_document["title"],
        "item_name": listing_document["item_name"],
        "raw_content": listing_document["raw_content"],
        "status": listing_document["status"],
        "last_seen_at": listing_document["last_seen_at"],
        "updated_at": listing_document["updated_at"],
    }
    if listing_document["thumbnail_url"] is not None:
        mutable_document["thumbnail_url"] = listing_document["thumbnail_url"]
        mutable_document["image"] = listing_document["image"]
    if listing_document["price"] is not None:
        mutable_document["price"] = listing_document["price"]

    add_to_set_document: dict[str, object] = {}
    if listing_document["matched_filters"]:
        add_to_set_document["matched_filters"] = {"$each": listing_document["matched_filters"]}
    if listing_document["matched_keywords"]:
        add_to_set_document["matched_keywords"] = {"$each": listing_document["matched_keywords"]}
    if listing_document["search_contexts"]:
        add_to_set_document["search_contexts"] = {"$each": listing_document["search_contexts"]}

    update_document: dict[str, object] = {
        "$setOnInsert": {
            "_id": listing_id,
            "first_seen_at": timestamp,
            "created_at": timestamp,
        },
        "$set": mutable_document,
    }
    if add_to_set_document:
        update_document["$addToSet"] = add_to_set_document

    result = await db_client.listings.update_one(
        {"_id": listing_id},
        update_document,
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


def _document_to_user(document: dict[str, Any]) -> UserRecord:
    return UserRecord(
        _id=document["_id"],
        email=document["email"],
        password_hash=document["password_hash"],
        created_at=_as_utc(document["created_at"]),
        updated_at=_as_utc(document["updated_at"]),
        status=UserStatus(document["status"]),
        plan=UserPlan(document["plan"]),
    )


def _document_to_watchlist(document: dict[str, Any]) -> WatchlistRecord:
    return WatchlistRecord(
        _id=document["_id"],
        owner_id=document["owner_id"],
        name=document["name"],
        keywords=document["keywords"],
        filters=WatchlistFilters.from_document(document.get("filters")),
        destination_id=document["destination_id"],
        enabled=document["enabled"],
        created_at=_as_utc(document["created_at"]),
        updated_at=_as_utc(document["updated_at"]),
    )


def _document_to_destination(document: dict[str, Any]) -> DestinationRecord:
    verified_at = document.get("verified_at")
    return DestinationRecord(
        _id=document["_id"],
        owner_id=document["owner_id"],
        type=DestinationType(document["type"]),
        webhook_url_encrypted=document["webhook_url_encrypted"],
        label=document["label"],
        verified_at=_as_utc(verified_at) if verified_at is not None else None,
        created_at=_as_utc(document["created_at"]),
        updated_at=_as_utc(document["updated_at"]),
    )


def _coerce_watchlist_filters(filters: WatchlistFilters | dict[str, Any]) -> WatchlistFilters:
    if isinstance(filters, WatchlistFilters):
        return filters
    return WatchlistFilters.model_validate(filters)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
