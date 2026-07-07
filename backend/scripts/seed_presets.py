"""Seed the preset keyword catalog from the legacy JSON config."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.config import AppConfig  # noqa: E402
from src.presets import PresetKeywordRecord  # noqa: E402

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_PATH = Path("config/config.json")


@dataclass(frozen=True, slots=True)
class SeedSummary:
    """Counts reported after a preset seed run."""

    total_parsed: int
    created: int
    updated: int
    skipped: int
    dry_run: bool = False


async def seed_presets(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    *,
    dry_run: bool = False,
) -> SeedSummary:
    """Seed preset keyword records from the legacy config and return a summary."""
    app_config = AppConfig.from_json(config_path)
    records, skipped = _records_from_config(app_config)
    if dry_run:
        return SeedSummary(
            total_parsed=len(app_config.filters),
            created=0,
            updated=0,
            skipped=skipped,
            dry_run=True,
        )

    from src.database import upsert_preset_keyword  # noqa: PLC0415

    created = 0
    updated = 0
    for record in records:
        _, inserted = await upsert_preset_keyword(record)
        if inserted:
            created += 1
        else:
            updated += 1

    return SeedSummary(
        total_parsed=len(app_config.filters),
        created=created,
        updated=updated,
        skipped=skipped,
    )


def format_summary(summary: SeedSummary) -> str:
    """Format a seed summary for command-line output."""
    dry_run_suffix = " dry_run=true" if summary.dry_run else ""
    return (
        f"total parsed={summary.total_parsed} created={summary.created} updated={summary.updated} "
        f"skipped={summary.skipped}{dry_run_suffix}"
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Seed preset keyword catalog entries from config/config.json.")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to the legacy JSON config.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to MongoDB.")
    return parser.parse_args()


async def main() -> None:
    """Run the preset seed command."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = await seed_presets(args.config, dry_run=args.dry_run)
    print(format_summary(summary))


def _records_from_config(app_config: AppConfig) -> tuple[list[PresetKeywordRecord], int]:
    records: list[PresetKeywordRecord] = []
    skipped = 0
    for filter_config in app_config.filters:
        try:
            record = PresetKeywordRecord.new(
                marketplace="mercari",
                name=filter_config.name,
                keywords=filter_config.keywords,
            )
        except ValueError as exc:
            if "keywords" not in str(exc):
                raise
            LOGGER.warning("Skipping preset with no valid keywords", extra={"preset_name": filter_config.name})
            skipped += 1
            continue
        records.append(record)
    return records, skipped


if __name__ == "__main__":
    asyncio.run(main())
