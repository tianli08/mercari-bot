"""Application account data for Clerk-authenticated users."""

from typing import Annotated

from fastapi import APIRouter, Depends

from ...users import UserRecord
from ..auth.context import require_user
from ..auth.schemas import PublicUser

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me", response_model=PublicUser)
async def current_user(user: Annotated[UserRecord, Depends(require_user)]) -> PublicUser:
    """Return only public tenant data; Clerk owns credentials and sessions."""
    return PublicUser.from_record(user)
