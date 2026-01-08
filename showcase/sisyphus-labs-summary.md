# Sisyphus Labs Community — Discord Summary

> **Generated:** 2026-01-07
> **Source:** Discord sync via community-agent-plugin
> **Messages analyzed:** 1,042 across 5 channels

---

## Overview

**Project:** Oh-My-OpenCode (OMO) — a multi-agent harness/plugin for OpenCode
**Maintainer:** @q_yeon_gyu_kim (Yeong-gyu Kim, Seoul)
**GitHub:** [code-yeongyu/oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode)

Oh-My-OpenCode orchestrates multiple specialized AI agents (Sisyphus, Oracle, Librarian, Explorer, etc.) to accomplish complex coding tasks that a single agent cannot handle alone.

---

## Recent Releases

| Version | Date | Highlights |
|---------|------|------------|
| **v2.14.0** | Jan 6 | BG task queue with concurrency limits, Exa websearch restored, Bun shell GC crash fix |
| **v2.13.1** | Jan 5 | `/refactor` command — AST-aware, LSP-powered refactoring with verification |
| **v2.13.0** | Jan 5 | Max reasoning effort mode, librarian → GLM 4.7 (token savings), slash command improvements |
| **v2.10.0** | Jan 1 | **Skill-embedded MCP**, built-in Playwright skill, recursive command loader |
| **v2.9.1** | Jan 1 | Skills usage improvements |

### v2.14.0 Highlights
- **Stability improvements**: Fixed Bun shell GC crash, session checks, token consumption, hook execution
- **Background Task Queue**: Concurrency limits for subscription-based services (default: 5)
- **Librarian optimization**: Reduced token usage by making searches conditional
- **Restored Exa websearch**: Web search MCP is back!

### v2.13.1 — The Refactor Command
```
/refactor "reconstruct Super big AuthService as Multiple services, after consulting with Oracle"
```
- Codebase understanding via parallel explore agents
- Deterministic planning with verification strategy
- LSP tools and AST-grep for precise transformations

### v2.10.0 — Skill-Embedded MCP
- Skills can embed MCP server configurations in YAML frontmatter
- Built-in Playwright skill for browser automation
- Recursive command loading from subdirectories

---

## Hot Topics & Common Issues

### 1. Webfetch is Broken (Critical)

The `webfetch` tool has **no token limit** — if it fetches 200k tokens, it crashes your session.

**Fix — add to your config:**
```json
{
  "tools": {
    "webfetch": false
  }
}
```

**Alternatives:**
- Use `exa` MCP for web search
- Use `github grep` for repository searching

---

### 2. Context Window / Compaction Issues

OpenCode compacts at 90-95% context (aggressive). If Sisyphus reads a big file near the limit, session crashes with "prompt too long" errors.

**Workarounds:**
- Manual `/compact` before big tasks
- `/export` conversation → start new session
- Tell Sisyphus session name to auto-continue

**Feature request:** Auto-handoff at 70% context (like AmpCode) — users implementing via tmux hooks

---

### 3. Model Switching Bug

Switching providers mid-session (Claude → Gemini → Claude) breaks the session.

**Solution:** Stick to one provider per session, or use subagents for different providers.

---

### 4. Antigravity Auth Plugin

Popular for accessing Claude models via Google AI credentials.

**Issues reported:**
- **Thinking-High mode** very slow (15+ sec between thinking rounds)
- Rate limits: ~5 hour refresh on Google AI Pro
- Double-thinking suspected (Google may not dedupe)

**User tip:** Use Flash models as explorers + Opus for final review to save tokens

---

### 5. Thinking-High Mode Performance

| Mode | Speed | Recommendation |
|------|-------|----------------|
| Thinking-High | Very slow (15+ sec/round) | Debugging/RCA only |
| Thinking-Medium | Moderate | General use |
| Regular | Fast | Quick tasks |

Community consensus: TH may not be worth the slowdown for building tasks.

---

## Recommended Configurations

### Power User Config (Multi-provider)
```json
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "google_auth": false,
  "agents": {
    "Sisyphus": { "model": "google/antigravity-claude-opus-4-5-thinking-high" },
    "oracle": { "model": "google/antigravity-claude-opus-4-5-thinking-high" },
    "librarian": { "model": "google/antigravity-claude-sonnet-4-5" },
    "explore": { "model": "google/antigravity-gemini-3-pro-high" },
    "frontend-ui-ux-engineer": { "model": "google/antigravity-gemini-3-pro-high" },
    "document-writer": { "model": "google/antigravity-claude-sonnet-4-5-thinking-medium" },
    "multimodal-looker": { "model": "google/antigravity-gemini-3-pro-high" }
  }
}
```

### Budget Config (Claude Pro only + Free models)
```json
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "google_auth": false,
  "agents": {
    "oracle": { "model": "anthropic/claude-opus-4-5" },
    "frontend-ui-ux-engineer": { "model": "google/antigravity-gemini-3-pro-high" },
    "document-writer": { "model": "google/antigravity-gemini-3-flash" },
    "multimodal-looker": { "model": "google/antigravity-gemini-3-flash" },
    "librarian": { "model": "google/antigravity-gemini-3-flash" },
    "explore": { "model": "google/antigravity-gemini-3-flash" }
  }
}
```

### Free Config (GLM 4.7)
```json
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "agents": {
    "Sisyphus": { "model": "zai-coding-plan/glm-4.7" },
    "librarian": { "model": "zai-coding-plan/glm-4.7" },
    "explore": { "model": "zai-coding-plan/glm-4.7" },
    "oracle": { "model": "zai-coding-plan/glm-4.7" }
  }
}
```

**Maintainer tip:** Use free GLM 4.7 or MiniMax for `explore` and `librarian` — saves tons of tokens while maintaining quality.

---

## Active Bug Reports

| Issue | Description | Status |
|-------|-------------|--------|
| [#412](https://github.com/code-yeongyu/oh-my-opencode/issues/412) | Ralph-loop gets stuck even when task completes | Open |
| Prompt too long | Usually webfetch related | Disable webfetch |
| Memory leak | Rising to 4GB after hours of use | Under investigation |
| Context destroyed | Unwanted continues after compaction | Known issue |
| Ripgrep spawn errors | During parallel exploration | Needs reproduction |

---

## Feature Requests & Community Tips

### Requested Features
1. **Notification system** — Sound alerts when tasks complete
2. **GitHub Copilot integration** — [PR #467](https://github.com/code-yeongyu/oh-my-opencode/pull/467)
3. **Auto-handoff** — Automatic session handoff at configurable context threshold

### Community Tips

**Anti-pattern detection prompt:**
```
Please review this repository for any engineering anti-patterns
and list them in a new file under \docs\ANTI-PATTERNS.md
```

**Explorer agent strategy:**
> "I have explorer agents (Flash models) spin up and propose different fixes. Then Opus just takes that output and reviews the codebase to figure out the best approach." — @jpjpjp9820

**Playwright testing:**
> "The new Playwright skill catches a lot of small flow issues you don't notice manually." — @duccp

---

## Tools & Integrations

### Built-in
- **Playwright skill** — Browser automation, web scraping, testing
- **Exa websearch** — Web search MCP (restored in v2.14.0)
- **Session management** — Continue from previous sessions

### Community Recommended
- [playwriter](https://github.com/remorses/playwriter) — Browser extension-based Playwright alternative
- [oracle](https://github.com/steipete/oracle) — GPT-5 Pro invocation with custom context
- [opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth) — Access Claude via Google AI credentials

---

## Key Community Members

| User | Role/Contribution |
|------|-------------------|
| @q_yeon_gyu_kim | Project maintainer |
| @kdcokenny | Active helper, config tips, webfetch fix discovery |
| @jpjpjp9820 | Power user, explorer agent strategies |
| @the_aneki | OpenSpec integration |
| @bcardarella | Bug reporter, compaction issues |
| @marcusrbrown | Antigravity/thinking-high analysis |

---

## Media Coverage

- **YouTube:** "Oh My OpenCode Is Actually Insane" — Multi-agent orchestration overview gaining traction

---

## Quick Start Checklist

- [ ] Install: `bunx oh-my-opencode`
- [ ] Disable webfetch in config
- [ ] Configure agents in `~/.config/opencode/oh-my-opencode.json`
- [ ] Set up model preferences (see configs above)
- [ ] Manual `/compact` before large tasks
- [ ] Consider Playwright skill for testing

---

## Key Takeaways

1. **Disable webfetch** — #1 cause of crashes
2. **Use GLM 4.7 free** for explore/librarian to save costs
3. **Manual /compact** before big tasks
4. **Thinking-High mode** is slow — consider medium or regular
5. **New /refactor command** is powerful for codebase restructuring
6. **Playwright skill** now built-in for browser automation
7. **Stick to one provider** per session to avoid switching bugs

---

*This summary was generated by analyzing Discord messages from the Sisyphus Labs Community server using the community-agent-plugin Discord sync feature.*
