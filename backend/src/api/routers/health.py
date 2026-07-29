"""API and database health checks."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ... import database
from ...logging_utils import get_logger
from ..schemas import HealthResponse

router = APIRouter(tags=["health"])
_logger = get_logger("api.health")


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def get_health(response: Response) -> HealthResponse:
    """Return API health after round-tripping the shared MongoDB database."""
    try:
        await database.db_client.db.command("ping")
    except Exception as exc:
        _logger.warning(
            "Database health check failed",
            context={"error_type": type(exc).__name__},
        )
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="unavailable")
    return HealthResponse(status="ok", database="ok")
