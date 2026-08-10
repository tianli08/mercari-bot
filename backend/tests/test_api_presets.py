"""Preset catalog and watchlist preset-copy API tests."""

from __future__ import annotations

import pytest
from api_resource_helpers import ApiResourceDatabase, client_for, create_destination, signup

from src import database
from src.api.app import create_app
from src.presets import PresetKeywordRecord

pytestmark = pytest.mark.asyncio


@pytest.fixture
def api_database(monkeypatch: pytest.MonkeyPatch) -> ApiResourceDatabase:
    """Patch persistence to an isolated in-memory database."""
    fake = ApiResourceDatabase("preset_api_tests")
    monkeypatch.setattr(database, "db_client", fake)
    return fake


async def test_enabled_presets_list_and_copy_idempotently(api_database: ApiResourceDatabase) -> None:
    """The catalog hides disabled presets and copying preserves other watchlist fields."""
    enabled = PresetKeywordRecord.new(
        name="Rick Owens",
        keywords=["Rick Owens", "リックオウエンス", "rick owens"],
    )
    disabled = PresetKeywordRecord.new(name="Hidden", keywords=["hidden"], enabled=False)
    alpha = PresetKeywordRecord.new(name="Alpha", keywords=["alpha"])
    for record in [enabled, disabled, alpha]:
        await database.upsert_preset_keyword(record)

    application = create_app()
    async with client_for(application) as client:
        await signup(client, "preset-user@example.com")
        destination = await create_destination(client)
        created = await client.post(
            "/api/v1/watchlists",
            json={
                "name": "Preset Target",
                "keywords": ["existing"],
                "filters": {"max_price": 9000},
                "destination_id": destination["id"],
                "enabled": False,
            },
        )
        watchlist = created.json()

        catalog = await client.get("/api/v1/presets")
        copied = await client.post(
            f"/api/v1/watchlists/{watchlist['id']}/keywords/from-preset",
            json={"preset_id": enabled._id},
        )
        copied_again = await client.post(
            f"/api/v1/watchlists/{watchlist['id']}/keywords/from-preset",
            json={"preset_id": enabled._id},
        )
        hidden = await client.post(
            f"/api/v1/watchlists/{watchlist['id']}/keywords/from-preset",
            json={"preset_id": disabled._id},
        )

    assert catalog.status_code == 200
    assert [preset["name"] for preset in catalog.json()] == ["Alpha", "Rick Owens"]
    assert all(set(preset) == {"id", "marketplace", "name", "keywords"} for preset in catalog.json())
    assert copied.status_code == copied_again.status_code == 200
    assert copied_again.json()["keywords"] == ["existing", "rick owens", "リックオウエンス"]
    assert copied_again.json()["name"] == watchlist["name"]
    assert copied_again.json()["filters"] == watchlist["filters"]
    assert copied_again.json()["destination_id"] == watchlist["destination_id"]
    assert copied_again.json()["enabled"] is False
    assert hidden.status_code == 404
    assert await database.get_registry_entry("mercari", "rick owens") is None


async def test_presets_require_authentication_and_foreign_watchlists_stay_hidden(
    api_database: ApiResourceDatabase,
) -> None:
    """Catalog access is authenticated and preset copying cannot cross tenants."""
    preset = PresetKeywordRecord.new(name="Julius", keywords=["julius"])
    await database.upsert_preset_keyword(preset)
    application = create_app()

    async with client_for(application) as anonymous:
        assert (await anonymous.get("/api/v1/presets")).status_code == 401

    async with client_for(application) as tenant_a, client_for(application) as tenant_b:
        await signup(tenant_a, "preset-a@example.com")
        await signup(tenant_b, "preset-b@example.com")
        destination_b = await create_destination(tenant_b)
        watchlist_b = await tenant_b.post(
            "/api/v1/watchlists",
            json={"name": "B", "destination_id": destination_b["id"]},
        )

        response = await tenant_a.post(
            f"/api/v1/watchlists/{watchlist_b.json()['id']}/keywords/from-preset",
            json={"preset_id": preset._id},
        )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
