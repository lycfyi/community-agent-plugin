---
name: discord-chat-summary
description: "Summarize Discord chat messages across servers. Use when user asks for chat summary, digest, highlights, recap, or overview of Discord conversations."
---

# Discord Chat Summary

Generate summaries of synced Discord chat messages. Claude reads the message files directly and produces a concise summary of key discussions, topics, and activity.

## When to Use

- User asks for a summary of Discord chats
- User wants a digest or recap of Discord conversations
- User asks "what's been happening" in Discord
- User wants highlights from Discord channels
- User asks for an overview of Discord activity
- User wants to catch up on Discord messages

## Smart Defaults (Reduce Questions)

**When user is vague, apply these defaults instead of asking:**

| User Says | Default Action |
|-----------|----------------|
| "summarize Discord" | Summarize ALL synced data, last 7 days |
| "what's happening" | Same as above |
| "summarize [server name]" | All channels in that server, last 7 days |
| No time specified | Default to last 7 days |

**When NO data exists:**
1. Don't just say "no data found"
2. Run `/discord-quickstart` flow instead
3. Offer to sync recommended servers, then summarize

**Only ask for clarification when:**
- Multiple interpretations are equally valid
- User explicitly asks "which servers do I have?"

## How to Execute

### Step 0: Handle Empty State

First check if any data exists:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_status.py --json
```

If `sync.has_data` is false:
- DON'T just say "no data, run sync first"
- Instead, run the `/discord-quickstart` flow to help them sync
- Then proceed to summarize

### Step 1: Get the Manifest

Get the manifest to understand what data is available:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_manifest.py
```

This shows all synced servers, channels, message counts, and last sync times.

**CRITICAL PATH RESOLUTION:** All data paths shown in the manifest are relative to the **current working directory** (cwd) where Claude is running - NOT relative to this skill file or the plugin directory.

### Step 2: Determine Scope

Ask user or infer from their request which scope to summarize:

| Scope | Description |
|-------|-------------|
| All servers | Summarize across all synced servers |
| Specific server | Summarize all channels in one server |
| Specific channel | Summarize a single channel |

### Step 3: Read Messages

Read the relevant `messages.md` files based on scope:

**For all servers:**
```
Read each: ./data/{server-dir}/{channel}/messages.md
```

**For specific server (e.g., "Midjourney"):**
```
Read: ./data/662267976984297473-midjourney/*/messages.md
```

**For specific channel:**
```
Read: ./data/{server-dir}/{channel-name}/messages.md
```

### Step 4: Apply Time Filtering (Optional)

If user specifies a time range, filter messages by date headers in the markdown:

| User Request | Filter Logic |
|--------------|--------------|
| "last 7 days" | Only include messages under `## YYYY-MM-DD` headers from the past 7 days |
| "this week" | Messages from current week (Monday-Sunday) |
| "since Jan 1" | Messages from `## 2026-01-01` onwards |
| "yesterday" | Messages from yesterday's date only |

Date headers in messages.md look like: `## 2026-01-03`

### Step 5: Generate Summary

Produce a summary including:

- **Key topics**: Main subjects discussed
- **Active participants**: Most active users (by message count)
- **Notable discussions**: Important conversations or decisions
- **Questions asked**: Unanswered questions if relevant
- **Sentiment**: Overall tone (helpful, heated, casual, etc.)

### Step 6: Update User Profile

After generating the summary, update the user profile to track engagement and learn interests:

```bash
# Add engagement for servers/channels summarized
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --add-interest "TOPIC_FROM_SUMMARY"
```

Or programmatically via ProfileManager:
```python
from lib.profile import get_profile

profile = get_profile()
profile.learn_from_summary(
    servers=["Claude Developers"],      # Servers that were summarized
    channels=["general", "help"],       # Channels that were summarized
    topics=["API usage", "new features"]  # Key topics extracted from summary
)
```

This allows the profile to:
- Track which servers/channels user focuses on (engagement scores)
- Learn interests from topics discussed
- Log activity for future reference

## Example Usage

**User:** "Summarize the Discord chats from last week"

**Claude:**
1. Runs `python ${CLAUDE_PLUGIN_ROOT}/tools/discord_manifest.py` to list available servers
2. Reads all `messages.md` files from paths in manifest
3. Filters to only include `## 2025-12-27` through `## 2026-01-03`
4. Generates summary

**User:** "What's been happening in the Midjourney server?"

**Claude:**
1. Runs `python ${CLAUDE_PLUGIN_ROOT}/tools/discord_manifest.py`
2. Finds Midjourney server directory from manifest
3. Reads all channel messages.md files in that server
4. Generates server-wide summary

**User:** "Give me a quick digest of #general"

**Claude:**
1. Runs `python ${CLAUDE_PLUGIN_ROOT}/tools/discord_manifest.py` to find #general channel path
2. Reads that specific `messages.md`
3. Generates channel-focused summary

## Message Format Reference

Messages in `messages.md` are structured as:

```markdown
## 2026-01-03

### 4:12 AM - @username (user_id)
Message content here

### 4:30 AM - @another_user (user_id)
↳ replying to @username:
Reply content

Reactions: heart 2 | rocket 1
```

## Prerequisites

- Messages must be synced first using the `discord-sync` skill
- At least one server/channel should have data in `./data/` directory (relative to cwd)

## Limitations

- Only summarizes locally synced messages (not live Discord data)
- Cannot summarize messages not yet pulled via `discord-sync`
- Large message volumes may require focusing on specific channels or date ranges

## Next Steps

- Use `discord-sync` to pull fresh messages before summarizing
- Use `discord-read` to view full message details after identifying interesting discussions
