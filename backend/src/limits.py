"""Tenant limit resolution and the frozen Step 3.5 policy.

Policy (enforcement is plans 3.5.2 and 3.5.4, not this module):

- ``max_keywords_per_user`` (default 100): stored watchlist keywords per tenant
  across all watchlists, including disabled ones, after ``normalize_keywords``
  deduplicates each watchlist. Counting only enabled lists would let a tenant
  stockpile keywords while disabled and exceed the cap on one toggle.
- ``max_keywords_per_request`` (default 50): maximum keyword-list length in one
  request body. Must not exceed ``max_keywords_per_user``.
- ``auth_rate_limit_attempts`` (default 10) and
  ``auth_rate_limit_window_seconds`` (default 60): unauthenticated limiter
  budget. Signup keys on client IP (``request.client.host``). Login keys on
  client IP and on ``users.normalize_email``. Reverse-proxy IP derivation is
  deferred to Phase 7.
- Violations: keyword cap → 409 ``keyword_limit_exceeded``; auth rate limit →
  429 ``rate_limited`` with a positive integer ``Retry-After`` seconds.
  Messages stay static and generic (no counts, caps, emails, or IPs).

Auth rate-limit parameters are global Settings, not fields on
``TenantLimits``. The limiter keys unauthenticated clients, not tenants.

Phase 8 will vary keyword caps by ``user.plan``. Call sites must go through
``resolve_tenant_limits`` rather than reading ``max_keywords_per_user``.
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
            the Settings keyword cap. Phase 8 will branch on plan here.
    """
    return TenantLimits(max_keywords_per_user=settings.max_keywords_per_user)
