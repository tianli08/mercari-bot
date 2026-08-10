"""Tenant-scoped Discord webhook destination routes."""

from __future__ import annotations

from typing import Annotated

import aiohttp
from fastapi import APIRouter, Depends, Response

from ... import database
from ...destinations import DestinationInUseError, DestinationNotFoundError, DestinationRecord
from ..auth.context import require_tenant_id
from ..schemas import DestinationCreateRequest, DestinationUpdateRequest, PublicDestination

router = APIRouter(prefix="/destinations", tags=["destinations"])
TenantId = Annotated[str, Depends(require_tenant_id)]


@router.post("", response_model=PublicDestination, status_code=201)
async def create_destination(payload: DestinationCreateRequest, tenant_id: TenantId) -> PublicDestination:
    """Create an encrypted Discord webhook destination for the tenant."""
    record = await database.create_destination(
        tenant_id,
        payload.webhook_url,
        payload.label,
        type=payload.type,
    )
    return PublicDestination.from_record(record)


@router.get("", response_model=list[PublicDestination])
async def list_destinations(tenant_id: TenantId) -> list[PublicDestination]:
    """List only secret-free metadata for the tenant's destinations."""
    records = await database.list_destinations_for_owner(tenant_id)
    return [PublicDestination.from_record(record) for record in records]


@router.get("/{destination_id}", response_model=PublicDestination)
async def get_destination(destination_id: str, tenant_id: TenantId) -> PublicDestination:
    """Read one destination through an owner-filtered selector."""
    return PublicDestination.from_record(await _require_owned_destination(destination_id, tenant_id))


@router.patch("/{destination_id}", response_model=PublicDestination)
async def update_destination(
    destination_id: str,
    payload: DestinationUpdateRequest,
    tenant_id: TenantId,
) -> PublicDestination:
    """Change an owned destination label and/or replace its webhook secret."""
    record = await database.update_destination_for_owner(
        destination_id,
        tenant_id,
        **payload.model_dump(exclude_unset=True),
    )
    return PublicDestination.from_record(record)


@router.delete("/{destination_id}", status_code=204)
async def delete_destination(destination_id: str, tenant_id: TenantId) -> Response:
    """Delete an unused owned destination."""
    await _require_owned_destination(destination_id, tenant_id)
    if await database.destination_is_referenced_for_owner(destination_id, tenant_id):
        raise DestinationInUseError(destination_id)
    if not await database.delete_destination_for_owner(destination_id, tenant_id):
        raise DestinationNotFoundError(destination_id)
    return Response(status_code=204)


@router.post("/{destination_id}/verify", response_model=PublicDestination)
async def verify_destination(destination_id: str, tenant_id: TenantId) -> PublicDestination:
    """Send a fixed test message and mark an owned destination verified on success."""
    from ...webhook_delivery import DiscordWebhookVerifier

    destination = await _require_owned_destination(destination_id, tenant_id)
    async with aiohttp.ClientSession() as session:
        verified = await DiscordWebhookVerifier(session)(destination, tenant_id)
    return PublicDestination.from_record(verified)


async def _require_owned_destination(destination_id: str, tenant_id: str) -> DestinationRecord:
    destination = await database.get_destination_for_owner(destination_id, tenant_id)
    if destination is None:
        raise DestinationNotFoundError(destination_id)
    return destination
