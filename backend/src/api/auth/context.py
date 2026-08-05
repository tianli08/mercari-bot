"""Typed authentication state and protected-route dependency."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from .exceptions import AuthenticationRequiredError

_STATE_ATTRIBUTE = "authentication"


@dataclass(frozen=True, slots=True)
class AuthenticationContext:
    """Trusted identity resolved exclusively from a validated session token."""

    tenant_id: str


def set_authentication_context(
    request: Request,
    context: AuthenticationContext | None,
) -> None:
    """Store validated authentication state on a request."""
    setattr(request.state, _STATE_ATTRIBUTE, context)


def require_tenant_id(request: Request) -> str:
    """Return the authenticated tenant ID or reject the request."""
    context = getattr(request.state, _STATE_ATTRIBUTE, None)
    if not isinstance(context, AuthenticationContext):
        raise AuthenticationRequiredError
    return context.tenant_id
