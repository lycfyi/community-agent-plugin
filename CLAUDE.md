# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a **user workspace** provides Claude Code with tools, agents, and skills to sync, analyze, and respond to Discord community messages.

## Available Skills

Use these slash commands to interact with Discord:

| Command           | Purpose                                     |
| ----------------- | ------------------------------------------- |
| `/discord-pull`   | Sync messages from Discord to local storage |
| `/discord-read`   | Read and analyze stored messages            |
| `/discord-send`   | Send messages to Discord channels           |
| `/discord-status` | Check sync status and statistics            |

## CLI Commands

Run from parent directory `/Users/velocity1/codebase/claudecode-for-discord`:

```bash
# Pull messages
python -m src.cli.main pull --incremental     # New messages only
python -m src.cli.main pull --days 7          # Last N days
python -m src.cli.main pull --full            # Full sync

# Send messages
python -m src.cli.main send --channel CHANNEL_ID --message "content" --no-confirm
python -m src.cli.main send --reply-to MSG_ID --channel CHANNEL_ID --message "reply" --no-confirm
python -m src.cli.main send --thread THREAD_ID --message "content" --no-confirm

# Status
python -m src.cli.main status --json
python -m src.cli.main list-channels --json
```

## Data Structure

```
data/{server_id}/
├── sync_state.json          # Tracks last sync per channel
├── server_info.yaml         # Channel list and server metadata
├── {channel_name}/
│   └── messages.md          # Channel messages in markdown
└── {channel_name}/threads/  # Thread conversations
```

### Message Format

Messages stored in `messages.md` use this format:

```markdown
### HH:MM:SS | @username (id:USER_ID) [🤖 if bot]

Message content here

---
```

## Workflow

1. **Check freshness**: Read `sync_state.json` to see last sync time
2. **Sync if stale**: Run `/discord-pull` if data is >1 hour old
3. **Read messages**: Use Read tool on `data/{server_id}/{channel}/messages.md`
4. **Search**: Use Grep tool with path `data/` for keyword search
5. **Respond**: Use `/discord-send` to post messages

## Current Server

- Server ID: `1455977506891890753`
- Server Name: DiscordHunt
- Data Directory: `data/1455977506891890753/`

## Configuration Files

- `.env` - Bot token (DISCORD_BOT_TOKEN)
- `config/server.yaml` - Server ID, retention_days, data_dir
