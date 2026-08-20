"""Tenant-scoped watchlist CRUD, keyword, monitoring, and isolation tests."""

from __future__ import annotations

import asyncio

import pytest
from api_resource_helpers import ApiResourceDatabase, client_for, create_destination, signup

from src import database
from src.api.app import create_app

pytestmark = pytest.mark.asyncio


@pytest.fixture
def api_database(monkeypatch: pytest.MonkeyPatch) -> ApiResourceDatabase:
    """Patch persistence to an isolated in-memory database."""
    fake = ApiResourceDatabase("watchlist_api_tests")
    monkeypatch.setattr(database, "db_client", fake)
    return fake


async def test_watchlist_crud_keywords_monitoring_and_registry(
    api_database: ApiResourceDatabase,
) -> None:
    """An authenticated tenant can manage a normalized watchlist end to end."""
    application = create_app()
    async with client_for(application) as client:
        tenant = await signup(client, "watchlist-owner@example.com")
        destination = await create_destination(client)

        created = await client.post(
            "/api/v1/watchlists",
            json={
                "name": "  Archive Finds  ",
                "keywords": ["  Rick   Owens ", "rick owens", "   "],
                "filters": {"min_price": 100, "max_price": 5000, "condition": "active"},
                "destination_id": destination["id"],
                "enabled": True,
            },
        )
        assert created.status_code == 201
        watchlist = created.json()
        assert set(watchlist) == {
            "id",
            "name",
            "keywords",
            "filters",
            "destination_id",
            "enabled",
            "created_at",
            "updated_at",
        }
        assert watchlist["name"] == "Archive Finds"
        assert watchlist["keywords"] == ["rick owens"]
        assert watchlist["filters"] == {"min_price": 100, "max_price": 5000, "condition": "active"}

        registry = await database.get_registry_entry("mercari", "rick owens")
        assert registry is not None
        assert [(subscriber.owner_id, subscriber.watchlist_id) for subscriber in registry.subscribers] == [
            (tenant["id"], watchlist["id"])
        ]

        added = await client.post(
            f"/api/v1/watchlists/{watchlist['id']}/keywords",
            json={"keyword": "  Maison   Margiela "},
        )
        duplicate = await client.post(
            f"/api/v1/watchlists/{watchlist['id']}/keywords",
            json={"keyword": "maison margiela"},
        )
        assert added.status_code == duplicate.status_code == 200
        assert duplicate.json()["keywords"] == ["rick owens", "maison margiela"]

        removed = await client.request(
            "DELETE",
            f"/api/v1/watchlists/{watchlist['id']}/keywords",
            json={"keyword": "rick owens"},
        )
        absent_remove = await client.request(
            "DELETE",
            f"/api/v1/watchlists/{watchlist['id']}/keywords",
            json={"keyword": "not subscribed"},
        )
        assert removed.status_code == absent_remove.status_code == 200
        assert absent_remove.json()["keywords"] == ["maison margiela"]
        assert await database.get_registry_entry("mercari", "rick owens") is None

        disabled = await client.patch(
            f"/api/v1/watchlists/{watchlist['id']}/monitoring",
            json={"enabled": False},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
        assert await database.get_registry_entry("mercari", "maison margiela") is None

        while_disabled = await client.post(
            f"/api/v1/watchlists/{watchlist['id']}/keywords",
            json={"keyword": "Julius"},
        )
        assert while_disabled.json()["keywords"] == ["maison margiela", "julius"]
        assert await database.get_registry_entry("mercari", "julius") is None

        enabled = await client.patch(
            f"/api/v1/watchlists/{watchlist['id']}/monitoring",
            json={"enabled": True},
        )
        assert enabled.json()["enabled"] is True
        assert await database.get_registry_entry("mercari", "julius") is not None

        updated = await client.patch(
            f"/api/v1/watchlists/{watchlist['id']}",
            json={"name": "Updated", "filters": {"condition": "any"}},
        )
        fetched = await client.get(f"/api/v1/watchlists/{watchlist['id']}")
        listed = await client.get("/api/v1/watchlists")
        assert updated.status_code == fetched.status_code == listed.status_code == 200
        assert fetched.json()["name"] == "Updated"
        assert listed.json() == [fetched.json()]

        deleted = await client.delete(f"/api/v1/watchlists/{watchlist['id']}")
        deleted_again = await client.delete(f"/api/v1/watchlists/{watchlist['id']}")
        assert deleted.status_code == 204
        assert deleted_again.status_code == 404
        assert await database.get_registry_entry("mercari", "julius") is None


async def test_watchlist_routes_reject_foreign_resources_and_ownership_injection(
    api_database: ApiResourceDatabase,
) -> None:
    """A tenant cannot reference, observe, or mutate another tenant's resources."""
    application = create_app()
    async with client_for(application) as tenant_a, client_for(application) as tenant_b:
        await signup(tenant_a, "tenant-a@example.com")
        await signup(tenant_b, "tenant-b@example.com")
        destination_a = await create_destination(tenant_a, "A")
        destination_b = await create_destination(tenant_b, "B")

        foreign_reference = await tenant_a.post(
            "/api/v1/watchlists",
            json={"name": "Nope", "destination_id": destination_b["id"]},
        )
        injected_owner = await tenant_a.post(
            "/api/v1/watchlists",
            json={
                "name": "Injected",
                "destination_id": destination_a["id"],
                "owner_id": "tenant-b",
            },
        )
        assert foreign_reference.status_code == 404
        assert injected_owner.status_code == 422

        created_b = await tenant_b.post(
            "/api/v1/watchlists",
            json={"name": "Tenant B", "keywords": ["secret keyword"], "destination_id": destination_b["id"]},
        )
        foreign_id = created_b.json()["id"]

        attempts = [
            await tenant_a.get(f"/api/v1/watchlists/{foreign_id}"),
            await tenant_a.patch(f"/api/v1/watchlists/{foreign_id}", json={"name": "Stolen"}),
            await tenant_a.post(f"/api/v1/watchlists/{foreign_id}/keywords", json={"keyword": "attack"}),
            await tenant_a.request(
                "DELETE",
                f"/api/v1/watchlists/{foreign_id}/keywords",
                json={"keyword": "secret keyword"},
            ),
            await tenant_a.patch(f"/api/v1/watchlists/{foreign_id}/monitoring", json={"enabled": False}),
            await tenant_a.delete(f"/api/v1/watchlists/{foreign_id}"),
        ]
        assert [response.status_code for response in attempts] == [404] * len(attempts)
        assert all(response.json()["code"] == "not_found" for response in attempts)

        still_owned = await tenant_b.get(f"/api/v1/watchlists/{foreign_id}")
        assert still_owned.status_code == 200
        assert still_owned.json()["name"] == "Tenant B"
        assert still_owned.json()["enabled"] is True
        assert still_owned.json()["keywords"] == ["secret keyword"]
        spoofed_list = await tenant_a.get("/api/v1/watchlists", params={"owner_id": "tenant-b"})
        assert spoofed_list.status_code == 200
        assert spoofed_list.json() == []


async def test_concurrent_keyword_adds_do_not_overwrite_each_other(
    api_database: ApiResourceDatabase,
) -> None:
    """Atomic set-style keyword updates retain concurrent normalized additions."""
    application = create_app()
    async with client_for(application) as client:
        await signup(client, "concurrent-keywords@example.com")
        destination = await create_destination(client)
        created = await client.post(
            "/api/v1/watchlists",
            json={"name": "Concurrent", "destination_id": destination["id"]},
        )
        watchlist_id = created.json()["id"]

        alpha, beta = await asyncio.gather(
            client.post(f"/api/v1/watchlists/{watchlist_id}/keywords", json={"keyword": "Alpha"}),
            client.post(f"/api/v1/watchlists/{watchlist_id}/keywords", json={"keyword": "Beta"}),
        )
        fetched = await client.get(f"/api/v1/watchlists/{watchlist_id}")

    assert alpha.status_code == beta.status_code == 200
    assert fetched.json()["keywords"] == ["alpha", "beta"]
    assert await database.get_registry_entry("mercari", "alpha") is not None
    assert await database.get_registry_entry("mercari", "beta") is not None


async def test_watchlist_list_requires_authentication(api_database: ApiResourceDatabase) -> None:
    """Protected watchlist routes reject requests without a valid session."""
    application = create_app()
    async with client_for(application) as client:
        response = await client.get("/api/v1/watchlists")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


async def test_keyword_add_rolls_back_when_registry_sync_fails(
    api_database: ApiResourceDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed keyword add leaves the watchlist and registry at the committed pre-image."""
    application = create_app()
    async with client_for(application) as client:
        tenant = await signup(client, "rollback-owner@example.com")
        destination = await create_destination(client)
        created = await client.post(
            "/api/v1/watchlists",
            json={"name": "Atomic", "keywords": ["rick owens"], "destination_id": destination["id"]},
        )
        watchlist_id = created.json()["id"]

        async def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("injected registry failure")

        monkeypatch.setattr(database, "sync_watchlist_subscriptions", boom)
        with pytest.raises(RuntimeError, match="injected registry failure"):
            await database.add_watchlist_keywords_for_owner(watchlist_id, tenant["id"], ["maison margiela"])
        fetched = await client.get(f"/api/v1/watchlists/{watchlist_id}")

    assert fetched.status_code == 200
    assert fetched.json()["keywords"] == ["rick owens"]
    assert await database.get_registry_entry("mercari", "rick owens") is not None
    assert await database.get_registry_entry("mercari", "maison margiela") is None


async def test_shared_keyword_registry_stays_isolated_across_tenants(
    api_database: ApiResourceDatabase,
) -> None:
    """One tenant removing a shared keyword does not drop the other tenant's subscriber."""
    application = create_app()
    async with client_for(application) as tenant_a, client_for(application) as tenant_b:
        await signup(tenant_a, "shared-a@example.com")
        await signup(tenant_b, "shared-b@example.com")
        destination_a = await create_destination(tenant_a, "A")
        destination_b = await create_destination(tenant_b, "B")
        created_a = await tenant_a.post(
            "/api/v1/watchlists",
            json={"name": "A", "keywords": ["shared"], "destination_id": destination_a["id"]},
        )
        created_b = await tenant_b.post(
            "/api/v1/watchlists",
            json={"name": "B", "keywords": ["shared"], "destination_id": destination_b["id"]},
        )
        watchlist_a = created_a.json()["id"]
        watchlist_b = created_b.json()["id"]

        removed = await tenant_a.request(
            "DELETE",
            f"/api/v1/watchlists/{watchlist_a}/keywords",
            json={"keyword": "shared"},
        )
        still_b = await tenant_b.get(f"/api/v1/watchlists/{watchlist_b}")
        entry = await database.get_registry_entry("mercari", "shared")
        deleted_b = await tenant_b.delete(f"/api/v1/watchlists/{watchlist_b}")

    assert removed.status_code == 200
    assert still_b.json()["keywords"] == ["shared"]
    assert entry is not None
    assert entry.subscriber_count == 1
    assert [subscriber.watchlist_id for subscriber in entry.subscribers] == [watchlist_b]
    assert deleted_b.status_code == 204
    leftover = await api_database.keyword_registry.find({"keyword": "shared"}).to_list(length=None)
    assert leftover == []
