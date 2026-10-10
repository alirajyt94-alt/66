import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    LAVALINK_HOST = os.getenv("LAVALINK_HOST", "127.0.0.1")
    LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 2333))
    LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")