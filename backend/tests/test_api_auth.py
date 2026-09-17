"""Clerk provisioning, legacy linking, and tenant authorization regressions."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from api_resource_helpers import ApiResourceDatabase, client_for, create_app, signup
from clerk_test_helpers import session_token

from src import database
from src.api.auth import clerk, context
from src.api.auth.exceptions import AuthenticationRequiredError, AuthenticationUnavailableError
from src.users import ClerkAccountConflictError, UserRecord, UserStatus

pytestmark = pytest.mark.asyncio


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> ApiResourceDatabase:
    """Isolate every identity test from external storage."""
    value = ApiResourceDatabase("clerk_auth_tests")
    monkeypatch.setattr(database, "db_client", value)
    return value


async def test_first_session_provisions_public_account(store, monkeypatch) -> None:
    """Only a verified provider profile supplies the tenant email."""
    lookup = AsyncMock(return_value="New@Example.com")
    monkeypatch.setattr(context, "get_verified_email", lookup)
    async with client_for(create_app()) as client:
        client.headers["Authorization"] = f"Bearer {session_token('user_new')}"
        response = await client.get("/api/v1/auth/me?email=attacker@example.com&tenant_id=other")
        again = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == again.json()
    assert set(response.json()) == {"id", "email", "status", "plan"}
    assert response.json()["email"] == "new@example.com"
    lookup.assert_awaited_once_with("user_new")
    saved = await store.users.find_one({"clerk_user_id": "user_new"})
    assert "password_hash" not in saved


async def test_link_preserves_existing_data_and_credentials(store) -> None:
    """Verified migration keeps the tenant ID, plan, and all existing data."""
    legacy = UserRecord.new(email="legacy@example.com")
    await store.users.insert_one(legacy.to_document())
    await store.users.update_one({"_id": legacy.tenant_id}, {"$set": {"password_hash": "legacy-private-hash"}})
    await store.watchlists.insert_one({"_id": "saved-list", "owner_id": legacy.tenant_id})
    linked = await database.link_clerk_user("user_legacy", " LEGACY@example.com ")
    assert linked.tenant_id == legacy.tenant_id
    assert linked.plan == legacy.plan
    assert await store.watchlists.count_documents({"owner_id": linked.tenant_id}) == 1
    assert (await store.users.find_one({"_id": linked.tenant_id}))["password_hash"] == "legacy-private-hash"


async def test_identity_cannot_reclaim_another_linked_email(store) -> None:
    """Even a verified email cannot move an already-linked tenant."""
    first = await database.link_clerk_user("user_first", "shared@example.com")
    with pytest.raises(ClerkAccountConflictError):
        await database.link_clerk_user("user_second", "shared@example.com")
    assert (await database.get_user_by_clerk_id("user_first")).tenant_id == first.tenant_id
    assert await database.get_user_by_clerk_id("user_second") is None


async def test_concurrent_first_requests_share_one_tenant(store) -> None:
    """Duplicate requests cannot split or overwrite identity ownership."""
    records = await asyncio.gather(*[database.link_clerk_user("user_race", "race@example.com") for _ in range(12)])
    assert len({record.tenant_id for record in records}) == 1
    assert await store.users.count_documents({}) == 1


async def test_link_race_after_initial_lookup(store, monkeypatch) -> None:
    """A concurrent link between the identity and email reads is idempotent."""
    existing = await database.link_clerk_user("user_race", "race@example.com")
    monkeypatch.setattr(database, "get_user_by_clerk_id", AsyncMock(return_value=None))
    linked = await database.link_clerk_user("user_race", "race@example.com")
    assert linked.tenant_id == existing.tenant_id


async def test_suspended_account_cannot_link_or_access_resources(store) -> None:
    """Local account restrictions apply to all routes, not just the profile page."""
    suspended = UserRecord.new(email="suspended@example.com", status=UserStatus.SUSPENDED)
    await store.users.insert_one(suspended.to_document())
    with pytest.raises(ClerkAccountConflictError):
        await database.link_clerk_user("user_suspended", "suspended@example.com")
    async with client_for(create_app()) as client:
        account = await signup(client, "active@example.com")
        await store.users.update_one({"_id": account["id"]}, {"$set": {"status": "suspended"}})
        for path in ["/auth/me", "/watchlists", "/destinations", "/alerts/recent", "/presets"]:
            response = await client.get(f"/api/v1{path}")
            assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "signup",
        "login",
        "logout",
        "password-reset/request",
        "password-reset/confirm",
        "verify-email/request",
        "verify-email/confirm",
    ],
)
async def test_retired_password_endpoints_are_unavailable(store, path) -> None:
    """Legacy credentials and recovery links cannot create sessions or mutate users."""
    async with client_for(create_app()) as client:
        response = await client.post(f"/api/v1/auth/{path}", json={"email": "old@example.com", "password": "old"})
    assert response.status_code == 404
    assert await store.users.count_documents({}) == 0


async def test_missing_and_legacy_sessions_rejected(store) -> None:
    """An old cookie never bypasses Clerk verification."""
    async with client_for(create_app()) as client:
        client.cookies.set("mercari_session", "old-token")
        response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.parametrize("verified,primary,banned", [(False, True, False), (True, False, False), (True, True, True)])
async def test_provider_profile_requires_verified_primary_email(monkeypatch, verified, primary, banned) -> None:
    """Unverified, secondary-only, and banned profiles cannot claim local data."""
    user = SimpleNamespace(
        id="user_profile",
        banned=banned,
        locked=False,
        primary_email_address_id="primary",
        email_addresses=[
            SimpleNamespace(
                id="primary" if primary else "secondary",
                email_address="person@example.com",
                verification=SimpleNamespace(status="verified" if verified else "unverified"),
            )
        ],
    )

    class FakeClerk:
        """Offline profile lookup."""

        async def __aenter__(self):
            """Return the fake SDK client."""
            return SimpleNamespace(users=SimpleNamespace(get_async=AsyncMock(return_value=user)))

        async def __aexit__(self, *args):
            """Close the fake client."""

    monkeypatch.setattr(clerk, "Clerk", lambda **kwargs: FakeClerk())
    with pytest.raises(AuthenticationRequiredError):
        await clerk.get_verified_email("user_profile")


async def test_auth_service_errors_are_generic(store, monkeypatch) -> None:
    """An unavailable provider yields a retryable response without leaking details."""
    monkeypatch.setattr(context, "get_verified_email", AsyncMock(side_effect=AuthenticationUnavailableError("secret")))
    async with client_for(create_app()) as client:
        client.headers["Authorization"] = f"Bearer {session_token('user_unavailable')}"
        response = await client.get("/api/v1/auth/me")
    assert response.status_code == 503
    assert response.json()["code"] == "authentication_unavailable"
    assert "secret" not in response.text
