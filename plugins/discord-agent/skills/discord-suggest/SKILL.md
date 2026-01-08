---
name: discord-suggest
description: "Get recommended actions and suggestions for community management. Use when user wants ideas, next steps, or asks what they should do with their Discord community."
---

# Discord Suggest

Analyze synced Discord data and provide actionable recommendations for community managers or users wanting to learn more about their community.

## When to Use

- User asks "what should I do?" or "what's next?"
- User wants suggestions or recommendations for their community
- User asks for ideas or action items
- User wants to know what needs attention
- User asks about trending topics or hot discussions
- User wants to understand their own participation
- User asks "what's happening in my community?"

## How to Execute

### Step 1: Get the Manifest

First, understand what data is available:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_manifest.py
```

If no data exists, guide the user to sync first.

### Step 2: Read Recent Messages

Read the most active channels' `messages.md` files to analyze recent activity. Focus on channels with the most messages or most recent sync times.

```
Read: ./data/{server-dir}/{channel}/messages.md
```

### Step 3: Generate Suggestions

Analyze the data and provide suggestions in these four categories:

#### Category 1: Community Health

Look for:

- **Unanswered questions**: Messages ending with `?` that have no replies (no `↳ replying to` following them)
- **Stale discussions**: Channels with no activity in the last 3+ days
- **Low engagement**: Messages with 0 reactions in busy channels

#### Category 2: Trending Topics

Look for:

- **Repeated keywords**: Topics mentioned multiple times across messages
- **High-reaction messages**: Posts with many reactions (look for `Reactions:` lines)
- **Active threads**: Chains of replies on the same topic

#### Category 3: Personal Profile (if user asks)

Analyze the user's participation:

- Count their messages across channels
- Identify which channels they're most active in
- Find who they interact with most (reply patterns)

Note: User needs to provide their Discord username for this analysis.

#### Category 4: Data Freshness

Check manifest for:

- **Last sync times**: Flag channels not synced in 24+ hours
- **Low message counts**: Channels that may need fuller sync
- **Missing channels**: Compare to `discord-list` output if available

## Output Format

Present suggestions as an actionable checklist:

```markdown
## Suggested Actions

### Community Health

- [ ] Reply to @user123's question in #support about "API rate limits" (2 days old)
- [ ] #announcements has been quiet for 5 days - consider posting an update
- [ ] 3 unanswered questions in #help-forum

### Trending Topics

- "new release" - mentioned 8 times across #general and #announcements
- High engagement: "Welcome post" in #introductions (12 reactions)
- Active discussion: debugging tips in #dev-chat (15 messages today)

### Data Status

- Last sync: 3 hours ago
- Consider running `/discord-sync` to catch recent messages
```

## Customization

Users can request specific categories:

- "Just show me unanswered questions" → Focus on Community Health
- "What's trending?" → Focus on Trending Topics
- "How active am I?" → Focus on Personal Profile (requires username)
- "Is my data fresh?" → Focus on Data Status

## Prerequisites

- Messages must be synced first using `discord-sync`
- At least one server/channel should have data in `./data/`

## Limitations

- Only analyzes locally synced messages (not live Discord data)
- Personal profile analysis requires user to provide their Discord username
- Trending topic detection is based on keyword frequency, not semantic analysis

## Next Steps

After reviewing suggestions:

- Use `discord-read` to dive deeper into specific discussions
- Use `discord-send` to respond to unanswered questions
- Use `discord-sync` to refresh data before re-running suggestions
- Use `discord-chat-summary` for detailed summaries of trending topics
