import discord
from discord.ext import commands
from discord import app_commands
import ravelink
from config import Config

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Connect to Lavalink with health-scored node pooling."""
        node = ravelink.Node(
            uri=f"http://{Config.LAVALINK_HOST}:{Config.LAVALINK_PORT}",
            password=Config.LAVALINK_PASSWORD,
        )
        await ravelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=512)
        print("Ravelink node pool connected.")

    @app_commands.command(name="play", description="Play a song from YouTube, Spotify, or SoundCloud")
    @app_commands.describe(search="Song name or URL")
    async def play(self, interaction: discord.Interaction, search: str):
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

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        player: ravelink.Player = interaction.guild.voice_client
        if not player or not player.playing:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
        await player.skip(force=True)
        await interaction.response.send_message("Skipped.")

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        player: ravelink.Player = interaction.guild.voice_client
        if not player or not player.playing:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
        await player.pause(True)
        await interaction.response.send_message("Paused.")

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        player: ravelink.Player = interaction.guild.voice_client
        if not player or not player.playing:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
        await player.pause(False)
        await interaction.response.send_message("Resumed.")

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
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

    @app_commands.command(name="autoplay", description="Toggle autoplay (radio mode)")
    async def autoplay(self, interaction: discord.Interaction):
        player: ravelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message("Nothing is playing.", ephemeral=True)

        enabled = not player.autoplay
        await player.set_autoplay(enabled)
        state = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"Autoplay {state}.")

    @app_commands.command(name="filters", description="Apply audio filters")
    @app_commands.choices(preset=[
        app_commands.Choice(name="Bassboost", value="bassboost"),
        app_commands.Choice(name="Nightcore", value="nightcore"),
        app_commands.Choice(name="8D Audio", value="eightd"),
        app_commands.Choice(name="None (reset)", value="none"),
    ])
    async def filters(self, interaction: discord.Interaction, preset: app_commands.Choice[str]):
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

    @app_commands.command(name="stop", description="Stop playback and disconnect")
    async def stop(self, interaction: discord.Interaction):
        player: ravelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message("Not connected.", ephemeral=True)
        await player.disconnect()
        await interaction.response.send_message("Stopped and disconnected.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))