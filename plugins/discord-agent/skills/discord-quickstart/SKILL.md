---
name: discord-quickstart
description: "Quick setup for Discord sync with smart defaults"
---

# Discord Quickstart

One-command setup that gets you from zero to synced Discord data. Uses your profile interests to recommend servers, or falls back to member count heuristics.

## When to Use

- User is new and asks to "set up Discord" or "get started"
- User asks for summary/read but has no data synced yet
- User says "quickstart" or "quick setup"
- User asks "help me sync Discord" without specifics
- Fallback when other skills detect empty state

## How to Execute

### Step 1: Check Current Status

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_status.py --json
```

Analyze the JSON output:
- If `token.configured` is false → Guide user to set up `.env`
- If `sync.has_data` is true → User already has data, skip to Step 4
- Otherwise → Continue to Step 2

### Step 2: Get Recommendations (if no data)

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_recommend.py --json
```

This analyzes the user's servers and returns:
- `recommended`: Servers matching profile interests/priority (sorted by relevance)
- `already_synced`: Servers that are already synced
- `total_servers`: How many servers they have access to
- `profile_configured`: Whether user has set up interests

### Step 3: Present One Confirmation

**CRITICAL: Ask only ONE question, not multiple.**

Present the recommendations naturally:

> "Based on your profile interests, I found these servers to sync:
> 1. [Server Name] (50K members) - matches: [keyword]
> 2. [Server Name] (23K members) - matches: [keyword]
>
> Want me to sync recent messages (last 7 days) from these? This takes about 2-3 minutes."

If no profile configured, say:
> "I found these active communities in your Discord. Want me to sync them?"

If user confirms → proceed to sync
If user wants different servers → let them specify, then sync those

### Step 4: Execute Sync

For each recommended server (or user-specified servers):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --server SERVER_ID --days 7
```

**Smart defaults applied:**
- 7 days of history (not overwhelming)
- Priority channels synced first (general, announcements)
- Max 5 channels per server initially

### Step 5: Show Summary

After sync completes, show what was synced:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_status.py
```

Then suggest next actions:
- "Your Discord is ready! Try `/discord-chat-summary` to see what's been happening."

## Smart Defaults Philosophy

**Reduce friction, not capability:**
- Sync 7 days by default (enough to be useful, not overwhelming)
- Prioritize AI/dev communities (what users likely care about)
- One confirmation, not a wizard with 5 questions
- Show progress, not just a spinner

**When user is vague, be smart:**
- "sync my Discord" → sync all recommended servers
- "those active ones" → pick top 3 by score
- "just Claude Developers" → sync only that one

## Example Flow

**User:** "help me summarize Discord"

**Claude checks status:** No data synced

**Claude runs recommend:** Found servers matching profile (or active communities if no profile)

**Claude responds:**
> "You don't have any Discord messages synced yet. Based on your interests, I recommend syncing:
> - [Server 1] (50K members) - matches: python
> - [Server 2] (23K members) - matches: automation
>
> Want me to sync the last 7 days from these? Takes about 2 minutes."

**User:** "yes"

**Claude syncs, then:**
> "Done! Synced 1,247 messages from 2 servers.
>
> Here's a quick summary: [proceeds to summarize]"

## Prerequisites

- `.env` with `DISCORD_USER_TOKEN`

## Anti-patterns to Avoid

- DON'T ask "which servers?" then "which channels?" then "how many days?"
- DON'T show a list of 37 servers and ask user to pick
- DON'T require config file before showing recommendations
- DON'T sync without any confirmation (respect user agency)
