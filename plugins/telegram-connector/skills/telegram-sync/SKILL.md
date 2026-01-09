---
name: telegram-sync
description: "Sync Telegram messages to local storage. Use when user asks to sync, pull, fetch, or download Telegram messages."
---

# telegram-sync

Sync Telegram messages to local Markdown storage.

## Trigger Phrases

- "sync Telegram"
- "pull from Telegram"
- "fetch Telegram messages"
- "download Telegram history"
- "telegram sync"

## Description

This skill downloads messages from Telegram groups to local Markdown files. Messages are stored in an LLM-friendly format that can be easily read and analyzed.

## Usage

Sync default group (last 7 days):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_sync.py
```

Sync specific group:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_sync.py --group 1234567890
```

Sync last 30 days:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_sync.py --days 30
```

Full sync (ignore previous state):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_sync.py --full
```

Sync specific topic in a forum group:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_sync.py --group 1234567890 --topic 5
```

Sync with custom message limit (for longer lookbacks):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_sync.py --days 30 --limit 5000
```

## Message Limit

The `--limit` option controls the maximum number of messages to sync per group/topic.

- Default: 2000 (configurable in `config/agents.yaml`)
- Use higher limits for longer lookback periods
- Example: `--days 90 --limit 10000` for 90-day archive

## Sync Modes

### Incremental Sync (default)
- Only fetches messages newer than the last sync
- Fast and efficient for regular updates
- Uses the `last_message_id` from sync state

### Full Sync (--full)
- Ignores previous sync state
- Downloads all messages within the date range
- Use when you want a fresh start

## Output

Messages are saved to:
```
data/{group_id}-{slug}/messages.md
data/{group_id}-{slug}/sync_state.yaml
data/{group_id}-{slug}/group.yaml
```

For forum groups with topics:
```
data/{group_id}-{slug}/{topic_name}/messages.md
```

## Rate Limiting

Telegram has strict rate limits. The sync tool:
- Adds delays between requests (100ms minimum)
- Handles FloodWait errors automatically
- Shows progress during sync

If rate limited, you'll see the wait time and can retry later.

## Message Format

```markdown
## 2026-01-06

### 10:30 AM - @alice (123456)
Hello everyone!

### 10:31 AM - @bob (789012)
↳ replying to @alice:
Hey there!

[photo: vacation.jpg (1.2MB)]

Reactions: heart 5 | thumbsup 3
```

## Exit Codes

- `0` - Success
- `1` - Authentication error
- `2` - Group not found or permission denied
- `3` - Rate limited

## Related Skills

- `telegram-init` - Initialize Telegram connection
- `telegram-list` - List groups and topics
- `telegram-read` - Read synced messages
