# CLAUDE.md

Plugin guidance for Claude Code when working with Telegram community data.

## Overview

This plugin provides skills for syncing and analyzing Telegram messages. Messages are stored as Markdown files optimized for LLM comprehension.

**WARNING**: Using a user account token may violate Telegram's Terms of Service. This is for personal archival and analysis only. Use at your own risk.

## Available Skills

| Skill | Trigger Phrases |
|-------|-----------------|
| `telegram-init` | "set up Telegram", "configure Telegram", "initialize Telegram" |
| `telegram-list` | "what groups do I have", "list Telegram groups", "show topics" |
| `telegram-sync` | "sync Telegram", "pull from Telegram", "fetch Telegram history" |
| `telegram-read` | "what's in the group", "search Telegram", "show Telegram messages" |
| `telegram-send` | "send to Telegram", "post in group", "reply in Telegram" |

## File Structure

**CRITICAL:** All file paths in this plugin are relative to the **current working directory** (cwd) where Claude Code is running - NOT the plugin directory.

```
your-project/                       # Current working directory
├── .env                           # Your credentials (Discord, Telegram, etc.)
├── config/
│   └── agents.yaml                # Unified config for all platforms
├── data/                          # Synced messages (auto-created)
│   ├── manifest.yaml              # Unified manifest for all platforms
│   └── telegram/
│       ├── groups/
│       │   └── {group_id}-{slug}/...
│       └── dms/
│           └── {user_id}-{slug}/...
```

## Data Locations

**All paths are relative to cwd (current working directory).**

**Storage Structure:** Uses unified v2 structure under `data/` with platform subdirectories.

### Group Data

**Manifest (index of all synced data):**
```
data/manifest.yaml
```

**Messages:**
```
data/telegram/groups/{group_id}-{slug}/messages.md
```

**Sync state:**
```
data/telegram/groups/{group_id}-{slug}/sync_state.yaml
```

**Metadata:**
```
data/telegram/groups/{group_id}-{slug}/group.yaml
```

### DM Data

**DM Manifest:**
```
data/telegram/dms/manifest.yaml
```

**DM Messages:**
```
data/telegram/dms/{user_id}-{username}/messages.md
```

### Migration Note

Legacy data (from v1 structure in `data/{group_id}/` and `dms/telegram/`) is automatically migrated to the unified structure on first sync.

## Message Format

Messages are stored in LLM-friendly Markdown (same format as discord-agent):

```markdown
## 2026-01-03

### 10:30 AM - @alice (123456789)
Hello everyone!

### 10:31 AM - @bob (987654321)
↳ replying to @alice:
Hey Alice!

[photo: vacation.jpg (1.2MB)]

↪ forwarded from @news_channel:
Breaking news content here...

Reactions: heart 3 | thumbsup 5
```

## Workflow

1. User generates session string externally (one-time setup)
2. User runs `telegram-init` to configure and verify connection
3. User runs `telegram-sync` to download messages
4. Read `messages.md` files directly or use `telegram-read` tool
5. Use `telegram-send` to respond when needed

## Prerequisites

User must have:
- `.env` with Telegram credentials:
  - `TELEGRAM_API_ID` - from my.telegram.org
  - `TELEGRAM_API_HASH` - from my.telegram.org
  - `TELEGRAM_SESSION` - pre-authenticated session string
- Python 3.11+ installed

## Session String Generation

Users must generate their session string externally before using this plugin:

```bash
pip install telethon
python scripts/generate_session.py
```

This will prompt for phone number, verification code, and 2FA password (if enabled).

## Warning

Using a user token may violate Telegram's Terms of Service. This tool is intended for personal use only:
- Archiving your own conversations
- Analyzing communities you actively participate in
- Never use for scraping, spam, or automation at scale

Use at your own risk. The authors are not responsible for any account restrictions.
