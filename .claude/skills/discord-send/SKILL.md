---
name: discord-send
description: "Send messages to Discord channels. Use for: (1) Post new messages (2) Reply to messages (3) Send to threads. Triggers: discord send, post to discord, send message"
---

# Discord Send - Post Messages

Send messages to Discord channels.

## Usage

Run from project directory `/Users/velocity1/codebase/claudecode-for-discord`:

### Send to Channel

```bash
python -m src.cli.main send --channel CHANNEL_ID --message "content" --no-confirm
```

### Reply to Message

```bash
python -m src.cli.main send --channel CHANNEL_ID --reply-to MESSAGE_ID --message "reply" --no-confirm
```

### Send to Thread

```bash
python -m src.cli.main send --thread THREAD_ID --message "thread reply" --no-confirm
```

## Available Channels

```bash
python -m src.cli.main list-channels --json
```

Current channels:
- `1455977507466641520` - general
- `1455990342422761596` - test-dubbing
- `1455990394843168859` - test-xbc
- `1456836441761120270` - e2e-test-pressure_test_v2

## Notes

- Use `--no-confirm` to skip confirmation prompt
