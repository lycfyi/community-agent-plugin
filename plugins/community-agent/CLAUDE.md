# CLAUDE.md

Core library for community agent plugins.

## Overview

This is a **library plugin** that provides shared utilities for platform-specific community agent plugins (Discord, Telegram, etc). It does not contain any skills itself.

## What This Library Provides

### Configuration (`lib/config.py`)
- `CommunityConfig` - Unified config management for all platforms
- Loads from `config/agents.yaml` with platform-specific sections
- Environment variable loading for credentials (`.env`)

### Storage Utilities (`lib/storage_base.py`)
- `ensure_dir()` - Create directories
- `sanitize_name()` - Clean names for filesystem
- `slugify()` - URL-friendly slugs
- `parse_last_n_messages()` - Extract last N messages from markdown
- `search_message_blocks()` - Keyword search in markdown messages

### Markdown Formatting (`lib/markdown_base.py`)
- `format_reply_indicator()` - "↳ replying to @user:"
- `format_date_header()` - "## YYYY-MM-DD"
- `group_messages_by_date()` - Group messages by date
- `format_size_bytes()` - Human-readable file sizes

### Rate Limiting (`lib/rate_limiter_base.py`)
- `format_duration()` - Human-readable durations
- `estimate_sync_time()` - ETA calculations

## Usage by Platform Plugins

Platform plugins (discord-only, telegram-only) import from this library via symlink:

```python
# In discord-only/lib/config.py
from community_agent.lib.config import (
    CommunityConfig,
    get_config,
)

# In telegram-only/lib/storage.py
from community_agent.lib.storage_base import (
    ensure_dir,
    sanitize_name,
    slugify,
)
```

## File Structure

```
community-agent/
├── .claude-plugin/plugin.json    # Plugin metadata
├── CLAUDE.md                     # This file
├── requirements.txt              # Python dependencies
└── lib/
    ├── __init__.py               # Public exports
    ├── config.py                 # CommunityConfig class
    ├── storage_base.py           # Storage utilities
    ├── markdown_base.py          # Formatting utilities
    └── rate_limiter_base.py      # Timing utilities
```

## Dependencies

- `pyyaml` - YAML config parsing
- `python-dotenv` - Environment variable loading

## For Developers

When adding new shared functionality:
1. Add to the appropriate `lib/*.py` file
2. Export in `lib/__init__.py`
3. Update this documentation
