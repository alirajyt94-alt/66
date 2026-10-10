import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
from config import Config

# Configure professional logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MusicBot")


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Force working directory to the folder containing bot.py
        base_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(base_dir)
        logger.info(f"Working directory set to: {base_dir}")

        # Verify music.py exists
        music_path = os.path.join(base_dir, "music.py")
        if not os.path.isfile(music_path):
            logger.critical(f"music.py not found at {music_path}. Aborting.")
            sys.exit(1)

        # Load music.py as a top-level extension
        try:
            await self.load_extension("music")
            logger.info("Loaded extension: music")
        except Exception as e:
            logger.critical(f"Failed to load music.py: {e}")
            sys.exit(1)

        # Sync slash commands globally
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

    async def on_command_error(self, ctx, error):
        logger.error(f"Command error: {error}")


async def main():
    if not Config.DISCORD_TOKEN:
        logger.critical("DISCORD_TOKEN is missing. Check your Railway variables.")
        sys.exit(1)

    async with MusicBot() as bot:
        try:
            await bot.start(Config.DISCORD_TOKEN)
        except discord.LoginFailure:
            logger.critical("Invalid Discord token. Please check your credentials.")
            sys.exit(1)
        except KeyboardInterrupt:
            logger.info("Shutdown requested. Closing bot...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
