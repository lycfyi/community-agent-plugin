---
name: discord-profile
description: "View and manage user profile - interests, preferences, and engagement patterns"
---

# Discord Profile

View and manage your user profile. The profile tracks your interests, watch keywords, engagement patterns, and activity history to improve recommendations and summaries.

## When to Use

- User asks "show my profile" or "what's my profile"
- User asks "what are my interests"
- User wants to "update my profile"
- User asks "add [topic] to my interests"
- User wants to reset or view their preferences

## How to Execute

### View Profile

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py
```

### View Specific Section

```bash
# Available sections: interests, keywords, engagement, activity, preferences, learned
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --section interests
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --section engagement
```

### Add Interest or Keyword

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --add-interest "kubernetes"
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --add-keyword "feature request"
```

### Set Profile Info

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --set-name "Alice"
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --set-role "developer"
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --set-style actionable
```

### Export as JSON

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --json
```

### Reset Profile

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/discord_profile.py --reset
```

## Profile Sections

| Section | Description |
|---------|-------------|
| Identity | Name and role |
| Interests | Topics extracted from your engagement |
| Watch Keywords | Keywords to highlight in messages |
| Preferences | Summary style, detail level, timezone |
| Engagement | Servers/channels you focus on, with scores |
| Activity | Recent actions (summaries, syncs, etc.) |
| Learned | Preferences inferred from interactions |

## Profile Location

The profile is stored at: `./config/profile.md` (relative to workspace cwd)

## How Profile is Updated

The profile is automatically updated:
- After generating chat summaries (learns engagement patterns)
- When you interact with specific servers/channels
- Topics and interests are extracted from your queries

You can also manually add interests and keywords using this skill.

## Example Output

```
User Profile
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Identity:
  Name: Alice
  Role: developer

Interests (8):
  • browser automation
  • python
  • api development
  ... and 5 more

Watch Keywords (3):
  bug, feature request, feedback

Preferences:
  Summary style: actionable
  Detail level: concise
  Timezone: UTC

Top Engagement:
  Claude Developers/#general: 85
  Browser Use/#help: 72
  Windsurf/#announcements: 45

Recent Activity (12 entries):
  2026-01-07 - summary: Claude Developers, last 7 days
  2026-01-05 - sync: Browser Use
  2026-01-03 - summary: All servers

Last updated: 2026-01-07T12:00:00Z
```

## Prerequisites

- Profile file at `./config/profile.md` (auto-created by discord-init or on first use)

## Next Steps

- Use `/discord-recommend` to see how profile affects server recommendations
- Use `/discord-chat-summary` to generate summaries and update profile automatically
