"""Tenant-scoped destination CRUD, verification, integrity, and redaction tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from api_resource_helpers import (
    WEBHOOK_TOKEN,
    WEBHOOK_URL,
    ApiResourceDatabase,
    client_for,
    create_destination,
    signup,
)

from src import database
from src.api.app import create_app
from src.destinations import DestinationRecord
from src.webhook_errors import WebhookPermanentError, WebhookTransientError

pytestmark = pytest.mark.asyncio


@pytest.fixture
def api_database(monkeypatch: pytest.MonkeyPatch) -> ApiResourceDatabase:
    """Patch persistence to an isolated in-memory database."""
    fake = ApiResourceDatabase("destination_api_tests")
    monkeypatch.setattr(database, "db_client", fake)
    return fake


async def test_destination_crud_redacts_secrets_and_enforces_references(
    api_database: ApiResourceDatabase,
) -> None:
    """Destination metadata is manageable while webhook credentials stay secret."""
    application = create_app()
    async with client_for(application) as client:
        tenant = await signup(client, "destination-owner@example.com")
        created_response = await client.post(
            "/api/v1/destinations",
            json={"label": "  Main Webhook  ", "webhook_url": WEBHOOK_URL},
        )
        assert created_response.status_code == 201
        created = created_response.json()
        assert set(created) == {"id", "type", "label", "verified_at", "created_at", "updated_at"}
        assert created["label"] == "Main Webhook"
        assert created["verified_at"] is None
        assert WEBHOOK_TOKEN not in created_response.text

        stored = await api_database.destinations.find_one({"_id": created["id"]})
        assert stored is not None
        assert stored["owner_id"] == tenant["id"]
        assert stored["webhook_url_encrypted"] != WEBHOOK_URL
        assert WEBHOOK_TOKEN not in stored["webhook_url_encrypted"]
        assert stored["webhook_url_encrypted"] not in created_response.text

        await database.mark_destination_verified_for_owner(created["id"], tenant["id"])
        replacement_url = "https://discord.com/api/webhooks/987654321/replacement-secret-token"
        updated = await client.patch(
            f"/api/v1/destinations/{created['id']}",
            json={"label": "Updated", "webhook_url": replacement_url},
        )
        fetched = await client.get(f"/api/v1/destinations/{created['id']}")
        listed = await client.get("/api/v1/destinations")
        assert updated.status_code == fetched.status_code == listed.status_code == 200
        assert updated.json()["label"] == "Updated"
        assert updated.json()["verified_at"] is None
        assert listed.json() == [fetched.json()]
        assert "replacement-secret-token" not in updated.text

        watchlist = await client.post(
            "/api/v1/watchlists",
            json={"name": "Uses Destination", "destination_id": created["id"]},
        )
        in_use = await client.delete(f"/api/v1/destinations/{created['id']}")
        assert in_use.status_code == 409
        assert in_use.json()["code"] == "destination_in_use"

        assert (await client.delete(f"/api/v1/watchlists/{watchlist.json()['id']}")).status_code == 204
        assert (await client.delete(f"/api/v1/destinations/{created['id']}")).status_code == 204
        assert (await client.delete(f"/api/v1/destinations/{created['id']}")).status_code == 404


async def test_destination_verification_uses_owned_boundary_and_creates_no_alert(
    api_database: ApiResourceDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful fixed-message verification stamps metadata but not the alert feed."""
    from src.webhook_delivery import DiscordWebhookVerifier

    observed: list[tuple[str, str]] = []

    async def verify(
        _: object,
        destination: DestinationRecord,
        owner_id: str,
    ) -> object:
        destination_id = destination._id
        observed.append((destination_id, owner_id))
        return await database.mark_destination_verified_for_owner(
            destination_id,
            owner_id,
            datetime(2025, 1, 1, tzinfo=UTC),
        )

    monkeypatch.setattr(DiscordWebhookVerifier, "__call__", verify)
    application = create_app()
    async with client_for(application) as client:
        tenant = await signup(client, "verify@example.com")
        destination = await create_destination(client)
        response = await client.post(f"/api/v1/destinations/{destination['id']}/verify")

    assert response.status_code == 200
    assert response.json()["verified_at"].startswith("2025-01-01T00:00:00")
    assert observed == [(destination["id"], tenant["id"])]
    assert await api_database.alerts.count_documents({}) == 0
    assert WEBHOOK_TOKEN not in response.text


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (WebhookPermanentError("destination", f"rejected {WEBHOOK_URL}"), 422, "webhook_rejected"),
        (WebhookTransientError("destination", f"unavailable {WEBHOOK_URL}"), 503, "webhook_unavailable"),
    ],
)
async def test_destination_verification_failures_are_stable_and_secret_free(
    api_database: ApiResourceDatabase,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    """Permanent and retryable verification failures expose only stable public errors."""
    from src.webhook_delivery import DiscordWebhookVerifier

    async def fail(_: object, __: object, ___: str) -> None:
        raise error

    monkeypatch.setattr(DiscordWebhookVerifier, "__call__", fail)
    application = create_app()
    async with client_for(application) as client:
        await signup(client, f"{code}@example.com")
        destination = await create_destination(client)
        response = await client.post(f"/api/v1/destinations/{destination['id']}/verify")

    assert response.status_code == status_code
    assert response.json()["code"] == code
    assert WEBHOOK_TOKEN not in response.text
    stored = await api_database.destinations.find_one({"_id": destination["id"]})
    assert stored is not None
    assert stored["verified_at"] is None


async def test_destination_routes_hide_foreign_ids_and_reject_injection(
    api_database: ApiResourceDatabase,
) -> None:
    """Foreign IDs look missing and request-provided ownership is rejected."""
    application = create_app()
    async with client_for(application) as tenant_a, client_for(application) as tenant_b:
        await signup(tenant_a, "destination-a@example.com")
        await signup(tenant_b, "destination-b@example.com")
        destination_b = await create_destination(tenant_b)

        injected = await tenant_a.post(
            "/api/v1/destinations",
            json={"label": "Injected", "webhook_url": WEBHOOK_URL, "owner_id": "tenant-b"},
        )
        attempts = [
            await tenant_a.get(f"/api/v1/destinations/{destination_b['id']}"),
            await tenant_a.patch(f"/api/v1/destinations/{destination_b['id']}", json={"label": "Stolen"}),
            await tenant_a.post(f"/api/v1/destinations/{destination_b['id']}/verify"),
            await tenant_a.delete(f"/api/v1/destinations/{destination_b['id']}"),
        ]

        assert injected.status_code == 422
        assert [response.status_code for response in attempts] == [404] * len(attempts)
        assert all(response.json()["code"] == "not_found" for response in attempts)
        spoofed_list = await tenant_a.get("/api/v1/destinations", params={"owner_id": "tenant-b"})
        assert spoofed_list.json() == []
        assert (await tenant_b.get(f"/api/v1/destinations/{destination_b['id']}")).status_code == 200
