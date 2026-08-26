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
from src.api.auth.exceptions import RateLimitedError  # noqa: E402
from src.api.auth.rate_limit import get_auth_rate_limiter, reset_auth_rate_limiter  # noqa: E402
from src.api.auth.security import create_access_token, hash_password  # noqa: E402
from src.config import settings  # noqa: E402
from src.users import UserStatus  # noqa: E402

pytestmark = pytest.mark.asyncio

PASSWORD = "correct horse battery staple"
_RATE_LIMITED = {"detail": "Too many requests", "code": "rate_limited"}


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
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)


@pytest.fixture
def fast_passwords(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Replace Argon2 with instant fakes that record whether hashing ran."""
    hashed: list[str] = []
    verified: list[str] = []

    def _hash_password(password: str) -> str:
        hashed.append(password)
        return f"hashed:{password}"

    def _verify_password(plain: str, stored: str) -> bool:
        verified.append(plain)
        return stored == f"hashed:{plain}"

    monkeypatch.setattr("src.api.routers.auth.hash_password", _hash_password)
    monkeypatch.setattr("src.api.routers.auth.verify_password", _verify_password)
    return {"hash": hashed, "verify": verified}


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


async def test_rate_limited_error_sets_retry_after_header(fake_database: FakeDatabaseClient) -> None:
    """429 responses use the public envelope and a positive integer Retry-After header."""
    application = create_app()

    @application.get("/api/v1/test-rate-limited")
    async def raise_limited() -> None:
        raise RateLimitedError(7)

    async with _client_for(application) as client:
        response = await client.get("/api/v1/test-rate-limited")

    assert response.status_code == 429
    assert response.json() == _RATE_LIMITED
    assert response.headers["retry-after"] == "7"


async def test_signup_burst_returns_rate_limited_before_hashing(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Sustained signup from one IP is rejected with 429 and does not hash the extra attempt."""
    application = create_app()

    async with _client_for(application) as client:
        for index in range(2):
            response = await client.post(
                "/api/v1/auth/signup",
                json={"email": f"burst{index}@example.com", "password": PASSWORD},
            )
            assert response.status_code == 201
        limited = await client.post(
            "/api/v1/auth/signup",
            json={"email": "burst2@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(limited, "burst2@example.com", PASSWORD)
    assert len(fast_passwords["hash"]) == 2
    assert await fake_database.users.count_documents({}) == 2


async def test_login_burst_is_identical_for_existing_and_unknown_emails(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """A spent login budget is not an account-existence oracle."""
    await database.create_user("known@example.com", f"hashed:{PASSWORD}")
    application = create_app()
    known_email = "known@example.com"
    unknown_email = "unknown@example.com"

    async with _client_for(application, client_host="203.0.113.10") as known_client:
        await known_client.post("/api/v1/auth/login", json={"email": known_email, "password": "wrong password!!"})
        await known_client.post("/api/v1/auth/login", json={"email": known_email, "password": "wrong password!!"})
        known_limited = await known_client.post(
            "/api/v1/auth/login",
            json={"email": known_email, "password": "wrong password!!"},
        )
    async with _client_for(application, client_host="203.0.113.11") as unknown_client:
        await unknown_client.post(
            "/api/v1/auth/login",
            json={"email": unknown_email, "password": "wrong password!!"},
        )
        await unknown_client.post(
            "/api/v1/auth/login",
            json={"email": unknown_email, "password": "wrong password!!"},
        )
        unknown_limited = await unknown_client.post(
            "/api/v1/auth/login",
            json={"email": unknown_email, "password": "wrong password!!"},
        )

    _assert_rate_limited(known_limited, known_email, unknown_email, PASSWORD, "wrong password!!")
    _assert_rate_limited(unknown_limited, known_email, unknown_email, PASSWORD, "wrong password!!")
    assert known_limited.json() == unknown_limited.json()


async def test_login_rate_limit_keys_are_independent(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Spending one login email or IP budget does not throttle a different email from a different IP."""
    application = create_app()

    async with _client_for(application, client_host="198.51.100.1") as victim_client:
        await victim_client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": PASSWORD},
        )
        await victim_client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": PASSWORD},
        )
        victim_limited = await victim_client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": PASSWORD},
        )
        other_email_same_ip = await victim_client.post(
            "/api/v1/auth/login",
            json={"email": "other@example.com", "password": PASSWORD},
        )
    async with _client_for(application, client_host="198.51.100.2") as other_client:
        other_email_other_ip = await other_client.post(
            "/api/v1/auth/login",
            json={"email": "other@example.com", "password": PASSWORD},
        )
        same_email_other_ip = await other_client.post(
            "/api/v1/auth/login",
            json={"email": "victim@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(victim_limited, "victim@example.com")
    _assert_rate_limited(other_email_same_ip, "other@example.com")
    assert other_email_other_ip.status_code == 401
    _assert_rate_limited(same_email_other_ip, "victim@example.com")


async def test_signup_and_login_budgets_are_independent(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Spending the signup IP budget does not consume the login budgets, and vice versa."""
    application = create_app()

    async with _client_for(application, client_host="192.0.2.10") as client:
        await client.post("/api/v1/auth/signup", json={"email": "one@example.com", "password": PASSWORD})
        await client.post("/api/v1/auth/signup", json={"email": "two@example.com", "password": PASSWORD})
        signup_limited = await client.post(
            "/api/v1/auth/signup",
            json={"email": "three@example.com", "password": PASSWORD},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "one@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(signup_limited, "three@example.com")
    assert login.status_code == 200

    reset_auth_rate_limiter()
    async with _client_for(application, client_host="192.0.2.11") as client:
        await client.post("/api/v1/auth/login", json={"email": "burn@example.com", "password": PASSWORD})
        await client.post("/api/v1/auth/login", json={"email": "burn@example.com", "password": PASSWORD})
        login_limited = await client.post(
            "/api/v1/auth/login",
            json={"email": "burn@example.com", "password": PASSWORD},
        )
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "fresh@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(login_limited, "burn@example.com")
    assert signup.status_code == 201


async def test_signup_rate_limit_is_per_ip(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """A second client IP keeps a full signup budget after the first IP is exhausted."""
    application = create_app()

    async with _client_for(application, client_host="192.0.2.20") as first:
        await first.post("/api/v1/auth/signup", json={"email": "ip-a@example.com", "password": PASSWORD})
        await first.post("/api/v1/auth/signup", json={"email": "ip-b@example.com", "password": PASSWORD})
        limited = await first.post(
            "/api/v1/auth/signup",
            json={"email": "ip-c@example.com", "password": PASSWORD},
        )
    async with _client_for(application, client_host="192.0.2.21") as second:
        allowed = await second.post(
            "/api/v1/auth/signup",
            json={"email": "ip-d@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(limited, "ip-c@example.com")
    assert allowed.status_code == 201


async def test_auth_rate_limit_recovers_after_window_without_sleeping(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Advancing the limiter clock restores signup after the window elapses."""
    clock = _FakeClock()
    get_auth_rate_limiter().set_clock(clock)
    application = create_app()

    async with _client_for(application) as client:
        await client.post("/api/v1/auth/signup", json={"email": "window0@example.com", "password": PASSWORD})
        await client.post("/api/v1/auth/signup", json={"email": "window1@example.com", "password": PASSWORD})
        limited = await client.post(
            "/api/v1/auth/signup",
            json={"email": "window2@example.com", "password": PASSWORD},
        )
        clock.advance(settings.auth_rate_limit_window_seconds + 0.01)
        recovered = await client.post(
            "/api/v1/auth/signup",
            json={"email": "window3@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(limited, "window2@example.com")
    assert recovered.status_code == 201


async def test_limiter_reset_restores_auth_access(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Tests can reset the in-process limiter instead of waiting on wall-clock time."""
    application = create_app()

    async with _client_for(application) as client:
        await client.post("/api/v1/auth/signup", json={"email": "reset0@example.com", "password": PASSWORD})
        await client.post("/api/v1/auth/signup", json={"email": "reset1@example.com", "password": PASSWORD})
        reset_auth_rate_limiter()
        recovered = await client.post(
            "/api/v1/auth/signup",
            json={"email": "reset2@example.com", "password": PASSWORD},
        )

    assert recovered.status_code == 201


async def test_login_rate_limit_does_not_run_password_verification(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Rejected login attempts never reach Argon2 verification."""
    await database.create_user("hash@example.com", f"hashed:{PASSWORD}")
    application = create_app()

    async with _client_for(application) as client:
        await client.post("/api/v1/auth/login", json={"email": "hash@example.com", "password": PASSWORD})
        await client.post("/api/v1/auth/login", json={"email": "hash@example.com", "password": PASSWORD})
        verify_count = len(fast_passwords["verify"])
        limited = await client.post(
            "/api/v1/auth/login",
            json={"email": "hash@example.com", "password": PASSWORD},
        )

    _assert_rate_limited(limited, "hash@example.com")
    assert len(fast_passwords["verify"]) == verify_count


async def test_logout_and_me_are_not_covered_by_the_auth_limiter(
    fake_database: FakeDatabaseClient,
    tiny_auth_limits: None,
    fast_passwords: dict[str, list[str]],
) -> None:
    """Spending the login budget does not throttle session logout or /me."""
    application = create_app()

    async with _client_for(application) as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "session@example.com", "password": PASSWORD},
        )
        assert signup.status_code == 201
        await client.post("/api/v1/auth/login", json={"email": "session@example.com", "password": PASSWORD})
        await client.post("/api/v1/auth/login", json={"email": "session@example.com", "password": PASSWORD})
        limited = await client.post(
            "/api/v1/auth/login",
            json={"email": "session@example.com", "password": PASSWORD},
        )
        me_response = await client.get("/api/v1/auth/me")
        logout_response = await client.post("/api/v1/auth/logout")

    _assert_rate_limited(limited, "session@example.com")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "session@example.com"
    assert logout_response.status_code == 204


def _assert_rate_limited(response: httpx.Response, *secrets: str) -> None:
    """Require the frozen 429 contract and the absence of caller-supplied secrets."""
    assert response.status_code == 429
    assert response.json() == _RATE_LIMITED
    retry_after = response.headers["retry-after"]
    assert retry_after.isdigit()
    assert int(retry_after) >= 1
    for secret in secrets:
        assert secret not in response.text


def _client_for(
    application: object,
    *,
    base_url: str = "http://test",
    cookies: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=application, client=(client_host, 123))
    return httpx.AsyncClient(
        transport=transport,
        base_url=base_url,
        cookies=cookies,
    )
