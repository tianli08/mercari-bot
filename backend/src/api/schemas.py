"""Shared API response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health status for the API and its database dependency."""

    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]


class ErrorResponse(BaseModel):
    """Consistent public error envelope."""

    detail: str
    code: str
