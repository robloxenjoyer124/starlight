# Discord Data Bot

A powerful Discord bot that provides data lookup tools via slash commands, including IP address lookup, TikTok account location lookup, and website information lookup.

## Features

### 🌐 IP Lookup (`/ip`)
Look up detailed information about any IP address using the IPInfo API.

**Usage:** `/ip lookup [ip_address]`

**Information provided:**
- IP Address
- Hostname
- Geographic location (Country, Region, City)
- Coordinates
- ISP/Organization
- Postal Code
- Timezone
- Bogon detection (private/reserved IPs)

### 🎵 TikTok Country Lookup (`/tiktok`)
Determine the location/country of a TikTok account.

**Usage:** `/tiktok country [username_or_url]`

**Supported formats:**
- `@username`
- `username`
- `https://tiktok.com/@username`

**Information provided:**
- Display Name
- Country
- Region
- Location (when available)

### 🌐 Website Lookup (`/website`)
Get comprehensive information about any website or domain.

**Usage:** `/website lookup [domain]`

**Information provided:**
- IP Address
- HTTP Status Code
- Protocol (HTTP/HTTPS)
- Server Software
- Domain Registrar
- Creation & Expiration Dates
- Name Servers
- DNS Records (A, AAAA, MX, NS, TXT)
- Technology Stack Detection (WordPress, React, Vue.js, etc.)

## Prerequisites

- Python 3.8 or higher
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- IPInfo API Key (from [IPInfo.io](https://ipinfo.io/))

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Create a Virtual Environment (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
cp .env.example .env
```

Edit the `.env` file and add your API keys:

```env
DISCORD_TOKEN=your_discord_bot_token_here
IPINFO_API_KEY=your_ipinfo_api_key_here
```

#### Getting API Keys

**Discord Bot Token:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Under the bot's username, click "Reset Token" to reveal your token
6. Copy the token to your `.env` file
7. Enable the following Privileged Gateway Intents:
   - Message Content Intent
8. Go to OAuth2 → URL Generator
9. Select scopes: `bot`, `applications.commands`
10. Select bot permissions: `Send Messages`, `Use Slash Commands`, `Embed Links`
11. Use the generated URL to invite the bot to your server

**IPInfo API Key:**
1. Sign up at [IPInfo.io](https://ipinfo.io/)
2. Go to your [dashboard](https://ipinfo.io/account/home)
3. Copy your API token
4. Add it to your `.env` file

## Running the Bot

```bash
python bot.py
```

You should see output indicating the bot has connected to Discord:

```
2024-01-01 12:00:00 - __main__ - INFO - Syncing commands...
2024-01-01 12:00:01 - __main__ - INFO - Commands synced successfully
2024-01-01 12:00:01 - __main__ - INFO - YourBotName#1234 has connected to Discord!
```

## Usage Examples

### IP Lookup
```
/ip lookup 8.8.8.8
```
Returns detailed information about Google's DNS server.

### TikTok Lookup
```
/tiktok country @username
/tiktok country https://tiktok.com/@username
```
Returns location information for the TikTok account.

### Website Lookup
```
/website lookup google.com
/website lookup https://www.github.com
```
Returns comprehensive information about the website.

## Error Handling

The bot includes comprehensive error handling for:
- Invalid inputs (malformed IP addresses, usernames, domains)
- API failures and rate limits
- Network connectivity issues
- Missing or invalid API keys
- Private/unavailable data

All errors are displayed as user-friendly Discord embeds with helpful information.

## Project Structure

```
.
├── bot.py                      # Main bot file
├── cogs/
│   ├── __init__.py
│   ├── ip_lookup.py           # IP lookup functionality
│   ├── tiktok_lookup.py       # TikTok lookup functionality
│   └── website_lookup.py      # Website lookup functionality
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore               # Git ignore rules
└── README.md               # This file
```

## Dependencies

- **discord.py** (>=2.3.2) - Discord API wrapper
- **python-dotenv** (>=1.0.0) - Environment variable management
- **requests** (>=2.31.0) - HTTP library
- **aiohttp** (>=3.9.0) - Async HTTP client
- **python-whois** (>=0.8.0) - WHOIS lookup
- **dnspython** (>=2.4.2) - DNS toolkit

## Troubleshooting

### Commands Not Showing Up
- Wait a few minutes after starting the bot (Discord can take time to sync commands)
- Make sure the bot has the `applications.commands` scope
- Try kicking and re-inviting the bot with the correct permissions

### API Errors
- Verify your API keys are correct in the `.env` file
- Check if you've exceeded your API rate limits
- Ensure your IPInfo account is active

### Import Errors
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Verify you're using Python 3.8 or higher: `python --version`

### Bot Not Connecting
- Check your Discord token is correct
- Ensure the bot is not disabled in the Developer Portal
- Check your internet connection

## Rate Limits

- **IPInfo API**: Free tier allows 50,000 requests per month
- **Discord API**: Rate limits apply per endpoint (handled automatically by discord.py)
- **TikTok**: No official API rate limits, but web scraping may be unreliable

## Privacy & Data

This bot does not store any user data or lookup results. All data is fetched in real-time from third-party APIs and displayed directly to the user.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is provided as-is for educational and personal use.

## Support

If you encounter any issues or have questions:
1. Check the Troubleshooting section
2. Review the error messages in the bot's logs
3. Open an issue on the repository

## Acknowledgments

- [IPInfo.io](https://ipinfo.io/) for IP geolocation data
- [discord.py](https://github.com/Rapptz/discord.py) for the Discord API wrapper
- TikTok for publicly available profile data
