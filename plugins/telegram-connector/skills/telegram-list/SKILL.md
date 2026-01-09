---
name: telegram-list
description: "List Telegram groups and channels. Use when user asks about available groups, channels, or wants to discover what's accessible."
---

# telegram-list

List Telegram groups, channels, and forum topics.

## Trigger Phrases

- "list Telegram groups"
- "what groups do I have on Telegram"
- "show my Telegram channels"
- "telegram list"
- "list topics in [group]"

## Description

This skill lists all accessible Telegram groups and channels. For groups with forum topics enabled, you can also list the individual topics.

## Usage

List all groups:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_list.py
```

List topics in a specific group:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_list.py --group 1234567890
```

Output as JSON:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_list.py --json
```

## Output Format

### Table Output (default)

```
Found 5 groups/channels:

ID              Type         Members    Topics   Name
----------------------------------------------------------------------
1234567890      supergroup   1500       Yes      My Community
9876543210      channel      5000       -        News Channel
...
```

### JSON Output (--json)

```json
[
  {
    "id": 1234567890,
    "name": "My Community",
    "type": "supergroup",
    "username": "mycommunity",
    "member_count": 1500,
    "has_topics": true
  }
]
```

## Group Types

- `private` - 1:1 private chats
- `group` - Basic groups (< 200 members)
- `supergroup` - Upgraded groups (can have topics)
- `channel` - Broadcast channels

## Forum Topics

Some supergroups have "forum topics" enabled, which is similar to Discord's channel structure. When a group has topics:
- Messages are organized by topic
- Use `--group GROUP_ID` to see available topics
- Sync will pull messages from each topic separately

## Exit Codes

- `0` - Success
- `1` - Authentication error
- `2` - Group not found or configuration error

## Related Skills

- `telegram-init` - Initialize Telegram connection
- `telegram-sync` - Sync messages from groups
- `telegram-read` - Read synced messages
