---
name: discord-pull
description: "Sync Discord messages to local storage. Use for: (1) Pull latest messages (2) Incremental sync (3) Full sync. Triggers: discord pull, sync discord, pull messages"
---

# Discord Pull - Message Sync

Sync messages from Discord server to local markdown files for Claude Code analysis.

## Usage

Run from project directory `/Users/velocity1/codebase/claudecode-for-discord`:

### Incremental Sync (default)

```bash
python -m src.cli.main pull --incremental
```

### Pull Last N Days

```bash
python -m src.cli.main pull --days 7
```

### Full Sync

```bash
python -m src.cli.main pull --full
```

### Specific Channel

```bash
python -m src.cli.main pull --channel CHANNEL_ID
```

## Output

- Messages: `data/{server_id}/{channel_name}/messages.md`
- Threads: `data/{server_id}/{channel_name}/threads/`
- State: `data/{server_id}/sync_state.json`

## Current Server

Server ID: `1455977506891890753` (DiscordHunt)
