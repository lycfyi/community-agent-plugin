# CLAUDE.md

Plugin guidance for Claude Code when working with Discord community data.

## Overview

This plugin provides skills for syncing and analyzing Discord messages. Messages are stored as Markdown files optimized for LLM comprehension.

## Available Skills

| Skill | Trigger Phrases |
|-------|-----------------|
| `discord-init` | "set up Discord", "configure Discord", "initialize Discord" |
| `discord-list` | "what servers do I have", "list channels in X" |
| `discord-sync` | "sync messages", "pull from Discord", "fetch history" |
| `discord-read` | "what's in #channel", "search Discord", "show messages" |
| `discord-send` | "send to Discord", "post in #channel", "reply to message" |
| `discord-chat-summary` | "summarize Discord", "what's been happening", "digest" |

## File Structure

**CRITICAL:** All file paths in this plugin are relative to the **current working directory** (cwd) where Claude Code is running - NOT the plugin directory. This allows the plugin to work from any directory.

```
your-project/                       # Current working directory (where you run Claude)
├── .env                           # Your Discord token
├── config/
│   └── server.yaml                # Your server config
├── data/                          # Synced messages (auto-created)
│   ├── manifest.yaml
│   └── {server_id}/...
```

The plugin code lives elsewhere and is referenced via `--plugin-dir`.

## Data Locations

**All paths are relative to cwd (current working directory), NOT the plugin directory:**

**Manifest (index of all synced data):**
```
data/manifest.yaml
```

**Messages:**
```
data/{server_id}/{channel_name}/messages.md
```

**Sync state:**
```
data/{server_id}/sync_state.yaml
```

**Metadata:**
```
data/{server_id}/server.yaml
data/{server_id}/{channel_name}/channel.yaml
```

## Message Format

Messages are stored in LLM-friendly Markdown:

```markdown
## 2026-01-03

### 10:30 AM - @alice (123456789)
Hello everyone!

### 10:31 AM - @bob (987654321)
↳ replying to @alice:
Hey Alice!

[attachment: file.png (245KB) https://...]

> [embed] **Title**
> Description text
> https://link

Reactions: heart 3 | rocket 5
```

## Workflow

1. User runs `discord-init` to configure server (or `discord-list` to browse)
2. User runs `discord-sync` to download messages
3. Read `messages.md` files directly or use `discord-read` tool
4. Use `discord-chat-summary` for AI analysis
5. Use `discord-send` to respond when needed

## Prerequisites

User must have:
- `.env` with `DISCORD_USER_TOKEN` set
- Python 3.11+ installed

## Warning

Using a user token may violate Discord's Terms of Service. This is for personal archival and analysis only.
