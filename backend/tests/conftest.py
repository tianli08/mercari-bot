"""Shared test environment configuration."""

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-with-at-least-32-characters")
os.environ.setdefault("API_ENVIRONMENT", "test")
os.environ.setdefault("AUTH_COOKIE_SECURE", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.auth.rate_limit import reset_auth_rate_limiter  # noqa: E402


@pytest.fixture(autouse=True)
def reset_auth_limiter_state() -> Iterator[None]:
    """Isolate in-process auth rate-limit budgets across tests."""
    reset_auth_rate_limiter()
    yield
    reset_auth_rate_limiter()
