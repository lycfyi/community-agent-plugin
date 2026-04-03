---
name: community-status
description: "Show unified status of all community platforms including Discord and Telegram configuration, sync state, and file paths. Use when user wants to check their setup, see sync status, troubleshoot configuration, or get a platform overview before other operations."
---

# Community Status

Show unified status across all configured community platforms (Discord, Telegram).

## When to Use

- User says "what's my setup" or "show status"
- User says "check my community agents"
- User wants to see which platforms are configured
- User asks "what have I synced"
- Before troubleshooting to see current state

## Workflow

1. Check if persona is configured (bootstrap trigger below)
2. Run the status command
3. Review platform connectivity, sync state, and file paths
4. Direct user to doctor or init skills if issues found

## How to Execute

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/community_status.py
```

### Check persona before showing status

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/persona_status.py --json
```

If `"configured": false`, initiate the Bootstrap Ritual (see CLAUDE.md) to help the user set up their agent identity before showing status.

## What It Shows

| Section | Details |
|---------|---------|
| **Platform Status** | Discord/Telegram: configured or not, connected server/group |
| **Sync Info** | Last sync time, total messages synced |
| **File Paths** | Config file, profile file, data directory locations |
| **Setup State** | Whether setup is complete, mode used (quickstart/advanced) |

## Example Output

```
Community Agent Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Platforms:
  ✓ Discord:  Connected (My Server)
  ✓ Telegram: Connected (My Group)

Sync:
  Last sync:     2 hours ago
  Messages:      1,234

Files:
  Config:   config/agents.yaml
  Profile:  config/PROFILE.md
  Data:     data/

Setup: Complete (quickstart mode)
```

## Status Icons

- ✓ Fully configured and ready
- ○ Partially configured (needs init)
- ✗ Not configured

## Next Steps

If platforms show issues:
- Run `discord-doctor` or `telegram-doctor` to diagnose
- Run `discord-init` or `telegram-init` to configure
