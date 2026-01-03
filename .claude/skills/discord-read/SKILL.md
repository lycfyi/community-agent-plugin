---
name: discord-read
description: "Read and analyze stored Discord messages. Use for: (1) View channel messages (2) Search content (3) Analyze discussions. Triggers: discord read, read discord, analyze discord"
---

# Discord Read - Message Analysis

Read locally stored Discord messages for analysis.

## Data Location

```
/Users/velocity1/codebase/claudecode-for-discord/data/1455977506891890753/
```

## Usage

### Read Channel Messages

Use Read tool on:
- `data/1455977506891890753/general/messages.md`
- `data/1455977506891890753/test-dubbing/messages.md`

### Search Messages

Use Grep tool:
- Pattern: `keyword` or `@username`
- Path: `data/`

### Check Sync State

Read `data/1455977506891890753/sync_state.json` to see:
- Message counts per channel
- Last sync time
- Whether re-sync is needed

## Workflow

1. Check `sync_state.json` for data freshness
2. If stale (>1 hour), suggest `/discord-pull`
3. Read relevant channel `messages.md`
4. Use Grep for keyword search
5. Summarize findings

## Available Channels

- general
- test-dubbing
- test-xbc
- test-dubbing-admin
- e2e-test-pressure_test_v2
