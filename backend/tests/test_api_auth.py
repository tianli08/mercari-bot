"""Authentication API and tenant-resolution tests."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import httpx
import pytest
from fastapi import Depends
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import database  # noqa: E402
from src.api.app import create_app  # noqa: E402
from src.api.auth.context import require_tenant_id  # noqa: E402
from src.api.auth.security import create_access_token, hash_password  # noqa: E402
from src.config import settings  # noqa: E402
from src.users import UserStatus  # noqa: E402

pytestmark = pytest.mark.asyncio

PASSWORD = "correct horse battery staple"


class FakeDatabaseClient:
    """In-memory database client with production collection attributes."""

    def __init__(self) -> None:
        """Initialize isolated fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["auth_api_tests"]
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


@pytest.fixture
def fake_database(monkeypatch: pytest.MonkeyPatch) -> FakeDatabaseClient:
    """Patch persistence to an isolated in-memory MongoDB replacement."""
    fake_client = FakeDatabaseClient()
    monkeypatch.setattr(database, "db_client", fake_client)
    return fake_client


async def test_signup_normalizes_email_hashes_password_and_starts_session(
    fake_database: FakeDatabaseClient,
) -> None:
    """Signup stores only a hash and returns an allowlisted public user."""
    application = create_app()

    async with _client_for(application) as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "  New.User@Example.COM  ", "password": PASSWORD},
        )
        me_response = await client.get("/api/v1/auth/me")

    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "status", "plan"}
    assert response.json()["email"] == "new.user@example.com"
    assert response.json()["status"] == "active"
    assert response.json()["plan"] == "free"
    assert PASSWORD not in response.text
    assert "$argon2" not in response.text
    assert me_response.status_code == 200
    assert me_response.json() == response.json()

    document = await fake_database.users.find_one({"email": "new.user@example.com"})
    assert document is not None
    assert document["password_hash"].startswith("$argon2id$")
    assert document["password_hash"] != PASSWORD

    cookie = response.headers["set-cookie"].lower()
    assert f"{settings.auth_cookie_name}=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert f"max-age={settings.jwt_token_lifetime_seconds}" in cookie
    assert "secure" not in cookie


async def test_concurrent_duplicate_normalized_signup_returns_conflict(
    fake_database: FakeDatabaseClient,
) -> None:
    """The unique email index settles concurrent case-variant signup attempts."""
    application = create_app()

    async def attempt(email: str) -> httpx.Response:
        async with _client_for(application) as client:
            return await client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": PASSWORD},
            )

    first, second = await asyncio.gather(
        attempt("duplicate@example.com"),
        attempt("DUPLICATE@example.com"),
    )

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    conflict = first if first.status_code == 409 else second
    assert conflict.json() == {
        "detail": "An account with this email already exists",
        "code": "email_exists",
    }
    assert await fake_database.users.count_documents({}) == 1


async def test_login_returns_generic_errors_for_unknown_and_wrong_password(
    fake_database: FakeDatabaseClient,
) -> None:
    """Unknown accounts and incorrect passwords share one public response."""
    application = create_app()
    await database.create_user("known@example.com", hash_password(PASSWORD))

    async with _client_for(application) as client:
        unknown = await client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": PASSWORD},
        )
        incorrect = await client.post(
            "/api/v1/auth/login",
            json={"email": "known@example.com", "password": "incorrect password"},
        )

    expected = {"detail": "Invalid email or password", "code": "invalid_credentials"}
    assert unknown.status_code == 401
    assert incorrect.status_code == 401
    assert unknown.json() == expected
    assert incorrect.json() == expected


@pytest.mark.parametrize("status", [UserStatus.PENDING, UserStatus.SUSPENDED])
async def test_login_rejects_ineligible_accounts_generically(
    fake_database: FakeDatabaseClient,
    status: UserStatus,
) -> None:
    """Pending and suspended accounts cannot establish new sessions."""
    await database.create_user(
        f"{status.value}@example.com",
        hash_password(PASSWORD),
        status=status,
    )
    application = create_app()

    async with _client_for(application) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": f"{status.value}@example.com", "password": PASSWORD},
        )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid email or password",
        "code": "invalid_credentials",
    }
    assert settings.auth_cookie_name not in response.cookies


async def test_login_handles_malformed_stored_hash_without_leaking_it(
    fake_database: FakeDatabaseClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A corrupt hash is observable internally but remains a generic login failure."""
    malformed_hash = "sensitive-malformed-hash"
    await database.create_user("corrupt@example.com", malformed_hash)
    application = create_app()

    with caplog.at_level(logging.WARNING, logger="mercari_bot"):
        async with _client_for(application) as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "corrupt@example.com", "password": PASSWORD},
            )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert malformed_hash not in response.text
    assert malformed_hash not in caplog.text
    assert PASSWORD not in caplog.text


async def test_login_sets_secure_cookie_when_configured(
    fake_database: FakeDatabaseClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deployment cookie security settings are reflected in login responses."""
    await database.create_user("secure@example.com", hash_password(PASSWORD))
    monkeypatch.setattr(settings, "auth_cookie_secure", True)
    application = create_app()

    async with _client_for(application, base_url="https://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "secure@example.com", "password": PASSWORD},
        )

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()
    assert response.json()["email"] == "secure@example.com"
    assert settings.auth_cookie_name not in response.text


async def test_logout_expires_session_cookie(fake_database: FakeDatabaseClient) -> None:
    """Logout clears the cookie and makes the current-user route unauthorized."""
    application = create_app()

    async with _client_for(application) as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "logout@example.com", "password": PASSWORD},
        )
        logout_response = await client.post("/api/v1/auth/logout")
        me_response = await client.get("/api/v1/auth/me")

    assert logout_response.status_code == 204
    cookie = logout_response.headers["set-cookie"].lower()
    assert f"{settings.auth_cookie_name}=" in cookie
    assert "max-age=0" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert me_response.status_code == 401
    assert me_response.json()["code"] == "authentication_required"


async def test_protected_dependency_uses_only_authenticated_tenant(
    fake_database: FakeDatabaseClient,
) -> None:
    """Client-supplied tenant values cannot replace signed authentication state."""
    application = create_app()

    @application.get("/api/v1/protected-tenant")
    async def protected_tenant(
        tenant_id: Annotated[str, Depends(require_tenant_id)],
    ) -> dict[str, str]:
        return {"tenant_id": tenant_id}

    async with _client_for(application) as client:
        signup_response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "tenant@example.com", "password": PASSWORD},
        )
        response = await client.get(
            "/api/v1/protected-tenant",
            params={"tenant_id": "attacker-controlled"},
            headers={"X-Tenant-Id": "attacker-controlled"},
        )

    assert response.status_code == 200
    assert response.json() == {"tenant_id": signup_response.json()["id"]}


@pytest.mark.parametrize("credential", ["missing", "malformed", "expired", "tampered"])
async def test_protected_dependency_rejects_untrusted_credentials(
    fake_database: FakeDatabaseClient,
    credential: str,
) -> None:
    """Missing, malformed, expired, and tampered cookies cannot reach a handler."""
    application = create_app()

    @application.get("/api/v1/protected")
    async def protected(
        tenant_id: Annotated[str, Depends(require_tenant_id)],
    ) -> dict[str, str]:
        return {"tenant_id": tenant_id}

    cookies: dict[str, str] = {}
    if credential == "malformed":
        cookies[settings.auth_cookie_name] = "not-a-jwt"
    elif credential == "expired":
        issued_at = datetime.now(UTC) - timedelta(seconds=settings.jwt_token_lifetime_seconds + 1)
        cookies[settings.auth_cookie_name] = create_access_token("tenant-123", now=issued_at)
    elif credential == "tampered":
        token = create_access_token("tenant-123")
        header, payload, signature = token.split(".")
        replacement = "a" if signature[0] != "a" else "b"
        cookies[settings.auth_cookie_name] = f"{header}.{payload}.{replacement}{signature[1:]}"

    async with _client_for(application, cookies=cookies) as client:
        response = await client.get("/api/v1/protected")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication required",
        "code": "authentication_required",
    }


async def test_invalid_cookie_does_not_block_public_routes(fake_database: FakeDatabaseClient) -> None:
    """Public health and login endpoints remain reachable with no valid session."""
    application = create_app()
    cookies = {settings.auth_cookie_name: "invalid-cookie-value"}

    async with _client_for(application, cookies=cookies) as client:
        health = await client.get("/api/v1/health")
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": PASSWORD},
        )

    assert health.status_code == 200
    assert login.status_code == 401
    assert login.json()["code"] == "invalid_credentials"


async def test_cors_rejects_unconfigured_origins(fake_database: FakeDatabaseClient) -> None:
    """Credentialed CORS responses do not authorize an unknown dashboard origin."""
    application = create_app()

    async with _client_for(application) as client:
        response = await client.get(
            "/api/v1/health",
            headers={"Origin": "https://untrusted.example"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_auth_validation_error_does_not_echo_password(
    fake_database: FakeDatabaseClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rejected auth input uses the generic envelope without echoing secrets."""
    submitted_password = "too-short"
    application = create_app()

    with caplog.at_level(logging.INFO, logger="mercari_bot"):
        async with _client_for(application) as client:
            response = await client.post(
                "/api/v1/auth/signup",
                json={"email": "valid@example.com", "password": submitted_password},
            )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request", "code": "validation_error"}
    assert submitted_password not in response.text
    assert submitted_password not in caplog.text


def _client_for(
    application: object,
    *,
    base_url: str = "http://test",
    cookies: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=application)
    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url,
        cookies=cookies,
    )
