import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import logging
import re
import socket
from typing import Optional, Dict
import dns.resolver
import whois
from datetime import datetime

logger = logging.getLogger(__name__)

class WebsiteLookup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    website_group = app_commands.Group(name="website", description="Website lookup commands")

    def extract_domain(self, url_or_domain: str) -> str:
        url_or_domain = url_or_domain.strip().lower()
        
        url_or_domain = re.sub(r'^https?://', '', url_or_domain)
        url_or_domain = re.sub(r'^www\.', '', url_or_domain)
        url_or_domain = url_or_domain.split('/')[0]
        url_or_domain = url_or_domain.split('?')[0]
        
        return url_or_domain

    @website_group.command(name="lookup", description="Look up information about a website or domain")
    @app_commands.describe(domain="The domain or URL to lookup")
    async def website_lookup(self, interaction: discord.Interaction, domain: str):
        await interaction.response.defer()

        clean_domain = self.extract_domain(domain)
        
        if not clean_domain or '.' not in clean_domain:
            embed = discord.Embed(
                title="❌ Invalid Domain",
                description="Please provide a valid domain name or URL.\n\nExamples:\n- `example.com`\n- `https://www.example.com`\n- `subdomain.example.com`",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        try:
            website_info = await self.gather_website_info(clean_domain)
            
            if website_info:
                embed = self.create_website_embed(website_info, clean_domain)
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Lookup Failed",
                    description=f"Unable to retrieve information for `{clean_domain}`.\n\nThe domain may not exist or is not accessible.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Unexpected error during website lookup: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    async def gather_website_info(self, domain: str) -> Optional[Dict]:
        info = {'domain': domain}
        
        ip_address = await self.get_ip_address(domain)
        if ip_address:
            info['ip_address'] = ip_address
        
        dns_records = await self.get_dns_records(domain)
        if dns_records:
            info['dns_records'] = dns_records
        
        http_info = await self.get_http_info(domain)
        if http_info:
            info.update(http_info)
        
        whois_info = await self.get_whois_info(domain)
        if whois_info:
            info.update(whois_info)
        
        if len(info) > 1:
            return info
        
        return None

    async def get_ip_address(self, domain: str) -> Optional[str]:
        try:
            ip = socket.gethostbyname(domain)
            return ip
        except socket.gaierror:
            logger.warning(f"Could not resolve IP for {domain}")
            return None
        except Exception as e:
            logger.error(f"Error getting IP for {domain}: {e}")
            return None

    async def get_dns_records(self, domain: str) -> Optional[Dict[str, list]]:
        records = {}
        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT']
        
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            
            for record_type in record_types:
                try:
                    answers = resolver.resolve(domain, record_type)
                    records[record_type] = [str(rdata) for rdata in answers]
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                    pass
                except Exception as e:
                    logger.debug(f"Error getting {record_type} record for {domain}: {e}")
            
            return records if records else None
        except Exception as e:
            logger.error(f"Error getting DNS records for {domain}: {e}")
            return None

    async def get_http_info(self, domain: str) -> Optional[Dict]:
        info = {}
        
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True) as response:
                        info['status_code'] = response.status
                        info['protocol'] = protocol.upper()
                        
                        if 'server' in response.headers:
                            info['server'] = response.headers['server']
                        
                        if 'content-type' in response.headers:
                            info['content_type'] = response.headers['content-type']
                        
                        if str(response.url) != url:
                            info['final_url'] = str(response.url)
                        
                        html = await response.text()
                        
                        tech_stack = self.detect_technologies(html, response.headers)
                        if tech_stack:
                            info['tech_stack'] = tech_stack
                        
                        return info
            except aiohttp.ClientError:
                continue
            except Exception as e:
                logger.debug(f"Error getting HTTP info for {url}: {e}")
                continue
        
        return None

    def detect_technologies(self, html: str, headers: dict) -> list:
        technologies = []
        
        if 'x-powered-by' in headers:
            technologies.append(headers['x-powered-by'])
        
        patterns = {
            'WordPress': [r'wp-content', r'wp-includes'],
            'React': [r'react', r'_react'],
            'Vue.js': [r'vue\.js', r'vue\.min\.js'],
            'Angular': [r'ng-app', r'angular'],
            'jQuery': [r'jquery'],
            'Bootstrap': [r'bootstrap'],
            'Next.js': [r'_next', r'__NEXT_DATA__'],
            'Shopify': [r'cdn\.shopify\.com'],
            'Wix': [r'wix\.com'],
            'Squarespace': [r'squarespace'],
        }
        
        for tech, patterns_list in patterns.items():
            for pattern in patterns_list:
                if re.search(pattern, html, re.IGNORECASE):
                    if tech not in technologies:
                        technologies.append(tech)
                    break
        
        return technologies[:5]

    async def get_whois_info(self, domain: str) -> Optional[Dict]:
        try:
            w = await self.bot.loop.run_in_executor(None, whois.whois, domain)
            
            info = {}
            
            if hasattr(w, 'registrar') and w.registrar:
                info['registrar'] = str(w.registrar)
            
            if hasattr(w, 'creation_date') and w.creation_date:
                creation_date = w.creation_date
                if isinstance(creation_date, list):
                    creation_date = creation_date[0]
                if isinstance(creation_date, datetime):
                    info['created'] = creation_date.strftime('%Y-%m-%d')
            
            if hasattr(w, 'expiration_date') and w.expiration_date:
                expiration_date = w.expiration_date
                if isinstance(expiration_date, list):
                    expiration_date = expiration_date[0]
                if isinstance(expiration_date, datetime):
                    info['expires'] = expiration_date.strftime('%Y-%m-%d')
            
            if hasattr(w, 'name_servers') and w.name_servers:
                name_servers = w.name_servers
                if isinstance(name_servers, list):
                    info['name_servers'] = [str(ns).lower() for ns in name_servers[:3]]
            
            return info if info else None
        except Exception as e:
            logger.debug(f"Error getting WHOIS info for {domain}: {e}")
            return None

    def create_website_embed(self, info: Dict, domain: str) -> discord.Embed:
        embed = discord.Embed(
            title=f"🌐 Website Information: {domain}",
            color=discord.Color.green()
        )

        if 'ip_address' in info:
            embed.add_field(name="IP Address", value=f"`{info['ip_address']}`", inline=True)
        
        if 'status_code' in info:
            status_emoji = "✅" if info['status_code'] == 200 else "⚠️"
            embed.add_field(name="HTTP Status", value=f"{status_emoji} {info['status_code']}", inline=True)
        
        if 'protocol' in info:
            embed.add_field(name="Protocol", value=info['protocol'], inline=True)
        
        if 'server' in info:
            embed.add_field(name="Server", value=info['server'], inline=True)
        
        if 'registrar' in info:
            embed.add_field(name="Registrar", value=info['registrar'], inline=True)
        
        if 'created' in info:
            embed.add_field(name="Created", value=info['created'], inline=True)
        
        if 'expires' in info:
            embed.add_field(name="Expires", value=info['expires'], inline=True)
        
        if 'tech_stack' in info and info['tech_stack']:
            tech_list = ', '.join(info['tech_stack'])
            embed.add_field(name="Technologies Detected", value=tech_list, inline=False)
        
        if 'name_servers' in info:
            ns_list = '\n'.join([f"• `{ns}`" for ns in info['name_servers']])
            embed.add_field(name="Name Servers", value=ns_list, inline=False)
        
        if 'dns_records' in info:
            dns_summary = []
            for record_type, records in info['dns_records'].items():
                if records:
                    dns_summary.append(f"**{record_type}**: {len(records)} record(s)")
            if dns_summary:
                embed.add_field(name="DNS Records", value='\n'.join(dns_summary[:3]), inline=False)

        embed.set_footer(text="Website lookup data may vary depending on accessibility and configuration")
        return embed

async def setup(bot: commands.Bot):
    await bot.add_cog(WebsiteLookup(bot))
