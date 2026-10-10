import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import sys
import logging
import random
import re
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "127.0.0.1")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
LAVALINK_SECURE = os.getenv("LAVALINK_SECURE", "false").lower() == "true"

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MusicBot")

# ============================================================
# IMPORT RAVELINK
# ============================================================
try:
    import ravelink
except ImportError:
    logger.critical("Ravelink is not installed. Run: pip install Ravelink[voice]")
    sys.exit(1)

# ============================================================
# PROFESSIONAL COLOR PALETTE
# ============================================================
COLORS = {
    "primary": 0x5865F2,      # Discord Blurple
    "success": 0x57F287,      # Green
    "warning": 0xFEE75C,      # Yellow
    "error": 0xED4245,        # Red
    "music": 0x9B59B6,        # Purple (music theme)
    "info": 0x3498DB,         # Blue
    "queue": 0xE67E22,        # Orange
    "lyrics": 0x1ABC9C,       # Teal
}


# ============================================================
# DASHBOARD UI VIEW
# ============================================================
class DashboardView(discord.ui.View):
    """Interactive playback controls attached to the Now Playing embed."""

    def __init__(self, player: ravelink.Player, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.player = player
        self.update_buttons()

    def update_buttons(self):
        """Sync button states with the current player state."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "dash_pause":
                    child.label = "Resume" if self.player.paused else "Pause"
                    child.style = (
                        discord.ButtonStyle.success
                        if self.player.paused
                        else discord.ButtonStyle.primary
                    )
                elif child.custom_id == "dash_loop":
                    modes = ["Off", "Track", "Queue"]
                    child.label = f"Loop: {modes[self.player.loop]}"
                    child.style = (
                        discord.ButtonStyle.success
                        if self.player.loop
                        else discord.ButtonStyle.secondary
                    )
                elif child.custom_id == "dash_autoplay":
                    child.label = f"Autoplay: {'On' if self.player.autoplay else 'Off'}"
                    child.style = (
                        discord.ButtonStyle.success
                        if self.player.autoplay
                        else discord.ButtonStyle.secondary
                    )

    async def on_timeout(self):
        """Disable buttons when the view times out."""
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.primary, custom_id="dash_pause")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.send_message("Player disconnected.", ephemeral=True)
        await self.player.pause(not self.player.paused)
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary, custom_id="dash_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.send_message("Player disconnected.", ephemeral=True)
        await self.player.skip(force=True)
        await interaction.response.send_message("Skipped.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="dash_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.send_message("Player disconnected.", ephemeral=True)
        await self.player.disconnect()
        self.stop()
        await interaction.response.send_message("Stopped and disconnected.", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="dash_loop")
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.send_message("Player disconnected.", ephemeral=True)
        await self.player.set_loop((self.player.loop + 1) % 3)
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🎲", style=discord.ButtonStyle.secondary, custom_id="dash_autoplay")
    async def autoplay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player:
            return await interaction.response.send_message("Player disconnected.", ephemeral=True)
        await self.player.set_autoplay(not self.player.autoplay)
        self.update_buttons()
        await interaction.response.edit_message(view=self)


# ============================================================
# BOT CLASS
# ============================================================
class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        scheme = "https" if LAVALINK_SECURE else "http"
        node = ravelink.Node(
            uri=f"{scheme}://{LAVALINK_HOST}:{LAVALINK_PORT}",
            password=LAVALINK_PASSWORD,
        )
        try:
            await ravelink.Pool.connect(nodes=[node], client=self, cache_capacity=512)
            logger.info(f"Connected to Lavalink at {scheme}://{LAVALINK_HOST}:{LAVALINK_PORT}")
        except Exception as e:
            logger.critical(f"Failed to connect to Lavalink: {e}")
            sys.exit(1)

        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands.")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s).")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="/play"
            )
        )

    async def on_voice_state_update(self, member, before, after):
        """Auto-disconnect when the bot is left alone in a voice channel."""
        if member.id == self.user.id:
            return
        if before.channel and not after.channel:
            vc = member.guild.voice_client
            if vc and vc.channel:
                if len(vc.channel.members) == 1 and vc.channel.members[0].id == self.user.id:
                    await vc.disconnect()
                    logger.info(f"Left empty voice channel in {member.guild.name}")


bot = MusicBot()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
async def _get_player(interaction: discord.Interaction, connect: bool = False):
    """Return the guild's player, optionally connecting to the user's VC."""
    player: ravelink.Player = interaction.guild.voice_client

    if player is None and connect:
        if not interaction.user.voice:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="❌ You must be in a voice channel first.",
                    color=COLORS["error"],
                ),
                ephemeral=True,
            )
            return None
        player = await interaction.user.voice.channel.connect(cls=ravelink.Player)

    if player is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                description="❌ Nothing is playing right now.",
                color=COLORS["error"],
            ),
            ephemeral=True,
        )
    return player


def _format_duration(ms: int) -> str:
    """Convert milliseconds to a readable time string."""
    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _now_playing_embed(player: ravelink.Player) -> discord.Embed:
    """Build the Dashboard UI Now Playing embed."""
    track = player.current
    if not track:
        return discord.Embed(description="Nothing playing.", color=COLORS["error"])

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"**[{track.title}]({track.uri})**",
        color=COLORS["music"],
    )
    embed.add_field(name="Artist", value=track.author or "Unknown", inline=True)
    embed.add_field(name="Duration", value=_format_duration(track.length), inline=True)
    embed.add_field(
        name="Status",
        value="▶️ Playing" if not player.paused else "⏸️ Paused",
        inline=True,
    )
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    embed.set_footer(text=f"Requested by {getattr(track, 'requester', 'Unknown')}")
    return embed


# ============================================================
# SLASH COMMANDS
# ============================================================
@bot.tree.command(name="play", description="Play a song from YouTube, Spotify, or SoundCloud")
@app_commands.describe(search="Song name or URL")
async def play(interaction: discord.Interaction, search: str):
    player = await _get_player(interaction, connect=True)
    if not player:
        return

    await interaction.response.defer()

    try:
        results = await ravelink.Playable.search(search)
    except Exception as e:
        logger.error(f"Search failed for '{search}': {e}")
        return await interaction.followup.send(
            embed=discord.Embed(
                description="❌ Search failed. The audio node may be unavailable.",
                color=COLORS["error"],
            )
        )

    if not results:
        return await interaction.followup.send(
            embed=discord.Embed(
                description="❌ No results found.",
                color=COLORS["error"],
            )
        )

    if isinstance(results, ravelink.Playlist):
        for track in results.tracks:
            player.queue.put(track)
        await interaction.followup.send(
            embed=discord.Embed(
                title="📋 Playlist Added",
                description=f"Added **{results.name}** ({len(results.tracks)} tracks) to the queue.",
                color=COLORS["success"],
            )
        )
    else:
        track = results[0]
        track.requester = interaction.user
        if not player.playing:
            await player.play(track)
            embed = _now_playing_embed(player)
            view = DashboardView(player)
            msg = await interaction.followup.send(embed=embed, view=view)
            view.message = msg
        else:
            player.queue.put(track)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="✅ Added to Queue",
                    description=f"**{track.title}**",
                    color=COLORS["success"],
                )
            )


@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player:
        return
    await player.skip(force=True)
    await interaction.response.send_message(
        embed=discord.Embed(description="⏭️ Skipped.", color=COLORS["primary"])
    )


@bot.tree.command(name="pause", description="Pause playback")
async def pause(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player:
        return
    if player.paused:
        return await interaction.response.send_message(
            embed=discord.Embed(description="⏸️ Already paused.", color=COLORS["warning"]),
            ephemeral=True,
        )
    await player.pause(True)
    await interaction.response.send_message(
        embed=discord.Embed(description="⏸️ Paused.", color=COLORS["success"])
    )


@bot.tree.command(name="resume", description="Resume playback")
async def resume(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player:
        return
    if not player.paused:
        return await interaction.response.send_message(
            embed=discord.Embed(description="▶️ Already playing.", color=COLORS["warning"]),
            ephemeral=True,
        )
    await player.pause(False)
    await interaction.response.send_message(
        embed=discord.Embed(description="▶️ Resumed.", color=COLORS["success"])
    )


@bot.tree.command(name="queue", description="Show the current queue")
async def queue(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player or not player.playing:
        return

    current = player.current
    upcoming = list(player.queue)[:10]

    embed = discord.Embed(
        title="📋 Music Queue",
        description=f"**Now Playing:** [{current.title}]({current.uri})",
        color=COLORS["queue"],
    )
    if upcoming:
        lines = [f"`{i+1}.` {t.title} — {_format_duration(t.length)}" for i, t in enumerate(upcoming)]
        embed.add_field(name=f"Up Next ({len(player.queue)} tracks)", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Up Next", value="Queue is empty.", inline=False)

    embed.set_footer(text=f"Total tracks in queue: {len(player.queue)}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="nowplaying", description="Show the currently playing track")
async def nowplaying(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player or not player.playing:
        return
    embed = _now_playing_embed(player)
    view = DashboardView(player)
    msg = await interaction.response.send_message(embed=embed, view=view)
    view.message = msg


@bot.tree.command(name="volume", description="Set the player volume (0-200)")
@app_commands.describe(level="Volume level from 0 to 200")
async def volume(interaction: discord.Interaction, level: app_commands.Range[int, 0, 200]):
    player = await _get_player(interaction)
    if not player:
        return
    await player.set_volume(level)
    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"🔊 Volume set to **{level}%**.",
            color=COLORS["info"],
        )
    )


@bot.tree.command(name="seek", description="Seek to a specific time in the current track")
@app_commands.describe(time="Time to seek to (e.g., 1:30 or 90)")
async def seek(interaction: discord.Interaction, time: str):
    player = await _get_player(interaction)
    if not player or not player.playing:
        return

    pattern = re.compile(r"^(\d{1,2}:)?\d{1,2}:\d{2}$|^\d+$")
    if not pattern.match(time):
        return await interaction.response.send_message(
            embed=discord.Embed(
                description="❌ Invalid time format. Use `1:30` or `90`.",
                color=COLORS["error"],
            ),
            ephemeral=True,
        )

    if ":" in time:
        parts = time.split(":")
        ms = (int(parts[0]) * 60 + int(parts[1])) * 1000
    else:
        ms = int(time) * 1000

    await player.seek(ms)
    await interaction.response.send_message(
        embed=discord.Embed(description=f"⏩ Seeked to **{time}**.", color=COLORS["success"])
    )


@bot.tree.command(name="shuffle", description="Shuffle the current queue")
async def shuffle(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player or not player.queue:
        return await interaction.response.send_message(
            embed=discord.Embed(description="❌ The queue is empty.", color=COLORS["error"]),
            ephemeral=True,
        )

    queue_list = list(player.queue)
    random.shuffle(queue_list)
    player.queue.clear()
    for track in queue_list:
        player.queue.put(track)

    await interaction.response.send_message(
        embed=discord.Embed(description="🔀 Queue shuffled.", color=COLORS["success"])
    )


@bot.tree.command(name="loop", description="Toggle loop mode (Off / Track / Queue)")
async def loop(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player:
        return
    await player.set_loop((player.loop + 1) % 3)
    modes = ["Off", "Track", "Queue"]
    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"🔁 Loop mode: **{modes[player.loop]}**.",
            color=COLORS["info"],
        )
    )


@bot.tree.command(name="autoplay", description="Toggle autoplay (radio mode)")
async def autoplay(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player:
        return
    await player.set_autoplay(not player.autoplay)
    state = "enabled" if player.autoplay else "disabled"
    await interaction.response.send_message(
        embed=discord.Embed(description=f"🎲 Autoplay **{state}**.", color=COLORS["info"])
    )


@bot.tree.command(name="filters", description="Apply an audio filter")
@app_commands.choices(preset=[
    app_commands.Choice(name="Bassboost", value="bassboost"),
    app_commands.Choice(name="Nightcore", value="nightcore"),
    app_commands.Choice(name="8D Audio", value="eightd"),
    app_commands.Choice(name="Vaporwave", value="vaporwave"),
    app_commands.Choice(name="None (reset)", value="none"),
])
async def filters(interaction: discord.Interaction, preset: app_commands.Choice[str]):
    player = await _get_player(interaction)
    if not player:
        return

    await player.filters.clear()
    if preset.value == "bassboost":
        await player.filters.set_bassboost()
    elif preset.value == "nightcore":
        await player.filters.set_timescale(speed=1.3, pitch=1.3)
    elif preset.value == "eightd":
        await player.filters.set_rotation(rotation_hz=0.2)
    elif preset.value == "vaporwave":
        await player.filters.set_timescale(speed=0.8, pitch=0.8)

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"🎛️ Filter applied: **{preset.name}**.",
            color=COLORS["music"],
        )
    )


@bot.tree.command(name="lyrics", description="Fetch lyrics for the current track")
async def lyrics(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player or not player.playing:
        return

    await interaction.response.defer()

    try:
        lyrics_data = await player.current_lyrics()
    except Exception as e:
        logger.error(f"Lyrics fetch failed: {e}")
        return await interaction.followup.send(
            embed=discord.Embed(
                description="❌ Lyrics not found for this track.",
                color=COLORS["error"],
            )
        )

    if not lyrics_data or not lyrics_data.text:
        return await interaction.followup.send(
            embed=discord.Embed(
                description="❌ No lyrics available for this track.",
                color=COLORS["error"],
            )
        )

    text = lyrics_data.text[:4000]
    embed = discord.Embed(
        title=f"📜 Lyrics — {player.current.title}",
        description=text,
        color=COLORS["lyrics"],
    )
    embed.set_footer(text=f"Source: {getattr(lyrics_data, 'sourceName', 'Unknown')}")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="stop", description="Stop playback and disconnect")
async def stop(interaction: discord.Interaction):
    player = await _get_player(interaction)
    if not player:
        return
    await player.disconnect()
    await interaction.response.send_message(
        embed=discord.Embed(description="⏹️ Stopped and disconnected.", color=COLORS["primary"])
    )


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎵 Music Bot — Command Reference",
        description="A professional Lavalink-powered music bot.",
        color=COLORS["primary"],
    )
    embed.add_field(
        name="🎶 Playback",
        value="`/play` — Play a song\n`/skip` — Skip current\n`/pause` — Pause\n`/resume` — Resume\n`/stop` — Stop & disconnect",
        inline=False,
    )
    embed.add_field(
        name="📋 Queue",
        value="`/queue` — Show queue\n`/shuffle` — Shuffle queue\n`/loop` — Toggle loop\n`/nowplaying` — Show current track",
        inline=False,
    )
    embed.add_field(
        name="🎛️ Controls",
        value="`/volume` — Set volume\n`/seek` — Seek to time\n`/autoplay` — Toggle radio mode\n`/filters` — Apply audio filter\n`/lyrics` — Fetch lyrics",
        inline=False,
    )
    embed.set_footer(text="Use the Dashboard buttons on the Now Playing embed for quick control.")
    await interaction.response.send_message(embed=embed)


# ============================================================
# ENTRY POINT
# ============================================================
async def main():
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN is missing.")
        sys.exit(1)

    async with bot:
        try:
            await bot.start(DISCORD_TOKEN)
        except discord.LoginFailure:
            logger.critical("Invalid Discord token.")
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)