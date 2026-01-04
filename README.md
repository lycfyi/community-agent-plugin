# Discord User Sync for Claude Code

Sync and analyze Discord messages using your personal user token. This tool enables Claude Code to read, search, and respond to Discord conversations.

## ⚠️ Important Warning

**Using a user token (self-bot) may violate Discord's Terms of Service.** This tool is intended for:
- Personal archival and backup
- Message analysis with AI assistance
- Private use on your own account

Use at your own risk. Discord may suspend accounts that use user tokens for automation.

## Features

- **List servers and channels** accessible with your token
- **Sync messages** from Discord to local Markdown files
- **Read and search** synced messages locally
- **Send messages** back to Discord channels
- **LLM-friendly format** optimized for Claude Code analysis

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get Your Discord Token

1. Open Discord in your web browser (discord.com)
2. Press F12 to open Developer Tools
3. Go to the Network tab
4. Perform any action in Discord (send message, switch channels)
5. Find any API request to `discord.com/api`
6. In Headers, copy the `Authorization` value

### 3. Configure

```bash
# Create .env with your token
echo 'DISCORD_USER_TOKEN=your_token_here' > .env

# Edit config/server.yaml with your server ID
# (use discord-list to find server IDs)
```

### 4. Use with Claude Code

Open Claude Code in this workspace:

```bash
cd workspace/claudecode-for-discord
claude
```

Then just ask naturally:
- "What Discord servers do I have?"
- "Sync messages from #general"
- "What's been discussed in #general?"
- "Search Discord for 'project update'"

## Manual Tool Usage

### List Servers

```bash
python tools/discord_list.py --servers
```

### List Channels

```bash
python tools/discord_list.py --channels SERVER_ID
```

### Sync Messages

```bash
# Sync all channels in configured server
python tools/discord_sync.py

# Sync specific channel
python tools/discord_sync.py --channel CHANNEL_ID

# Sync last 7 days
python tools/discord_sync.py --days 7
```

### Read Messages

```bash
# Read all messages
python tools/discord_read.py --channel general

# Read last 20 messages
python tools/discord_read.py --channel general --last 20

# Search for keyword
python tools/discord_read.py --channel general --search "project"
```

### Send Messages

```bash
# Send to channel
python tools/discord_send.py --channel CHANNEL_ID --message "Hello!"

# Reply to a message
python tools/discord_send.py --channel CHANNEL_ID --message "Reply" --reply-to MESSAGE_ID
```

## Data Storage

Messages are stored as Markdown files:

```
data/
└── {server_id}/
    ├── sync_state.yaml
    ├── server.yaml
    └── {channel_name}/
        ├── messages.md
        └── channel.yaml
```

## Message Format

Messages are formatted for easy LLM consumption:

```markdown
## 2026-01-03

### 10:30 AM - @alice (123456789)
Hello everyone!

### 10:31 AM - @bob (987654321)
↳ replying to @alice:
Hey Alice!
```

## License

MIT License - Use at your own risk.
