# Community Agent Plugin Marketplace

A Claude Code plugin marketplace for community management tools. Sync and analyze Discord & Telegram messages directly from Claude Code.

## What You Can Do

Talk to Claude in natural language to manage your community:

**Track Growth & New Members**
```
"How many members joined this week?"
"Show me the growth stats for the last month"
```

**Find Silent Members & Lurkers**
```
"List lurkers who joined over 30 days ago but never posted"
"Show me the engagement breakdown"
```

**Smart Member Search**
```
"Find members interested in AI"
"Search for developers with moderator role"
"Find active members who joined last month"
```

**Track Churn**
```
"Who left the server recently?"
"Which departing members were actually active?"
```

**Analyze & Export**
```
"Which members are most active?"
"Export member list as CSV"
"Analyze community health"
```

## Quick Start

### 1. Install the Plugin

```bash
/plugin marketplace add https://github.com/lycfyi/community-agent-plugin
```

Then select the plugin(s) you want to install from the marketplace.

### 2. Set Up Your First Connector

**For Discord:**
```
"Set up Discord sync for my account"
```

**For Telegram:**
```
"Set up Telegram sync for my account"
```

### 3. Start Using

```
"Sync my Discord messages"
"Summarize what's happening in my community"
"Analyze community health"
```

## Prerequisites

- Claude Code CLI
- Python 3.11+
- Discord account (for discord-user-connector)
- Telegram account (for telegram-connector)

## Demo

**Summarize discussion topics from a Discord server:**

![Summarize Topics](assets/demo1.png)

**Find the most active community members:**

![Active Members](assets/demo2.png)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   community-agent                        │
│                   (THE BRAIN)                            │
│                                                          │
│  Orchestrating agent that coordinates cross-platform     │
│  workflows using platform connectors as "hands"          │
└─────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│discord-user  │    │ discord-bot  │    │  telegram    │
│ -connector   │    │ -connector   │    │ -connector   │
│              │    │              │    │              │
│ Messages     │    │ Fast member  │    │ Messages     │
│ DMs, Profiles│    │ sync (100k+) │    │ Groups       │
└──────────────┘    └──────────────┘    └──────────────┘
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `community-agent` | Orchestrating agent + shared library. Coordinates cross-platform workflows. |
| `discord-user-connector` | Sync messages, read DMs, get rich profiles (user token) |
| `discord-bot-connector` | Fast member sync for large servers - 100k+ members (bot token) |
| `telegram-connector` | Sync, read, and analyze Telegram messages |

---

## community-agent

The brain of the system. Provides:

- **community-manager agent** - Coordinates cross-platform workflows
- **community-patterns skill** - Domain knowledge for community management
- **Shared utilities** - Config, storage, formatting used by all connectors

**Example conversations:**
- "Sync all my communities" (coordinates Discord + Telegram)
- "Summarize activity across all platforms"
- "Send announcement to all my communities"

---

## discord-user-connector

Sync, read, and analyze Discord messages directly from Claude Code.

| Skill                  | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `discord-init`         | Initialize configuration from your Discord account |
| `discord-list`         | List accessible servers and channels               |
| `discord-sync`         | Sync messages to local Markdown storage            |
| `discord-read`         | Read and search synced messages                    |
| `discord-send`         | Send messages to Discord channels                  |
| `discord-members`      | Query members, track churn, get rich profiles      |
| `discord-chat-summary` | AI-powered summary of Discord conversations        |
| `discord-analyze`      | Generate community health reports with metrics     |
| `discord-doctor`       | Diagnose configuration issues                      |

**Example conversations:**

- "Set up Discord sync for my account"
- "Show me all the servers I have access to"
- "Sync the last 7 days of messages from all servers"
- "Summarize what's been happening in XXX Server"
- "Search for messages mentioning 'bug report'"
- "Analyze community health for my Discord server"
- "Draft a self-intro for me and send it to proper discord server and channels"

**Getting your Discord token:**

[How to get your Discord user token (guide)](https://discordhunt.com/articles/how-to-get-discord-user-token)

> **Warning:** Using a user token may violate Discord's Terms of Service. This tool is intended for personal archival and analysis only. Use at your own risk.

---

## discord-bot-connector

Fast member syncing for large Discord servers using bot tokens. Can fetch complete member lists from servers with 100k+ members.

| Skill                  | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `discord-bot-members`  | Sync complete member list via Gateway API          |
| `discord-sync`         | Sync messages (shares data with user-connector)    |

**When to use bot-connector vs user-connector:**

| Feature | Bot Connector | User Connector |
|---------|---------------|----------------|
| Member Sync | Fast, complete list | Cached only |
| Message Sync | Yes | Yes |
| DM Access | No | Yes |
| Rich Profiles (bio, pronouns) | No | Yes |
| ToS Compliant | Yes | Gray area |

**Setup:** Create a bot at [Discord Developer Portal](https://discord.com/developers/applications), enable SERVER MEMBERS INTENT, and add to `.env`:
```
DISCORD_BOT_TOKEN=your_bot_token
```

---

## telegram-connector

Sync, read, and analyze Telegram messages directly from Claude Code.

| Skill            | Purpose                                      |
| ---------------- | -------------------------------------------- |
| `telegram-init`  | Initialize Telegram connection and config    |
| `telegram-list`  | List accessible groups and forum topics      |
| `telegram-sync`  | Sync messages to local Markdown storage      |
| `telegram-read`  | Read and search synced messages              |
| `telegram-send`  | Send messages to Telegram groups             |
| `telegram-doctor`| Diagnose configuration issues                |

**Example conversations:**

- "Set up Telegram sync for my account"
- "List all my Telegram groups"
- "Sync the last 7 days of messages from my group"
- "Search Telegram messages for 'meeting'"
- "Send a message to my Telegram group"

**Getting your Telegram credentials:**

1. Get API credentials from https://my.telegram.org/apps
2. Generate a session string (see important note below)
3. Add to `.env`:
   ```
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   TELEGRAM_SESSION=your_session_string
   ```

**⚠️ Important: Run session generation directly in your terminal**

Telegram verification codes expire in ~2-5 minutes. You **must** run the session generation script directly in your terminal (not through Claude Code chat) to enter the code immediately when you receive it:

```bash
# Run this directly in your terminal
python plugins/telegram-connector/scripts/generate_session.py

# Enter your phone number when prompted
# Enter the verification code IMMEDIATELY when you receive it via SMS/Telegram
```

Why? The Claude Code chat workflow adds latency (typing the code → Claude processing → script execution), which often causes the code to expire before it reaches Telegram's API. Running directly in terminal allows immediate input.

**For users in regions where Telegram is blocked:** Ensure your VPN connection is stable before starting, as network latency can contribute to code expiration.

> **Warning:** Using a user token may violate Telegram's Terms of Service. This tool is intended for personal archival and analysis only. Use at your own risk.

---

## Directory Structure

After running any connector, your working directory will have:

```
your-project/
├── .env                           # Your credentials
├── config/
│   └── agents.yaml                # Unified config for all platforms
└── data/                          # Synced messages
    ├── manifest.yaml              # Index of all synced data
    ├── {server_id}-{slug}/        # Discord servers
    │   ├── server.yaml
    │   ├── sync_state.yaml
    │   ├── health-report.md       # Health analysis (if generated)
    │   └── {channel}/
    │       └── messages.md
    └── {group_id}-{slug}/         # Telegram groups
        ├── group.yaml
        ├── sync_state.yaml
        └── messages.md
```

## Plugin Structure

```
plugins/
├── community-agent/         # THE BRAIN
│   ├── agents/
│   │   └── community-manager.md    # Orchestrating agent
│   ├── skills/
│   │   └── community-patterns/     # Domain knowledge
│   └── lib/                        # Shared utilities
│
├── discord-user-connector/  # HANDS (Discord user token)
│   ├── skills/              # Messages, DMs, profiles
│   ├── tools/
│   └── lib/
│
├── discord-bot-connector/   # HANDS (Discord bot token)
│   ├── skills/              # Fast member sync
│   ├── tools/
│   └── lib/
│
└── telegram-connector/      # HANDS (Telegram)
    ├── skills/
    ├── tools/
    └── lib/
```

## License

AGPL-3.0
