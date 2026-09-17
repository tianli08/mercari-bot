"""Resolve verified Clerk sessions to stable application tenants."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ... import database
from ...users import UserRecord, UserStatus
from .clerk import get_clerk_user_id, get_verified_email
from .exceptions import AuthenticationRequiredError


async def require_user(clerk_user_id: Annotated[str, Depends(get_clerk_user_id)]) -> UserRecord:
    """Authorize an active tenant, preserving existing ownership during migration."""
    user = await database.get_user_by_clerk_id(clerk_user_id)
    if user is None:
        email = await get_verified_email(clerk_user_id)
        user = await database.link_clerk_user(clerk_user_id, email)
    if user.status is not UserStatus.ACTIVE:
        raise AuthenticationRequiredError
    return user


async def require_tenant_id(user: Annotated[UserRecord, Depends(require_user)]) -> str:
    """Return the active account's ID for tenant-scoped resource operations."""
    return user.tenant_id
