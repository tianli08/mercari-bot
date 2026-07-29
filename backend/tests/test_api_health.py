"""FastAPI application plumbing and health endpoint tests."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_WEBHOOK", "https://discord.com/api/webhooks/123/test")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")

from src import database  # noqa: E402
from src.api.app import create_app  # noqa: E402
from src.watchlists import WatchlistNotFoundError  # noqa: E402

_ENGINE_MODULES_AFTER_API_IMPORT = {"discord", "selenium"}.intersection(sys.modules)

pytestmark = pytest.mark.asyncio


class FakeDatabaseClient:
    """In-memory database client with the same collection attributes as production."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["api_tests"]
        self.listings = self.db["marketplace_listings"]
        self.alerts = self.db["listing_alerts"]
        self.users = self.db["users"]
        self.watchlists = self.db["watchlists"]
        self.destinations = self.db["destinations"]
        self.keyword_registry = self.db["keyword_registry"]
        self.preset_keywords = self.db["preset_keywords"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the same indexes as the production client."""
        await database.DatabaseClient.ensure_indexes(self)


@pytest.fixture
def fake_database(monkeypatch: pytest.MonkeyPatch) -> FakeDatabaseClient:
    """Patch database access to use an in-memory MongoDB fake."""
    fake_client = FakeDatabaseClient()
    monkeypatch.setattr(database, "db_client", fake_client)
    return fake_client


async def test_health_returns_ok(fake_database: FakeDatabaseClient) -> None:
    """The health endpoint reports success after a database ping."""
    application = create_app()

    async with _client_for(application) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_returns_degraded_when_ping_fails(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The health endpoint returns a secret-safe 503 when MongoDB is unavailable."""
    monkeypatch.setattr(
        fake_database.db,
        "command",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )
    application = create_app()

    async with _client_for(application) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
    assert "database unavailable" not in response.text


async def test_app_factory_does_not_import_engine_modules(fake_database: FakeDatabaseClient) -> None:
    """Building the API application does not load Selenium or discord.py."""
    application = create_app()

    assert application.title == "Marketplace Monitor API"
    assert "/api/v1/health" in application.openapi()["paths"]
    assert not _ENGINE_MODULES_AFTER_API_IMPORT


async def test_lifespan_initializes_indexes_and_closes_database(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API fails fast through index setup and closes its Mongo client on shutdown."""
    ensure_indexes = AsyncMock()
    close_client = Mock()
    monkeypatch.setattr(fake_database, "ensure_indexes", ensure_indexes)
    monkeypatch.setattr(fake_database.client, "close", close_client)
    application = create_app()

    async with application.router.lifespan_context(application):
        ensure_indexes.assert_awaited_once_with()

    close_client.assert_called_once_with()


async def test_domain_exception_handler_returns_error_envelope(fake_database: FakeDatabaseClient) -> None:
    """Domain exceptions map to their configured HTTP status and machine-readable code."""
    application = create_app()

    @application.get("/api/v1/test-not-found")
    async def raise_not_found() -> None:
        raise WatchlistNotFoundError("sensitive-internal-id")

    async with _client_for(application) as client:
        response = await client.get("/api/v1/test-not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "Resource not found", "code": "not_found"}
    assert "sensitive-internal-id" not in response.text


async def test_unhandled_exception_is_generic_and_secret_safe(
    fake_database: FakeDatabaseClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unexpected errors redact their message from both the response and traceback log."""
    sensitive_message = "https://discord.com/api/webhooks/123/plaintext-token"
    application = create_app()

    @application.get("/api/v1/test-internal-error")
    async def raise_internal_error() -> None:
        raise RuntimeError(sensitive_message)

    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="mercari_bot"):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/test-internal-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "code": "internal_error"}
    assert sensitive_message not in response.text
    assert sensitive_message not in caplog.text


async def test_cors_allows_local_dashboard_origin(fake_database: FakeDatabaseClient) -> None:
    """The default local Next.js origin receives the CORS allow-origin header."""
    application = create_app()

    async with _client_for(application) as client:
        response = await client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},
        )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def _client_for(application: object) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=application)
    return httpx.AsyncClient(transport=transport, base_url="http://test")
