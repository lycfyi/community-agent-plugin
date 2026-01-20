---
name: discord-sync
description: "Sync Discord messages to local storage. Use when user asks to sync, pull, fetch, or download Discord messages."
---

# Discord Sync

Syncs messages from Discord servers to local Markdown files for reading and analysis.

## When to Use

- User asks to "sync Discord messages"
- User asks to "pull messages from Discord"
- User wants to "get Discord history"
- User wants to "update Discord data"
- User wants to "download Discord messages"
- User asks to "fetch messages from #channel"

## Smart Defaults (Reduce Questions)

**When user is vague, apply these defaults instead of asking:**

| User Says | Default Action |
|-----------|----------------|
| "sync my Discord" | Sync the configured default server from agents.yaml |
| "sync [server name]" | Find server by name, sync with 7 days default |
| No --days specified | Default to 7 days |
| "sync everything" | List available servers and ask user to pick |

**Only ask for clarification when:**
- User's server name matches multiple servers
- User explicitly asks "which servers can I sync?"

## How to Execute

### Sync all channels in configured server:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py
```

### Sync specific channel:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --channel CHANNEL_ID
```

### Sync specific server:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --server SERVER_ID
```

### Sync with custom history range:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --days 7
```

### Full re-sync (ignore previous sync state):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --full
```

### Sync DMs

**DMs are included by default.** Use `--no-dms` to sync servers only.

Sync all (servers + DMs):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py
```

Sync servers only (exclude DMs):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --no-dms
```

Sync a specific DM by channel ID:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --dm CHANNEL_ID
```

Sync DMs with custom message limit (default: 100):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --dm-limit 500
```

## DM Message Limits

### DM Limit (`--dm-limit`)
- Default: 100 (privacy-conscious default)
- Lower than server channel limit by design
- Increase manually if needed: `--dm-limit 500`

### Server Channel Limit (`--limit`)
- Default: 200 for quick mode
- Use config file to set higher limits for full sync

## Output Location

All paths are relative to cwd (current working directory):

### Server Messages
Messages saved to: `./data/{server_id}/{channel_name}/messages.md`

Sync state tracked in: `./data/{server_id}/sync_state.yaml`

### DM Messages
DM messages saved to: `./dms/discord/{user_id}-{username}/messages.md`

DM manifest: `./dms/discord/manifest.yaml`

## Prerequisites

- `./.env` file with `DISCORD_USER_TOKEN` set (in cwd)
- `./config/agents.yaml` with `discord.default_server_id` configured (unless using --server flag)

## Incremental Sync

By default, sync is incremental - only new messages since last sync are fetched.
Use `--full` to re-sync all messages within the date range.

## Next Steps

After syncing, use discord-read skill to view or search messages.
