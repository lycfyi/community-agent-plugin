# Member Profile Management

Manage community member profiles to build persistent understanding of who community members are over time.

## When to Use

- User asks to "remember" something about a community member
- User wants to look up information about a specific member
- User asks "who is @username" or wants member context
- User wants to search for members with specific interests/skills
- User asks for a list of community members
- When building context for personalized responses to members
- After gathering profile-relevant information from chat activity

## Smart Defaults

| User Says | Default Action |
|-----------|----------------|
| "remember that @alice works in fintech" | Save observation to Alice's profile |
| "who is @bob" | Get Bob's profile and display |
| "who knows Python" | Search profiles for "python" |
| "list members" | List all profiles (default platform: discord) |

## Commands

### Save or Update a Profile

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py save \
  --platform discord \
  --member-id "123456789" \
  --name "Alice Smith" \
  --observation "Works at a fintech startup"
```

**Parameters:**
- `--platform`: Required. Platform identifier (`discord` or `telegram`)
- `--member-id`: Required. The member's platform-specific ID
- `--name`: Required for new profiles. Display name (max 100 chars)
- `--observation`: Optional. Initial observation to record
- `--notes`: Optional. Free-form notes about the member
- `--keywords`: Optional. Keywords for search (space-separated)
- `--json`: Optional. Output in JSON format

### Get a Profile

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py get \
  --platform discord \
  --member-id "123456789"
```

**Parameters:**
- `--platform`: Required. Platform identifier
- `--member-id`: Required. The member's ID
- `--json`: Optional. Output in JSON format

### Add an Observation

Use this to record new information learned about a member without needing to reload their full profile.

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py add-observation \
  --platform discord \
  --member-id "123456789" \
  --text "Interested in Python and machine learning"
```

**Parameters:**
- `--platform`: Required. Platform identifier
- `--member-id`: Required. The member's ID
- `--text`: Required. Observation text (max 500 chars)
- `--name`: Optional. Display name (required if profile doesn't exist yet)
- `--json`: Optional. Output in JSON format

### Search Profiles

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py search \
  --platform discord \
  --query "python developer" \
  --limit 20
```

**Parameters:**
- `--platform`: Required. Platform identifier
- `--query`: Required. Search query string
- `--limit`: Optional. Maximum results (default: 20)
- `--json`: Optional. Output in JSON format

### List All Profiles

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py list \
  --platform discord \
  --offset 0 \
  --limit 50
```

**Parameters:**
- `--platform`: Required. Platform identifier
- `--offset`: Optional. Skip first N profiles (default: 0)
- `--limit`: Optional. Maximum results (default: 50)
- `--json`: Optional. Output in JSON format

### Count Profiles

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py count \
  --platform discord
```

### Rebuild Index

Use if the index becomes corrupted or out of sync with profile files.

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py rebuild-index \
  --platform discord
```

## Profile Data Structure

Each profile contains:

| Field | Description |
|-------|-------------|
| `member_id` | Platform-specific unique identifier |
| `platform` | "discord" or "telegram" |
| `display_name` | Current display name |
| `first_seen` | When profile was created |
| `last_updated` | When profile was last modified |
| `observations` | Timestamped facts about the member (max 50) |
| `notes` | Free-form agent notes |
| `keywords` | Extracted keywords for search (max 10) |

## Storage Location

Profiles are stored in:
```
profiles/
├── discord/
│   ├── index.yaml          # Fast lookup index
│   └── {member_id}.yaml    # Individual profiles
└── telegram/
    ├── index.yaml
    └── {member_id}.yaml
```

## Examples

### Remember information about a member

When a user shares that "@alice works in fintech":

```bash
# First check if profile exists
python {{PLUGIN_DIR}}/tools/member_profile.py get \
  --platform discord \
  --member-id "123456789" \
  --json

# If exists, add observation:
python {{PLUGIN_DIR}}/tools/member_profile.py add-observation \
  --platform discord \
  --member-id "123456789" \
  --text "Works at a fintech startup"

# If new, create profile:
python {{PLUGIN_DIR}}/tools/member_profile.py save \
  --platform discord \
  --member-id "123456789" \
  --name "Alice" \
  --observation "Works at a fintech startup"
```

### Look up a member

When user asks "who is @bob":

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py get \
  --platform discord \
  --member-id "987654321" \
  --json
```

### Find members with specific skills

When user asks "who knows Python here":

```bash
python {{PLUGIN_DIR}}/tools/member_profile.py search \
  --platform discord \
  --query "python" \
  --json
```

## Limits

- **Observations**: Max 50 per profile (oldest trimmed automatically)
- **Keywords**: Max 10 per profile
- **Display name**: Max 100 characters
- **Observation text**: Max 500 characters
- **Notes**: Max 2000 characters
- **Profiles**: Supports up to 100,000 per platform

## Notes

- Profiles are **platform-scoped**: One profile per member per platform
- A member active in multiple Discord servers shares **one Discord profile**
- Observations are **append-only** - conflicting info is preserved with timestamps
- The index enables **fast search** without loading all profiles
- Use `--json` flag for programmatic access to output
