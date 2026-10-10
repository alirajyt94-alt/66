import discord
from discord.ext import commands
import asyncio
from config import Config

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)

    import os

async def setup_hook(self):
    # Force working directory to the folder containing bot.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    await self.load_extension("cogs.music")
    await self.tree.sync()
        print("Slash commands synced.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="/play")
        )

async def main():
    async with MusicBot() as bot:
        await bot.start(Config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
