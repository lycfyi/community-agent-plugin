# Community Agent Plugin Marketplace

A Claude Code plugin marketplace for community management tools.

## Prerequisites

- Discord account
- Claude Code CLI

## Install

```bash
/plugin marketplace add https://github.com/lycfyi/community-agent-plugin
```

Then select the plugin(s) you want to install from the marketplace.

## Available Plugins

### discord-agent

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

> ⚠️ **Warning:** Using a user token may violate Discord's Terms of Service. This tool is intended for personal archival and analysis only. Use at your own risk.

**Directory structure after first run:**

```
cwd/
├── .env                    # Your token (safe from plugin updates)
├── config/
│   └── server.yaml         # Auto-generated config
├── data/                   # Synced messages
```

## License

AGPL-3.0
