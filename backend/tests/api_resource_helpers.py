"""Shared in-memory database and authenticated-client helpers for resource API tests."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import database  # noqa: E402

PASSWORD = "correct horse battery staple"
WEBHOOK_TOKEN = "super-secret-webhook-token"
WEBHOOK_URL = f"https://discord.com/api/webhooks/123456789/{WEBHOOK_TOKEN}"


class ApiResourceDatabase:
    """In-memory database client with the production collection surface."""

    def __init__(self, database_name: str) -> None:
        """Initialize isolated MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client[database_name]
        self.listings = self.db["marketplace_listings"]
        self.alerts = self.db["listing_alerts"]
        self.users = self.db["users"]
        self.watchlists = self.db["watchlists"]
        self.destinations = self.db["destinations"]
        self.keyword_registry = self.db["keyword_registry"]
        self.preset_keywords = self.db["preset_keywords"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the same indexes as the production database client."""
        await database.DatabaseClient.ensure_indexes(self)


def client_for(application: object) -> httpx.AsyncClient:
    """Return an isolated cookie-aware ASGI client."""
    transport = httpx.ASGITransport(app=application)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def signup(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    """Create a tenant through the public API and retain its session cookie."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 201
    return response.json()


async def create_destination(client: httpx.AsyncClient, label: str = "Main") -> dict[str, object]:
    """Create one destination through the public API."""
    response = await client.post(
        "/api/v1/destinations",
        json={"label": label, "webhook_url": WEBHOOK_URL},
    )
    assert response.status_code == 201
    return response.json()
