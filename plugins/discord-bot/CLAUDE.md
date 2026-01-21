# CLAUDE.md

Plugin guidance for Claude Code when working with Discord bot token operations.

## IMPORTANT: How to Use This Plugin

**ALWAYS use the Skill tool to invoke Discord bot operations.** Do NOT try to run `discord-bot` as a bash command.

When user asks about member syncing with bot tokens, invoke the appropriate skill:

```
Skill(skill: "discord-bot:discord-bot-members")    # Sync members with bot token
```

The skill will load instructions showing which Python scripts to run.

## Overview

This plugin provides **fast member syncing** for Discord servers using bot tokens via direct HTTP API calls. It can fetch complete member lists from servers with 100k+ members efficiently.

**Works alongside discord.py-self** - Uses aiohttp for direct API calls, no library namespace conflicts.

**For user token features** (rich profiles, message sync), use the `discord-connector` plugin instead.

## Available Skills

| Skill | Trigger Phrases |
|-------|-----------------|
| `discord-bot-members` | "sync members with bot", "fast member sync", "complete member list" |

## When to Use This Plugin

Use `discord-bot` when you need:
- Fast member syncing (100k+ members)
- Complete member lists (not just cached members)
- Official API compliance
- Server administration features

Use `discord-connector` when you need:
- Rich profile data (bio, pronouns, connected accounts)
- Message syncing and reading
- User token features

## File Structure

```
your-project/                       # Current working directory
├── .env                           # DISCORD_BOT_TOKEN
├── config/
│   └── agents.yaml                # Configuration
└── data/
    └── discord-bot/
        └── {server_id}_{slug}/
            └── members/
                ├── current.yaml       # Latest member list
                └── snapshots/         # Historical snapshots
```

## Prerequisites

User must have:
- Python 3.11+ installed
- `aiohttp` and `pyyaml` libraries installed
- `.env` with `DISCORD_BOT_TOKEN` set
- Bot added to server with SERVER MEMBERS INTENT enabled

## Library Setup

This plugin uses direct HTTP API calls via aiohttp (no discord.py required):

```bash
pip install aiohttp pyyaml python-dotenv
```

**Note:** This plugin works even when `discord.py-self` is installed - no namespace conflicts.

## Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application or select existing one
3. Go to "Bot" section
4. Enable "SERVER MEMBERS INTENT" under Privileged Gateway Intents
5. Copy the bot token
6. Add bot to your server with appropriate permissions

## Token Configuration

### .env Configuration

```bash
# Bot token (required for this plugin)
DISCORD_BOT_TOKEN=your_bot_token_here
```

## Data Locations

All paths are relative to cwd (current working directory):

**Member Data:**
```
data/discord-bot/{server_id}_{slug}/members/current.yaml
data/discord-bot/{server_id}_{slug}/members/snapshots/
data/discord-bot/{server_id}_{slug}/members/sync_history.yaml
```

## Workflow

1. Set up bot token in `.env`
2. Ensure bot is in the target server with proper intents
3. Run member sync skill
4. Member data saved to `data/discord-bot/`

## Comparison with discord-connector

| Feature | discord-bot | discord-connector |
|---------|-------------|-------------------|
| Library | aiohttp (HTTP API) | discord.py-self |
| Token | Bot Token | User Token |
| Member Sync | ✅ Fast (complete list) | ⚠️ Only cached members |
| Rich Profiles | ❌ Basic only | ✅ Full |
| Message Sync | ❌ Not included | ✅ Full |
| ToS Compliant | ✅ Yes | ⚠️ Gray area |
| Works with discord.py-self | ✅ Yes | N/A |
