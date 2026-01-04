# Use Case 001: Multi-Server Message Summary

## Scenario

User follows multiple Discord servers and needs to quickly understand discussion highlights across communities, identifying conversations worth joining.

## User Needs

1. **Quickly grasp discussion dynamics across multiple servers**
2. **Identify discussions worth following up or participating in**
3. **Get direct jump links to relevant threads**

## Workflow

```
1. discord-sync  →  Sync messages from multiple servers
2. Read manifest.yaml  →  Get overview of all synced data
3. Read messages.md files  →  Analyze message content
4. Generate summary report  →  Categorize by server/topic
5. Provide discussion links  →  Enable direct participation
```

## Example Conversation

**User**: what messages worth me following up or joining discussion? give me couple of links

**Claude**: Analyzes synced messages, identifies:
- Unanswered technical questions
- Active discussion threads
- Valuable topics lacking responses

**User**: summarize all the messages

**Claude**: Generates structured summary by server:
- Main topic categories
- Key discussion points
- Community activity assessment
- Notable unanswered questions

## Real Case Study

### Input Data
- **Midjourney #discussion**: 861 messages
- **LimeWire #general**: 725 messages
- **Time range**: 2025-12-21 ~ 2026-01-04

### Output Summary

#### Midjourney (High-Value Community)
| Topic | Content |
|-------|---------|
| V8 Anticipation | No release date, expected Feb, improved text generation |
| Relax Mode Issues | Users formally complaining about non-functional feature |
| AI Video Workflow | DaVinci Resolve + Topaz Studio combo recommended |
| Unanswered Questions | Grokking research, UI design generation, AI upscalers |

#### LimeWire (Low-Value Community)
| Topic | Content |
|-------|---------|
| Community State | 2M+ members but almost no conversation |
| Reason | Discord image generation disabled, moved to website |
| Content Type | Mostly greetings, some nostalgia discussion |

### Identified Participation Opportunities

1. **Grokking Research Question** - Technical question with no meaningful response
   - `https://discord.com/channels/662267976984297473/938713143759216720`

2. **UI Design from Wireframes** - Practical question with no response
   - `https://discord.com/channels/662267976984297473/938713143759216720`

## Value Summary

- **Time saved**: 1500+ messages → 5-minute readable summary
- **Information density**: Filters noise, highlights valuable content
- **Actionable**: Provides direct participation links
- **Multi-language**: Can switch between Chinese/English output on demand

## Related Skills

- `discord-sync`: Sync messages
- `discord-read`: Read and search messages
- `discord-list`: View available servers and channels

---

*Recorded: 2026-01-04*
*Decision: User explicitly approved this use case value, documented as standard usage pattern*
