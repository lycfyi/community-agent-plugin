# Community Agent Plugin Marketplace

A Claude Code plugin marketplace for community management tools.

## Prerequisites

- Python 3.11+
- Discord account
- Claude Code CLI

## Install

```bash
/plugin git@github.com:lycfyi/community-agent-plugin.git
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

**Setup from empty directory:**

```bash
# 1. Clone/install the plugin
git clone https://github.com/lycfyi/community-agent-plugin.git .
# Or via Claude Code: /plugin git@github.com:lycfyi/community-agent-plugin.git

# 2. Copy config template to workspace root
cp plugins/discord-agent/.env.example .env

# 3. Edit .env and add your Discord token
# DISCORD_USER_TOKEN=your_token_here

# 4. Initialize configuration (auto-creates config/server.yaml)
python plugins/discord-agent/tools/discord_init.py

# 5. Sync messages
python plugins/discord-agent/tools/discord_sync.py --days 3
```

**Getting your Discord token:**

1. Open Discord in your browser
2. Press F12 to open Developer Tools
3. Go to Network tab
4. Perform any action in Discord
5. Find a request to `discord.com/api`
6. Copy the `Authorization` header value

> ⚠️ **Warning:** Using a user token may violate Discord's Terms of Service. This tool is intended for personal archival and analysis only. Use at your own risk.

**Directory structure after setup:**

```
your-workspace/
├── .env                    # Your token (safe from plugin updates)
├── config/
│   └── server.yaml         # Auto-generated config
├── data/                   # Synced messages
└── plugins/
    └── discord-agent/      # Plugin code
```

See [plugins/discord-agent/CLAUDE.md](plugins/discord-agent/CLAUDE.md) for full documentation.

## Repository Structure

```
.claude-plugin/
  marketplace.json        # Defines available plugins
plugins/
  discord-agent/          # Discord plugin
    .claude-plugin/
      plugin.json         # Plugin metadata
    skills/               # Skill definitions
    tools/                # Tool implementations
    lib/                  # Shared utilities
```

## Contributing

To add a new plugin:

1. Create `plugins/<your-plugin>/` directory
2. Add `.claude-plugin/plugin.json` with plugin metadata
3. Add your skills, tools, and CLAUDE.md
4. Update `.claude-plugin/marketplace.json` to include your plugin
5. Submit a PR

## License

AGPL-3.0
