"""Canonical listing models and marketplace-specific parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

Marketplace = Literal["mercari", "rakuma", "rakuten"]

_MERCARI_ITEM_PATTERN = re.compile(r"/item/([A-Za-z0-9_-]+)")
_MERCARI_SHOPS_PRODUCT_PATTERN = re.compile(r"/shops/product/([A-Za-z0-9_-]+)")
_PRICE_PATTERN = re.compile(r"([¥￥])\s*([0-9][0-9,]*)")
_RAKUMA_HOSTS = {"fril.jp", "item.fril.jp", "rakuma.fril.jp"}
_RAKUTEN_HOSTS = {"rakuten.co.jp", "www.rakuten.co.jp", "item.rakuten.co.jp"}


@dataclass(frozen=True, slots=True)
class SearchContext:
    """Metadata about the search that matched a listing."""

    filter_name: str
    keyword: str
    search_url: str

    def to_document(self) -> dict[str, str]:
        """Serialize the context for MongoDB."""
        return {
            "filter_name": self.filter_name,
            "keyword": self.keyword,
            "search_url": self.search_url,
        }


@dataclass(frozen=True, slots=True)
class SearchDefinition:
    """A normalized search query definition."""

    marketplace: Marketplace
    filter_name: str
    keyword: str
    url: str


@dataclass(slots=True)
class ListingRecord:
    """Canonical listing data, independent from delivery state."""

    marketplace: Marketplace
    item_id: str
    canonical_id: str
    url: str
    title: str
    image_url: str | None
    raw_content: str
    price_text: str | None
    price_value: int | None
    currency: str | None
    status: str
    matched_filters: set[str] = field(default_factory=set)
    matched_keywords: set[str] = field(default_factory=set)
    search_contexts: list[SearchContext] = field(default_factory=list)

    @classmethod
    def from_scrape(
        cls,
        *,
        marketplace: Marketplace,
        url: str,
        title: str,
        image_url: str | None,
        raw_content: str,
        search_context: SearchContext,
    ) -> "ListingRecord":
        """Create a canonical listing record from a scraped card."""
        item_id = extract_marketplace_item_id(marketplace, url)
        if item_id is None:
            raise ValueError(f"Could not extract item id for {marketplace}: {url}")

        price_text, price_value, currency = extract_price(raw_content)
        canonical_url = canonical_listing_url(marketplace, item_id, fallback=url)
        return cls(
            marketplace=marketplace,
            item_id=item_id,
            canonical_id=build_canonical_id(marketplace, item_id),
            url=canonical_url,
            title=title.strip(),
            image_url=image_url,
            raw_content=raw_content.strip(),
            price_text=price_text,
            price_value=price_value,
            currency=currency,
            status=infer_listing_status(raw_content),
            matched_filters={search_context.filter_name},
            matched_keywords={search_context.keyword},
            search_contexts=[search_context],
        )

    def merge(self, other: "ListingRecord") -> None:
        """Merge search matches for the same canonical listing."""
        if self.canonical_id != other.canonical_id:
            raise ValueError("Cannot merge listings with different canonical ids")

        self.matched_filters.update(other.matched_filters)
        self.matched_keywords.update(other.matched_keywords)

        existing_contexts = {
            (context.filter_name, context.keyword, context.search_url)
            for context in self.search_contexts
        }
        for context in other.search_contexts:
            context_key = (context.filter_name, context.keyword, context.search_url)
            if context_key not in existing_contexts:
                self.search_contexts.append(context)
                existing_contexts.add(context_key)

        if not self.image_url and other.image_url:
            self.image_url = other.image_url
        if len(other.raw_content) > len(self.raw_content):
            self.raw_content = other.raw_content
        if other.price_value is not None:
            self.price_value = other.price_value
            self.price_text = other.price_text
            self.currency = other.currency
        if self.status != "sold" and other.status == "sold":
            self.status = "sold"

    def to_document(self, observed_at: datetime | None = None) -> dict[str, Any]:
        """Serialize the listing for MongoDB storage."""
        timestamp = observed_at or datetime.now(UTC)
        search_contexts = [context.to_document() for context in self.search_contexts]
        price_document = None
        if self.price_text is not None or self.price_value is not None:
            price_document = {
                "display": self.price_text,
                "amount": self.price_value,
                "currency": self.currency,
            }

        return {
            "_id": self.canonical_id,
            "listing_id": self.canonical_id,
            "marketplace": self.marketplace,
            "item_id": self.item_id,
            "canonical_url": self.url,
            "url": self.url,
            "title": self.title,
            "item_name": self.title,
            "thumbnail_url": self.image_url,
            "image": self.image_url,
            "raw_content": self.raw_content,
            "price": price_document,
            "status": self.status,
            "matched_filters": sorted(self.matched_filters),
            "matched_keywords": sorted(self.matched_keywords),
            "search_contexts": search_contexts,
            "last_seen_at": timestamp,
            "updated_at": timestamp,
        }


def build_canonical_id(marketplace: Marketplace, item_id: str) -> str:
    """Build the cross-marketplace canonical listing key."""
    return f"{marketplace}:{item_id}"


def canonical_listing_url(marketplace: Marketplace, item_id: str, fallback: str) -> str:
    """Build a canonical listing URL for supported marketplaces."""
    if marketplace == "mercari":
        if _MERCARI_SHOPS_PRODUCT_PATTERN.search(fallback):
            return fallback.split("?", maxsplit=1)[0]
        return f"https://jp.mercari.com/item/{item_id}"
    if marketplace == "rakuma":
        return f"https://item.fril.jp/{item_id}"
    if marketplace == "rakuten":
        return fallback.split("?", maxsplit=1)[0]
    return fallback


def extract_marketplace_item_id(marketplace: Marketplace, url: str) -> str | None:
    """Extract a marketplace-native listing id from the listing URL."""
    if marketplace == "mercari":
        item_match = _MERCARI_ITEM_PATTERN.search(url)
        if item_match:
            return item_match.group(1)

        shops_match = _MERCARI_SHOPS_PRODUCT_PATTERN.search(url)
        if shops_match:
            return shops_match.group(1)

        return None

    if marketplace == "rakuma":
        return _extract_last_url_segment(url, allowed_hosts=_RAKUMA_HOSTS)

    if marketplace == "rakuten":
        return _extract_last_url_segment(url, allowed_hosts=_RAKUTEN_HOSTS)

    return None


def extract_price(raw_content: str) -> tuple[str | None, int | None, str | None]:
    """Extract a normalized price from raw card content."""
    match = _PRICE_PATTERN.search(raw_content)
    if match is None:
        return None, None, None

    symbol, raw_amount = match.groups()
    amount = int(raw_amount.replace(",", ""))
    return f"{symbol}{raw_amount}", amount, "JPY"


def infer_listing_status(raw_content: str) -> str:
    """Infer the listing state from the scraped item text."""
    normalized_content = raw_content.casefold()
    if "sold" in normalized_content or "売り切れ" in raw_content:
        return "sold"
    return "active"


def _extract_last_url_segment(url: str, allowed_hosts: set[str]) -> str | None:
    """Return the last non-empty path segment for the given host."""
    host_candidate = url.split("//", maxsplit=1)[-1].split("/", maxsplit=1)[0].casefold()
    host = host_candidate.split(":", maxsplit=1)[0]
    if host and host not in allowed_hosts:
        return None

    path = url.split("?", maxsplit=1)[0].rstrip("/")
    if "/" not in path:
        return None

    segment = path.rsplit("/", maxsplit=1)[-1].strip()
    return segment or None
