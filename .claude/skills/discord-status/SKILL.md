---
name: discord-status
description: "Check Discord sync status and statistics. Use for: (1) View sync state (2) Message counts (3) List channels. Triggers: discord status, check discord, sync status"
---

# Discord Status - View State

Check Discord message sync status and statistics.

## Usage

Run from project directory `/Users/velocity1/codebase/claudecode-for-discord`:

### View Sync Status

```bash
python -m src.cli.main status --json
```

Output includes:
- Server ID
- Per-channel message counts
- Last sync times
- Total message count

### List Available Channels

```bash
python -m src.cli.main list-channels --json
```

Output includes:
- Channel names and IDs
- Channel types (text/voice)
- Permission status (can read/can write)

## Current Server

- Server ID: `1455977506891890753`
- Server Name: DiscordHunt
- Data Directory: `data/1455977506891890753/`
