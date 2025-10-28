import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class IPLookup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv('IPINFO_API_KEY')
        if not self.api_key:
            logger.warning("IPINFO_API_KEY not found in environment variables")

    ip_group = app_commands.Group(name="ip", description="IP address lookup commands")

    @ip_group.command(name="lookup", description="Look up information about an IP address")
    @app_commands.describe(ip_address="The IP address to lookup")
    async def ip_lookup(self, interaction: discord.Interaction, ip_address: str):
        await interaction.response.defer()

        if not self.api_key:
            embed = discord.Embed(
                title="❌ Configuration Error",
                description="IPInfo API key is not configured. Please contact the bot administrator.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://ipinfo.io/{ip_address}"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        embed = self.create_ip_embed(data, ip_address)
                        await interaction.followup.send(embed=embed)
                    elif response.status == 404:
                        embed = discord.Embed(
                            title="❌ Invalid IP Address",
                            description=f"The IP address `{ip_address}` is not valid or not found.",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed)
                    elif response.status == 429:
                        embed = discord.Embed(
                            title="❌ Rate Limit Exceeded",
                            description="Too many requests. Please try again later.",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed)
                    else:
                        error_text = await response.text()
                        logger.error(f"IPInfo API error: {response.status} - {error_text}")
                        embed = discord.Embed(
                            title="❌ API Error",
                            description=f"Failed to fetch IP information. Status code: {response.status}",
                            color=discord.Color.red()
                        )
                        await interaction.followup.send(embed=embed)

        except aiohttp.ClientError as e:
            logger.error(f"Network error during IP lookup: {e}")
            embed = discord.Embed(
                title="❌ Network Error",
                description="Failed to connect to the IP lookup service. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Unexpected error during IP lookup: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    def create_ip_embed(self, data: dict, ip_address: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🌐 IP Information: {ip_address}",
            color=discord.Color.blue()
        )

        if 'ip' in data:
            embed.add_field(name="IP Address", value=data['ip'], inline=True)
        
        if 'hostname' in data:
            embed.add_field(name="Hostname", value=data['hostname'], inline=True)
        
        if 'city' in data:
            embed.add_field(name="City", value=data['city'], inline=True)
        
        if 'region' in data:
            embed.add_field(name="Region", value=data['region'], inline=True)
        
        if 'country' in data:
            country_name = data.get('country', 'Unknown')
            embed.add_field(name="Country", value=country_name, inline=True)
        
        if 'loc' in data:
            embed.add_field(name="Coordinates", value=data['loc'], inline=True)
        
        if 'org' in data:
            embed.add_field(name="Organization/ISP", value=data['org'], inline=False)
        
        if 'postal' in data:
            embed.add_field(name="Postal Code", value=data['postal'], inline=True)
        
        if 'timezone' in data:
            embed.add_field(name="Timezone", value=data['timezone'], inline=True)

        if 'bogon' in data and data['bogon']:
            embed.add_field(
                name="⚠️ Notice",
                value="This is a bogon IP address (reserved/private)",
                inline=False
            )

        embed.set_footer(text="Data provided by IPInfo.io")
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(IPLookup(bot))
