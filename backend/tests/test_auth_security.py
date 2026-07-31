"""Authentication hashing, token, and settings tests."""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.auth.exceptions import InvalidAuthenticationTokenError  # noqa: E402
from src.api.auth.security import (  # noqa: E402
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from src.config import Settings, settings  # noqa: E402


def test_passwords_use_salted_argon2id_hashes() -> None:
    """Repeated hashing produces distinct, verifiable Argon2id values."""
    password = "correct horse battery staple"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash.startswith("$argon2id$")
    assert first_hash != second_hash
    assert password not in first_hash
    assert verify_password(password, first_hash)
    assert not verify_password("incorrect password", first_hash)


def test_malformed_password_hash_is_secret_safe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed stored hashes fail without writing the hash or password to logs."""
    password = "plaintext-password-value"
    malformed_hash = "malformed-stored-hash-value"

    with caplog.at_level(logging.WARNING, logger="mercari_bot"):
        assert not verify_password(password, malformed_hash)

    assert "invalid stored hash" in caplog.text
    assert password not in caplog.text
    assert malformed_hash not in caplog.text


def test_dummy_hash_uses_normal_verification_path() -> None:
    """The fixed unknown-user hash is valid and always rejects caller passwords."""
    assert DUMMY_PASSWORD_HASH.startswith("$argon2id$")
    assert not verify_password("unrelated caller password", DUMMY_PASSWORD_HASH)


def test_token_round_trip_resolves_exact_tenant() -> None:
    """A signed token validates to its exact subject and finite timestamps."""
    token = create_access_token("tenant-123")

    payload = decode_access_token(token)

    assert payload.tenant_id == "tenant-123"
    assert payload.expires_at > payload.issued_at


def test_expired_token_is_rejected() -> None:
    """A token issued beyond the configured lifetime cannot authenticate."""
    issued_at = datetime.now(UTC) - timedelta(seconds=settings.jwt_token_lifetime_seconds + 1)
    token = create_access_token("tenant-123", now=issued_at)

    with pytest.raises(InvalidAuthenticationTokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected() -> None:
    """Changing a signed token invalidates its signature."""
    token = create_access_token("tenant-123")
    header, payload, signature = token.split(".")
    replacement = "a" if signature[0] != "a" else "b"
    tampered = f"{header}.{payload}.{replacement}{signature[1:]}"

    with pytest.raises(InvalidAuthenticationTokenError):
        decode_access_token(tampered)


def test_wrong_algorithm_is_rejected() -> None:
    """The decoder accepts only the configured signing algorithm."""
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "tenant-123",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS384",
    )

    with pytest.raises(InvalidAuthenticationTokenError):
        decode_access_token(token)


def test_missing_and_invalid_subjects_are_rejected() -> None:
    """Authentication tokens must contain a bounded, nonblank string subject."""
    now = datetime.now(UTC)
    base_claims = {
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    missing_subject = jwt.encode(
        base_claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    blank_subject = jwt.encode(
        {**base_claims, "sub": " "},
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidAuthenticationTokenError):
        decode_access_token(missing_subject)
    with pytest.raises(InvalidAuthenticationTokenError):
        decode_access_token(blank_subject)


def test_unsigned_token_is_rejected() -> None:
    """An unsigned token is never accepted as an authenticated session."""
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "tenant-123",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        key="",
        algorithm="none",
    )

    with pytest.raises(InvalidAuthenticationTokenError):
        decode_access_token(token)


def test_settings_reject_missing_and_weak_secret_without_exposing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup validation requires a strong secret without echoing its value."""
    weak_secret = "sensitive-short-secret"
    with pytest.raises(ValidationError, match="at least 32") as weak_error:
        Settings(jwt_secret=weak_secret)
    assert weak_secret not in str(weak_error.value)

    monkeypatch.delenv("JWT_SECRET")
    with pytest.raises(ValidationError, match="Field required"):
        Settings(_env_file=None)


def test_settings_reject_insecure_cookie_and_cors_policies() -> None:
    """Startup validation rejects unsafe credentialed-browser policies."""
    with pytest.raises(ValidationError, match="must be enabled in production"):
        Settings(api_environment="production", auth_cookie_secure=False)

    with pytest.raises(ValidationError, match="must be Secure"):
        Settings(auth_cookie_samesite="none", auth_cookie_secure=False)

    with pytest.raises(ValidationError, match="cannot use a wildcard"):
        Settings(api_cors_origins=["*"])
