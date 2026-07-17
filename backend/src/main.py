"""Service entrypoint for the Discord marketplace monitor bot."""

import argparse
import asyncio

from . import discord_bot
from .config import settings


def run_bot(send_initial_items: bool) -> None:
    """Start the Discord bot event loop."""
    try:
        asyncio.run(discord_bot.entry(send_initial_items=send_initial_items))
    except KeyboardInterrupt:
        pass


def parse_args() -> argparse.Namespace:
    """Parse service flags, falling back to environment-backed settings."""
    parser = argparse.ArgumentParser(description="Run the marketplace monitor bot service.")
    parser.add_argument(
        "--send-initial-items",
        dest="send_initial_items",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override SEND_INITIAL_ITEMS: post items discovered during per-keyword baseline scans.",
    )
    return parser.parse_args()


def main() -> None:
    """Non-interactive service entrypoint for the marketplace monitor bot."""
    args = parse_args()
    send_initial_items = args.send_initial_items if args.send_initial_items is not None else settings.send_initial_items
    run_bot(send_initial_items=send_initial_items)


if __name__ == "__main__":
    main()
