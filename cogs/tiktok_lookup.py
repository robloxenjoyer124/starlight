import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

class TikTokLookup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    tiktok_group = app_commands.Group(name="tiktok", description="TikTok account lookup commands")

    def extract_username(self, username_or_url: str) -> Optional[str]:
        username_or_url = username_or_url.strip()
        
        url_pattern = r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]+)'
        match = re.search(url_pattern, username_or_url)
        if match:
            return match.group(1)
        
        username_pattern = r'^@?([a-zA-Z0-9_.]+)$'
        match = re.match(username_pattern, username_or_url)
        if match:
            return match.group(1)
        
        return None

    @tiktok_group.command(name="country", description="Look up TikTok account location information")
    @app_commands.describe(username_or_url="TikTok username or profile URL")
    async def tiktok_country(self, interaction: discord.Interaction, username_or_url: str):
        await interaction.response.defer()

        username = self.extract_username(username_or_url)
        if not username:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description="Please provide a valid TikTok username or URL.\n\nExamples:\n- `@username`\n- `username`\n- `https://tiktok.com/@username`",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
                url = f"https://www.tiktok.com/@{username}"
                
                async with session.get(url, headers=headers, allow_redirects=True) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        user_info = self.parse_tiktok_data(html, username)
                        
                        if user_info:
                            embed = self.create_tiktok_embed(user_info, username)
                            await interaction.followup.send(embed=embed)
                        else:
                            embed = discord.Embed(
                                title="⚠️ Limited Information",
                                description=f"Found TikTok profile `@{username}` but unable to extract location data.\n\nThis could be because:\n- The user hasn't set their location publicly\n- TikTok's page structure has changed\n- The profile is private",
                                color=discord.Color.orange()
                            )
                            embed.add_field(
                                name="Profile URL",
                                value=f"https://www.tiktok.com/@{username}",
                                inline=False
                            )
                            await interaction.followup.send(embed=embed)
                    elif response.status == 404:
                        embed = discord.Embed(
                            title="❌ Account Not Found",
                            description=f"TikTok account `@{username}` does not exist or has been deleted.",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed)
                    else:
                        logger.error(f"TikTok lookup error: {response.status}")
                        embed = discord.Embed(
                            title="❌ Lookup Failed",
                            description=f"Unable to fetch TikTok profile. Status code: {response.status}",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error(f"Network error during TikTok lookup: {e}")
            embed = discord.Embed(
                title="❌ Network Error",
                description="Failed to connect to TikTok. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Unexpected error during TikTok lookup: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    def parse_tiktok_data(self, html: str, username: str) -> Optional[dict]:
        info = {'username': username}
        
        try:
            import json
            
            schema_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
            matches = re.findall(schema_pattern, html, re.DOTALL)
            
            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict):
                        if 'author' in data and isinstance(data['author'], dict):
                            author = data['author']
                            if 'name' in author:
                                info['name'] = author['name']
                        
                        if 'contentLocation' in data:
                            location = data['contentLocation']
                            if isinstance(location, dict) and 'name' in location:
                                info['location'] = location['name']
                            elif isinstance(location, str):
                                info['location'] = location
                except json.JSONDecodeError:
                    continue
            
            seo_pattern = r'"subTitle":"([^"]*?)"'
            seo_matches = re.findall(seo_pattern, html)
            if seo_matches and not info.get('name'):
                info['name'] = seo_matches[0].replace('\\u0040', '@')
            
            country_pattern = r'"country":"([^"]*?)"'
            country_matches = re.findall(country_pattern, html)
            if country_matches:
                info['country'] = country_matches[0]
            
            region_pattern = r'"region":"([^"]*?)"'
            region_matches = re.findall(region_pattern, html)
            if region_matches:
                info['region'] = region_matches[0]
            
            if len(info) > 1:
                return info
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing TikTok data: {e}")
            return None

    def create_tiktok_embed(self, user_info: dict, username: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎵 TikTok Account: @{username}",
            url=f"https://www.tiktok.com/@{username}",
            color=discord.Color.from_rgb(255, 0, 80)
        )

        if 'name' in user_info:
            embed.add_field(name="Display Name", value=user_info['name'], inline=True)
        
        if 'country' in user_info:
            embed.add_field(name="Country", value=user_info['country'], inline=True)
        
        if 'region' in user_info:
            embed.add_field(name="Region", value=user_info['region'], inline=True)
        
        if 'location' in user_info:
            embed.add_field(name="Location", value=user_info['location'], inline=False)

        if len(embed.fields) == 0:
            embed.add_field(
                name="Status",
                value="Profile found but no location data available",
                inline=False
            )

        embed.set_footer(text="Location data may not always be available or accurate")
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(TikTokLookup(bot))
