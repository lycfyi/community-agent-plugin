# CLAUDE.md

Community management orchestrator and shared library.

## Overview

This plugin serves two purposes:

1. **Orchestrating Agent** - The `community-manager` agent coordinates cross-platform workflows across Discord and Telegram
2. **Shared Library** - Provides utilities used by all platform connectors

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   community-agent                        │
│                   (THE BRAIN)                            │
│                                                          │
│  Orchestrates cross-platform workflows using             │
│  platform connectors as "hands"                          │
└─────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
┌───────────────────┐              ┌───────────────────┐
│ discord-user-connector │              │telegram-connector │
│    (HANDS)        │              │    (HANDS)        │
└───────────────────┘              └───────────────────┘
```

## Available Agent

### community-manager

Cross-platform community management specialist.

**Invoke:** When user asks for cross-platform tasks like "sync all communities", "summarize activity everywhere", or "send announcement to all platforms".

**Capabilities:**
- Coordinates Discord and Telegram skills
- Synthesizes cross-platform insights
- Maintains consistent persona across platforms

## Available Skills

### community-patterns

Domain knowledge for community management. Automatically loaded when handling community-related tasks.

**Provides:**
- Healthy community indicators
- Warning signs to watch for
- Response and moderation guidelines
- Metric benchmarks

## Shared Library

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

### Bot Persona (`lib/persona.py`)
- `BotPersona` - Dataclass for bot identity (name, role, personality, tasks)
- `PERSONA_PRESETS` - Pre-configured personas (community_manager, friendly_helper, tech_expert)
- `select_persona_interactive()` - Interactive persona selection
- `get_persona_prompt()` - Generate LLM-ready prompt from persona

## Bot Persona

**IMPORTANT:** The agent has a configured persona stored in `config/agents.yaml`. Before generating responses or taking actions, load the persona context.

### Loading Persona

```bash
# Get persona as LLM prompt
python tools/persona_status.py --prompt

# Get persona as JSON
python tools/persona_status.py --json

# Human-readable output
python tools/persona_status.py
```

### Persona Fields
- **Name**: How the bot identifies itself
- **Role**: The bot's job/function
- **Personality**: Character traits and demeanor
- **Tasks**: What the bot is responsible for
- **Communication Style**: How the bot communicates
- **Background**: Context/backstory

## Bootstrap Ritual (First-Time Setup)

**When no persona is configured**, run an interactive conversation to help the user define their agent's identity. This is more engaging than just picking a preset.

### Detecting First Run

Check if persona is configured:

```bash
python tools/persona_status.py --json
```

If the output shows `"configured": false` or returns an error, initiate the bootstrap ritual.

### The Conversation

Start with a friendly introduction, then ask 3-5 questions to learn:

```
Hello! I'm setting up as your community management assistant.

Before I get started, I'd love to learn a bit about how you'd like me to operate:

1. **What should I call myself?**
   (e.g., "Alex", "Community Bot", or something fun like "Scout")

2. **What's my vibe?**
   - Professional & organized (formal tone, structured responses)
   - Friendly & casual (warm, conversational, uses emoji occasionally)
   - Technical & precise (data-driven, minimal fluff)

3. **Any specific style preferences?**
   - How should I sign messages? (name only, name + role, no signature)
   - Should I use bullet points or prose?
   - Any phrases or approaches to avoid?
```

### Writing the Persona

After gathering responses, write to `config/agents.yaml` using the config structure:

```yaml
persona:
  name: "<user's choice>"
  role: "Community Manager"
  personality: "<based on vibe choice>"
  communication_style: "<based on style preferences>"
  tasks:
    - "Monitor community health"
    - "Summarize conversations"
    - "Send messages on behalf of user"
  background: "Configured via bootstrap ritual on <date>"
  preset: "custom"
```

### Example Bootstrap Flow

**User runs:** `/community-status` (and no persona exists)

**Claude:**
> I notice you haven't set up a persona for me yet. I'd love to get to know how you'd like me to operate!
>
> First question: **What should I call myself?** I could be "Alex" (professional), "Scout" (friendly explorer), or whatever name feels right to you.

**User:** Let's go with Maya

**Claude:**
> Maya it is! Nice to meet you (as myself, I suppose).
>
> **What's my vibe?** Should I be:
> 1. Professional & organized
> 2. Friendly & casual
> 3. Technical & precise

**User:** Friendly but still professional

**Claude:**
> Got it - warm and approachable, but I won't overdo the emojis or get too casual.
>
> **Last question: Any style preferences?**
> - How should I sign messages? (e.g., "- Maya", "Maya, Community Manager", or no signature)
> - Bullet points or flowing prose?

**User:** Sign with just the name. Bullet points are fine.

**Claude:**
> Perfect! Here's who I am now:
>
> **Name:** Maya
> **Role:** Community Manager
> **Personality:** Friendly and professional - warm but organized
> **Style:** Bullet points, signs messages with "- Maya"
>
> I've saved this to `config/agents.yaml`. You can update it anytime with `/community-init --mode advanced`.
>
> Ready to help with your communities!

### When to Trigger Bootstrap

Trigger this ritual when:
- User runs `/community-status` and no persona exists
- User runs `/community-init` without `--persona` flag
- User explicitly asks "help me set up" or "configure the agent"

**Do NOT trigger** if:
- Persona already exists (offer to update instead)
- User ran with explicit preset (`--persona friendly_helper`)

## File Structure

```
community-agent/
├── .claude-plugin/plugin.json    # Plugin metadata
├── CLAUDE.md                     # This file
├── requirements.txt              # Python dependencies
├── agents/
│   └── community-manager.md      # Orchestrating agent definition
├── skills/
│   └── community-patterns/
│       └── SKILL.md              # Community management knowledge
├── lib/
│   ├── __init__.py               # Public exports
│   ├── config.py                 # CommunityConfig class
│   ├── persona.py                # Bot persona configuration
│   ├── profile.py                # User profile preferences
│   ├── storage_base.py           # Storage utilities
│   ├── markdown_base.py          # Formatting utilities
│   └── rate_limiter_base.py      # Timing utilities
└── tools/
    └── persona_status.py         # CLI tool to view/manage persona
```

## Usage by Platform Plugins

Platform plugins import from this library via symlink:

```python
# In discord-user-connector/lib/config.py
from community_agent.lib.config import (
    CommunityConfig,
    get_config,
)

# In telegram-connector/lib/storage.py
from community_agent.lib.storage_base import (
    ensure_dir,
    sanitize_name,
    slugify,
)
```

## Dependencies

- `pyyaml` - YAML config parsing
- `python-dotenv` - Environment variable loading

## For Developers

When adding new shared functionality:
1. Add to the appropriate `lib/*.py` file
2. Export in `lib/__init__.py`
3. Update this documentation
