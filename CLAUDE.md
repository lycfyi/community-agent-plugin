# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with Discord community data.

## Overview

This workspace contains tools for syncing and analyzing Discord messages using a user token. Messages are stored as Markdown files for easy reading and analysis.

## Available Skills

### discord-init
Initialize configuration from your Discord account.
- "Set up Discord"
- "Configure my Discord server"

### discord-list
List Discord servers and channels accessible with your token.
- "What Discord servers do I have?"
- "Show me channels in server X"

### discord-sync
Sync Discord messages to local Markdown files.
- "Sync my Discord messages"
- "Pull messages from #general"
- "Get Discord history from the last 7 days"

### discord-read
Read and search locally synced messages.
- "What's been discussed in #general?"
- "Search Discord for 'project update'"
- "Show me recent Discord messages"

### discord-send
Send messages to Discord channels (when implemented).
- "Reply to that Discord message"
- "Post in #general"

## Data Location

**Overview of all synced data:**
```
data/manifest.yaml
```

Messages are stored in:
```
data/{server_id}/{channel_name}/messages.md
```

Sync state is tracked in:
```
data/{server_id}/sync_state.yaml
```

Server/channel metadata:
```
data/{server_id}/server.yaml
data/{server_id}/{channel_name}/channel.yaml
```

The `manifest.yaml` provides a holistic view of all synced servers, channels, message counts, and quick-access paths.

## Configuration

1. **Token**: Set `DISCORD_USER_TOKEN` in `.env`
2. **Server**: Run `python tools/discord_init.py` to auto-configure (or manually edit `config/server.yaml`)

## Workflow

1. Use discord-init to auto-configure server (or discord-list to browse)
2. Use discord-sync to download messages
3. Read messages.md files or use discord-read tool
4. Use discord-send to respond (when needed)

## Message Format

Messages are stored in LLM-friendly Markdown format:

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

😀 3 | 👍 5
```

## Warning

Using a user token (self-bot) may violate Discord's Terms of Service. Use at your own risk for personal archival and analysis purposes only.
