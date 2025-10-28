from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import discord
from discord import app_commands
from discord.ext import commands

from .logger import LoggerCog

_MAGNET_REGEX = re.compile(r"magnet:\?xt=urn:btih:([a-zA-Z0-9]{32,})", re.IGNORECASE)


@dataclass(slots=True)
class TrackedTorrent:
    """Represents a tracked torrent resource shared within Discord."""

    magnet_uri: str
    info_hash: str
    added_by: int
    added_at: datetime
    source: str


class TorrentHandler(commands.Cog):
    """Cog that tracks torrent links and provides basic management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        base_logger = getattr(bot, "logger", logging.getLogger("virusbot"))
        self.logger = base_logger.getChild("torrent_handler")
        self.tracked: Dict[str, TrackedTorrent] = {}

    def _logger_cog(self) -> Optional[LoggerCog]:
        """Retrieve the logger cog instance if it is loaded."""

        cog = self.bot.get_cog("LoggerCog")
        return cog if isinstance(cog, LoggerCog) else None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Automatically monitor messages for torrent information."""

        if message.author.bot:
            return

        magnets = self._extract_magnets(message.content)
        for magnet in magnets:
            entry = self._register_magnet(magnet, user_id=message.author.id, source="message")
            if entry:
                await self._notify_magnet_tracked(message.channel, entry)

        for attachment in message.attachments:
            if attachment.filename.lower().endswith(".torrent"):
                entry = await self._handle_torrent_attachment(attachment, message.author.id)
                if entry:
                    await message.channel.send(
                        f"Tracked torrent file `{attachment.filename}` shared by {message.author.mention}.",
                        delete_after=45,
                    )

    def _extract_magnets(self, content: str) -> List[str]:
        """Find and return all magnet URIs embedded in the provided message content."""

        return [match.group(0) for match in _MAGNET_REGEX.finditer(content or "")]

    def _register_magnet(self, magnet_uri: str, *, user_id: int, source: str) -> Optional[TrackedTorrent]:
        """Store a magnet URI if it has not already been tracked."""

        info_hash = self._parse_info_hash(magnet_uri)
        if not info_hash:
            self.logger.debug("Ignoring malformed magnet URI: %s", magnet_uri)
            return None

        info_hash = info_hash.upper()
        if info_hash in self.tracked:
            self.logger.debug("Magnet %s already tracked", info_hash)
            return None

        entry = TrackedTorrent(
            magnet_uri=magnet_uri,
            info_hash=info_hash,
            added_by=user_id,
            added_at=datetime.now(timezone.utc),
            source=source,
        )
        self.tracked[info_hash] = entry
        self._log_torrent_event(entry, action="track")
        return entry

    async def _handle_torrent_attachment(
        self, attachment: discord.Attachment, user_id: int
    ) -> Optional[TrackedTorrent]:
        """Process a .torrent attachment and store it as a tracked resource."""

        try:
            file_bytes = await attachment.read()
        except discord.HTTPException as exc:
            self.logger.error("Failed to download torrent attachment %s: %s", attachment.filename, exc)
            return None

        info_hash = hashlib.sha1(file_bytes).hexdigest().upper()
        if info_hash in self.tracked:
            self.logger.debug("Torrent attachment %s already tracked", attachment.filename)
            return None

        magnet_uri = f"magnet:?xt=urn:btih:{info_hash}"
        entry = TrackedTorrent(
            magnet_uri=magnet_uri,
            info_hash=info_hash,
            added_by=user_id,
            added_at=datetime.now(timezone.utc),
            source=f"attachment:{attachment.filename}",
        )
        self.tracked[info_hash] = entry
        self._log_torrent_event(entry, action="track_attachment")
        return entry

    async def _notify_magnet_tracked(self, channel: discord.abc.Messageable, entry: TrackedTorrent) -> None:
        """Send a notification message when a magnet link is tracked automatically."""

        try:
            await channel.send(
                f"Detected and tracked magnet link (`{entry.info_hash}`) shared in this channel.",
                delete_after=45,
            )
        except discord.HTTPException as exc:
            self.logger.error("Failed to send magnet tracking notice: %s", exc)

    def _log_torrent_event(self, entry: TrackedTorrent, *, action: str) -> None:
        """Relay torrent management events to the shared logger."""

        logger_cog = self._logger_cog()
        if logger_cog:
            logger_cog.log_torrent_activity(
                action=action,
                magnet_hash=entry.info_hash,
                user_id=entry.added_by,
                timestamp=entry.added_at,
                description=f"Source: {entry.source}",
            )
        self.logger.info(
            "Torrent tracked | hash=%s user_id=%s source=%s",
            entry.info_hash,
            entry.added_by,
            entry.source,
        )

    def _parse_info_hash(self, magnet_uri: str) -> Optional[str]:
        """Extract the BitTorrent info-hash from a magnet URI."""

        parsed = urlparse(magnet_uri)
        if parsed.scheme != "magnet":
            return None
        query = parse_qs(parsed.query)
        xt_values = query.get("xt")
        if not xt_values:
            return None
        for value in xt_values:
            if value.lower().startswith("urn:btih:"):
                return value.split(":")[-1]
        return None

    @app_commands.command(name="torrent_add", description="Manually track a magnet link")
    async def add_torrent(self, interaction: discord.Interaction, magnet_link: str) -> None:
        """Allow moderators to manually register a magnet link for tracking."""

        await interaction.response.defer(ephemeral=True)
        entry = self._register_magnet(magnet_link, user_id=interaction.user.id, source="command")
        if not entry:
            await interaction.followup.send("Failed to track magnet link. It may be invalid or already tracked.", ephemeral=True)
            return

        await interaction.followup.send(
            f"Magnet link tracked. Info hash: `{entry.info_hash}`.",
            ephemeral=True,
        )

    @app_commands.command(name="torrent_list", description="List tracked magnet hashes")
    async def list_torrents(self, interaction: discord.Interaction) -> None:
        """Provide a summary of all tracked torrents to the requesting user."""

        await interaction.response.defer(ephemeral=True)
        if not self.tracked:
            await interaction.followup.send("No torrents are currently being tracked.", ephemeral=True)
            return

        summaries = [
            f"`{info_hash}` • added by <@{entry.added_by}> on {entry.added_at.strftime('%Y-%m-%d %H:%M:%SZ')}"
            for info_hash, entry in list(self.tracked.items())[:10]
        ]
        if len(self.tracked) > 10:
            summaries.append(f"...and {len(self.tracked) - 10} more.")

        await interaction.followup.send("\n".join(summaries), ephemeral=True)

    @app_commands.command(name="torrent_remove", description="Stop tracking a torrent by its info hash")
    async def remove_torrent(self, interaction: discord.Interaction, info_hash: str) -> None:
        """Remove a tracked torrent identified by its info hash."""

        await interaction.response.defer(ephemeral=True)
        key = info_hash.upper()
        if key not in self.tracked:
            await interaction.followup.send("That info hash is not currently tracked.", ephemeral=True)
            return

        entry = self.tracked.pop(key)
        self._log_torrent_event(entry, action="untrack")
        await interaction.followup.send(
            f"Stopped tracking torrent `{entry.info_hash}`.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    """Register the torrent handler cog with the bot."""

    await bot.add_cog(TorrentHandler(bot))
