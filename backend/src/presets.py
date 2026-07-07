"""Preset keyword catalog models and normalization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .keyword_registry import normalize_registry_keyword
from .listings import Marketplace

_PRESET_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class PresetNameExistsError(Exception):
    """Raised when a preset name already exists for the same marketplace."""


class PresetNotFoundError(Exception):
    """Raised when a preset keyword record cannot be found."""


@dataclass(slots=True)
class PresetKeywordRecord:
    """Centrally managed preset keyword catalog entry stored in MongoDB."""

    _id: str
    marketplace: Marketplace
    name: str
    keywords: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        name: str,
        keywords: list[str],
        marketplace: Marketplace = "mercari",
        enabled: bool = True,
        created_at: datetime | None = None,
    ) -> "PresetKeywordRecord":
        """Create a preset keyword record with normalized fields and deterministic id."""
        timestamp = created_at or datetime.now(UTC)
        normalized_name = normalize_preset_name(name)
        return cls(
            _id=build_preset_id(marketplace, normalized_name),
            marketplace=marketplace,
            name=normalized_name,
            keywords=_normalize_preset_keywords(keywords),
            enabled=enabled,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_document(self) -> dict[str, Any]:
        """Serialize the preset keyword record for MongoDB storage."""
        return {
            "_id": self._id,
            "marketplace": self.marketplace,
            "name": self.name,
            "keywords": self.keywords,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def build_preset_id(marketplace: Marketplace, name: str) -> str:
    """Build the deterministic preset id for a marketplace and display name."""
    normalized_name = normalize_preset_name(name)
    slug = _PRESET_SLUG_PATTERN.sub("-", normalized_name.lower()).strip("-")
    if not slug:
        raise ValueError("preset slug must be non-empty")
    return f"{marketplace}:{slug}"


def normalize_preset_name(name: str) -> str:
    """Normalize a preset display name and ensure it is non-empty."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("preset name must be non-empty")
    return normalized_name


def _normalize_preset_keywords(keywords: list[str]) -> list[str]:
    normalized_keywords: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        try:
            normalized_keyword = normalize_registry_keyword(keyword)
        except ValueError:
            continue
        if normalized_keyword in seen:
            continue
        normalized_keywords.append(normalized_keyword)
        seen.add(normalized_keyword)
    if not normalized_keywords:
        raise ValueError("preset keywords must be non-empty")
    return normalized_keywords
