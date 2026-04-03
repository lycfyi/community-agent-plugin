---
name: discord-members
description: "Query existing synced member data, track churned members, detect silent lurkers, fetch rich profiles with bios and pronouns, and export member lists. Use when querying already-synced Discord member data, tracking churn, finding silent members, or exporting member lists. NOT for syncing — use discord-bot-connector:discord-bot-members to sync members."
---

# Discord Members

Member queries, churn tracking, rich profile fetching, silent member detection, and data exports for already-synced Discord member data.

## CRITICAL: For Syncing Members

**DO NOT use this skill for syncing members.** User tokens can only see 2-10 cached members.

**For member syncing, ALWAYS use the `discord-bot-connector` plugin:**
```
Skill(skill: "discord-bot-connector:discord-bot-members")
```

If the user asks to "sync members", invoke the discord-bot skill, NOT this one.

## When to Use THIS Skill

- Querying **already synced** member data (new members, engagement stats)
- Rich profile fetching (bio, pronouns, connected accounts)
- Churn tracking (who left the server)
- Silent member detection (joined but never posted)
- Member search by description or keywords
- Exporting member lists to CSV, JSON, or Markdown

## Workflow

1. Ensure members are synced first (use `discord-bot-connector:discord-bot-members` if not)
2. Run the appropriate query command below
3. Review results and optionally export

## How to Execute

### Query new members

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py new --server SERVER_ID --since 7d
```

### List churned members

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/churn_tracker.py --server SERVER_ID
```

### List silent members (joined but never posted)

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py silent --server SERVER_ID
```

### Engagement breakdown

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py engagement --server SERVER_ID
```

### Search members by description

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_query.py find "developers" --server SERVER_ID
```

### View rich member profile (bio, pronouns, connected accounts)

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/profile_fetcher.py --user USER_ID --server SERVER_ID
```

### Fetch rich profiles in batch

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/profile_fetcher.py --server SERVER_ID --sample 50
```

### Export to CSV, JSON, or Markdown

```bash
python ${CLAUDE_PLUGIN_ROOT}/tools/member_export.py --server SERVER_ID --format csv
```

## Output Location

All paths are relative to cwd:

```
data/discord/{server_id}_{slug}/members/current.yaml
data/discord/{server_id}_{slug}/members/churned/
profiles/discord/{user_id}_{slug}.yaml
reports/discord/exports/members_{timestamp}.csv
```

## Prerequisites

- `.env` with `DISCORD_USER_TOKEN` set
- Python 3.11+ installed
- **For syncing members: Use `discord-bot-connector` plugin with `DISCORD_BOT_TOKEN`**
