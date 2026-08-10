"""Authenticated read-only preset catalog routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ... import database
from ..auth.context import require_tenant_id
from ..schemas import PublicPreset

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("", response_model=list[PublicPreset])
async def list_presets(
    _: Annotated[str, Depends(require_tenant_id)],
) -> list[PublicPreset]:
    """List enabled Mercari presets in deterministic display-name order."""
    records = await database.list_preset_keywords("mercari", enabled_only=True)
    return [PublicPreset.from_record(record) for record in records]
