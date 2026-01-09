---
name: telegram-send
description: "Send messages to Telegram channels. Use when user wants to post, reply, or send messages to Telegram."
---

# telegram-send

Send messages to Telegram groups.

## Trigger Phrases

- "send to Telegram"
- "post in Telegram group"
- "reply on Telegram"
- "message the Telegram group"
- "telegram send"

## Description

This skill sends messages to Telegram groups. It requires confirmation before sending to prevent accidental messages.

**WARNING**: Using a user token may violate Telegram's Terms of Service. This tool is intended for personal use only.

## Usage

Send a message to default group:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_send.py --message "Hello everyone!"
```

Send to specific group:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_send.py --group 1234567890 --message "Hello!"
```

Reply to a specific message:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_send.py --message "Great point!" --reply-to 12345
```

Send to a specific topic (forum groups):
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_send.py --message "Update" --topic 5
```

Skip confirmation prompt:
```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/telegram_send.py --message "Hello" --confirm
```

## Confirmation

By default, the tool shows your message and asks for confirmation:

```
Message to send:
----------------------------------------
Hello everyone! This is a test message.
----------------------------------------

Send this message? (y/N):
```

Use `--confirm` to skip this prompt (useful for automation).

## Output

On success:
```
Sending to: My Group (1234567890)

========================================
Message sent successfully!
Message ID: 98765
Timestamp: 2026-01-06T12:00:00+00:00
```

## Forum Topics

For groups with forum topics, you can target a specific topic:

1. First, list topics: `telegram-list --group 1234567890`
2. Then send to topic: `telegram-send --group 1234567890 --topic 5 --message "Hello"`

## Rate Limiting

If you send too many messages too quickly, you may be rate limited. The tool will show how long to wait before trying again.

## Exit Codes

- `0` - Success
- `1` - Authentication error
- `2` - Permission denied or configuration error
- `3` - Rate limited

## Safety Notes

1. **Always verify the target group** before sending
2. **Use confirmation prompt** (don't use `--confirm` unless necessary)
3. **Be respectful** of group rules and other members
4. **Don't spam** - excessive messaging may result in account restrictions

## Related Skills

- `telegram-init` - Initialize Telegram connection
- `telegram-list` - List groups and topics
- `telegram-sync` - Sync messages from groups
- `telegram-read` - Read synced messages
