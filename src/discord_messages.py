"""Discord presentation helpers for listing alert messages."""

import asyncio

import discord

from . import retrieve_utils
from .config import settings
from .listings import ListingRecord
from .logging_utils import get_logger, log_exception

discord_logger = get_logger("discord")


class View(discord.ui.View):
    """Persistent message actions for listing cards."""

    def __init__(self) -> None:
        """Create a persistent action row for listing messages."""
        super().__init__(timeout=None)
        self.is_saved = False
        self.save_lock = asyncio.Lock()

    def disable_save_actions(self) -> None:
        """Disable interactive controls after a listing has been saved."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Save Item", emoji="\N{WHITE HEAVY CHECK MARK}")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Copy the current listing embed into the saved-items channel once."""
        await interaction.response.defer(ephemeral=True, thinking=False)

        if interaction.message is None or not interaction.message.embeds:
            await interaction.followup.send("This listing message is missing its embed.", ephemeral=True)
            return

        async with self.save_lock:
            if self.is_saved:
                self.disable_save_actions()
                await interaction.message.edit(view=self)
                await interaction.followup.send("Listing already saved.", ephemeral=True)
                return

            channel = interaction.client.get_channel(int(settings.saved_channel_id))
            if channel is None:
                discord_logger.warning(
                    "Saved-items channel is not available",
                    context={"channel_id": settings.saved_channel_id},
                )
                await interaction.followup.send("Saved-items channel not found.", ephemeral=True)
                return

            embed = interaction.message.embeds[0]
            try:
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                log_exception(
                    discord_logger,
                    "Failed to send listing embed to saved-items channel",
                    exc,
                    channel_id=settings.saved_channel_id,
                )
                await interaction.followup.send("Saving failed. Try again.", ephemeral=True)
                return

            self.is_saved = True
            self.disable_save_actions()
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.followup.send("Listing saved!", ephemeral=True)


def build_listing_embed(item: ListingRecord) -> discord.Embed:
    """Build the Discord embed for a single canonical listing."""
    proxy_link = retrieve_utils.link_crafter(item.url) if item.marketplace == "mercari" else None
    description_lines = [f"Marketplace: {item.marketplace.title()}"]

    if item.matched_filters:
        description_lines.append(f"Filters: {', '.join(sorted(item.matched_filters))}")
    if item.matched_keywords:
        description_lines.append(f"Keywords: {', '.join(sorted(item.matched_keywords))}")
    if item.price_text:
        description_lines.append(f"Price: {item.price_text}")
    if proxy_link:
        description_lines.append(f"Proxy: [Open listing]({proxy_link})")

    embed = discord.Embed(
        title=item.title,
        url=item.url,
        description="\n".join(description_lines),
    )
    if item.image_url:
        embed.set_image(url=item.image_url)
    embed.set_footer(text=f"ArchiveStatic | {item.canonical_id}")
    return embed


async def send_listing_message(
    channel: discord.abc.Messageable,
    item: ListingRecord,
) -> None:
    """Send a Discord embed for a single canonical listing."""
    await channel.send(embed=build_listing_embed(item), view=View())
