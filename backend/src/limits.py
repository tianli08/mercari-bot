"""Tenant keyword limits.

The total cap includes disabled watchlists after per-list normalization.
Request bodies also have a keyword-list limit, bounded by the total cap.
Keyword-cap violations return a generic 409 keyword_limit_exceeded response.
Clerk manages authentication rate limits independently.

Call sites resolve limits through resolve_tenant_limits so billing tiers can
change without changing resource authorization.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import settings


@dataclass(frozen=True, slots=True)
class TenantLimits:
    """Effective per-tenant guardrails for one request."""

    max_keywords_per_user: int


def resolve_tenant_limits(user_plan: str) -> TenantLimits:
    """Return this tenant's effective keyword-cap limits.

    Args:
        user_plan: Tenant billing plan. Ignored today so every tenant receives
            the Settings keyword cap.
    """
    return TenantLimits(max_keywords_per_user=settings.max_keywords_per_user)
