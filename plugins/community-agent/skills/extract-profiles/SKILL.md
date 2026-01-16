# Extract Member Profiles

Automatically extract member profiles from synced Discord/Telegram messages using heuristic classification.

## When to Use

- User asks to "extract profiles" or "build member profiles"
- User wants to "populate profiles from messages" or "analyze member activity"
- User asks to "create profiles from chat history"
- After syncing a server's messages for the first time
- When user wants to understand who's active in a community

## Smart Defaults

| User Says | Default Action |
|-----------|----------------|
| "extract profiles from TopMediai" | Extract from server 1092630146143506494 |
| "build member profiles" | Extract with incremental mode (only new messages) |
| "re-extract all profiles" | Extract with --full flag |
| "what would be extracted?" | Run with --dry-run |

## Commands

### Extract Profiles from Server

```bash
python {{PLUGIN_DIR}}/tools/extract_profiles.py extract \
  --server 1092630146143506494 \
  --platform discord
```

**Parameters:**
- `--server`: Required. Server ID (numeric portion only, e.g., "1092630146143506494")
- `--platform`: Optional. Platform identifier (`discord` or `telegram`). Default: discord
- `--full`: Optional. Process all messages (ignore incremental state)
- `--dry-run`: Optional. Show what would be extracted without saving
- `--min-messages`: Optional. Minimum messages to create a profile (default: 3)
- `--json`: Optional. Output in JSON format

### Check Extraction Status

```bash
python {{PLUGIN_DIR}}/tools/extract_profiles.py status \
  --server 1092630146143506494 \
  --platform discord
```

Shows:
- Last extraction timestamp
- Channels processed
- New messages since last extraction

### Reset Extraction State

```bash
python {{PLUGIN_DIR}}/tools/extract_profiles.py reset \
  --server 1092630146143506494 \
  --force
```

Resets the incremental state, causing full re-extraction on next run.

## How It Works

### Message Classification

The extractor classifies each message into types:

| Type | Detection Method | Example |
|------|------------------|---------|
| Question | Contains "?" or question words | "How do I use the API?" |
| Issue Report | Contains "not working", "error", "bug" | "Getting 500 error on webhooks" |
| Expertise | Reply containing code or solution | "Try using async/await here" |
| Introduction | In intro channel + "I'm a/I work" | "Hi, I'm a backend developer" |
| High Engagement | 5+ reactions | Popular posts |
| Feature Request | "would be nice", "please add" | "Could you add dark mode?" |
| Feedback | "love it", "great", or negative sentiment | "This tool is awesome!" |

### Generated Observations

Based on activity, the extractor generates observations like:

- `Active in #api-issues, #general (42 messages); topics: API, billing, webhook`
- `Self-intro: Hi everyone, I'm a backend developer working on...`
- `Asked 5 questions about: authentication, rate limits, pricing`
- `Reported issue: webhooks returning 500 error when...`
- `Helped others 3 times; expertise: OAuth, API integration`
- `Popular post (15 reactions): Tip: You can use...`

### Incremental Processing

The extractor tracks state per server:
- Remembers last processed date per channel
- Only processes new messages on subsequent runs
- Use `--full` to force complete re-extraction

## Examples

### First-time extraction for a server

```bash
# Check what data is available
python {{PLUGIN_DIR}}/tools/extract_profiles.py status \
  --server 1092630146143506494

# Do a dry run first
python {{PLUGIN_DIR}}/tools/extract_profiles.py extract \
  --server 1092630146143506494 \
  --dry-run

# If looks good, run for real
python {{PLUGIN_DIR}}/tools/extract_profiles.py extract \
  --server 1092630146143506494
```

### Re-extract after new messages synced

```bash
# Check for new messages
python {{PLUGIN_DIR}}/tools/extract_profiles.py status \
  --server 1092630146143506494

# Extract only new messages (default behavior)
python {{PLUGIN_DIR}}/tools/extract_profiles.py extract \
  --server 1092630146143506494
```

### Force full re-extraction

```bash
# Reset state first
python {{PLUGIN_DIR}}/tools/extract_profiles.py reset \
  --server 1092630146143506494 \
  --force

# Or use --full flag
python {{PLUGIN_DIR}}/tools/extract_profiles.py extract \
  --server 1092630146143506494 \
  --full
```

### Check created profiles

After extraction, use the member-profile skill to view profiles:

```bash
# List all profiles
python {{PLUGIN_DIR}}/tools/member_profile.py list --platform discord

# Get a specific profile
python {{PLUGIN_DIR}}/tools/member_profile.py get \
  --platform discord \
  --member-id 1349572197227827261
```

## Storage

### Extraction State

State is stored at:
```
profiles/{platform}/.extraction_state_{server_id}.yaml
```

### Profiles

Profiles are stored at:
```
profiles/{platform}/{member_id}.yaml
```

## Limits

- **Min messages**: Default 3 messages required to create a profile
- **Max observations per run**: 10 observations added per member per extraction
- **Profile observation limit**: 50 total (oldest trimmed automatically)

## Notes

- Extraction is **additive** - it adds observations to existing profiles
- Running extraction multiple times won't create duplicate observations
- Use `--dry-run` to preview changes before committing
- The `--full` flag reprocesses all messages but still adds to existing profiles
- To start fresh, delete the profile files manually before extracting
