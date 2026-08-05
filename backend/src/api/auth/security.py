"""Password hashing and signed authentication-token services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ...config import settings
from ...logging_utils import get_logger
from .exceptions import InvalidAuthenticationTokenError

_logger = get_logger("api.auth")
_password_hasher = PasswordHasher()

# This is an Argon2id hash of an irrelevant fixed value. It keeps unknown-email
# login attempts on the same password-verification path as known accounts.
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$dmJtQ3l0NGJpMzJ4WFdBMA$hdNLF2Rzsi5XnQeMGnBczxmhzCB45RMKt3nKJrXThW0"
)


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Validated identity claims from an authentication token."""

    tenant_id: str
    issued_at: datetime
    expires_at: datetime


def hash_password(plain_password: str) -> str:
    """Hash a password with Argon2id and a fresh random salt."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return whether a password matches, treating malformed hashes as failures."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, VerificationError):
        _logger.warning("Password verification rejected an invalid stored hash")
        return False


def create_access_token(tenant_id: str, *, now: datetime | None = None) -> str:
    """Create a signed, expiring JWT for one tenant."""
    issued_at = _as_utc(now or datetime.now(UTC))
    expires_at = issued_at + timedelta(seconds=settings.jwt_token_lifetime_seconds)
    claims = {
        "sub": tenant_id,
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(
        claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    """Validate a JWT and return only its trusted authentication claims."""
    if not token or len(token) > 4096:
        raise InvalidAuthenticationTokenError

    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "iat", "exp", "iss", "aud"]},
        )
        tenant_id = claims["sub"]
        issued_at = datetime.fromtimestamp(claims["iat"], UTC)
        expires_at = datetime.fromtimestamp(claims["exp"], UTC)
    except (KeyError, OSError, OverflowError, TypeError, ValueError, jwt.PyJWTError) as exc:
        raise InvalidAuthenticationTokenError from exc

    if not isinstance(tenant_id, str) or not tenant_id or tenant_id != tenant_id.strip() or len(tenant_id) > 128:
        raise InvalidAuthenticationTokenError

    return TokenPayload(
        tenant_id=tenant_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
