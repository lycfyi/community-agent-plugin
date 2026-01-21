# Discord Member Feature Test Cases

**Version:** 1.4.0-rc5
**Feature:** Discord Member List & Profile (spec 013)
**Last Updated:** 2026-01-20

## Overview

Natural language test prompts for validating the Discord member management features. These prompts simulate real user requests and can be used for manual testing or demo purposes.

---

## Test Cases by Feature

### 1. Member Sync

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| SYNC-01 | "sync members from my discord server" | Runs Gateway sync, saves member list |
| SYNC-02 | "sync members and enrich profiles" | Sync + profile enrichment |

> **i18n variant:** "同步一下discord服务器的成员" (Chinese)

### 2. New Member Tracking

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| NEW-01 | "看下medeo discord社区今天新增了多少用户" | Shows members joined today |
| NEW-02 | "how many members joined this week?" | Lists new members (last 7 days) |
| NEW-03 | "show new members since January 15th 2026" | Date-filtered new member list |

### 3. Growth Statistics

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| GROWTH-01 | "show me the growth stats for the last month" | Daily join chart for 30 days |
| GROWTH-02 | "what's our member growth like?" | Weekly growth summary |

> **i18n variant:** "社区增长情况怎么样" (Chinese)

### 4. Silent Member Detection

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| SILENT-01 | "没发言的用户有统计到吗？我想要详细的用户名单" | Lists members who never posted |
| SILENT-02 | "list lurkers who joined over 30 days ago" | Silent + join date filter |

> **i18n variant:** Covered by SILENT-01

### 5. Engagement Analysis

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| ENGAGE-01 | "show me the engagement breakdown" | Tier distribution (champion/active/occasional/lurker/silent) |
| ENGAGE-02 | "which members are most active?" | Champion tier members |
| ENGAGE-03 | "list all lurkers" | Members with 1-4 messages |

### 6. Member Search (Fuzzy)

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| SEARCH-01 | "find members interested in gaming" | Fuzzy search on interests/roles |
| SEARCH-02 | "search for developers with moderator role" | Compound filter (role + keyword) |
| SEARCH-03 | "find active members who joined last month" | Engagement + date filter |

> **i18n variant:** "找一下对AI感兴趣的成员" (Chinese)

### 7. Churn Tracking

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| CHURN-01 | "who left the server recently?" | Churned members list |
| CHURN-02 | "show churned member summary" | Aggregate churn stats |
| CHURN-03 | "which departing members were actually active?" | Churned with activity data |

> **i18n variant:** "有多少人离开了服务器" (Chinese)

### 8. Member Profiles

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| PROFILE-01 | "show me the profile for user 123456789" | Single profile view |
| PROFILE-02 | "fetch rich profiles for 50 members" | Batch profile fetch |
| PROFILE-03 | "show unified profile with behavioral data" | Combined discord + behavioral view |

### 9. Data Export

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| EXPORT-01 | "export members to CSV" | CSV file in reports/ |
| EXPORT-02 | "export member list as markdown report" | MD report with stats |
| EXPORT-03 | "download member data as JSON" | JSON export |

---

## Prerequisites for Testing

1. **Member data synced**: Run `discord members sync --server <id>` first
2. **Message data synced**: Run `discord sync --server <id>` for engagement/silent detection
3. **Profiles enriched** (optional): Use `--enrich-profiles` flag for richer search

---

## Expected Output Locations

| Feature | Output Location |
|---------|-----------------|
| Member list | `data/discord/{server}/members/current.yaml` |
| Snapshots | `data/discord/{server}/members/snapshots/` |
| Churned | `data/discord/{server}/members/churned/` |
| Profiles | `profiles/discord/{user_id}_{slug}.yaml` |
| Exports | `reports/discord/exports/` |

---

## Notes

- All prompts should work with the default server if `default_server_id` is configured in `config/agents.yaml`
- Chinese prompts test internationalization readiness
- Compound queries (e.g., "active developers joined last month") test natural language parsing
- Deduped from 31 to 20 unique test cases (2026-01-20)
