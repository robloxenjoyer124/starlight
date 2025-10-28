import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import logging

from cogs.ip_lookup import IPLookup
from cogs.tiktok_lookup import TikTokLookup
from cogs.website_lookup import WebsiteLookup

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.add_cog(IPLookup(self))
        await self.add_cog(TikTokLookup(self))
        await self.add_cog(WebsiteLookup(self))
        
        logger.info("Syncing commands...")
        await self.tree.sync()
        logger.info("Commands synced successfully")

    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')

def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found in environment variables")
        return

    bot = DataBot()
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
