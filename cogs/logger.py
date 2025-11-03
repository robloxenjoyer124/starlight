from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

import discord
from discord.ext import commands


class LoggerCog(commands.Cog):
    """Cog responsible for centralising structured logging across the bot."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.logger = bot.logger.getChild("activity")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Log a message when the bot becomes ready to receive events."""

        user_display = str(self.bot.user) if self.bot.user else "Unknown User"
        self.logger.info("Bot connected to Discord as %s", user_display)

    def log_scan_result(
        self,
        *,
        filename: str,
        file_hash: str,
        user_id: int,
        timestamp: datetime,
        verdict: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record the outcome of a virus scan with structured context."""

        payload = additional_data or {}
        formatted_context = " ".join(
            f"{key}={value}" for key, value in payload.items()
        )
        self.logger.info(
            "virus_scan filename=%s hash=%s user_id=%s timestamp=%s verdict=%s %s",
            filename,
            file_hash,
            user_id,
            timestamp.isoformat(),
            verdict,
            formatted_context,
        )

    def log_torrent_activity(
        self,
        *,
        action: str,
        magnet_hash: str,
        user_id: int,
        timestamp: datetime,
        description: str,
    ) -> None:
        """Log torrent management actions performed by users."""

        self.logger.info(
            "torrent_action action=%s hash=%s user_id=%s timestamp=%s description=%s",
            action,
            magnet_hash,
            user_id,
            timestamp.isoformat(),
            description,
        )

    def log_exception(self, message: str, *, error: BaseException) -> None:
        """Persist exception information using the shared logger."""

        self.logger.exception(message, exc_info=error)


async def setup(bot: commands.Bot) -> None:
    """Add the logger cog to the running bot instance."""

    await bot.add_cog(LoggerCog(bot))
