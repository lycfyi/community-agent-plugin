# CLAUDE.md

Community Agent Plugin Marketplace for Claude Code.

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `community-agent` | Core shared library (storage, formatting, config) |
| `discord-connector` | Sync, read, and analyze Discord messages with Claude Code |
| `telegram-connector` | Sync, read, and analyze Telegram messages with Claude Code |

## Architecture

```
plugins/
├── community-agent/         # Core library (no skills)
│   └── lib/
│       ├── config.py        # CommunityConfig
│       ├── storage_base.py  # Storage utilities
│       ├── markdown_base.py # Formatting utilities
│       └── rate_limiter_base.py
│
├── discord-connector/       # Discord platform connector
│   ├── community_agent -> ../community-agent
│   ├── lib/
│   ├── tools/
│   └── skills/              # discord-init, discord-sync, etc.
│
└── telegram-connector/      # Telegram platform connector
    ├── community_agent -> ../community-agent
    ├── lib/
    ├── tools/
    └── skills/              # telegram-init, telegram-sync, etc.
```

## Installation

Install this marketplace in Claude Code:
```
/plugin git@github.com:lycfyi/community-agent-plugin.git
```

Then install individual plugins from the marketplace.

## Configuration

All plugins share a unified configuration file at `config/agents.yaml`:

```yaml
# Shared settings
data_dir: "./data"

# Discord settings
discord:
  retention_days: 30
  sync_limits:
    max_messages_per_channel: 500
    ...

# Telegram settings
telegram:
  retention_days: 7
  sync_limits:
    max_messages_per_group: 2000
    ...
```

Credentials are stored in `.env`:
```
DISCORD_USER_TOKEN=your_discord_token
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION=your_session_string
```

## Plugin Locations

Each plugin is located in `plugins/<plugin-name>/` with its own:
- `.claude-plugin/plugin.json` - Plugin metadata
- `CLAUDE.md` - Plugin-specific guidance
- `skills/` - Available skills (platform connectors only)
- `tools/` - Tool implementations
- `lib/` - Library code

Platform connectors depend on `community-agent` via symlink.

## Contributing

To add a new plugin:
1. Create a new directory under `plugins/`
2. Add `.claude-plugin/plugin.json` with plugin metadata
3. If it's a platform connector, add symlink: `community_agent -> ../community-agent`
4. Update `.claude-plugin/marketplace.json` to include your plugin
