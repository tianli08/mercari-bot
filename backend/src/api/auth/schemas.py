"""Public application account schemas."""

from pydantic import BaseModel, EmailStr

from ...users import UserPlan, UserRecord, UserStatus


class PublicUser(BaseModel):
    """Allowlisted tenant fields safe for API responses."""

    id: str
    email: EmailStr
    status: UserStatus
    plan: UserPlan

    @classmethod
    def from_record(cls, user: UserRecord) -> "PublicUser":
        """Build a public account without serializing internal identity fields."""
        return cls(id=user.tenant_id, email=user.email, status=user.status, plan=user.plan)
