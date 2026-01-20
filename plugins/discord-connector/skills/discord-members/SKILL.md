---
name: discord-members
description: "Sync and manage Discord server member lists. Use when user asks about members, who joined, who left, or member profiles."
---

# Discord Members

Syncs and manages Discord server member lists, tracks new/churned members, and provides member profile management.

## When to Use

- User asks to "sync members" or "get member list"
- User asks "how many joined today" or "new members"
- User asks "who left" or "churned members"
- User asks about "silent members" or "inactive users"
- User wants to "find members" by description
- User wants to see a "member profile"
- User wants to "export members" to CSV/JSON

## Smart Defaults (Reduce Questions)

**When user is vague, apply these defaults instead of asking:**

| User Says | Default Action |
|-----------|----------------|
| "sync members" | Sync configured default server |
| "who joined recently" | Show new members from last 7 days |
| "who left" | Show churned members from all time |
| No --server specified | Use default_server_id from agents.yaml |

## How to Execute

All commands use Python scripts in the tools directory.

### Sync member list from server:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_sync.py --server SERVER_ID
```

### Sync with profile enrichment:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_sync.py --server SERVER_ID --enrich-profiles
```

### List new members (last 7 days):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py new --server SERVER_ID --since 7d
```

### List new members (custom range):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py new --server SERVER_ID --since 2026-01-15 --until 2026-01-20
```

### Show growth statistics:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py growth --server SERVER_ID --period week
```

### List churned members:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/churn_tracker.py --server SERVER_ID
```

### Churned members with activity:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/churn_tracker.py --server SERVER_ID --with-activity
```

### Churned member summary:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/churn_tracker.py --server SERVER_ID --summary
```

### List silent members (never posted):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py silent --server SERVER_ID
```

### Silent members who joined before a date:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py silent --server SERVER_ID --joined-before 30d
```

### Engagement breakdown (summary):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py engagement --server SERVER_ID
```

### List members in a specific engagement tier:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py engagement --server SERVER_ID --tier active --format table
```

### Search members by description (fuzzy search):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py find "gamers" --server SERVER_ID
```

### Search with filters:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py find "developers" --server SERVER_ID --role moderator --engagement active
```

### Natural language search:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py find "active developers joined last month" --server SERVER_ID
```

### View member profile:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/profile_fetcher.py --user USER_ID --server SERVER_ID
```

### View unified profile (with behavioral data):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/profile_fetcher.py --user USER_ID --server SERVER_ID --unified
```

### Fetch rich profiles (batch):

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/profile_fetcher.py --server SERVER_ID --sample 50
```

### Export to CSV:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_export.py --server SERVER_ID --format csv
```

### Export to JSON:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_export.py --server SERVER_ID --format json
```

### Export to Markdown:

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_export.py --server SERVER_ID --format md
```

## Output Location

All paths are relative to cwd (current working directory):

### Member Data

```
data/discord/{server_id}_{slug}/members/current.yaml    # Latest member list
data/discord/{server_id}_{slug}/members/snapshots/      # Historical snapshots
data/discord/{server_id}_{slug}/members/churned/        # Churned member records
data/discord/{server_id}_{slug}/members/sync_history.yaml
```

### Profile Data

```
profiles/discord/{user_id}_{slug}.yaml    # Unified member profiles
profiles/discord/index.yaml               # Profile index
```

### Exports

```
reports/discord/exports/members_{timestamp}.csv
reports/discord/exports/members_{timestamp}.json
reports/discord/exports/members_{timestamp}.md
```

## Prerequisites

- `.env` with `DISCORD_USER_TOKEN` or `DISCORD_BOT_TOKEN` set
- Python 3.11+ installed
- For rich profiles (bio, connected accounts): User Token required

## Notes

- Gateway API is used for full member list (supports 100k+ members)
- Bot Token can sync basic data; User Token adds bio, connected accounts
- Churn detection works by comparing consecutive sync snapshots
- Silent member detection requires message sync first (`discord-sync`)
