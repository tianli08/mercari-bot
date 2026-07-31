"""Authentication cookie lifecycle helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Response

from ...config import settings

_COOKIE_PATH = "/"


def set_authentication_cookie(response: Response, token: str) -> None:
    """Set the signed credential using the configured browser cookie policy."""
    lifetime = settings.jwt_token_lifetime_seconds
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=lifetime,
        expires=datetime.now(UTC) + timedelta(seconds=lifetime),
        path=_COOKIE_PATH,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )


def clear_authentication_cookie(response: Response) -> None:
    """Expire the authentication cookie using matching policy attributes."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path=_COOKIE_PATH,
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )
