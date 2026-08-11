"""Tenant recent-alert feed isolation, pagination, and validation tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from api_resource_helpers import ApiResourceDatabase, client_for, signup

from src import database
from src.api.app import create_app
from src.listings import ListingRecord

pytestmark = pytest.mark.asyncio


@pytest.fixture
def api_database(monkeypatch: pytest.MonkeyPatch) -> ApiResourceDatabase:
    """Patch persistence to an isolated in-memory database."""
    fake = ApiResourceDatabase("alert_api_tests")
    monkeypatch.setattr(database, "db_client", fake)
    return fake


def build_listing(item_id: str, keyword: str) -> ListingRecord:
    """Build one allowlisted alert source record."""
    return ListingRecord(
        marketplace="mercari",
        item_id=item_id,
        canonical_id=f"mercari:{item_id}",
        url=f"https://jp.mercari.com/item/{item_id}",
        title=f"Listing {item_id}",
        image_url="https://example.com/private-thumbnail.jpg",
        raw_content="private raw listing body",
        price_text="JPY 1200",
        price_value=1200,
        currency="JPY",
        status="active",
        matched_filters={"private-filter"},
        matched_keywords={keyword},
    )


async def add_sent_alert(
    owner_id: str | None,
    *,
    destination_id: str,
    item_id: str,
    created_at: datetime,
) -> str:
    """Reserve and mark one durable sent alert."""
    listing = build_listing(item_id, f"keyword-{item_id}")
    delivery_id = await database.reserve_alert_delivery(
        listing,
        destination_id,
        owner_id=owner_id,
        observed_at=created_at,
    )
    assert delivery_id is not None
    await database.mark_alert_delivery_sent(delivery_id, listing.canonical_id, delivered_at=created_at)
    return delivery_id


async def test_recent_alerts_are_tenant_filtered_and_stably_paginated(
    api_database: ApiResourceDatabase,
) -> None:
    """Tied timestamps paginate by ID without duplication or tenant leakage."""
    application = create_app()
    async with client_for(application) as tenant_a, client_for(application) as tenant_b:
        user_a = await signup(tenant_a, "alerts-a@example.com")
        user_b = await signup(tenant_b, "alerts-b@example.com")

        timestamp = datetime(2025, 1, 2, tzinfo=UTC)
        older = timestamp - timedelta(days=1)
        expected_ids = [
            await add_sent_alert(
                user_a["id"],
                destination_id="destination-z",
                item_id="a-z",
                created_at=timestamp,
            ),
            await add_sent_alert(
                user_a["id"],
                destination_id="destination-y",
                item_id="a-y",
                created_at=timestamp,
            ),
            await add_sent_alert(
                user_a["id"],
                destination_id="destination-old",
                item_id="a-old",
                created_at=older,
            ),
        ]
        expected_ids.sort(reverse=True)
        # The older item always follows both tied newest items.
        expected_ids = [delivery_id for delivery_id in expected_ids if "a-old" not in delivery_id] + [
            delivery_id for delivery_id in expected_ids if "a-old" in delivery_id
        ]
        foreign_id = await add_sent_alert(
            user_b["id"],
            destination_id="destination-b",
            item_id="b-only",
            created_at=timestamp + timedelta(days=1),
        )
        await add_sent_alert(
            None,
            destination_id="legacy",
            item_id="legacy",
            created_at=timestamp + timedelta(days=2),
        )
        pending_listing = build_listing("pending", "pending")
        await database.reserve_alert_delivery(
            pending_listing,
            "pending-destination",
            owner_id=user_a["id"],
            observed_at=timestamp + timedelta(days=3),
        )

        first = await tenant_a.get("/api/v1/alerts/recent", params={"limit": 2, "owner_id": user_b["id"]})
        second = await tenant_a.get(
            "/api/v1/alerts/recent",
            params={"limit": 2, "cursor": first.json()["next_cursor"]},
        )
        tenant_b_feed = await tenant_b.get("/api/v1/alerts/recent")

    assert first.status_code == second.status_code == tenant_b_feed.status_code == 200
    assert [item["id"] for item in first.json()["items"]] == expected_ids[:2]
    assert [item["id"] for item in second.json()["items"]] == expected_ids[2:]
    assert first.json()["next_cursor"] is not None
    assert second.json()["next_cursor"] is None
    assert tenant_b_feed.json()["items"][0]["id"] == foreign_id

    all_items = first.json()["items"] + second.json()["items"]
    assert len({item["id"] for item in all_items}) == 3
    assert all(item["status"] == "sent" for item in all_items)
    assert all(set(item) == {
        "id",
        "listing_id",
        "destination_id",
        "marketplace",
        "title",
        "canonical_url",
        "matched_keywords",
        "status",
        "created_at",
        "delivered_at",
    } for item in all_items)
    response_text = first.text + second.text
    assert "private raw listing body" not in response_text
    assert "private-filter" not in response_text
    assert "private-thumbnail" not in response_text
    assert foreign_id not in response_text


async def test_recent_alert_validation_empty_feed_and_authentication(
    api_database: ApiResourceDatabase,
) -> None:
    """Empty feeds are well shaped and invalid pagination input is rejected."""
    application = create_app()
    async with client_for(application) as client:
        await signup(client, "empty-alerts@example.com")
        empty = await client.get("/api/v1/alerts/recent")
        invalid_cursor = await client.get("/api/v1/alerts/recent", params={"cursor": "not-a-cursor"})
        too_small = await client.get("/api/v1/alerts/recent", params={"limit": 0})
        too_large = await client.get("/api/v1/alerts/recent", params={"limit": 101})

    async with client_for(application) as anonymous:
        unauthenticated = await anonymous.get("/api/v1/alerts/recent")

    assert empty.json() == {"items": [], "next_cursor": None}
    assert invalid_cursor.status_code == too_small.status_code == too_large.status_code == 422
    assert invalid_cursor.json()["code"] == "validation_error"
    assert unauthenticated.status_code == 401

    indexes = await api_database.alerts.index_information()
    assert "alerts_owner_status_created_id_idx" in indexes
