# Discord Plugin for Claude Code

Sync, read, and analyze Discord messages directly from Claude Code.

## Install

```bash
claude plugin add https://github.com/lycfyi/community-agent-plugin
claude plugin install discord
```

## Skills

| Skill | Purpose |
|-------|---------|
| `/discord:init` | Initialize configuration from your Discord account |
| `/discord:list` | List accessible servers and channels |
| `/discord:sync` | Sync messages to local Markdown storage |
| `/discord:read` | Read and search synced messages |
| `/discord:send` | Send messages to Discord channels |
| `/discord:chat-summary` | AI-powered summary of Discord conversations |

## Setup

### 1. Get Your Discord Token

1. Open Discord in your browser (discord.com)
2. Press `F12` to open Developer Tools
3. Go to **Network** tab
4. Click anywhere in Discord
5. Find any request to `discord.com/api`
6. Copy the `Authorization` header value

### 2. Configure Your Project

Create a `.env` file in your project:

```
DISCORD_USER_TOKEN=your_token_here
```

### 3. Initialize

```
/discord:init
```

Or ask Claude naturally: "Set up Discord for this project"

## Usage

### Natural Language

Just talk to Claude:

- "What Discord servers do I have?"
- "Sync messages from #general"
- "What's been discussed in the last 3 days?"
- "Search for 'project update' in my Discord"
- "Summarize the key topics in #announcements"

### Commands

```
/discord:list              # See your servers
/discord:sync              # Pull latest messages
/discord:read              # View synced messages
/discord:chat-summary      # Get AI summary
```

## Data Storage

Messages sync to your project directory:

```
your-project/
├── .env                           # Your Discord token
├── config/server.yaml             # Server configuration
└── data/
    ├── manifest.yaml              # Index of all synced data
    └── {server-id}/
        ├── server.yaml            # Server metadata
        └── {channel}/
            ├── messages.md        # Message archive
            └── channel.yaml       # Channel metadata
```

Messages are stored in LLM-optimized Markdown format for easy analysis.

## Example Workflows

### Community Monitoring

```
> Sync messages from my top 3 servers for the last week
> Summarize the main topics and sentiment
> Are there any questions I should respond to?
```

### Research & Analysis

```
> What's the community saying about [topic]?
> Find all discussions about pricing changes
> Show me messages mentioning bugs or issues
```

### Catch Up Quickly

```
> I've been away for a week, summarize what I missed
> Any announcements I should know about?
```

## Requirements

- Python 3.11+
- Dependencies (installed automatically):
  - discord.py-self
  - pyyaml
  - python-dotenv
  - aiohttp

## Warning

Using a user token (self-bot) may violate Discord's Terms of Service. This tool is intended for:
- Personal archival and backup
- Private AI-assisted analysis
- Your own account only

Use at your own risk.

## License

MIT
