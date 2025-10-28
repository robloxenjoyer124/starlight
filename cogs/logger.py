"""Logging cog providing structured logging for the Discord bot."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from rich.console import Console
from rich.logging import RichHandler
from discord.ext import commands

__all__ = ["LoggingCog", "configure_logging"]

_LOG_FORMAT_CONSOLE = "%(message)s"
_LOG_FORMAT_FILE = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

_LOGGING_CONFIGURED = False


def _resolve_log_level(level: str) -> int:
    """Return the logging level for the provided textual level."""
    if not level:
        return logging.INFO
    return getattr(logging, level.strip().upper(), logging.INFO)


def configure_logging(level: str = "INFO", log_file: str = "logs/bot.log") -> None:
    """Configure application-wide logging.

    Parameters
    ----------
    level:
        Textual log level (e.g. "INFO", "DEBUG"). Defaults to "INFO".
    log_file:
        Path to the log file.
    """
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        logging.getLogger(__name__).debug("Logging already configured; skipping reconfiguration.")
        return

    log_level = _resolve_log_level(level)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any pre-existing handlers to avoid duplicate logs.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console = Console(markup=True, color_system="auto")
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
        markup=True,
    )
    rich_handler.setFormatter(logging.Formatter(_LOG_FORMAT_CONSOLE))

    file_path = Path(log_file)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT_FILE))

    root_logger.addHandler(rich_handler)
    root_logger.addHandler(file_handler)

    _LOGGING_CONFIGURED = True
    root_logger.debug("Logging configured with level %s and file %s", level, file_path)


class LoggingCog(commands.Cog):
    """Cog responsible for logging bot lifecycle events and errors."""

    def __init__(self, bot: commands.Bot, *, level: str = "INFO", log_file: str = "logs/bot.log") -> None:
        self.bot = bot
        configure_logging(level=level, log_file=log_file)
        self.logger = logging.getLogger("discord.bot")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Log when the bot is ready."""
        if self.bot.user is None:
            return
        self.logger.info("Logged in as %s (ID: %s)", self.bot.user, self.bot.user.id)

    @commands.Cog.listener()
    async def on_disconnect(self) -> None:
        """Log when the bot disconnects."""
        self.logger.warning("Bot disconnected from Discord.")

    @commands.Cog.listener()
    async def on_resumed(self) -> None:
        """Log when the bot reconnects."""
        self.logger.info("Bot resumed connection to Discord.")

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command[Any, Any, Any]) -> None:
        """Log successful completion of slash commands."""
        if interaction.user:
            self.logger.info(
                "Command /%s completed for user %s (Guild: %s)",
                command.qualified_name,
                interaction.user,
                interaction.guild.id if interaction.guild else "DM",
            )

    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Log slash command errors and provide user feedback."""
        if interaction.command:
            self.logger.exception(
                "Error executing command /%s: %s",
                interaction.command.qualified_name,
                error,
            )
        else:
            self.logger.exception("Error executing unknown command: %s", error)

        message = "An unexpected error occurred while executing that command. Please try again later."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            self.logger.exception("Failed to send error message to user.")

