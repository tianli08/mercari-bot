"""In-process per-key rate limiting for unauthenticated auth routes."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fastapi import Request

from ...config import settings
from ...users import normalize_email
from .exceptions import RateLimitedError
from .schemas import LoginRequest, SignupRequest


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of recording one request against one or more limiter keys."""

    allowed: bool
    retry_after_seconds: int | None = None


class InMemoryKeyedRateLimiter:
    """Sliding-window counter keyed by client identity, not by tenant.

    Idle keys expire after the configured window so spraying random IPs or
    emails cannot grow the map without bound. The clock is injectable so tests
    can advance the window without sleeping.
    """

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        """Create an empty limiter that reads budget settings on every hit."""
        self._default_clock = clock or time.monotonic
        self._clock = self._default_clock
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def set_clock(self, clock: Callable[[], float]) -> None:
        """Replace the time source used to age hits and idle keys."""
        self._clock = clock

    def reset(self) -> None:
        """Drop all recorded hits and restore the limiter's default clock."""
        with self._lock:
            self._hits.clear()
            self._clock = self._default_clock

    def stored_keys(self) -> frozenset[str]:
        """Return the keys currently retained in memory."""
        with self._lock:
            return frozenset(self._hits)

    def hit(self, *keys: str) -> RateLimitDecision:
        """Record this request against every key and deny if any is exhausted.

        Every supplied key is incremented, including when another key is already
        over budget, so a request that happened still counts on all dimensions.
        """
        if not keys:
            return RateLimitDecision(allowed=True)

        with self._lock:
            now = self._clock()
            window = float(settings.auth_rate_limit_window_seconds)
            max_attempts = settings.auth_rate_limit_attempts
            cutoff = now - window
            self._drop_idle_keys(cutoff)

            retry_after = 0
            allowed = True
            for key in keys:
                timestamps = [stamp for stamp in self._hits.get(key, []) if stamp > cutoff]
                if len(timestamps) >= max_attempts:
                    allowed = False
                    oldest = timestamps[0]
                    remaining = window - (now - oldest)
                    retry_after = max(retry_after, max(1, math.ceil(remaining)))
                timestamps.append(now)
                self._hits[key] = timestamps

            if allowed:
                return RateLimitDecision(allowed=True)
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

    def _drop_idle_keys(self, cutoff: float) -> None:
        idle_keys = [
            key for key, timestamps in self._hits.items() if not timestamps or timestamps[-1] <= cutoff
        ]
        for key in idle_keys:
            del self._hits[key]


_limiter = InMemoryKeyedRateLimiter()


def get_auth_rate_limiter() -> InMemoryKeyedRateLimiter:
    """Return the process-wide auth limiter used by signup and login."""
    return _limiter


def reset_auth_rate_limiter() -> None:
    """Clear limiter state between tests (and restore the real clock)."""
    _limiter.reset()


def signup_ip_key(ip: str) -> str:
    """Return the limiter key for a signup attempt from one client IP."""
    return f"signup:ip:{ip}"


def login_ip_key(ip: str) -> str:
    """Return the limiter key for a login attempt from one client IP."""
    return f"login:ip:{ip}"


def login_email_key(email: str) -> str:
    """Return the limiter key for a login attempt against one normalized email."""
    return f"login:email:{email}"


def client_ip(request: Request) -> str:
    """Return ``request.client.host``, falling back when the client is missing.

    Reverse-proxy forwarded headers are ignored until Phase 7.
    """
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _raise_if_limited(keys: Sequence[str]) -> None:
    decision = get_auth_rate_limiter().hit(*keys)
    if not decision.allowed:
        raise RateLimitedError(decision.retry_after_seconds or 1)


async def enforce_signup_rate_limit(request: Request, payload: SignupRequest) -> None:
    """Reject signup bursts from one client IP before password hashing."""
    _ = payload
    _raise_if_limited((signup_ip_key(client_ip(request)),))


async def enforce_login_rate_limit(request: Request, payload: LoginRequest) -> None:
    """Reject login bursts per client IP and per normalized email before hashing."""
    _raise_if_limited(
        (
            login_ip_key(client_ip(request)),
            login_email_key(normalize_email(str(payload.email))),
        )
    )
