# CLAUDE.md

Community Agent Plugin Marketplace for Claude Code.

## Available Plugins

| Plugin | Description |
|--------|-------------|
| `discord-agent` | Sync, read, and analyze Discord messages with Claude Code |

## Installation

Install this marketplace in Claude Code:
```
/plugin git@github.com:lycfyi/community-agent-plugin.git
```

Then install individual plugins from the marketplace.

## Plugin Locations

Each plugin is located in `plugins/<plugin-name>/` with its own:
- `.claude-plugin/plugin.json` - Plugin metadata
- `CLAUDE.md` - Plugin-specific guidance
- `skills/` - Available skills
- `tools/` - Tool implementations
- `lib/` - Shared utilities

## Contributing

To add a new plugin:
1. Create a new directory under `plugins/`
2. Add `.claude-plugin/plugin.json` with plugin metadata
3. Update `.claude-plugin/marketplace.json` to include your plugin
