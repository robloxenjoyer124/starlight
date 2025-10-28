from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .logger import LoggerCog


VT_FILE_SCAN_ENDPOINT = "https://www.virustotal.com/api/v3/files"
VT_URL_SCAN_ENDPOINT = "https://www.virustotal.com/api/v3/urls"
VT_ANALYSIS_ENDPOINT = "https://www.virustotal.com/api/v3/analyses/{analysis_id}"
MAX_FREE_FILE_SIZE = 32 * 1024 * 1024


@dataclass(slots=True)
class VirusScanResult:
    """Container describing the outcome of a VirusTotal scan."""

    filename: str
    file_hash: str
    user_id: int
    timestamp: datetime
    verdict: str
    malicious: int
    suspicious: int
    undetected: int
    timeout: bool = False
    error: Optional[str] = None

    @property
    def is_infected(self) -> bool:
        """Determine whether the scan indicates the presence of malware."""

        return self.malicious > 0 or self.suspicious > 0 or self.verdict == "infected"


class VirusScanner(commands.Cog):
    """Cog responsible for scanning files and URLs using the VirusTotal API."""

    def __init__(self, bot: commands.Bot, api_key: str) -> None:
        self.bot = bot
        self.api_key = api_key
        base_logger = getattr(bot, "logger", logging.getLogger("virusbot"))
        self.logger = base_logger.getChild("virus_scanner")
        self.session = aiohttp.ClientSession()
        self.headers = {"x-apikey": self.api_key}
        self.poll_interval = 5
        self.max_poll_attempts = 10

    def cog_unload(self) -> None:
        """Ensure the aiohttp session is closed when the cog unloads."""

        if not self.session.closed:
            asyncio.create_task(self.session.close())

    def _logger_cog(self) -> Optional[LoggerCog]:
        """Retrieve the logger cog instance if it is loaded."""

        cog = self.bot.get_cog("LoggerCog")
        return cog if isinstance(cog, LoggerCog) else None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Automatically scan attachments uploaded in a Discord channel."""

        if message.author.bot:
            return
        if not message.attachments:
            return

        for attachment in message.attachments:
            try:
                await self._handle_attachment(message, attachment)
            except Exception as exc:  # pragma: no cover - runtime safeguard
                self.logger.exception(
                    "Unhandled error while scanning attachment %s", attachment.filename, exc_info=exc
                )

    async def _handle_attachment(self, message: discord.Message, attachment: discord.Attachment) -> None:
        """Download, scan, and process a message attachment."""

        if attachment.size > MAX_FREE_FILE_SIZE:
            self.logger.warning(
                "Attachment %s exceeds VirusTotal free-tier size limit", attachment.filename
            )
            await message.channel.send(
                f"{message.author.mention} file `{attachment.filename}` is too large to scan (limit 32MB).",
                delete_after=30,
            )
            return

        try:
            file_content = await attachment.read()
        except discord.HTTPException as exc:
            self.logger.error("Failed to download attachment %s: %s", attachment.filename, exc)
            return

        result = await self.scan_bytes(
            file_bytes=file_content,
            file_name=attachment.filename,
            user_id=message.author.id,
        )

        self._log_scan_result(result)

        if result.error:
            await message.channel.send(
                f"{message.author.mention} scanning `{attachment.filename}` failed: {result.error}",
                delete_after=30,
            )
            return

        if result.is_infected:
            try:
                await message.delete()
            except discord.Forbidden:
                self.logger.warning(
                    "Insufficient permissions to delete infected message from user %s", message.author.id
                )
            except discord.HTTPException as exc:
                self.logger.error(
                    "Failed to delete infected message posted by %s: %s", message.author.id, exc
                )
            else:
                await message.channel.send(
                    f"Message removed: `{attachment.filename}` from {message.author.mention} was flagged as malicious.",
                    delete_after=45,
                )
        else:
            try:
                await message.author.send(
                    f"Your upload `{attachment.filename}` was scanned and appears clean (verdict: {result.verdict})."
                )
            except discord.Forbidden:
                self.logger.info("Unable to DM user %s regarding scan result", message.author.id)

    async def scan_bytes(self, *, file_bytes: bytes, file_name: str, user_id: int) -> VirusScanResult:
        """Submit raw bytes to VirusTotal for analysis and return the outcome."""

        timestamp = datetime.now(timezone.utc)
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        try:
            analysis_id = await self._submit_file(file_bytes, file_name)
            stats, verdict = await self._poll_analysis(analysis_id)
        except asyncio.TimeoutError:
            return VirusScanResult(
                filename=file_name,
                file_hash=file_hash,
                user_id=user_id,
                timestamp=timestamp,
                verdict="timeout",
                malicious=0,
                suspicious=0,
                undetected=0,
                timeout=True,
                error="Analysis timed out",
            )
        except Exception as exc:
            self.logger.exception("File scan failed for %s", file_name, exc_info=exc)
            return VirusScanResult(
                filename=file_name,
                file_hash=file_hash,
                user_id=user_id,
                timestamp=timestamp,
                verdict="error",
                malicious=0,
                suspicious=0,
                undetected=0,
                error=str(exc),
            )

        return VirusScanResult(
            filename=file_name,
            file_hash=file_hash,
            user_id=user_id,
            timestamp=timestamp,
            verdict=verdict,
            malicious=stats.get("malicious", 0),
            suspicious=stats.get("suspicious", 0),
            undetected=stats.get("undetected", 0),
        )

    async def scan_url(self, *, url: str, user_id: int) -> VirusScanResult:
        """Submit a remote URL to VirusTotal for testing and return the analysis result."""

        timestamp = datetime.now(timezone.utc)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return VirusScanResult(
                filename=url,
                file_hash=hashlib.sha256(url.encode("utf-8")).hexdigest(),
                user_id=user_id,
                timestamp=timestamp,
                verdict="invalid_url",
                malicious=0,
                suspicious=0,
                undetected=0,
                error="URL must start with http or https",
            )

        try:
            analysis_id = await self._submit_url(url)
            stats, verdict = await self._poll_analysis(analysis_id)
        except asyncio.TimeoutError:
            return VirusScanResult(
                filename=url,
                file_hash=hashlib.sha256(url.encode("utf-8")).hexdigest(),
                user_id=user_id,
                timestamp=timestamp,
                verdict="timeout",
                malicious=0,
                suspicious=0,
                undetected=0,
                timeout=True,
                error="Analysis timed out",
            )
        except Exception as exc:
            self.logger.exception("URL scan failed for %s", url, exc_info=exc)
            return VirusScanResult(
                filename=url,
                file_hash=hashlib.sha256(url.encode("utf-8")).hexdigest(),
                user_id=user_id,
                timestamp=timestamp,
                verdict="error",
                malicious=0,
                suspicious=0,
                undetected=0,
                error=str(exc),
            )

        return VirusScanResult(
            filename=url,
            file_hash=hashlib.sha256(url.encode("utf-8")).hexdigest(),
            user_id=user_id,
            timestamp=timestamp,
            verdict=verdict,
            malicious=stats.get("malicious", 0),
            suspicious=stats.get("suspicious", 0),
            undetected=stats.get("undetected", 0),
        )

    async def _submit_file(self, file_bytes: bytes, file_name: str) -> str:
        """Upload a file to VirusTotal and return the generated analysis identifier."""

        form = aiohttp.FormData()
        form.add_field("file", file_bytes, filename=file_name, content_type="application/octet-stream")
        async with self.session.post(VT_FILE_SCAN_ENDPOINT, data=form, headers=self.headers) as response:
            payload = await self._handle_response(response)
        return payload["data"]["id"]

    async def _submit_url(self, url: str) -> str:
        """Upload a URL to VirusTotal and return the analysis identifier."""

        async with self.session.post(VT_URL_SCAN_ENDPOINT, data={"url": url}, headers=self.headers) as response:
            payload = await self._handle_response(response)
        return payload["data"]["id"]

    async def _poll_analysis(self, analysis_id: str) -> Tuple[Dict[str, int], str]:
        """Poll the VirusTotal analysis endpoint until the scan completes."""

        for attempt in range(self.max_poll_attempts):
            async with self.session.get(
                VT_ANALYSIS_ENDPOINT.format(analysis_id=analysis_id), headers=self.headers
            ) as response:
                payload = await self._handle_response(response)

            attributes = payload["data"]["attributes"]
            status = attributes.get("status")
            if status == "completed":
                stats: Dict[str, int] = attributes.get("stats", {})
                verdict = self._evaluate_verdict(attributes)
                return stats, verdict
            if status == "error":
                raise RuntimeError("VirusTotal reported an error while analysing the resource")

            await asyncio.sleep(self.poll_interval)

        raise asyncio.TimeoutError("VirusTotal analysis did not finish in time")

    def _evaluate_verdict(self, attributes: Dict[str, Any]) -> str:
        """Derive a human-readable verdict from VirusTotal attributes."""

        stats: Dict[str, int] = attributes.get("stats", {})
        if stats.get("malicious", 0) > 0:
            return "infected"
        if stats.get("suspicious", 0) > 0:
            return "suspicious"
        return attributes.get("status", "unknown")

    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Validate an HTTP response and return its JSON payload."""

        try:
            response.raise_for_status()
            payload = await response.json()
        except aiohttp.ClientResponseError as exc:
            text = await response.text()
            raise RuntimeError(f"VirusTotal API error: {exc.status} -> {text}") from exc
        except aiohttp.ContentTypeError:
            text = await response.text()
            raise RuntimeError(f"Unexpected response from VirusTotal: {text}")
        return payload

    def _log_scan_result(self, result: VirusScanResult) -> None:
        """Forward scan outcomes to the logger cog and the cog's logger."""

        data = {
            "malicious": result.malicious,
            "suspicious": result.suspicious,
            "undetected": result.undetected,
            "timeout": result.timeout,
            "error": result.error or "",
        }
        logger_cog = self._logger_cog()
        if logger_cog:
            logger_cog.log_scan_result(
                filename=result.filename,
                file_hash=result.file_hash,
                user_id=result.user_id,
                timestamp=result.timestamp,
                verdict=result.verdict,
                additional_data=data,
            )
        self.logger.info(
            "Scan result -> file=%s hash=%s verdict=%s malicious=%s suspicious=%s undetected=%s user_id=%s error=%s",
            result.filename,
            result.file_hash,
            result.verdict,
            result.malicious,
            result.suspicious,
            result.undetected,
            result.user_id,
            result.error,
        )

    @app_commands.command(name="scan", description="Scan a remote file URL using VirusTotal")
    async def scan_command(self, interaction: discord.Interaction, url: str) -> None:
        """Provide a slash command for manually scanning URLs through VirusTotal."""

        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await self.scan_url(url=url, user_id=interaction.user.id)
        self._log_scan_result(result)

        if result.error:
            await interaction.followup.send(
                f"Scanning failed for `{url}`: {result.error}", ephemeral=True
            )
            return

        if result.is_infected:
            message = (
                f"⚠️ The URL `{url}` appears malicious. Verdict: {result.verdict}. "
                f"Malicious detections: {result.malicious}."
            )
        else:
            message = (
                f"✅ The URL `{url}` appears clean. Verdict: {result.verdict}. "
                f"Malicious detections: {result.malicious}."
            )

        await interaction.followup.send(message, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Register the virus scanner cog with the bot."""

    api_key: str = bot.config.virustotal_api_key  # type: ignore[attr-defined]
    await bot.add_cog(VirusScanner(bot, api_key))
