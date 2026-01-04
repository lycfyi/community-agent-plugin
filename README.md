# Discord Sync for Claude Code

Let Claude Code read, analyze, and interact with your Discord communities.

## What This Does

Connect Claude Code to your Discord account so you can:

- **"What servers am I in?"** - Browse your Discord servers and channels
- **"Sync messages from #general"** - Pull Discord history to local storage
- **"What's been discussed this week?"** - Analyze conversations with AI
- **"Summarize the key topics in #announcements"** - Get insights from any channel
- **"Reply to that message"** - Send messages back to Discord

## Setup

### 1. Get Your Discord Token

1. Open Discord in your browser (discord.com)
2. Press `F12` to open Developer Tools
3. Go to **Network** tab
4. Click anywhere in Discord
5. Find any request to `discord.com/api`
6. Copy the `Authorization` header value

### 2. Configure

Create a `.env` file:
```
DISCORD_USER_TOKEN=your_token_here
```

### 3. Use with Claude Code

Just open Claude Code and ask naturally:

```
> What Discord servers do I have?
> List channels in Midjourney
> Sync the last 3 days from #discussion
> What are people talking about?
> Search for "API" in my Discord messages
```

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
> I've been away for a week, summarize what I missed in #general
> Any announcements I should know about?
```

## How It Works

Messages are synced to local Markdown files that Claude Code can read and analyze:

```
data/{server_id}/{channel_name}/messages.md
```

The format is optimized for LLM comprehension with timestamps, authors, replies, and reactions preserved.

## Important Warning

Using a user token may violate Discord's Terms of Service. This tool is for:
- Personal archival and backup
- Private AI-assisted analysis
- Your own account only

Use at your own risk.

## License

MIT
