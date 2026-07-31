"""Secret-safe authentication request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from ...users import UserPlan, UserRecord, UserStatus

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class SignupRequest(BaseModel):
    """Credentials accepted when creating an account."""

    email: EmailStr
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        repr=False,
    )


class LoginRequest(BaseModel):
    """Credentials accepted when starting a session."""

    email: EmailStr
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        repr=False,
    )


class PublicUser(BaseModel):
    """Allowlisted user fields safe for API responses."""

    id: str
    email: EmailStr
    status: UserStatus
    plan: UserPlan

    @classmethod
    def from_record(cls, user: UserRecord) -> "PublicUser":
        """Build a public user without serializing its credential fields."""
        return cls(
            id=user.tenant_id,
            email=user.email,
            status=user.status,
            plan=user.plan,
        )
