# Development Guide

## Project Overview

This Discord bot uses the discord.py library with slash commands to provide data lookup functionality.

## Architecture

### Main Components

- **bot.py**: Main bot entry point. Initializes the bot, loads cogs, and syncs commands.
- **cogs/**: Command modules organized by feature
  - `ip_lookup.py`: IP address information lookup
  - `tiktok_lookup.py`: TikTok account location lookup
  - `website_lookup.py`: Website/domain information lookup

### Command Structure

All commands use Discord's slash command system with command groups:

```python
# Example: /ip lookup 8.8.8.8
class SomeCog(commands.Cog):
    group = app_commands.Group(name="group", description="...")
    
    @group.command(name="subcommand", description="...")
    async def handler(self, interaction, param: str):
        await interaction.response.defer()  # Always defer for slow operations
        # ... process command ...
        await interaction.followup.send(embed=embed)
```

### Error Handling Pattern

All commands follow this error handling pattern:

1. Defer the interaction response immediately for operations that may take time
2. Validate input and return user-friendly error embeds
3. Use try-except blocks for API calls and network operations
4. Log errors using the logging module
5. Always send user-friendly error messages via Discord embeds

### Embed Color Scheme

- Blue: Informational responses
- Green: Successful lookups
- Orange: Warnings/limited information
- Red: Errors

## Adding New Commands

To add a new command:

1. Create a new file in `cogs/` (e.g., `new_feature.py`)
2. Create a Cog class that inherits from `commands.Cog`
3. Define a command group using `app_commands.Group`
4. Implement command handlers with `@group.command`
5. Add the cog to `bot.py` in the `setup_hook` method
6. Update README.md with usage examples

Example:

```python
import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class NewFeature(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    feature_group = app_commands.Group(name="feature", description="Feature commands")

    @feature_group.command(name="action", description="Perform an action")
    @app_commands.describe(param="Description of parameter")
    async def action(self, interaction: discord.Interaction, param: str):
        await interaction.response.defer()
        
        # Your logic here
        embed = discord.Embed(
            title="Result",
            description="Success",
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(NewFeature(bot))
```

## Testing

### Local Testing

1. Set up a Discord bot in the Developer Portal
2. Create a test server
3. Add required API keys to `.env`
4. Run the bot: `python bot.py`
5. Test commands in your test server

### Syntax Checking

```bash
# Check Python syntax
python3 -m py_compile bot.py cogs/*.py

# Or use AST parsing
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['bot.py', 'cogs/ip_lookup.py', 'cogs/tiktok_lookup.py', 'cogs/website_lookup.py']]"
```

## API Keys and Configuration

All sensitive configuration is stored in environment variables:

- `DISCORD_TOKEN`: Discord bot token (required)
- `IPINFO_API_KEY`: IPInfo.io API key (required for `/ip lookup`)

Additional API keys can be added to `.env` and accessed via `os.getenv()`.

## Deployment Considerations

### Rate Limiting

- IPInfo API: 50,000 requests/month on free tier
- Discord API: Rate limits handled automatically by discord.py
- TikTok: Web scraping, may be subject to rate limiting

### Error Recovery

The bot includes comprehensive error handling and will continue running even if individual command executions fail. Errors are logged and user-friendly messages are sent.

### Logging

All logs are output to console with timestamps. For production:

```python
# Add file logging
handler = logging.FileHandler('bot.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
```

## Dependencies

See `requirements.txt` for all dependencies. Key libraries:

- **discord.py**: Discord API wrapper with slash command support
- **aiohttp**: Async HTTP client for API calls
- **python-whois**: WHOIS lookups
- **dnspython**: DNS record queries

## Coding Standards

- Use async/await for all I/O operations
- Include type hints for function parameters
- Use descriptive variable names
- Follow PEP 8 style guidelines
- Log errors, don't print them
- Always provide user-friendly error messages
