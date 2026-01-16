# CLAUDE.md

Community Agent Plugin Marketplace for Claude Code.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   community-agent                        │
│                   (THE BRAIN)                            │
│                                                          │
│  - community-manager agent (orchestrates platforms)      │
│  - community-patterns skill (domain knowledge)           │
│  - Shared utilities (config, storage, formatting)        │
└─────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
┌───────────────────┐              ┌───────────────────┐
│ discord-connector │              │telegram-connector │
│    (HANDS)        │              │    (HANDS)        │
│                   │              │                   │
│ discord-init      │              │ telegram-init     │
│ discord-sync      │              │ telegram-sync     │
│ discord-read      │              │ telegram-read     │
│ discord-send      │              │ telegram-send     │
│ discord-analyze   │              │ telegram-doctor   │
│ discord-summary   │              │                   │
│ discord-doctor    │              │                   │
└───────────────────┘              └───────────────────┘
```

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `community-agent` | Orchestrating agent + shared library. Coordinates cross-platform workflows. |
| `discord-connector` | Skills for syncing, reading, and analyzing Discord messages |
| `telegram-connector` | Skills for syncing, reading, and analyzing Telegram messages |

## Plugin Structure

```
plugins/
├── community-agent/         # THE BRAIN
│   ├── agents/
│   │   └── community-manager.md    # Orchestrating agent
│   ├── skills/
│   │   └── community-patterns/     # Domain knowledge
│   └── lib/                        # Shared utilities (source of truth)
│
├── discord-connector/       # HANDS (Discord) - Self-contained
│   ├── skills/              # Platform skills
│   ├── tools/               # Python implementations
│   └── lib/                 # Includes bundled shared code
│
└── telegram-connector/      # HANDS (Telegram) - Self-contained
    ├── skills/              # Platform skills
    ├── tools/               # Python implementations
    └── lib/                 # Includes bundled shared code
```

Each connector is self-contained with bundled copies of shared utilities (config, profile, persona).
This ensures plugins work correctly when installed separately.

## Installation

Install this marketplace in Claude Code:
```
/plugin marketplace add https://github.com/lycfyi/community-agent-plugin
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
- `agents/` - Agent definitions (community-agent only)
- `skills/` - Available skills
- `tools/` - Tool implementations
- `lib/` - Library code (connectors include bundled shared utilities)

## Contributing

To add a new plugin:
1. Create a new directory under `plugins/`
2. Add `.claude-plugin/plugin.json` with plugin metadata
3. If it's a platform connector, copy shared utilities from `community-agent/lib/` (config, profile, persona)
4. Update `.claude-plugin/marketplace.json` to include your plugin
