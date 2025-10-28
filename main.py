"""Entry point for the Discord music bot."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.logger import LoggingCog, configure_logging


class MusicBot(commands.Bot):
    """Discord bot configured for music playback via slash commands."""

    def __init__(self, *, log_level: str, log_file: str, intents: discord.Intents) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
            activity=discord.Game(name="/play"),
        )
        self.log_level = log_level
        self.log_file = log_file
        self.logger = logging.getLogger("music_bot")

    async def setup_hook(self) -> None:
        """Load cogs and synchronise slash commands."""
        # Ensure logging cog is loaded first so subsequent cogs can reuse the logger.
        await self.add_cog(LoggingCog(self, level=self.log_level, log_file=self.log_file))

        for extension in ("cogs.music",):
            await self.load_extension(extension)
            self.logger.debug("Loaded extension %s", extension)

        synced = await self.tree.sync()
        self.logger.info("Synchronized %s application commands.", len(synced))

    async def on_ready(self) -> None:  # noqa: D401 - docstring inherited
        """Log initial ready event information."""
        if self.user:
            self.logger.info("Bot ready: %s (ID: %s)", self.user, self.user.id)

    async def close(self) -> None:
        """Handle shutdown and cleanup tasks before closing the bot."""
        self.logger.info("Shutting down bot and closing voice connections.")
        await super().close()


def ensure_cache_directory(path: str | None) -> Path | None:
    """Ensure the cache directory exists when caching is enabled."""
    if not path:
        return None

    cache_path = Path(path).expanduser().resolve()
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


async def run_bot() -> None:
    """Create and run the Discord music bot."""
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set. Please configure the .env file before running the bot.")

    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/bot.log")

    configure_logging(level=log_level, log_file=log_file)

    intents = discord.Intents.default()
    intents.guilds = True
    intents.voice_states = True

    cache_dir = ensure_cache_directory(os.getenv("CACHE_DIR"))
    if cache_dir:
        logging.getLogger(__name__).info("Audio cache directory configured at %s", cache_dir)

    bot = MusicBot(log_level=log_level, log_file=log_file, intents=intents)
    bot.cache_directory = cache_dir  # type: ignore[attr-defined]

    async with bot:
        await bot.start(token, reconnect=True)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
