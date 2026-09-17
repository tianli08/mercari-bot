"""Verify Clerk sessions and obtain provider-verified account identities."""

from __future__ import annotations

import asyncio
import re

import httpx
from clerk_backend_api import AuthenticateRequestOptions, Clerk, authenticate_request_async
from clerk_backend_api.models import SDKError
from fastapi import Request

from ...config import settings
from .exceptions import AuthenticationRequiredError, AuthenticationUnavailableError


async def get_clerk_user_id(request: Request) -> str:
    """Accept only signed Clerk session bearer tokens from configured origins."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 16384:
        raise AuthenticationRequiredError
    if settings.clerk_secret_key is None:
        raise AuthenticationUnavailableError
    options = AuthenticateRequestOptions(
        secret_key=settings.clerk_secret_key.get_secret_value(),
        jwt_key=settings.clerk_jwt_key,
        authorized_parties=settings.clerk_authorized_parties,
        accepts_token=["session_token"],
        clock_skew_in_ms=5000,
    )
    # Omit cookies so they cannot act as a fallback for a missing bearer token.
    clerk_request = httpx.Request("GET", "https://api.local/", headers={"Authorization": f"Bearer {token}"})
    try:
        async with asyncio.timeout(10):
            state = await authenticate_request_async(clerk_request, options)
    except (httpx.RequestError, TimeoutError) as exc:
        raise AuthenticationUnavailableError from exc
    if not state.is_signed_in or not state.payload:
        if state.reason and state.reason.name in {"JWK_FAILED_TO_LOAD", "SERVER_ERROR"}:
            raise AuthenticationUnavailableError
        raise AuthenticationRequiredError
    claims = state.payload
    subject = claims.get("sub")
    session = claims.get("sid")
    if (
        not isinstance(subject, str)
        or not re.fullmatch(r"user_[A-Za-z0-9]{1,128}", subject)
        or not isinstance(session, str)
        or not session.startswith("sess_")
        or claims.get("sts", "active") != "active"
        or not all(type(claims.get(name)) is int for name in ("exp", "iat", "nbf"))
        or not isinstance(claims.get("iss"), str)
        or (settings.clerk_issuer and claims["iss"] != settings.clerk_issuer)
    ):
        raise AuthenticationRequiredError
    return subject


async def get_verified_email(clerk_user_id: str) -> str:
    """Read a verified primary email from Clerk, never from caller input."""
    if settings.clerk_secret_key is None:
        raise AuthenticationUnavailableError
    try:
        async with (
            asyncio.timeout(10),
            Clerk(bearer_auth=settings.clerk_secret_key.get_secret_value(), timeout_ms=8000) as clerk,
        ):
            user = await clerk.users.get_async(user_id=clerk_user_id, retries=None)
    except SDKError as exc:
        if exc.status_code == 404:
            raise AuthenticationRequiredError from exc
        raise AuthenticationUnavailableError from exc
    except (httpx.RequestError, TimeoutError) as exc:
        raise AuthenticationUnavailableError from exc
    if user.id != clerk_user_id or user.banned or user.locked:
        raise AuthenticationRequiredError
    for email in user.email_addresses:
        if (
            email.id == user.primary_email_address_id
            and email.verification is not None
            and email.verification.status == "verified"
        ):
            return email.email_address
    raise AuthenticationRequiredError
