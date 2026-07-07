"""Preset keyword catalog tests."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("DISCORD_KEY", "test-discord-key")
os.environ.setdefault("DESTINATION_SECRET_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
os.environ.setdefault("DESIGNER_WEBHOOK", "https://discord.com/api/webhooks/123/test")
os.environ.setdefault("DESIGNER_CHANNEL_ID", "designer")
os.environ.setdefault("SAVED_CHANNEL_ID", "saved")

from scripts.seed_presets import seed_presets  # noqa: E402
from src import database  # noqa: E402
from src.presets import PresetKeywordRecord, build_preset_id  # noqa: E402


class FakeDatabaseClient:
    """In-memory database client with the same collection attributes as production."""

    def __init__(self) -> None:
        """Initialize fake MongoDB collections."""
        self.client = AsyncMongoMockClient()
        self.db = self.client["preset_tests"]
        self.listings = self.db["marketplace_listings"]
        self.alerts = self.db["listing_alerts"]
        self.users = self.db["users"]
        self.watchlists = self.db["watchlists"]
        self.destinations = self.db["destinations"]
        self.keyword_registry = self.db["keyword_registry"]
        self.preset_keywords = self.db["preset_keywords"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        """Create the same indexes as the production client."""
        await database.DatabaseClient.ensure_indexes(self)


@pytest.fixture
def fake_database(monkeypatch: pytest.MonkeyPatch) -> FakeDatabaseClient:
    """Patch database access to use an in-memory MongoDB fake."""
    fake_client = FakeDatabaseClient()
    monkeypatch.setattr(database, "db_client", fake_client)
    return fake_client


def test_build_preset_id_slugging() -> None:
    """Preset ids use stable lowercase slugs for catalog names."""
    assert build_preset_id("mercari", "Rick Owens") == "mercari:rick-owens"
    assert build_preset_id("mercari", "A&G Rock n Roll Couture") == "mercari:a-g-rock-n-roll-couture"
    assert build_preset_id("mercari", "Number (N)ine") == "mercari:number-n-ine"
    assert build_preset_id("mercari", "14th Addiction") == "mercari:14th-addiction"


def test_preset_record_normalizes_keywords_and_rejects_empty_values() -> None:
    """Preset construction strips names, dedupes normalized keywords, and rejects empty fields."""
    record = PresetKeywordRecord.new(
        name="  Rick Owens  ",
        keywords=["  Rick   Owens ", "rick owens", "", "リックオウエンス"],
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    assert record._id == "mercari:rick-owens"
    assert record.name == "Rick Owens"
    assert record.keywords == ["rick owens", "リックオウエンス"]

    with pytest.raises(ValueError, match="preset name"):
        PresetKeywordRecord.new(name=" ", keywords=["rick owens"])
    with pytest.raises(ValueError, match="preset keywords"):
        PresetKeywordRecord.new(name="Rick Owens", keywords=[" ", ""])


@pytest.mark.asyncio
async def test_upsert_preset_keyword_updates_without_duplicates(fake_database: FakeDatabaseClient) -> None:
    """Preset upserts insert once, update mutable fields, and preserve created_at."""
    first_timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    second_timestamp = datetime(2025, 1, 2, tzinfo=UTC)
    first_record = PresetKeywordRecord.new(
        name="Rick Owens",
        keywords=["rick owens"],
        created_at=first_timestamp,
    )
    second_record = PresetKeywordRecord.new(
        name="Rick Owens",
        keywords=["rick owens", "リックオウエンス"],
        created_at=second_timestamp,
    )

    stored_record, inserted = await database.upsert_preset_keyword(first_record)
    updated_record, updated_inserted = await database.upsert_preset_keyword(second_record)

    assert inserted is True
    assert stored_record.created_at == first_timestamp
    assert updated_inserted is False
    assert updated_record.keywords == ["rick owens", "リックオウエンス"]
    assert updated_record.created_at == first_timestamp
    assert updated_record.updated_at == second_timestamp
    assert await fake_database.preset_keywords.count_documents({}) == 1


@pytest.mark.asyncio
async def test_list_preset_keywords_filters_enabled_and_sorts(fake_database: FakeDatabaseClient) -> None:
    """Preset listing returns enabled records by default and sorts by display name."""
    for record in [
        PresetKeywordRecord.new(name="Zed", keywords=["zed"]),
        PresetKeywordRecord.new(name="Alpha", keywords=["alpha"]),
        PresetKeywordRecord.new(name="Beta", keywords=["beta"], enabled=False),
    ]:
        await database.upsert_preset_keyword(record)

    enabled_records = await database.list_preset_keywords()
    all_records = await database.list_preset_keywords(enabled_only=False)

    assert [record.name for record in enabled_records] == ["Alpha", "Zed"]
    assert [record.name for record in all_records] == ["Alpha", "Beta", "Zed"]


@pytest.mark.asyncio
async def test_seed_presets_is_idempotent_for_real_config(fake_database: FakeDatabaseClient) -> None:
    """Seeding the real catalog twice creates no duplicates and reports updates on rerun."""
    config_path = Path(__file__).resolve().parents[1] / "config" / "config.json"

    first_summary = await seed_presets(config_path)
    second_summary = await seed_presets(config_path)
    stored_records = await database.list_preset_keywords(enabled_only=False)

    assert first_summary.total_parsed == 20
    assert first_summary.created == 20
    assert first_summary.updated == 0
    assert first_summary.skipped == 0
    assert second_summary.total_parsed == 20
    assert second_summary.created == 0
    assert second_summary.updated == 20
    assert second_summary.skipped == 0
    assert len(stored_records) == 20
    assert await database.get_preset_keyword_by_id("mercari:rick-owens") is not None
    assert await database.get_preset_keyword_by_id("mercari:number-n-ine") is not None
