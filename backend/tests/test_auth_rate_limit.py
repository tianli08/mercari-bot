"""Per-key auth rate limiter unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.auth.exceptions import RateLimitedError  # noqa: E402
from src.api.auth.rate_limit import (  # noqa: E402
    InMemoryKeyedRateLimiter,
    get_auth_rate_limiter,
    login_email_key,
    login_ip_key,
    reset_auth_rate_limiter,
    signup_ip_key,
)
from src.config import settings  # noqa: E402


class _FakeClock:
    """Monotonic clock that tests can advance without sleeping."""

    def __init__(self, now: float = 1_000.0) -> None:
        """Start the clock at an arbitrary monotonic timestamp."""
        self.now = now

    def __call__(self) -> float:
        """Return the current fake timestamp."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds``."""
        self.now += seconds


@pytest.fixture
def tiny_auth_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the auth budget so exhaustion is cheap to prove."""
    monkeypatch.setattr(settings, "auth_rate_limit_attempts", 2)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 10)


def test_hit_allows_until_budget_then_reports_retry_after(tiny_auth_limits: None) -> None:
    """A key is admitted until the attempt budget is spent, then Retry-After is set."""
    clock = _FakeClock()
    limiter = InMemoryKeyedRateLimiter(clock=clock)

    first = limiter.hit("ip:1")
    second = limiter.hit("ip:1")
    third = limiter.hit("ip:1")

    assert first.allowed
    assert second.allowed
    assert not third.allowed
    assert third.retry_after_seconds == 10


def test_separate_keys_do_not_share_a_budget(tiny_auth_limits: None) -> None:
    """Exhausting one key leaves an unrelated key with a full budget."""
    limiter = InMemoryKeyedRateLimiter(clock=_FakeClock())
    limiter.hit("signup:ip:1")
    limiter.hit("signup:ip:1")

    other = limiter.hit("signup:ip:2")
    login = limiter.hit("login:ip:1")

    assert not limiter.hit("signup:ip:1").allowed
    assert other.allowed
    assert login.allowed


def test_multi_key_hit_denies_when_any_key_is_exhausted(tiny_auth_limits: None) -> None:
    """Login-style dual keying rejects the request if either key is spent."""
    limiter = InMemoryKeyedRateLimiter(clock=_FakeClock())
    email = login_email_key("victim@example.com")
    limiter.hit(login_ip_key("1.1.1.1"), email)
    limiter.hit(login_ip_key("2.2.2.2"), email)

    denied = limiter.hit(login_ip_key("3.3.3.3"), email)
    fresh = limiter.hit(login_ip_key("3.3.3.3"), login_email_key("other@example.com"))

    assert not denied.allowed
    assert denied.retry_after_seconds is not None
    assert denied.retry_after_seconds >= 1
    assert fresh.allowed


def test_stale_keys_expire_after_the_window(tiny_auth_limits: None) -> None:
    """Idle keys are dropped once their window elapses so the map cannot grow forever."""
    clock = _FakeClock()
    limiter = InMemoryKeyedRateLimiter(clock=clock)
    limiter.hit("stale")
    assert "stale" in limiter.stored_keys()

    clock.advance(settings.auth_rate_limit_window_seconds + 0.01)
    limiter.hit("fresh")

    assert "stale" not in limiter.stored_keys()
    assert "fresh" in limiter.stored_keys()


def test_window_expiry_restores_access_without_sleeping(tiny_auth_limits: None) -> None:
    """Advancing the injected clock replenishes a spent key."""
    clock = _FakeClock()
    limiter = InMemoryKeyedRateLimiter(clock=clock)
    limiter.hit("ip:1")
    limiter.hit("ip:1")
    assert not limiter.hit("ip:1").allowed

    clock.advance(settings.auth_rate_limit_window_seconds + 0.01)

    recovered = limiter.hit("ip:1")
    assert recovered.allowed
    assert recovered.retry_after_seconds is None


def test_reset_clears_hits_and_restores_the_real_clock(tiny_auth_limits: None) -> None:
    """Tests can wipe limiter state instead of waiting out a window."""
    clock = _FakeClock()
    limiter = get_auth_rate_limiter()
    limiter.set_clock(clock)
    limiter.hit("ip:1")
    limiter.hit("ip:1")
    assert not limiter.hit("ip:1").allowed

    reset_auth_rate_limiter()

    assert limiter.stored_keys() == frozenset()
    assert limiter.hit("ip:1").allowed


def test_retry_after_is_a_positive_integer(tiny_auth_limits: None) -> None:
    """Rejected hits always report a whole number of seconds of at least one."""
    limiter = InMemoryKeyedRateLimiter(clock=_FakeClock())
    limiter.hit("ip:1")
    limiter.hit("ip:1")
    denied = limiter.hit("ip:1")

    assert denied.retry_after_seconds is not None
    assert isinstance(denied.retry_after_seconds, int)
    assert denied.retry_after_seconds >= 1


def test_rate_limited_error_clamps_retry_after_to_at_least_one_second() -> None:
    """The public 429 mapping never receives a zero or negative Retry-After."""
    error = RateLimitedError(0)

    assert error.retry_after_seconds == 1


def test_signup_and_login_key_helpers_use_distinct_namespaces() -> None:
    """Signup IP, login IP, and login email budgets cannot collide by construction."""
    ip = "203.0.113.9"
    email = "user@example.com"

    assert len({signup_ip_key(ip), login_ip_key(ip), login_email_key(email)}) == 3
