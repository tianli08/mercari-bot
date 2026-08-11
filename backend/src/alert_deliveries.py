"""Tenant alert-delivery records exposed by the recent-alert feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .listings import Marketplace


@dataclass(frozen=True, slots=True)
class AlertDeliveryRecord:
    """Allowlisted durable delivery data loaded from MongoDB."""

    _id: str
    listing_id: str
    destination_id: str
    marketplace: Marketplace
    title: str
    canonical_url: str
    matched_keywords: list[str]
    status: str
    created_at: datetime
    delivered_at: datetime | None
