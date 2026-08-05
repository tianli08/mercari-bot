"""Signup, login, logout, and current-user endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from starlette.concurrency import run_in_threadpool

from ... import database
from ...users import UserStatus
from ..auth.context import require_tenant_id
from ..auth.cookies import clear_authentication_cookie, set_authentication_cookie
from ..auth.exceptions import AuthenticationRequiredError, InvalidCredentialsError
from ..auth.schemas import LoginRequest, PublicUser, SignupRequest
from ..auth.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=PublicUser, status_code=201)
async def signup(payload: SignupRequest, response: Response) -> PublicUser:
    """Create an active tenant and establish its browser session."""
    password_hash = await run_in_threadpool(hash_password, payload.password)
    user = await database.create_user(str(payload.email), password_hash)
    set_authentication_cookie(response, create_access_token(user.tenant_id))
    return PublicUser.from_record(user)


@router.post("/login", response_model=PublicUser)
async def login(payload: LoginRequest, response: Response) -> PublicUser:
    """Verify active-account credentials and establish a browser session."""
    user = await database.get_user_by_email(str(payload.email))
    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = await run_in_threadpool(verify_password, payload.password, password_hash)
    if user is None or not password_matches or user.status is not UserStatus.ACTIVE:
        raise InvalidCredentialsError

    set_authentication_cookie(response, create_access_token(user.tenant_id))
    return PublicUser.from_record(user)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> Response:
    """Expire the browser authentication cookie."""
    response.status_code = 204
    clear_authentication_cookie(response)
    return response


@router.get("/me", response_model=PublicUser)
async def current_user(
    tenant_id: Annotated[str, Depends(require_tenant_id)],
) -> PublicUser:
    """Return the authenticated tenant's current public account data."""
    user = await database.get_user_by_id(tenant_id)
    if user is None or user.status is not UserStatus.ACTIVE:
        raise AuthenticationRequiredError
    return PublicUser.from_record(user)
