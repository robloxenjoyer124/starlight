"""Music cog implementing slash commands and queue management."""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qs, urlparse

import discord
from discord import app_commands
from discord.ext import commands

import yt_dlp

try:
    import itunespy
except ImportError:  # pragma: no cover - optional dependency
    itunespy = None  # type: ignore[assignment]

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except ImportError:  # pragma: no cover - optional dependency
    spotipy = None  # type: ignore[assignment]
    SpotifyClientCredentials = None  # type: ignore[assignment]

__all__ = ["MusicCog"]

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


class ResolverError(Exception):
    """Raised when track resolution fails."""


@dataclass(slots=True)
class Track:
    """Representation of a track queued for playback."""

    query: str
    title: str
    webpage_url: str
    duration: int
    source: str
    thumbnail: Optional[str]
    author: Optional[str]
    requester: discord.abc.User

    @property
    def duration_display(self) -> str:
        """Return the track duration as a human-readable string."""
        if self.duration <= 0:
            return "Live"
        return str(datetime.timedelta(seconds=int(self.duration)))

    @property
    def label(self) -> str:
        """Return a formatted label for queue displays."""
        display_name = getattr(self.requester, "display_name", self.requester.name)
        return f"{self.title} • Requested by {display_name}"


class SourceResolver:
    """Resolve arbitrary inputs into playable tracks."""

    def __init__(self, *, loop: asyncio.AbstractEventLoop, cache_dir: Optional[Path], logger: logging.Logger) -> None:
        self.loop = loop
        self.cache_dir = cache_dir
        self.logger = logger
        self.spotify_client = self._build_spotify_client()

    @property
    def cache_enabled(self) -> bool:
        """Return whether caching is enabled."""
        return self.cache_dir is not None

    def _build_spotify_client(self) -> Optional["spotipy.Spotify"]:
        """Build a Spotify client using credentials from environment variables."""
        if spotipy is None or SpotifyClientCredentials is None:
            return None

        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            return None

        try:
            auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
            return spotipy.Spotify(auth_manager=auth_manager)
        except Exception as exc:  # pragma: no cover - only executed when Spotify credentials invalid
            self.logger.warning("Failed to initialise Spotify client: %s", exc)
            return None

    async def resolve(self, raw_query: str, requester: discord.abc.User) -> List[Track]:
        """Resolve the provided query into a list of tracks."""
        query = raw_query.strip()
        if not query:
            raise ResolverError("The provided query was empty.")

        parsed = urlparse(query)
        if parsed.scheme and parsed.netloc:
            domain = parsed.netloc.lower()
            if "spotify" in domain:
                return await self._resolve_spotify(query, requester)
            if "music.apple" in domain or "itunes.apple" in domain:
                return await self._resolve_itunes(query, requester)
            if "soundcloud" in domain:
                info = await self._extract_metadata(query)
                return self._info_to_tracks(info, requester, source_override="SoundCloud")
            # All other URLs are processed directly via yt-dlp (e.g. YouTube).
            info = await self._extract_metadata(query)
            return self._info_to_tracks(info, requester)

        # Non-URL queries default to a YouTube search.
        return await self._search_youtube(query, requester, source_label="YouTube Search")

    async def create_playback_source(self, track: Track) -> tuple[str, Dict[str, Any], Optional[Path]]:
        """Return the playback URL or file path for the provided track."""

        def _inner() -> tuple[str, Dict[str, Any], Optional[Path]]:
            ytdl = self._build_ytdl(download=self.cache_enabled)
            data = ytdl.extract_info(track.query, download=self.cache_enabled)
            if data is None:
                raise ResolverError("Failed to gather playback information for the requested track.")

            if isinstance(data, dict) and data.get("entries"):
                data = data["entries"][0]

            if not isinstance(data, dict):
                raise ResolverError("Received unexpected data when preparing playback.")

            file_path: Optional[Path] = None
            playback_reference: str
            if self.cache_enabled:
                filename = ytdl.prepare_filename(data)
                file_path = Path(filename)
                playback_reference = str(file_path)
            else:
                playback_reference = data["url"]

            return playback_reference, data, file_path

        return await self.loop.run_in_executor(None, _inner)

    async def _extract_metadata(self, query: str) -> Dict[str, Any]:
        """Use yt-dlp to extract metadata for the query without downloading."""

        def _inner() -> Dict[str, Any]:
            ytdl = self._build_ytdl(download=False)
            result = ytdl.extract_info(query, download=False)
            if result is None:
                raise ResolverError("No results were returned for the provided query.")
            return result

        return await self.loop.run_in_executor(None, _inner)

    def _build_ytdl(self, *, download: bool) -> yt_dlp.YoutubeDL:
        """Create a configured YoutubeDL instance."""
        options: Dict[str, Any] = {
            "format": "bestaudio/best",
            "quiet": True,
            "ignoreerrors": True,
            "no_warnings": True,
            "logtostderr": False,
            "default_search": "ytsearch",
            "restrictfilenames": True,
            "source_address": "0.0.0.0",
        }

        if download:
            if self.cache_dir is None:
                raise ResolverError("Caching is disabled but a download was requested.")
            options["outtmpl"] = str(self.cache_dir / "%(title)s-%(id)s.%(ext)s")
            options["noplaylist"] = True
            options["cachedir"] = str(self.cache_dir)
        else:
            options["skip_download"] = True

        return yt_dlp.YoutubeDL(options)

    async def _search_youtube(self, query: str, requester: discord.abc.User, *, source_label: str) -> List[Track]:
        """Perform a YouTube search and return the first matching track."""
        info = await self._extract_metadata(f"ytsearch1:{query}")
        tracks = self._info_to_tracks(info, requester, source_override=source_label)
        if not tracks:
            raise ResolverError("No tracks were found for the provided search query.")
        return tracks

    def _info_to_tracks(
        self,
        info: Dict[str, Any],
        requester: discord.abc.User,
        *,
        source_override: Optional[str] = None,
    ) -> List[Track]:
        """Convert yt-dlp metadata into Track instances."""
        entries = info.get("entries") if isinstance(info, dict) else None
        results: List[Track] = []

        if entries:
            for entry in entries[:100]:
                track = self._entry_to_track(entry, requester, source_override=source_override)
                if track:
                    results.append(track)
            return results

        track = self._entry_to_track(info, requester, source_override=source_override)
        return [track] if track else []

    def _entry_to_track(
        self,
        entry: Optional[Dict[str, Any]],
        requester: discord.abc.User,
        *,
        source_override: Optional[str] = None,
    ) -> Optional[Track]:
        """Convert a single yt-dlp entry into a Track."""
        if not entry:
            return None

        title = entry.get("title") or "Unknown Title"
        webpage_url = entry.get("webpage_url") or entry.get("url") or ""
        query = webpage_url or entry.get("url") or ""
        if not query:
            return None

        duration = int(entry.get("duration") or 0)
        thumbnail: Optional[str] = entry.get("thumbnail")
        if not thumbnail:
            thumbnails = entry.get("thumbnails") or []
            if thumbnails:
                thumbnail = thumbnails[0].get("url")

        author = entry.get("uploader") or entry.get("artist") or entry.get("channel")
        source = source_override or entry.get("extractor_key") or entry.get("extractor") or "Unknown"

        return Track(
            query=query,
            title=title,
            webpage_url=webpage_url or query,
            duration=duration,
            source=source,
            thumbnail=thumbnail,
            author=author,
            requester=requester,
        )

    async def _resolve_spotify(self, url: str, requester: discord.abc.User) -> List[Track]:
        """Resolve Spotify tracks or playlists by searching on YouTube."""
        if self.spotify_client is None:
            self.logger.info("Spotify credentials missing; falling back to metadata extraction.")
            info = await self._extract_metadata(url)
            tracks = self._info_to_tracks(info, requester, source_override="Spotify")
            if not tracks:
                raise ResolverError("Failed to resolve Spotify link. Configure Spotify API credentials in the environment.")
            return tracks

        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ResolverError("Unsupported Spotify URL format.")

        item_type, item_id = parts[0], parts[1]
        if item_type == "track":
            return await self._resolve_spotify_track(item_id, requester)
        if item_type in {"playlist", "album"}:
            return await self._resolve_spotify_collection(item_id, requester, collection_type=item_type)

        raise ResolverError(f"Spotify item type '{item_type}' is not supported.")

    async def _resolve_spotify_track(self, track_id: str, requester: discord.abc.User) -> List[Track]:
        if self.spotify_client is None:
            raise ResolverError("Spotify client was not initialised.")

        def _inner() -> Dict[str, Any]:
            return self.spotify_client.track(track_id)  # type: ignore[call-arg]

        data = await self.loop.run_in_executor(None, _inner)
        title = data.get("name")
        artists = ", ".join(artist["name"] for artist in data.get("artists", []))
        search_term = f"{artists} - {title}" if artists else title
        return await self._search_youtube(search_term, requester, source_label="Spotify")

    async def _resolve_spotify_collection(
        self,
        collection_id: str,
        requester: discord.abc.User,
        *,
        collection_type: str,
        limit: int = 100,
    ) -> List[Track]:
        if self.spotify_client is None:
            raise ResolverError("Spotify client was not initialised.")

        def _inner() -> List[Dict[str, Any]]:
            if collection_type == "playlist":
                results = self.spotify_client.playlist_items(collection_id, additional_types=("track",), limit=limit)  # type: ignore[call-arg]
                return [item.get("track") for item in results.get("items", []) if item.get("track")]
            results = self.spotify_client.album_tracks(collection_id, limit=limit)  # type: ignore[call-arg]
            return results.get("items", [])

        tracks = await self.loop.run_in_executor(None, _inner)
        resolved: List[Track] = []
        for track in tracks:
            title = track.get("name")
            artists = ", ".join(artist["name"] for artist in track.get("artists", []))
            search_term = f"{artists} - {title}" if artists else title
            try:
                youtube_tracks = await self._search_youtube(search_term, requester, source_label="Spotify")
            except ResolverError as error:
                self.logger.warning("Failed to resolve Spotify track '%s': %s", title, error)
                continue
            resolved.extend(youtube_tracks)

        if not resolved:
            raise ResolverError("No playable tracks were found in the Spotify collection.")
        return resolved

    async def _resolve_itunes(self, url: str, requester: discord.abc.User) -> List[Track]:
        """Resolve iTunes/Apple Music URLs by searching on YouTube."""
        if itunespy is None:
            self.logger.info("itunespy is not installed; attempting metadata extraction for Apple Music link.")
            info = await self._extract_metadata(url)
            tracks = self._info_to_tracks(info, requester, source_override="Apple Music")
            if not tracks:
                raise ResolverError(
                    "Failed to resolve Apple Music link. Install itunespy or provide a searchable track query."
                )
            return tracks

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        track_id = query_params.get("i", [None])[0]
        if not track_id and parsed.path:
            parts = [part for part in parsed.path.split("/") if part]
            if parts:
                track_id = parts[-1]

        if not track_id:
            raise ResolverError("Unable to determine the Apple Music track identifier from the URL.")

        def _inner() -> Sequence[Any]:
            return itunespy.lookup(id=track_id)  # type: ignore[call-arg]

        results = await self.loop.run_in_executor(None, _inner)
        if not results:
            raise ResolverError("No results were returned for the provided Apple Music link.")

        item = results[0]
        track_name = getattr(item, "track_name", None) or getattr(item, "collection_name", None)
        artist_name = getattr(item, "artist_name", "")
        search_term = f"{artist_name} - {track_name}" if artist_name else track_name
        if not search_term:
            raise ResolverError("Unable to determine the Apple Music track metadata for searching.")

        return await self._search_youtube(search_term, requester, source_label="Apple Music")


class MusicPlayer:
    """Handle per-guild music playback and queue management."""

    def __init__(self, cog: "MusicCog", guild: discord.Guild, resolver: SourceResolver) -> None:
        self.cog = cog
        self.guild = guild
        self.resolver = resolver
        self.queue: asyncio.Queue[Track] = asyncio.Queue()
        self.next_event = asyncio.Event()
        self.current: Optional[Track] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.channel: Optional[discord.VoiceChannel] = None
        self.volume: float = 0.5
        self.logger = logging.getLogger(f"MusicPlayer[{guild.id}]")
        self.start_time: Optional[float] = None
        self._player_task = self.cog.bot.loop.create_task(self._player_loop())

    @property
    def is_playing(self) -> bool:
        """Return whether audio is currently playing."""
        return bool(self.voice_client and self.voice_client.is_playing())

    async def enqueue(self, track: Track) -> None:
        """Add a track to the queue."""
        await self.queue.put(track)
        self.logger.info("Queued track '%s' for guild %s.", track.title, self.guild.id)

    async def connect(self, channel: discord.VoiceChannel) -> None:
        """Ensure the bot is connected to the provided voice channel."""
        self.channel = channel
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel and self.voice_client.channel.id == channel.id:
                return
            await self.voice_client.move_to(channel)
            return

        self.voice_client = await channel.connect(reconnect=True)
        self.logger.info("Connected to voice channel %s", channel)

    async def disconnect(self) -> None:
        """Disconnect from the voice channel and cancel playback."""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        self.voice_client = None
        self.channel = None
        self.logger.info("Disconnected voice client for guild %s", self.guild.id)

    async def stop(self) -> None:
        """Stop playback and clear the queue."""
        self.clear_queue()
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
        await self.disconnect()
        self.current = None
        self.start_time = None

    def clear_queue(self) -> None:
        """Remove all pending tracks from the queue."""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:  # pragma: no cover - defensive, queue emptiness already checked
                break
        self.logger.debug("Cleared queue for guild %s", self.guild.id)

    async def skip(self) -> None:
        """Skip the currently playing track."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            self.logger.info("Skipped track in guild %s", self.guild.id)

    async def pause(self) -> None:
        """Pause playback."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.logger.info("Paused playback in guild %s", self.guild.id)

    async def resume(self) -> None:
        """Resume playback."""
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.logger.info("Resumed playback in guild %s", self.guild.id)

    def set_volume(self, level: float) -> None:
        """Update playback volume for the guild."""
        self.volume = max(0.0, min(level, 2.0))
        if self.voice_client and self.voice_client.source and isinstance(self.voice_client.source, discord.PCMVolumeTransformer):
            self.voice_client.source.volume = self.volume
        self.logger.info("Volume for guild %s set to %.2f", self.guild.id, self.volume)

    def formatted_queue(self) -> List[str]:
        """Return a formatted representation of the queue."""
        items = list(self.queue._queue)  # pylint: disable=protected-access
        lines = []
        for index, track in enumerate(items, start=1):
            lines.append(f"{index}. {track.title} ({track.duration_display})")
        return lines

    def progress_bar(self, length: int = 18) -> str:
        """Return a textual progress bar for the currently playing track."""
        if not self.current or not self.start_time or self.current.duration <= 0:
            return "[stream]"

        elapsed = time.monotonic() - self.start_time
        fraction = min(max(elapsed / self.current.duration, 0.0), 1.0)
        filled = int(fraction * length)
        bar = "█" * filled + "─" * (length - filled)
        elapsed_display = str(datetime.timedelta(seconds=int(elapsed)))
        duration_display = self.current.duration_display
        return f"{elapsed_display} [{bar}] {duration_display}"

    async def _player_loop(self) -> None:
        """Background task responsible for playing queued tracks."""
        await self.cog.bot.wait_until_ready()
        while not self.cog.bot.is_closed():
            self.next_event.clear()
            try:
                track = await self.queue.get()
            except asyncio.CancelledError:
                break

            self.current = track
            self.logger.info("Starting playback for '%s'", track.title)

            if not await self._ensure_voice_connection():
                self.logger.error("Unable to connect to a voice channel for guild %s", self.guild.id)
                self.queue.task_done()
                self.current = None
                continue

            try:
                playback_reference, data, file_path = await self.resolver.create_playback_source(track)
            except Exception as error:  # noqa: BLE001 - prefer broad handling to notify users gracefully
                self.logger.exception("Failed to prepare playback for '%s': %s", track.title, error)
                self.queue.task_done()
                self.current = None
                await self.cog.send_playback_error(self.guild, track, str(error))
                continue

            if track.duration <= 0 and isinstance(data.get("duration"), (int, float)):
                track.duration = int(data["duration"])

            source = discord.FFmpegPCMAudio(
                playback_reference,
                before_options=FFMPEG_BEFORE_OPTIONS,
                options=FFMPEG_OPTIONS,
            )
            transformed = discord.PCMVolumeTransformer(source, volume=self.volume)
            cleanup_path = file_path if file_path and not self.resolver.cache_enabled else None

            def _after_playback(exception: Optional[Exception]) -> None:
                if exception:
                    self.logger.error("Error during playback: %s", exception)
                self.cog.bot.loop.call_soon_threadsafe(self.next_event.set)

            if self.voice_client is None:
                self.logger.error("Voice client missing just before playback, skipping track.")
                self.queue.task_done()
                continue

            self.voice_client.play(transformed, after=_after_playback)
            self.start_time = time.monotonic()
            await self.next_event.wait()
            self.queue.task_done()
            self.start_time = None
            self.current = None

            if cleanup_path and cleanup_path.exists():
                try:
                    cleanup_path.unlink(missing_ok=True)
                except OSError:
                    self.logger.warning("Failed to remove temporary file %s", cleanup_path)

    async def _ensure_voice_connection(self) -> bool:
        """Ensure that a voice connection exists for playback."""
        if self.voice_client and self.voice_client.is_connected():
            return True

        if not self.channel:
            return False

        try:
            self.voice_client = await self.channel.connect(reconnect=True)
            return True
        except Exception as error:  # noqa: BLE001 - ensure reconnection attempts do not crash the bot
            self.logger.error("Failed to reconnect voice client: %s", error)
            return False

    def cleanup(self) -> None:
        """Cancel the background task and cleanup resources."""
        if self._player_task:
            self._player_task.cancel()
        if self.voice_client and self.voice_client.is_connected():
            self.cog.bot.loop.create_task(self.voice_client.disconnect())


class MusicCog(commands.Cog):
    """Cog responsible for music-related slash commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        cache_dir = getattr(self.bot, "cache_directory", None)
        self.logger = logging.getLogger("MusicCog")
        self.resolver = SourceResolver(loop=bot.loop, cache_dir=cache_dir, logger=self.logger)
        self.players: Dict[int, MusicPlayer] = {}

    def cog_unload(self) -> None:
        """Cleanup when the cog is unloaded."""
        for player in self.players.values():
            player.cleanup()

    def get_player(self, guild: discord.Guild) -> MusicPlayer:
        """Retrieve the guild-specific player, creating it if required."""
        if guild.id not in self.players:
            self.players[guild.id] = MusicPlayer(self, guild, self.resolver)
        return self.players[guild.id]

    async def send_playback_error(self, guild: discord.Guild, track: Track, message: str) -> None:
        """Send an error notification to the system channel if available."""
        system_channel = guild.system_channel
        if not system_channel:
            self.logger.warning("Unable to deliver playback error for guild %s: %s", guild.id, message)
            return
        try:
            await system_channel.send(f"Playback error for **{track.title}**: {message}")
        except discord.HTTPException:
            self.logger.warning("Failed to send playback error message to guild %s", guild.id)

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command can only be used within a server.", ephemeral=True)
            return None
        member = interaction.user
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message("You must join a voice channel first.", ephemeral=True)
            return None
        return member.voice.channel

    @app_commands.command(name="play", description="Play or queue audio from a URL or search query")
    @app_commands.describe(query="URL or search query to play")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        """Handle the /play command."""
        voice_channel = await self._ensure_voice(interaction)
        if voice_channel is None:
            return

        await interaction.response.defer()
        assert interaction.guild is not None  # nosec: ensured by _ensure_voice
        player = self.get_player(interaction.guild)

        try:
            await player.connect(voice_channel)
        except discord.Forbidden:
            await interaction.followup.send("I do not have permission to join that voice channel.", ephemeral=True)
            return
        except discord.HTTPException as error:
            self.logger.exception("Failed to connect to voice channel: %s", error)
            await interaction.followup.send("Failed to connect to the voice channel.", ephemeral=True)
            return
        except discord.ClientException as error:
            self.logger.exception("Client exception during voice connection: %s", error)
            await interaction.followup.send("Unable to join that voice channel.", ephemeral=True)
            return

        try:
            tracks = await self.resolver.resolve(query, requester=interaction.user)
        except ResolverError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        except Exception as error:  # noqa: BLE001 - ensure user feedback on unexpected errors
            self.logger.exception("Unexpected error resolving query '%s': %s", query, error)
            await interaction.followup.send("Failed to resolve that audio source.", ephemeral=True)
            return

        for track in tracks:
            await player.enqueue(track)

        if len(tracks) == 1:
            embed = self._build_track_embed(tracks[0], title="Track queued")
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title="Playlist queued", colour=discord.Colour.blurple())
            embed.description = "\n".join(track.label for track in tracks[:10])
            if len(tracks) > 10:
                embed.description += f"\n…and {len(tracks) - 10} more"
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="pause", description="Pause the current playback")
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause playback for the guild."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue for this server.", ephemeral=True)
            return
        await player.pause()
        await interaction.followup.send("Playback paused.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume paused playback")
    async def resume(self, interaction: discord.Interaction) -> None:
        """Resume playback for the guild."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue for this server.", ephemeral=True)
            return
        await player.resume()
        await interaction.followup.send("Playback resumed.", ephemeral=True)

    @app_commands.command(name="skip", description="Skip to the next track in the queue")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip the currently playing track."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue to skip.", ephemeral=True)
            return
        await player.skip()
        await interaction.followup.send("Skipped the current track.", ephemeral=True)

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop playback entirely and clear the queue."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue to stop.", ephemeral=True)
            return
        await player.stop()
        await interaction.followup.send("Playback stopped and queue cleared.", ephemeral=True)

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction) -> None:
        """Display the current queue."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue for this server.", ephemeral=True)
            return

        lines = player.formatted_queue()
        if not lines:
            await interaction.followup.send("The queue is currently empty.", ephemeral=True)
            return

        description = "\n".join(lines[:10])
        embed = discord.Embed(title="Current Queue", description=description, colour=discord.Colour.purple())
        if len(lines) > 10:
            embed.set_footer(text=f"…and {len(lines) - 10} more tracks queued")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="volume", description="Set the playback volume (0-100)")
    @app_commands.describe(level="Volume level between 0 and 100")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]) -> None:
        """Adjust playback volume."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue for this server.", ephemeral=True)
            return
        player.set_volume(level / 100)
        await interaction.followup.send(f"Volume set to {level}%.", ephemeral=True)

    @app_commands.command(name="nowplaying", description="Show the currently playing track")
    async def now_playing(self, interaction: discord.Interaction) -> None:
        """Display information about the currently playing track."""
        await interaction.response.defer(ephemeral=True)
        player = self._require_player(interaction)
        if not player:
            await interaction.followup.send("There is no active queue for this server.", ephemeral=True)
            return
        if not player.current:
            await interaction.followup.send("Nothing is currently playing.", ephemeral=True)
            return

        embed = self._build_track_embed(player.current, title="Now Playing")
        embed.add_field(name="Progress", value=player.progress_bar(), inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    def _require_player(self, interaction: discord.Interaction) -> Optional[MusicPlayer]:
        if not interaction.guild:
            return None
        guild_id = interaction.guild.id
        if guild_id not in self.players:
            self.logger.debug("Player requested for guild %s but no queue exists.", guild_id)
            return None
        return self.players[guild_id]

    def _build_track_embed(self, track: Track, *, title: str) -> discord.Embed:
        embed = discord.Embed(title=title, description=f"[{track.title}]({track.webpage_url})", colour=discord.Colour.green())
        embed.add_field(name="Source", value=track.source, inline=True)
        embed.add_field(name="Duration", value=track.duration_display, inline=True)
        if track.author:
            embed.add_field(name="Artist", value=track.author, inline=True)
        embed.set_footer(text=f"Requested by {track.requester.display_name if isinstance(track.requester, discord.Member) else track.requester.name}")
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        return embed


async def setup(bot: commands.Bot) -> None:
    """Setup function required by discord.py to load the cog."""
    await bot.add_cog(MusicCog(bot))
