"""Discord webhook delivery transport tests."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_WEBHOOK", "https://discord.com/api/webhooks/123/test")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "123")
os.environ.setdefault("SAVED_CHANNEL_ID", "456")

from src import database  # noqa: E402
from src.destinations import DestinationRecord  # noqa: E402
from src.listings import ListingRecord  # noqa: E402
from src.webhook_delivery import (  # noqa: E402
    DiscordWebhookSender,
    WebhookPermanentError,
    WebhookTransientError,
)

pytestmark = pytest.mark.asyncio

WEBHOOK_TOKEN = "super-secret-token-ABC123"
WEBHOOK_URL = f"https://discord.com/api/webhooks/123456789/{WEBHOOK_TOKEN}"


class _StubResponse:
    def __init__(
        self,
        status: int,
        *,
        json_body: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.json_body = json_body
        self.headers = headers or {}

    async def json(self, *, content_type: str | None = None) -> object:
        del content_type
        if isinstance(self.json_body, Exception):
            raise self.json_body
        return self.json_body


class _StubRequestContext:
    def __init__(self, outcome: _StubResponse | Exception) -> None:
        self.outcome = outcome

    async def __aenter__(self) -> _StubResponse:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def __aexit__(self, *args: object) -> None:
        del args


class _StubSession:
    def __init__(self, outcomes: list[_StubResponse | Exception]) -> None:
        self.outcomes = outcomes
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> _StubRequestContext:
        self.requests.append((url, kwargs))
        return _StubRequestContext(self.outcomes.pop(0))


class FakeDatabaseClient:
    """In-memory database client with production collection attributes."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["webhook_delivery_tests"]
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
def skip_verification_stamp(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Stub verification persistence for transport-only tests."""
    stamp = AsyncMock()
    monkeypatch.setattr(database, "mark_destination_verified", stamp)
    return stamp


def build_destination() -> DestinationRecord:
    """Build an encrypted Discord webhook destination."""
    return DestinationRecord.new(owner_id="owner-1", webhook_url=WEBHOOK_URL, label="Main")


def build_listing() -> ListingRecord:
    """Build a canonical listing for webhook tests."""
    return ListingRecord(
        marketplace="mercari",
        item_id="m123",
        canonical_id="mercari:m123",
        url="https://jp.mercari.com/item/m123",
        title="Listing m123",
        image_url="https://example.com/image.jpg",
        raw_content="Listing body JPY 1200",
        price_text="JPY 1200",
        price_value=1200,
        currency="JPY",
        status="active",
        matched_filters={"designer"},
        matched_keywords={"rick owens"},
    )


def recording_sleep(delays: list[float]) -> Callable[[float], Awaitable[None]]:
    """Return a no-wait sleep replacement that records delays."""

    async def sleep(delay: float) -> None:
        delays.append(delay)

    return sleep


async def test_success_posts_embed_only_and_stamps_destination(skip_verification_stamp: AsyncMock) -> None:
    """A successful request posts the shared listing embed with no interactive view."""
    session = _StubSession([_StubResponse(204)])
    destination = build_destination()

    await DiscordWebhookSender(session, timeout_seconds=7.5)(destination, build_listing())

    assert len(session.requests) == 1
    target_url, request = session.requests[0]
    assert target_url == WEBHOOK_URL
    assert request["allow_redirects"] is False
    assert request["timeout"].total == 7.5
    assert set(request["json"]) == {"embeds"}
    embed = request["json"]["embeds"][0]
    assert embed["title"] == "Listing m123"
    assert embed["url"] == "https://jp.mercari.com/item/m123"
    assert embed["footer"]["text"] == "ArchiveStatic | mercari:m123"
    assert "view" not in request["json"]
    assert "components" not in request["json"]
    skip_verification_stamp.assert_awaited_once()


async def test_rate_limit_retries_after_json_delay_then_succeeds(skip_verification_stamp: AsyncMock) -> None:
    """A 429 response honors its JSON retry delay and retries once."""
    session = _StubSession([_StubResponse(429, json_body={"retry_after": 0.25}), _StubResponse(204)])
    delays: list[float] = []

    await DiscordWebhookSender(session, max_attempts=3, sleep=recording_sleep(delays))(
        build_destination(),
        build_listing(),
    )

    assert len(session.requests) == 2
    assert delays == [0.25]


async def test_rate_limit_uses_header_fallback(skip_verification_stamp: AsyncMock) -> None:
    """A malformed 429 body falls back to the Retry-After header."""
    session = _StubSession(
        [
            _StubResponse(429, json_body=ValueError("bad JSON"), headers={"Retry-After": "0.5"}),
            _StubResponse(204),
        ]
    )
    delays: list[float] = []

    await DiscordWebhookSender(session, sleep=recording_sleep(delays))(build_destination(), build_listing())

    assert delays == [0.5]


async def test_rate_limit_exhaustion_is_capped(skip_verification_stamp: AsyncMock) -> None:
    """Repeated rate limits stop at the configured attempt cap."""
    session = _StubSession([_StubResponse(429, json_body={"retry_after": 0}) for _ in range(5)])

    with pytest.raises(WebhookTransientError):
        await DiscordWebhookSender(session, max_attempts=3, sleep=recording_sleep([]))(
            build_destination(),
            build_listing(),
        )

    assert len(session.requests) == 3


async def test_not_found_is_permanent_and_not_retried(skip_verification_stamp: AsyncMock) -> None:
    """A missing webhook raises a permanent error after one request."""
    session = _StubSession([_StubResponse(404)])

    with pytest.raises(WebhookPermanentError):
        await DiscordWebhookSender(session, max_attempts=3)(build_destination(), build_listing())

    assert len(session.requests) == 1


@pytest.mark.parametrize(
    "outcome",
    [
        _StubResponse(503),
        aiohttp.ClientConnectionError(f"failed: {WEBHOOK_URL}"),
        TimeoutError(f"timed out posting to {WEBHOOK_URL}"),
    ],
)
async def test_transient_failures_retry_then_raise_without_secret(
    outcome: _StubResponse | Exception,
    caplog: pytest.LogCaptureFixture,
    skip_verification_stamp: AsyncMock,
) -> None:
    """Server and connection failures exhaust retries with secret-safe errors and logs."""
    del skip_verification_stamp
    outcomes = [outcome, outcome]
    session = _StubSession(outcomes)
    caplog.set_level(logging.WARNING, logger="mercari_bot")

    with pytest.raises(WebhookTransientError) as raised:
        await DiscordWebhookSender(session, max_attempts=2, sleep=recording_sleep([]))(
            build_destination(),
            build_listing(),
        )

    assert len(session.requests) == 2
    assert_secret_absent(str(raised.value), caplog.records)


@pytest.mark.parametrize(
    ("outcomes", "error_type", "expected_requests"),
    [
        ([_StubResponse(404)], WebhookPermanentError, 1),
        ([_StubResponse(429, json_body={"retry_after": 0})] * 2, WebhookTransientError, 2),
        ([_StubResponse(502)] * 2, WebhookTransientError, 2),
        ([aiohttp.ClientConnectionError(WEBHOOK_URL)] * 2, WebhookTransientError, 2),
        ([TimeoutError(WEBHOOK_URL)] * 2, WebhookTransientError, 2),
    ],
)
async def test_all_failure_modes_keep_webhook_secret_out_of_errors_and_logs(
    outcomes: list[_StubResponse | Exception],
    error_type: type[WebhookPermanentError] | type[WebhookTransientError],
    expected_requests: int,
    caplog: pytest.LogCaptureFixture,
    skip_verification_stamp: AsyncMock,
) -> None:
    """Permanent, rate-limit, server, connection, and timeout failures never expose the webhook secret."""
    del skip_verification_stamp
    session = _StubSession(outcomes.copy())
    caplog.set_level(logging.WARNING, logger="mercari_bot")

    with pytest.raises(error_type) as raised:
        await DiscordWebhookSender(session, max_attempts=2, sleep=recording_sleep([]))(
            build_destination(),
            build_listing(),
        )

    assert len(session.requests) == expected_requests
    assert_secret_absent(str(raised.value), caplog.records)


async def test_verified_at_is_set_once_across_successful_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated successful sends preserve the destination's first verification timestamp."""
    fake_client = FakeDatabaseClient()
    monkeypatch.setattr(database, "db_client", fake_client)
    destination = await database.create_destination(owner_id="owner-1", webhook_url=WEBHOOK_URL, label="Main")
    session = _StubSession([_StubResponse(204), _StubResponse(204)])
    sender = DiscordWebhookSender(session)

    await sender(destination, build_listing())
    first_document = await fake_client.destinations.find_one({"_id": destination._id})
    assert first_document is not None
    first_verified_at = first_document["verified_at"]
    first_updated_at = first_document["updated_at"]
    assert first_verified_at is not None

    await sender(destination, build_listing())
    second_document = await fake_client.destinations.find_one({"_id": destination._id})
    assert second_document is not None
    assert second_document["verified_at"] == first_verified_at
    assert second_document["updated_at"] == first_updated_at


async def test_verification_stamp_failure_is_logged_and_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Persistence trouble after a successful post cannot turn delivery into a failure."""

    async def fail_stamp(destination_id: str, verified_at: object) -> None:
        del destination_id, verified_at
        raise RuntimeError(f"database failed near {WEBHOOK_URL}")

    monkeypatch.setattr(database, "mark_destination_verified", fail_stamp)
    caplog.set_level(logging.ERROR, logger="mercari_bot")
    session = _StubSession([_StubResponse(204)])

    await DiscordWebhookSender(session)(build_destination(), build_listing())

    assert len(session.requests) == 1
    assert any("verification stamp failed" in record.getMessage() for record in caplog.records)
    assert_secret_absent("", caplog.records)


def assert_secret_absent(exception_text: str, records: list[logging.LogRecord]) -> None:
    """Assert the webhook token and full URL are absent from errors and logs."""
    combined_logs = "\n".join(record.getMessage() for record in records)
    assert WEBHOOK_TOKEN not in exception_text
    assert WEBHOOK_URL not in exception_text
    assert WEBHOOK_TOKEN not in combined_logs
    assert WEBHOOK_URL not in combined_logs
