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
| "sync my Discord" | Sync recommended servers from profile (use discord_recommend.py) |
| "sync those active ones" | Pick top 3 from recommendations |
| "sync [server name]" | Find server by name, sync with 7 days default |
| No --days specified | Default to 7 days |
| "sync everything" | Sync all recommended, 30 days |

**Get smart recommendations:**
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_recommend.py --json
```

This returns servers sorted by:
1. `priority_servers` from config (highest)
2. Matches against `profile.interests` and `profile.watch_keywords`
3. Member count heuristics (if no profile configured)

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

## Output Location

All paths are relative to cwd (current working directory):

Messages saved to: `./data/{server_id}/{channel_name}/messages.md`

Sync state tracked in: `./data/{server_id}/sync_state.yaml`

## Prerequisites

- `./.env` file with `DISCORD_USER_TOKEN` set (in cwd)
- `./config/agents.yaml` with `discord.default_server_id` configured (unless using --server flag)

## Incremental Sync

By default, sync is incremental - only new messages since last sync are fetched.
Use `--full` to re-sync all messages within the date range.

## Next Steps

After syncing, use discord-read skill to view or search messages.
