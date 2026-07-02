"""Tenant watchlist models, filters, and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, model_validator

from .listings import extract_price, infer_listing_status


class WatchlistCondition(StrEnum):
    """Listing status values used by watchlist filters.

    This reflects status inferred by ``infer_listing_status``, not Mercari item-condition grades.
    """

    ACTIVE = "active"
    SOLD = "sold"
    ANY = "any"


class WatchlistNameExistsError(Exception):
    """Raised when a watchlist name already exists for the same owner."""


class WatchlistNotFoundError(Exception):
    """Raised when a watchlist cannot be found for an update."""


class WatchlistFilters(BaseModel):
    """Optional price and status filters for a tenant watchlist."""

    min_price: int | None = None
    max_price: int | None = None
    condition: WatchlistCondition = WatchlistCondition.ANY

    @model_validator(mode="after")
    def _validate_price_bounds(self) -> "WatchlistFilters":
        if self.min_price is not None and self.min_price < 0:
            raise ValueError("min_price must be greater than or equal to 0")
        if self.max_price is not None and self.max_price < 0:
            raise ValueError("max_price must be greater than or equal to 0")
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must be less than or equal to max_price")
        return self

    def matches(self, price_value: int | None, status: str) -> bool:
        """Return whether a listing price and status satisfy these filters.

        Price bounds are inclusive. A missing price passes only when no price bound is configured.
        """
        if self.condition is not WatchlistCondition.ANY and status != self.condition.value:
            return False

        if price_value is None:
            return self.min_price is None and self.max_price is None

        if self.min_price is not None and price_value < self.min_price:
            return False
        if self.max_price is not None and price_value > self.max_price:
            return False
        return True

    def matches_raw_content(self, raw_content: str) -> bool:
        """Return whether scraped card content satisfies these filters."""
        _, price_value, _ = extract_price(raw_content)
        return self.matches(price_value, infer_listing_status(raw_content))

    def to_document(self) -> dict[str, Any]:
        """Serialize the filters for MongoDB storage."""
        return {
            "min_price": self.min_price,
            "max_price": self.max_price,
            "condition": self.condition.value,
        }

    @classmethod
    def from_document(cls, document: dict[str, Any] | None) -> "WatchlistFilters":
        """Create filters from a MongoDB document."""
        if document is None:
            return cls()
        return cls.model_validate(document)


@dataclass(slots=True)
class WatchlistRecord:
    """Tenant-owned keyword watchlist data stored in MongoDB."""

    _id: str
    owner_id: str
    name: str
    keywords: list[str]
    filters: WatchlistFilters
    destination_id: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        owner_id: str,
        name: str,
        keywords: list[str],
        filters: WatchlistFilters | dict[str, Any] | None = None,
        destination_id: str,
        enabled: bool = True,
        created_at: datetime | None = None,
    ) -> "WatchlistRecord":
        """Create a new watchlist record with normalized fields and timestamps."""
        timestamp = created_at or datetime.now(UTC)
        return cls(
            _id=uuid4().hex,
            owner_id=owner_id,
            name=normalize_watchlist_name(name),
            keywords=normalize_keywords(keywords),
            filters=_coerce_filters(filters),
            destination_id=destination_id,
            enabled=enabled,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_document(self) -> dict[str, Any]:
        """Serialize the watchlist for MongoDB storage."""
        return {
            "_id": self._id,
            "owner_id": self.owner_id,
            "name": self.name,
            "keywords": self.keywords,
            "filters": self.filters.to_document(),
            "destination_id": self.destination_id,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def normalize_watchlist_name(name: str) -> str:
    """Normalize a watchlist name and ensure it is non-empty."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("watchlist name must be non-empty")
    return normalized_name


def normalize_keywords(keywords: list[str]) -> list[str]:
    """Normalize watchlist keywords while preserving first-seen order."""
    normalized_keywords: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized_keyword = keyword.strip().lower()
        if not normalized_keyword or normalized_keyword in seen:
            continue
        normalized_keywords.append(normalized_keyword)
        seen.add(normalized_keyword)
    return normalized_keywords


def _coerce_filters(filters: WatchlistFilters | dict[str, Any] | None) -> WatchlistFilters:
    if filters is None:
        return WatchlistFilters()
    if isinstance(filters, WatchlistFilters):
        return filters
    return WatchlistFilters.model_validate(filters)
