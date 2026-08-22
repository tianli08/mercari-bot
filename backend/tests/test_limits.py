"""Limit settings validation and tenant-limit resolution tests."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Settings  # noqa: E402
from src.limits import resolve_tenant_limits  # noqa: E402

_LIMIT_ENV_VARS = (
    "MAX_KEYWORDS_PER_USER",
    "MAX_KEYWORDS_PER_REQUEST",
    "AUTH_RATE_LIMIT_ATTEMPTS",
    "AUTH_RATE_LIMIT_WINDOW_SECONDS",
)


def _clear_limit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop env overrides so Settings tests observe field defaults."""
    for name in _LIMIT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_limit_settings_use_generous_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings load without new env vars and keep the frozen generous defaults."""
    _clear_limit_overrides(monkeypatch)

    loaded = Settings(_env_file=None)

    assert loaded.max_keywords_per_user == 100
    assert loaded.max_keywords_per_request == 50
    assert loaded.auth_rate_limit_attempts == 10
    assert loaded.auth_rate_limit_window_seconds == 60


def test_limit_settings_reject_out_of_range_values() -> None:
    """Zero, negative, and oversized limits fail at Settings construction."""
    with pytest.raises(ValidationError, match="max_keywords_per_user"):
        Settings(max_keywords_per_user=0)
    with pytest.raises(ValidationError, match="max_keywords_per_request"):
        Settings(max_keywords_per_request=0)
    with pytest.raises(ValidationError, match="auth_rate_limit_attempts"):
        Settings(auth_rate_limit_attempts=0)
    with pytest.raises(ValidationError, match="auth_rate_limit_window_seconds"):
        Settings(auth_rate_limit_window_seconds=0)
    with pytest.raises(ValidationError, match="max_keywords_per_user"):
        Settings(max_keywords_per_user=10001)


def test_limit_settings_reject_request_bound_above_user_cap() -> None:
    """A request list bound larger than the per-user cap is a startup failure."""
    with pytest.raises(ValidationError, match="MAX_KEYWORDS_PER_REQUEST") as inverted:
        Settings(max_keywords_per_user=10, max_keywords_per_request=50)

    assert "MAX_KEYWORDS_PER_USER" in str(inverted.value)


def test_limit_settings_allow_equal_request_and_user_caps() -> None:
    """The request bound may equal the per-user cap."""
    loaded = Settings(max_keywords_per_user=50, max_keywords_per_request=50)

    assert loaded.max_keywords_per_request == loaded.max_keywords_per_user == 50


def test_resolve_tenant_limits_returns_settings_keyword_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default resolution reads the keyword cap from Settings and ignores plan."""
    _clear_limit_overrides(monkeypatch)
    overridden = Settings(_env_file=None, max_keywords_per_user=25, max_keywords_per_request=10)
    monkeypatch.setattr("src.limits.settings", overridden)

    limits = resolve_tenant_limits("free")

    assert limits.max_keywords_per_user == 25
    assert resolve_tenant_limits("ignored-plan").max_keywords_per_user == 25


def test_tenant_limits_are_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolved limits cannot be mutated by callers."""
    _clear_limit_overrides(monkeypatch)
    monkeypatch.setattr("src.limits.settings", Settings(_env_file=None))

    limits = resolve_tenant_limits("free")

    with pytest.raises(FrozenInstanceError):
        limits.max_keywords_per_user = 1  # type: ignore[misc]
