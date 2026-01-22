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
│  - Persona & profile management (personality, prefs)     │
│  - Cross-platform coordination & intelligence            │
└─────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
┌───────────────────┐              ┌───────────────────┐
│ discord-user-connector │              │telegram-connector │
│  (DATA IO ONLY)   │              │  (DATA IO ONLY)   │
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

**Architecture Principles:**
- **Connectors = Data IO only**: Read/write messages, sync data, basic analysis
- **Agent = Brain**: Personality, preferences, recommendations, cross-platform coordination

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `community-agent` | Orchestrating agent + shared library. Coordinates cross-platform workflows. |
| `discord-user-connector` | Data IO for Discord - sync, read, send messages (no persona/profile) |
| `telegram-connector` | Data IO for Telegram - sync, read, send messages (no persona/profile) |

## Plugin Structure

```
plugins/
├── community-agent/         # THE BRAIN
│   ├── agents/
│   │   └── community-manager.md    # Orchestrating agent
│   ├── skills/
│   │   └── community-patterns/     # Domain knowledge
│   └── lib/                        # Shared utilities + persona + profile
│       ├── config.py              # Configuration management
│       ├── persona.py             # Bot personality settings
│       └── profile.py             # User preferences & interests
│
├── discord-user-connector/       # DATA IO (Discord) - Self-contained
│   ├── skills/              # Platform skills (sync, read, send, analyze)
│   ├── tools/               # Python implementations
│   └── lib/                 # Bundled config only (no persona/profile)
│       └── community_config.py    # Config loader
│
└── telegram-connector/      # DATA IO (Telegram) - Self-contained
    ├── skills/              # Platform skills (sync, read, send)
    ├── tools/               # Python implementations
    └── lib/                 # Bundled config only (no persona/profile)
        └── community_config.py    # Config loader
```

Connectors are self-contained with bundled config utilities only.
Persona and profile management belong to the agent (brain), not connectors (data IO).

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
    max_messages_per_channel: 1000
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
3. If it's a platform connector (data IO):
   - Copy only `community_config.py` from `community-agent/lib/`
   - Do NOT include persona.py or profile.py (those are brain concerns)
4. Update `.claude-plugin/marketplace.json` to include your plugin
