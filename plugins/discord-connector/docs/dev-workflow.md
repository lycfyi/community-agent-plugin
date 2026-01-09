# Discord Agent Rapid Development Workflow

## SpecStory → ClaudeCode Iteration Loop

An efficient skill development and optimization loop driven by real conversation data.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  SpecStory  │───▶│   Manual    │───▶│ ClaudeCode  │     │
│  │   Record    │    │ Calibration │    │  Analysis   │     │
│  └─────────────┘    └─────────────┘    └──────┬──────┘     │
│         ▲                                      │            │
│         │                                      │            │
│         │         ┌─────────────┐              │            │
│         └─────────│ Update Skill│◀─────────────┘            │
│                   │   Iterate   │                           │
│                   └─────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Step-by-Step Guide

### 1. Record Conversations with SpecStory

Use [SpecStory](https://specstory.com) to automatically record complete interaction history with Claude:

- All user inputs
- Claude's complete responses
- Tool calls and results
- Error messages and exceptions

**Why SpecStory?**

- Automatic capture, no manual copying needed
- Preserves full context
- Easy to review and analyze

### 2. Manual Calibration

Annotate the recorded conversations:

- ✅ Correct response - meets expectations
- ❌ Incorrect response - needs correction
- 💡 Expected response - what the ideal answer should be
- ⚠️ Edge case - scenarios requiring special handling

**Calibration Focus:**

- Did Claude correctly understand the user's intent?
- Was the chosen tool appropriate?
- Does the response format and content meet expectations?
- Are there missing features or scenarios?

### 3. Submit to ClaudeCode for Analysis

Submit the entire conversation history to ClaudeCode for analysis:

```
Please analyze this conversation history and identify:
1. Which skill definitions need optimization?
2. Are new skills needed?
3. Is the parameter design of existing tools reasonable?
4. What edge cases are not covered?
```

### 4. Skill Iteration

Based on ClaudeCode's analysis:

- Update descriptions and examples in `skills/*/SKILL.md`
- Optimize implementation logic in `tools/*.py`
- Add missing functionality
- Add edge case handling

## Best Practices

### Efficient Recording

1. **Scenario coverage**: Ensure conversations cover main use cases
2. **Edge testing**: Deliberately trigger edge cases
3. **Error recovery**: Test recovery capability in error scenarios

### High-Quality Calibration

1. **Timely annotation**: Calibrate immediately after conversation while memory is fresh
2. **Specific descriptions**: Clearly explain why a response is wrong and what's expected
3. **Priority sorting**: Fix high-impact issues first

### Effective Analysis

1. **Focus on issues**: Each analysis focuses on 1-2 topics
2. **Comparative verification**: Re-test the same scenarios after optimization
3. **Incremental iteration**: Small steps, frequent validation

## Example

### Identifying a Problem

```
User: Show me what Sisyphus Labs has been discussing recently
Claude: [calls discord_read] ... returned too many irrelevant messages

Calibration: ❌ Should first use discord_list to find the correct channel, then read
```

### Optimizing the Skill

Update `discord-read/SKILL.md`:

```markdown
## Usage Flow

1. If the user doesn't specify a channel, first use discord_list to list available channels
2. Select the most relevant channel based on user intent
3. Then call discord_read to fetch messages
```

## Related Files

- `skills/*/SKILL.md` - Skill definition files
- `tools/*.py` - Tool implementation code
- `CLAUDE.md` - Project overview
