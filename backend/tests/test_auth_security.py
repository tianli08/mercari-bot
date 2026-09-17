"""Exercise Clerk's verifier using signed tokens without network access."""

import time

import httpx
import jwt
import pytest
from clerk_test_helpers import session_token
from pydantic import ValidationError
from starlette.requests import Request

from src.api.auth.clerk import get_clerk_user_id
from src.api.auth.exceptions import AuthenticationRequiredError, AuthenticationUnavailableError
from src.config import Settings


def request_for(token: str | None = None, cookie: str | None = None) -> Request:
    """Build an isolated bearer-authenticated request."""
    headers = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    if cookie is not None:
        headers.append((b"cookie", f"__session={cookie}".encode()))
    return Request({"type": "http", "headers": headers})


@pytest.mark.asyncio
async def test_valid_session() -> None:
    """A verified subject is preserved exactly."""
    assert await get_clerk_user_id(request_for(session_token("user_valid"))) == "user_valid"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"exp": int(time.time()) - 30},
        {"nbf": int(time.time()) + 60},
        {"iat": int(time.time()) + 60},
        {"azp": "https://evil.example"},
        {"iss": "https://other.clerk.accounts.dev"},
        {"sts": "pending"},
        {"sub": "tenant-local"},
        {"sub": None},
        {"sid": None},
        {"exp": None},
        {"nbf": None},
        {"iat": None},
        {"azp": None},
        {"iss": None},
    ],
)
async def test_invalid_claims(changes: dict) -> None:
    """Expired, incomplete, foreign, or pending sessions fail closed."""
    with pytest.raises(AuthenticationRequiredError):
        await get_clerk_user_id(request_for(session_token("user_valid", **changes)))


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["garbage", "a.b.c", "", "ak_invalid", "oat_invalid", "x" * 16385])
async def test_malformed_and_machine_tokens(token: str) -> None:
    """A protected endpoint accepts only bounded session tokens."""
    with pytest.raises(AuthenticationRequiredError):
        await get_clerk_user_id(request_for(token))


@pytest.mark.asyncio
async def test_signature_and_algorithm_rejections() -> None:
    """Tampering, unsigned tokens, and HMAC tokens cannot impersonate tenants."""
    valid = session_token("user_valid")
    header, payload, signature = valid.split(".")
    tampered = f"{header}.{payload}.{'A' if signature[0] != 'A' else 'B'}{signature[1:]}"
    claims = jwt.decode(valid, options={"verify_signature": False})
    for token in [
        tampered,
        jwt.encode(claims, "", algorithm="none"),
        jwt.encode(claims, "offline-secret-long-enough-for-hmac", algorithm="HS256"),
    ]:
        with pytest.raises(AuthenticationRequiredError):
            await get_clerk_user_id(request_for(token))


@pytest.mark.asyncio
async def test_cookie_is_not_authentication() -> None:
    """Cookies never grant access to the cross-origin backend."""
    with pytest.raises(AuthenticationRequiredError):
        await get_clerk_user_id(request_for(cookie=session_token("user_valid")))


@pytest.mark.asyncio
async def test_provider_failure_is_secret_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider outages are distinguishable from an invalid session."""
    from src.api.auth import clerk

    async def unavailable(*args):
        raise httpx.ConnectError("sensitive-provider-response")

    monkeypatch.setattr(clerk, "authenticate_request_async", unavailable)
    with pytest.raises(AuthenticationUnavailableError):
        await get_clerk_user_id(request_for(session_token("user_valid")))


def test_settings_reject_unsafe_origins() -> None:
    """Empty, wildcard, or non-HTTPS production origins cannot weaken verification."""
    for overrides in [
        {"clerk_authorized_parties": []},
        {"api_cors_origins": ["*"]},
        {"clerk_authorized_parties": ["https://site.example/path"]},
        {"api_environment": "production"},
    ]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **overrides)


def test_api_requires_clerk_configuration() -> None:
    """The worker may run without Clerk, but the API fails before serving traffic."""
    with pytest.raises(ValueError, match="CLERK_SECRET_KEY"):
        Settings(_env_file=None, clerk_secret_key=None).validate_clerk_configuration()
    with pytest.raises(ValueError, match="CLERK_PUBLISHABLE_KEY"):
        Settings(_env_file=None, clerk_publishable_key=None).validate_clerk_configuration()
