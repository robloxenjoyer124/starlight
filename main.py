from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List

import discord
from discord.ext import commands
from dotenv import load_dotenv
from rich.logging import RichHandler


@dataclass(frozen=True)
class BotConfig:
    """Configuration values required for running the Discord bot."""

    token: str
    virustotal_api_key: str
    log_path: Path


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure application logging with both file and rich console handlers."""

    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    file_handler = RotatingFileHandler(
        filename=log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )

    rich_handler = RichHandler(
        markup=True,
        rich_tracebacks=True,
        show_time=False,
        show_level=True,
        show_path=False,
    )
    rich_handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(rich_handler)

    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)

    application_logger = logging.getLogger("virusbot")
    application_logger.info(
        "Logging initialised. File output -> %s", log_path.resolve()
    )
    return application_logger


class VirusBot(commands.Bot):
    """Discord bot responsible for orchestrating the virus scanning workflow."""

    def __init__(self, intents: discord.Intents, config: BotConfig, logger: logging.Logger) -> None:
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=intents)
        self.config = config
        self.logger = logger

    async def setup_hook(self) -> None:
        """Automatically load all cogs located in the cogs directory."""

        self.logger.info("Commencing dynamic cog loading")
        loaded_cogs: List[str] = []
        for path in sorted(Path("cogs").glob("*.py")):
            if path.name.startswith("__"):
                continue
            extension = f"cogs.{path.stem}"
            try:
                await self.load_extension(extension)
            except Exception as exc:  # pragma: no cover - startup logging
                self.logger.exception("Failed loading cog %s", extension, exc_info=exc)
            else:
                loaded_cogs.append(extension)
        self.logger.info("Loaded cogs: %s", ", ".join(loaded_cogs) or "None")
        await self.tree.sync()
        self.logger.info("Application commands synced with Discord")


async def create_bot() -> VirusBot:
    """Instantiate and configure the Discord bot instance."""

    load_dotenv()

    token = os.getenv("TOKEN")
    api_key = os.getenv("VIRUSTOTAL_API_KEY")
    log_path_value = os.getenv("LOG_PATH")

    if not token:
        raise ValueError("TOKEN environment variable is required.")
    if not api_key:
        raise ValueError("VIRUSTOTAL_API_KEY environment variable is required.")
    if not log_path_value:
        raise ValueError("LOG_PATH environment variable is required.")

    log_path = Path(log_path_value)
    logger = configure_logging(log_path)

    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    config = BotConfig(token=token, virustotal_api_key=api_key, log_path=log_path)
    bot = VirusBot(intents=intents, config=config, logger=logger)
    return bot


async def main() -> None:
    """Run the Discord bot using an async context manager for clean shutdowns."""

    try:
        bot = await create_bot()
        async with bot:
            await bot.start(bot.config.token)
    except KeyboardInterrupt:
        logging.getLogger("virusbot").info("Shutdown requested by user.")
    except discord.LoginFailure as exc:
        logging.getLogger("virusbot").error("Failed to authenticate with Discord: %s", exc)
        raise


if __name__ == "__main__":
    asyncio.run(main())
