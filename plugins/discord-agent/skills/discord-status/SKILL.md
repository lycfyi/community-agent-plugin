---
name: discord-status
description: "Show Discord connection status, synced data, and health"
---

# Discord Status

Shows the current state of your Discord integration at a glance.

## When to Use

- User asks "how's my Discord?" or "Discord status"
- User asks "show status" or "what do I have?"
- User wants to check if sync is needed
- User asks "is Discord connected?" or "am I connected?"
- User asks "what's synced?" or "check my setup"

## How to Execute

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_status.py
```

For machine-readable output:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_status.py --json
```

## Output Explanation

The status shows:

| Section | Description |
|---------|-------------|
| Token | Whether Discord token is configured and valid |
| Config | Whether config file exists with default server |
| Data | Count of synced servers, channels, messages |
| Sync Status | Per-server freshness (Fresh <24h, Stale >24h, Old >7d) |
| Next Steps | Suggested action based on current state |

## Example Output

```
Discord Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Token:     ✓ Connected as @username
Config:    ✓ Server configured (Claude Developers)
Data:      ✓ 3 servers, 12 channels, 1,523 messages

Sync Status:
  Claude Developers    2h ago     Fresh
  Browser Use          5d ago     Stale
  Windsurf             Never      Not synced

Next Steps:
  Run /discord-sync to refresh 1 stale server(s)
```

## Prerequisites

- `.env` file (optional, but needed for full status)

## Next Steps

Based on the status output:
- If no token: Guide user to create `.env` with `DISCORD_USER_TOKEN`
- If no data: Suggest `/discord-quickstart` or `/discord-sync`
- If stale data: Suggest `/discord-sync` to refresh
- If all fresh: Ready for `/discord-chat-summary` or `/discord-read`
