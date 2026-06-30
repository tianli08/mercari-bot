"""Tenant user models and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class UserStatus(StrEnum):
    """Allowed tenant account states."""

    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"


class UserPlan(StrEnum):
    """Allowed tenant billing plans."""

    FREE = "free"


class EmailAlreadyExistsError(Exception):
    """Raised when a normalized email is already attached to a tenant."""


@dataclass(slots=True)
class UserRecord:
    """Tenant user data stored in MongoDB."""

    _id: str
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime
    status: UserStatus
    plan: UserPlan

    @property
    def tenant_id(self) -> str:
        """Return the stable tenant identifier."""
        return self._id

    @classmethod
    def new(
        cls,
        *,
        email: str,
        password_hash: str,
        status: UserStatus | str = UserStatus.ACTIVE,
        plan: UserPlan | str = UserPlan.FREE,
        created_at: datetime | None = None,
    ) -> "UserRecord":
        """Create a new tenant user record with normalized fields and timestamps."""
        timestamp = created_at or datetime.now(UTC)
        return cls(
            _id=uuid4().hex,
            email=normalize_email(email),
            password_hash=password_hash,
            created_at=timestamp,
            updated_at=timestamp,
            status=UserStatus(status),
            plan=UserPlan(plan),
        )

    def to_document(self) -> dict[str, Any]:
        """Serialize the user for MongoDB storage."""
        return {
            "_id": self._id,
            "email": self.email,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "plan": self.plan.value,
        }


def normalize_email(email: str) -> str:
    """Normalize an email address for uniqueness checks."""
    return email.strip().lower()
