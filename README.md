# Community Agent Plugin Marketplace

A Claude Code plugin marketplace for community management tools. Sync and analyze Discord & Telegram messages directly from Claude Code.

## Prerequisites

- Claude Code CLI
- Python 3.11+
- Discord account (for discord-connector)
- Telegram account (for telegram-connector)

## Install

```bash
/plugin marketplace add https://github.com/lycfyi/community-agent-plugin
```

Then select the plugin(s) you want to install from the marketplace.

## Demo

**Summarize discussion topics from a Discord server:**

![Summarize Topics](assets/demo1.png)

**Find the most active community members:**

![Active Members](assets/demo2.png)

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `community-agent` | Core shared library (auto-installed with connectors) |
| `discord-connector` | Sync, read, and analyze Discord messages |
| `telegram-connector` | Sync, read, and analyze Telegram messages |

---

### discord-connector

Sync, read, and analyze Discord messages directly from Claude Code.

| Skill                  | Purpose                                            |
| ---------------------- | -------------------------------------------------- |
| `discord-init`         | Initialize configuration from your Discord account |
| `discord-list`         | List accessible servers and channels               |
| `discord-sync`         | Sync messages to local Markdown storage            |
| `discord-read`         | Read and search synced messages                    |
| `discord-send`         | Send messages to Discord channels                  |
| `discord-chat-summary` | AI-powered summary of Discord conversations        |

**Example conversations:**

- "Set up Discord sync for my account"
- "Show me all the servers I have access to"
- "Sync the last 7 days of messages from all servers"
- "Summarize what's been happening in XXX Server"
- "Search for messages mentioning 'bug report'"
- "Draft a self-intro for me and send it to proper discord server and channels"

**Getting your Discord token:**

[How to get your Discord user token (guide)](https://discordhunt.com/articles/how-to-get-discord-user-token)

> **Warning:** Using a user token may violate Discord's Terms of Service. This tool is intended for personal archival and analysis only. Use at your own risk.

---

### telegram-connector

Sync, read, and analyze Telegram messages directly from Claude Code.

| Skill           | Purpose                                      |
| --------------- | -------------------------------------------- |
| `telegram-init` | Initialize Telegram connection and config    |
| `telegram-list` | List accessible groups and forum topics      |
| `telegram-sync` | Sync messages to local Markdown storage      |
| `telegram-read` | Read and search synced messages              |
| `telegram-send` | Send messages to Telegram groups             |

**Example conversations:**

- "Set up Telegram sync for my account"
- "List all my Telegram groups"
- "Sync the last 7 days of messages from my group"
- "Search Telegram messages for 'meeting'"
- "Send a message to my Telegram group"

**Getting your Telegram credentials:**

1. Get API credentials from https://my.telegram.org/apps
2. Generate a session string: `python plugins/telegram-connector/scripts/generate_session.py`
3. Add to `.env`:
   ```
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   TELEGRAM_SESSION=your_session_string
   ```

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
    │   └── {channel}/
    │       └── messages.md
    └── {group_id}-{slug}/         # Telegram groups
        ├── group.yaml
        ├── sync_state.yaml
        └── messages.md
```

## Architecture

```
plugins/
├── community-agent/         # Core shared library
│   └── lib/
│       ├── config.py        # Unified configuration
│       ├── storage_base.py  # Storage utilities
│       └── markdown_base.py # Formatting utilities
│
├── discord-connector/       # Discord platform connector
│   ├── community_agent/     # Symlink to core library
│   ├── lib/
│   ├── tools/
│   └── skills/
│
└── telegram-connector/      # Telegram platform connector
    ├── community_agent/     # Symlink to core library
    ├── lib/
    ├── tools/
    └── skills/
```

## License

AGPL-3.0
