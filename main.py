import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "127.0.0.1")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")

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
# IMPORT RAVELINK (with graceful failure)
# ============================================================
try:
    import ravelink
except ImportError:
    logger.critical("Ravelink is not installed. Run: pip install Ravelink[voice]")
    sys.exit(1)


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
        # Connect to Lavalink node pool
        node = ravelink.Node(
            uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}",
            password=LAVALINK_PASSWORD,
        )
        try:
            await ravelink.Pool.connect(nodes=[node], client=self, cache_capacity=512)
            logger.info(f"Connected to Lavalink at {LAVALINK_HOST}:{LAVALINK_PORT}")
        except Exception as e:
            logger.critical(f"Failed to connect to Lavalink: {e}")
            sys.exit(1)

        # Sync slash commands
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


# ============================================================
# INITIALIZE BOT
# ============================================================
bot = MusicBot()


# ============================================================
# SLASH COMMANDS
# ============================================================
@bot.tree.command(name="play", description="Play a song from YouTube, Spotify, or SoundCloud")
@app_commands.describe(search="Song name or URL")
async def play(interaction: discord.Interaction, search: str):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            "You must be in a voice channel.", ephemeral=True
        )

    player: ravelink.Player = (
        interaction.guild.voice_client
        or await interaction.user.voice.channel.connect(cls=ravelink.Player)
    )

    results = await ravelink.Playable.search(search)
    if not results:
        return await interaction.response.send_message("No results found.", ephemeral=True)

    if isinstance(results, ravelink.Playlist):
        for track in results.tracks:
            player.queue.put(track)
        await interaction.response.send_message(
            f"Added playlist **{results.name}** ({len(results.tracks)} tracks) to queue."
        )
    else:
        track = results[0]
        if not player.playing:
            await player.play(track)
            await interaction.response.send_message(f"Now playing: **{track.title}**")
        else:
            player.queue.put(track)
            await interaction.response.send_message(f"Queued: **{track.title}**")


@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    player: ravelink.Player = interaction.guild.voice_client
    if not player or not player.playing:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
    await player.skip(force=True)
    await interaction.response.send_message("Skipped.")


@bot.tree.command(name="pause", description="Pause playback")
async def pause(interaction: discord.Interaction):
    player: ravelink.Player = interaction.guild.voice_client
    if not player or not player.playing:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
    await player.pause(True)
    await interaction.response.send_message("Paused.")


@bot.tree.command(name="resume", description="Resume playback")
async def resume(interaction: discord.Interaction):
    player: ravelink.Player = interaction.guild.voice_client
    if not player or not player.playing:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
    await player.pause(False)
    await interaction.response.send_message("Resumed.")


@bot.tree.command(name="queue", description="Show the current queue")
async def queue(interaction: discord.Interaction):
    player: ravelink.Player = interaction.guild.voice_client
    if not player or not player.playing:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    current = player.current
    upcoming = list(player.queue)[:10]

    embed = discord.Embed(
        title="Queue",
        description=f"**Now Playing:** {current.title}",
        color=discord.Color.blurple(),
    )
    if upcoming:
        lines = [f"`{i+1}.` {t.title}" for i, t in enumerate(upcoming)]
        embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Up Next", value="Queue is empty", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="autoplay", description="Toggle autoplay (radio mode)")
async def autoplay(interaction: discord.Interaction):
    player: ravelink.Player = interaction.guild.voice_client
    if not player:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    enabled = not player.autoplay
    await player.set_autoplay(enabled)
    state = "enabled" if enabled else "disabled"
    await interaction.response.send_message(f"Autoplay {state}.")


@bot.tree.command(name="filters", description="Apply audio filters")
@app_commands.choices(preset=[
    app_commands.Choice(name="Bassboost", value="bassboost"),
    app_commands.Choice(name="Nightcore", value="nightcore"),
    app_commands.Choice(name="8D Audio", value="eightd"),
    app_commands.Choice(name="None (reset)", value="none"),
])
async def filters(interaction: discord.Interaction, preset: app_commands.Choice[str]):
    player: ravelink.Player = interaction.guild.voice_client
    if not player:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    await player.filters.clear()
    if preset.value == "bassboost":
        await player.filters.set_bassboost()
    elif preset.value == "nightcore":
        await player.filters.set_timescale(speed=1.3, pitch=1.3)
    elif preset.value == "eightd":
        await player.filters.set_rotation(rotation_hz=0.2)
    await interaction.response.send_message(f"Filter: **{preset.name}** applied.")


@bot.tree.command(name="stop", description="Stop playback and disconnect")
async def stop(interaction: discord.Interaction):
    player: ravelink.Player = interaction.guild.voice_client
    if not player:
        return await interaction.response.send_message("Not connected.", ephemeral=True)
    await player.disconnect()
    await interaction.response.send_message("Stopped and disconnected.")


# ============================================================
# ENTRY POINT
# ============================================================
async def main():
    if not DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN is missing. Set it in Railway variables or .env.")
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