"""MongoDB persistence for marketplace monitoring data.

Includes listings, per-destination alert deliveries, tenants, watchlists, destinations, keywords, and presets.
"""

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
from .keyword_registry import (
    KeywordRegistryEntryNotFoundError,
    KeywordRegistryRecord,
    RegistrySubscriber,
    build_registry_id,
    normalize_registry_keyword,
)
from .listings import ListingRecord, Marketplace
from .presets import PresetKeywordRecord, PresetNameExistsError, PresetNotFoundError
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
        self.keyword_registry = self.db[settings.mongo_keyword_registry_collection_name]
        self.preset_keywords = self.db[settings.mongo_preset_keywords_collection_name]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the indexes needed for marketplace monitoring data.

        Includes listings, destination alert dedupe, tenants, watchlists, destinations, keywords, and presets.
        """
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
            [("listing_id", ASCENDING), ("destination_id", ASCENDING)],
            unique=True,
            name="listing_destination_unique",
        )
        await self.alerts.create_index("owner_id", name="alerts_owner_idx")
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
        await self.keyword_registry.create_index(
            [("marketplace", ASCENDING), ("keyword", ASCENDING)],
            unique=True,
            name="keyword_registry_marketplace_keyword_unique",
        )
        await self.keyword_registry.create_index("subscriber_count", name="keyword_registry_subscriber_count_idx")
        await self.keyword_registry.create_index("last_scraped_at", name="keyword_registry_last_scraped_at_idx")
        preset_keywords = getattr(self, "preset_keywords", None)
        if preset_keywords is not None:
            await preset_keywords.create_index(
                [("marketplace", ASCENDING), ("name", ASCENDING)],
                unique=True,
                name="preset_keywords_marketplace_name_unique",
            )
            await preset_keywords.create_index("enabled", name="preset_keywords_enabled_idx")
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
    await sync_watchlist_subscriptions(watchlist, "mercari", previous_keywords=[])
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

    previous_document = await db_client.watchlists.find_one({"_id": watchlist_id})
    if previous_document is None:
        raise WatchlistNotFoundError(watchlist_id)
    previous_watchlist = _document_to_watchlist(previous_document)

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
    watchlist = _document_to_watchlist(document)
    previous_keywords = previous_watchlist.keywords if previous_watchlist.enabled else []
    await sync_watchlist_subscriptions(watchlist, "mercari", previous_keywords=previous_keywords)
    return watchlist


async def set_watchlist_enabled(watchlist_id: str, enabled: bool) -> WatchlistRecord:
    """Set a watchlist's enabled flag and return the updated record."""
    await db_client.ensure_indexes()

    previous_document = await db_client.watchlists.find_one({"_id": watchlist_id})
    if previous_document is None:
        raise WatchlistNotFoundError(watchlist_id)
    previous_watchlist = _document_to_watchlist(previous_document)

    document = await db_client.watchlists.find_one_and_update(
        {"_id": watchlist_id},
        {"$set": {"enabled": enabled, "updated_at": datetime.now(UTC)}},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise WatchlistNotFoundError(watchlist_id)
    watchlist = _document_to_watchlist(document)
    previous_keywords = previous_watchlist.keywords if previous_watchlist.enabled else []
    await sync_watchlist_subscriptions(watchlist, "mercari", previous_keywords=previous_keywords)
    return watchlist


async def delete_watchlist(watchlist_id: str) -> bool:
    """Delete a watchlist and return whether a document was removed."""
    await db_client.ensure_indexes()

    previous_document = await db_client.watchlists.find_one({"_id": watchlist_id})
    if previous_document is None:
        return False

    result = await db_client.watchlists.delete_one({"_id": watchlist_id})
    if result.deleted_count > 0:
        await remove_watchlist_subscriptions(watchlist_id, "mercari")
    return result.deleted_count > 0


async def upsert_preset_keyword(record: PresetKeywordRecord) -> tuple[PresetKeywordRecord, bool]:
    """Upsert a preset keyword record and return the stored record plus insert status."""
    await db_client.ensure_indexes()

    record_document = record.to_document()
    try:
        result = await db_client.preset_keywords.update_one(
            {"_id": record._id},
            {
                "$setOnInsert": {
                    "_id": record_document["_id"],
                    "marketplace": record_document["marketplace"],
                    "created_at": record_document["created_at"],
                },
                "$set": {
                    "name": record_document["name"],
                    "keywords": record_document["keywords"],
                    "enabled": record_document["enabled"],
                    "updated_at": record_document["updated_at"],
                },
            },
            upsert=True,
        )
    except DuplicateKeyError as exc:
        raise PresetNameExistsError("preset name already exists for this marketplace") from exc

    document = await db_client.preset_keywords.find_one({"_id": record._id})
    if document is None:
        raise PresetNotFoundError(record._id)
    return _document_to_preset_keyword(document), result.upserted_id is not None


async def get_preset_keyword_by_id(preset_id: str) -> PresetKeywordRecord | None:
    """Return a preset keyword by deterministic id."""
    await db_client.ensure_indexes()

    document = await db_client.preset_keywords.find_one({"_id": preset_id})
    if document is None:
        return None
    return _document_to_preset_keyword(document)


async def list_preset_keywords(
    marketplace: Marketplace = "mercari",
    *,
    enabled_only: bool = True,
) -> list[PresetKeywordRecord]:
    """Return preset keywords for a marketplace sorted by display name."""
    await db_client.ensure_indexes()

    query: dict[str, Any] = {"marketplace": marketplace}
    if enabled_only:
        query["enabled"] = True
    documents = await db_client.preset_keywords.find(query).sort([("name", ASCENDING)]).to_list(length=None)
    return [_document_to_preset_keyword(document) for document in documents]


async def subscribe_keyword(
    marketplace: Marketplace,
    keyword: str,
    *,
    owner_id: str,
    watchlist_id: str,
) -> KeywordRegistryRecord:
    """Subscribe a watchlist to a marketplace keyword and return the registry entry."""
    await db_client.ensure_indexes()

    normalized_keyword = normalize_registry_keyword(keyword)
    registry_id = build_registry_id(marketplace, normalized_keyword)
    timestamp = datetime.now(UTC)
    subscriber = RegistrySubscriber(owner_id=owner_id, watchlist_id=watchlist_id)
    subscriber_document = subscriber.to_document()
    subscriber_absent_query: dict[str, Any] = {
        "_id": registry_id,
        "subscribers": {"$not": {"$elemMatch": subscriber_document}},
    }
    update_document = {
        "$setOnInsert": {
            "_id": registry_id,
            "marketplace": marketplace,
            "keyword": normalized_keyword,
            "last_scraped_at": None,
            "created_at": timestamp,
        },
        "$addToSet": {"subscribers": subscriber_document},
        "$inc": {"subscriber_count": 1},
        "$set": {"updated_at": timestamp},
    }

    for _ in range(2):
        try:
            await db_client.keyword_registry.update_one(subscriber_absent_query, update_document, upsert=True)
        except DuplicateKeyError:
            await db_client.keyword_registry.update_one(subscriber_absent_query, update_document)

        document = await db_client.keyword_registry.find_one({"_id": registry_id})
        if document is not None:
            return _document_to_keyword_registry(document)

    raise KeywordRegistryEntryNotFoundError(registry_id)


async def unsubscribe_keyword(
    marketplace: Marketplace,
    keyword: str,
    *,
    owner_id: str,
    watchlist_id: str,
) -> None:
    """Unsubscribe a watchlist from a marketplace keyword."""
    await db_client.ensure_indexes()

    normalized_keyword = normalize_registry_keyword(keyword)
    registry_id = build_registry_id(marketplace, normalized_keyword)
    subscriber_document = RegistrySubscriber(owner_id=owner_id, watchlist_id=watchlist_id).to_document()
    result = await db_client.keyword_registry.update_one(
        {"_id": registry_id, "subscribers": {"$elemMatch": subscriber_document}},
        {
            "$pull": {"subscribers": subscriber_document},
            "$inc": {"subscriber_count": -1},
            "$set": {"updated_at": datetime.now(UTC)},
        },
    )
    if result.matched_count > 0:
        await db_client.keyword_registry.delete_one({"_id": registry_id, "subscribers": {"$size": 0}})


async def sync_watchlist_subscriptions(
    watchlist: WatchlistRecord,
    marketplace: Marketplace,
    *,
    previous_keywords: list[str] | None = None,
) -> None:
    """Synchronize registry subscriptions for one watchlist."""
    await db_client.ensure_indexes()

    desired_keywords = normalize_keywords(watchlist.keywords) if watchlist.enabled else []
    desired_keyword_set = set(desired_keywords)
    if previous_keywords is None:
        await _remove_watchlist_subscriptions_except(
            watchlist._id,
            marketplace,
            keep_keywords=desired_keyword_set,
        )
        previous_keyword_set: set[str] = set()
    else:
        previous_keyword_set = set(normalize_keywords(previous_keywords))

    for keyword_to_remove in previous_keyword_set - desired_keyword_set:
        await unsubscribe_keyword(
            marketplace,
            keyword_to_remove,
            owner_id=watchlist.owner_id,
            watchlist_id=watchlist._id,
        )

    for keyword_to_add in desired_keywords:
        if keyword_to_add in previous_keyword_set:
            continue
        await subscribe_keyword(
            marketplace,
            keyword_to_add,
            owner_id=watchlist.owner_id,
            watchlist_id=watchlist._id,
        )


async def remove_watchlist_subscriptions(watchlist_id: str, marketplace: Marketplace) -> None:
    """Remove a watchlist from every registry entry for a marketplace."""
    await db_client.ensure_indexes()

    await _remove_watchlist_subscriptions_except(watchlist_id, marketplace, keep_keywords=set())


async def get_registry_entry(marketplace: Marketplace, keyword: str) -> KeywordRegistryRecord | None:
    """Return a keyword registry entry by marketplace and keyword."""
    await db_client.ensure_indexes()

    document = await db_client.keyword_registry.find_one({"_id": build_registry_id(marketplace, keyword)})
    if document is None:
        return None
    return _document_to_keyword_registry(document)


async def list_active_registry_entries(
    marketplace: Marketplace,
    *,
    stale_before: datetime | None = None,
    limit: int | None = None,
) -> list[KeywordRegistryRecord]:
    """Return active registry entries ordered by scrape urgency."""
    await db_client.ensure_indexes()

    query: dict[str, Any] = {
        "marketplace": marketplace,
        "subscriber_count": {"$gt": 0},
    }
    if stale_before is not None:
        query["$or"] = [
            {"last_scraped_at": None},
            {"last_scraped_at": {"$lt": _as_utc(stale_before)}},
        ]

    cursor = db_client.keyword_registry.find(query).sort(
        [("last_scraped_at", ASCENDING), ("keyword", ASCENDING)]
    )
    if limit is not None:
        cursor = cursor.limit(limit)
    documents = await cursor.to_list(length=limit)
    return [_document_to_keyword_registry(document) for document in documents]


async def mark_keyword_scraped(
    marketplace: Marketplace,
    keyword: str,
    scraped_at: datetime | None = None,
) -> KeywordRegistryRecord:
    """Set a registry entry's scrape timestamp and return the updated entry."""
    await db_client.ensure_indexes()

    timestamp = datetime.now(UTC)
    scraped_timestamp = _as_utc(scraped_at) if scraped_at is not None else timestamp
    document = await db_client.keyword_registry.find_one_and_update(
        {"_id": build_registry_id(marketplace, keyword)},
        {"$set": {"last_scraped_at": scraped_timestamp, "updated_at": timestamp}},
        return_document=ReturnDocument.AFTER,
    )
    if document is None:
        raise KeywordRegistryEntryNotFoundError(build_registry_id(marketplace, keyword))
    return _document_to_keyword_registry(document)


async def rebuild_keyword_registry(marketplace: Marketplace) -> int:
    """Rebuild one marketplace's registry projection from enabled watchlists."""
    await db_client.ensure_indexes()

    desired_subscribers: dict[str, list[RegistrySubscriber]] = {}
    desired_seen: dict[str, set[RegistrySubscriber]] = {}
    watchlist_documents = await db_client.watchlists.find({"enabled": True}).to_list(length=None)
    for watchlist_document in watchlist_documents:
        watchlist = _document_to_watchlist(watchlist_document)
        for keyword in normalize_keywords(watchlist.keywords):
            subscriber = RegistrySubscriber(owner_id=watchlist.owner_id, watchlist_id=watchlist._id)
            if subscriber in desired_seen.setdefault(keyword, set()):
                continue
            desired_subscribers.setdefault(keyword, []).append(subscriber)
            desired_seen[keyword].add(subscriber)

    existing_documents = await db_client.keyword_registry.find({"marketplace": marketplace}).to_list(length=None)
    timestamp = datetime.now(UTC)
    for keyword, subscribers in desired_subscribers.items():
        registry_id = build_registry_id(marketplace, keyword)
        subscriber_documents = [subscriber.to_document() for subscriber in subscribers]
        await db_client.keyword_registry.update_one(
            {"_id": registry_id},
            {
                "$setOnInsert": {
                    "_id": registry_id,
                    "marketplace": marketplace,
                    "keyword": keyword,
                    "last_scraped_at": None,
                    "created_at": timestamp,
                },
                "$set": {
                    "subscribers": subscriber_documents,
                    "subscriber_count": len(subscriber_documents),
                    "updated_at": timestamp,
                },
            },
            upsert=True,
        )

    for document in existing_documents:
        if document["keyword"] not in desired_subscribers:
            await db_client.keyword_registry.delete_one({"_id": document["_id"]})

    return len(desired_subscribers)


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
    destination_id: str,
    *,
    owner_id: str | None = None,
    observed_at: datetime | None = None,
) -> str | None:
    """Reserve a per-destination delivery slot and return its id if this alert is new.

    Listings remain globally deduped by canonical listing id, while alert delivery is scoped to one
    destination plus that canonical listing. Legacy single-operator Discord calls leave ``owner_id`` as
    ``None``; tenant fan-out must pass a concrete owner id in later phases.
    """
    await db_client.ensure_indexes()

    timestamp = observed_at or datetime.now(UTC)
    delivery_id = f"{destination_id}:{listing.canonical_id}"
    result = await db_client.alerts.update_one(
        {"_id": delivery_id},
        {
            "$setOnInsert": {
                "_id": delivery_id,
                "listing_id": listing.canonical_id,
                "destination_id": destination_id,
                "owner_id": owner_id,
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


def _document_to_keyword_registry(document: dict[str, Any]) -> KeywordRegistryRecord:
    last_scraped_at = document.get("last_scraped_at")
    return KeywordRegistryRecord(
        _id=document["_id"],
        marketplace=document["marketplace"],
        keyword=document["keyword"],
        subscribers=[
            RegistrySubscriber.from_document(subscriber) for subscriber in document.get("subscribers", [])
        ],
        subscriber_count=document.get("subscriber_count", len(document.get("subscribers", []))),
        last_scraped_at=_as_utc(last_scraped_at) if last_scraped_at is not None else None,
        created_at=_as_utc(document["created_at"]),
        updated_at=_as_utc(document["updated_at"]),
    )


def _document_to_preset_keyword(document: dict[str, Any]) -> PresetKeywordRecord:
    return PresetKeywordRecord(
        _id=document["_id"],
        marketplace=document["marketplace"],
        name=document["name"],
        keywords=document["keywords"],
        enabled=document["enabled"],
        created_at=_as_utc(document["created_at"]),
        updated_at=_as_utc(document["updated_at"]),
    )


async def _remove_watchlist_subscriptions_except(
    watchlist_id: str,
    marketplace: Marketplace,
    *,
    keep_keywords: set[str],
) -> None:
    documents = await db_client.keyword_registry.find(
        {"marketplace": marketplace, "subscribers.watchlist_id": watchlist_id}
    ).to_list(length=None)
    for document in documents:
        keyword = document["keyword"]
        if keyword in keep_keywords:
            continue
        for subscriber in document.get("subscribers", []):
            if subscriber.get("watchlist_id") != watchlist_id:
                continue
            await unsubscribe_keyword(
                marketplace,
                keyword,
                owner_id=subscriber["owner_id"],
                watchlist_id=watchlist_id,
            )


def _coerce_watchlist_filters(filters: WatchlistFilters | dict[str, Any]) -> WatchlistFilters:
    if isinstance(filters, WatchlistFilters):
        return filters
    return WatchlistFilters.model_validate(filters)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
