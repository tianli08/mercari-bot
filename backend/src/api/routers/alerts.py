"""Tenant-scoped recent alert feed."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from ... import database
from ..auth.context import require_tenant_id
from ..schemas import PublicAlertDelivery, RecentAlertsPage

router = APIRouter(prefix="/alerts", tags=["alerts"])
TenantId = Annotated[str, Depends(require_tenant_id)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
OpaqueCursor = Annotated[str | None, Query(max_length=1024)]


@router.get("/recent", response_model=RecentAlertsPage)
async def recent_alerts(
    tenant_id: TenantId,
    limit: PageLimit = 20,
    cursor: OpaqueCursor = None,
) -> RecentAlertsPage:
    """Return sent tenant alerts newest first using an opaque stable cursor."""
    before_created_at: datetime | None = None
    before_id: str | None = None
    if cursor is not None:
        before_created_at, before_id = _decode_cursor(cursor)

    records = await database.list_recent_alert_deliveries_for_owner(
        tenant_id,
        limit=limit + 1,
        before_created_at=before_created_at,
        before_id=before_id,
    )
    has_more = len(records) > limit
    page_records = records[:limit]
    next_cursor = None
    if has_more and page_records:
        last_record = page_records[-1]
        next_cursor = _encode_cursor(last_record.created_at, last_record._id)
    return RecentAlertsPage(
        items=[PublicAlertDelivery.from_record(record) for record in page_records],
        next_cursor=next_cursor,
    )


def _encode_cursor(created_at: datetime, alert_id: str) -> str:
    payload = json.dumps(
        {"created_at": created_at.astimezone(UTC).isoformat(), "id": alert_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload: Any = json.loads(base64.b64decode(cursor + padding, altchars=b"-_", validate=True))
        if not isinstance(payload, dict) or set(payload) != {"created_at", "id"}:
            raise ValueError
        if not isinstance(payload["created_at"], str) or not isinstance(payload["id"], str) or not payload["id"]:
            raise ValueError
        created_at = datetime.fromisoformat(payload["created_at"])
        if created_at.tzinfo is None:
            raise ValueError
    except (UnicodeDecodeError, binascii.Error, json.JSONDecodeError, TypeError, ValueError):
        raise ValueError("invalid alert cursor") from None
    return created_at.astimezone(UTC), payload["id"]
