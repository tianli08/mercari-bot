import asyncio
import discord_bot

START_PROMPT = "Press Enter to start the bot..."
INITIAL_SEND_PROMPT = (
    "Send initial discovered items to Discord during startup? [y/N]: "
)


def run_bot(send_initial_items: bool) -> None:
    """Start the Discord bot event loop."""
    asyncio.run(discord_bot.entry(send_initial_items=send_initial_items))


def ask_send_initial_items() -> bool:
    """Ask whether startup-discovered items should be posted to Discord."""
    response = input(INITIAL_SEND_PROMPT).strip().lower()
    return response in {"y", "yes"}


def main() -> None:
    """CLI entrypoint for the Mercari bot."""
    # Keep a manual start gate so users can confirm terminal readiness.
    input(START_PROMPT)
    send_initial_items = ask_send_initial_items()
    run_bot(send_initial_items=send_initial_items)


if __name__ == "__main__":
    main()
