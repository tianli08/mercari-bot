"""Global keyword registry models and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .listings import Marketplace

_WHITESPACE_PATTERN = re.compile(r"\s+")


class KeywordRegistryEntryNotFoundError(Exception):
    """Raised when a keyword registry entry cannot be found."""


@dataclass(frozen=True, slots=True)
class RegistrySubscriber:
    """Watchlist subscription embedded in a keyword registry entry."""

    owner_id: str
    watchlist_id: str

    def to_document(self) -> dict[str, str]:
        """Serialize the subscriber for MongoDB storage."""
        return {
            "owner_id": self.owner_id,
            "watchlist_id": self.watchlist_id,
        }

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "RegistrySubscriber":
        """Create a subscriber from a MongoDB document."""
        return cls(
            owner_id=document["owner_id"],
            watchlist_id=document["watchlist_id"],
        )


@dataclass(slots=True)
class KeywordRegistryRecord:
    """Global keyword registry entry stored in MongoDB."""

    _id: str
    marketplace: Marketplace
    keyword: str
    subscribers: list[RegistrySubscriber]
    subscriber_count: int
    last_scraped_at: datetime | None
    baselined_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        marketplace: Marketplace,
        keyword: str,
        subscribers: list[RegistrySubscriber] | None = None,
        last_scraped_at: datetime | None = None,
        baselined_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> "KeywordRegistryRecord":
        """Create a new registry entry with normalized fields and timestamps."""
        timestamp = created_at or datetime.now(UTC)
        normalized_keyword = normalize_registry_keyword(keyword)
        normalized_subscribers = _dedupe_subscribers(subscribers or [])
        return cls(
            _id=build_registry_id(marketplace, normalized_keyword),
            marketplace=marketplace,
            keyword=normalized_keyword,
            subscribers=normalized_subscribers,
            subscriber_count=len(normalized_subscribers),
            last_scraped_at=last_scraped_at,
            baselined_at=baselined_at,
            created_at=timestamp,
            updated_at=timestamp,
        )

    @property
    def registry_id(self) -> str:
        """Return the deterministic natural key for this registry entry."""
        return build_registry_id(self.marketplace, self.keyword)

    def to_document(self) -> dict[str, Any]:
        """Serialize the registry entry for MongoDB storage."""
        subscribers = [subscriber.to_document() for subscriber in self.subscribers]
        return {
            "_id": self._id,
            "marketplace": self.marketplace,
            "keyword": self.keyword,
            "subscribers": subscribers,
            "subscriber_count": len(subscribers),
            "last_scraped_at": self.last_scraped_at,
            "baselined_at": self.baselined_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def build_registry_id(marketplace: Marketplace, keyword: str) -> str:
    """Build the deterministic registry id for a marketplace keyword."""
    return f"{marketplace}:{normalize_registry_keyword(keyword)}"


def normalize_registry_keyword(keyword: str) -> str:
    """Normalize a registry keyword and ensure it is non-empty."""
    normalized_keyword = _WHITESPACE_PATTERN.sub(" ", keyword.strip().lower())
    if not normalized_keyword:
        raise ValueError("keyword must be non-empty")
    return normalized_keyword


def _dedupe_subscribers(subscribers: list[RegistrySubscriber]) -> list[RegistrySubscriber]:
    deduped_subscribers: list[RegistrySubscriber] = []
    seen: set[RegistrySubscriber] = set()
    for subscriber in subscribers:
        if subscriber in seen:
            continue
        deduped_subscribers.append(subscriber)
        seen.add(subscriber)
    return deduped_subscribers
