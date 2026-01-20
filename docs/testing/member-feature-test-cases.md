# Discord Member Feature Test Cases

**Version:** 1.4.0-rc1
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
| SYNC-02 | "同步一下discord服务器的成员" | Same as above (Chinese) |
| SYNC-03 | "update the member list" | Triggers member sync |
| SYNC-04 | "sync members and enrich profiles" | Sync + profile enrichment |

### 2. New Member Tracking

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| NEW-01 | "看下medeo discord社区今天新增了多少用户" | Shows members joined today |
| NEW-02 | "how many members joined this week?" | Lists new members (last 7 days) |
| NEW-03 | "show new members since January 15th" | Date-filtered new member list |
| NEW-04 | "who joined recently?" | Default to last 7 days |

### 3. Growth Statistics

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| GROWTH-01 | "show me the growth stats for the last month" | Daily join chart for 30 days |
| GROWTH-02 | "what's our member growth like?" | Weekly growth summary |
| GROWTH-03 | "社区增长情况怎么样" | Growth stats (Chinese) |

### 4. Silent Member Detection

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| SILENT-01 | "没发言的用户有统计到吗？我想要详细的用户名单" | Lists members who never posted |
| SILENT-02 | "who are the silent members in my server?" | Silent member list with stats |
| SILENT-03 | "list lurkers who joined over 30 days ago" | Silent + join date filter |
| SILENT-04 | "find inactive users" | Silent member detection |

### 5. Engagement Analysis

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| ENGAGE-01 | "show me the engagement breakdown" | Tier distribution (champion/active/occasional/lurker/silent) |
| ENGAGE-02 | "which members are most active?" | Champion tier members |
| ENGAGE-03 | "list all lurkers" | Members with 1-4 messages |
| ENGAGE-04 | "how engaged is my community?" | Engagement summary stats |

### 6. Member Search (Fuzzy)

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| SEARCH-01 | "find members interested in gaming" | Fuzzy search on interests/roles |
| SEARCH-02 | "search for developers with moderator role" | Compound filter (role + keyword) |
| SEARCH-03 | "find active members who joined last month" | Engagement + date filter |
| SEARCH-04 | "找一下对AI感兴趣的成员" | Search (Chinese) |

### 7. Churn Tracking

| Test ID | Prompt | Expected Behavior |
|---------|--------|-------------------|
| CHURN-01 | "who left the server recently?" | Churned members list |
| CHURN-02 | "show churned member summary" | Aggregate churn stats |
| CHURN-03 | "which departing members were actually active?" | Churned with activity data |
| CHURN-04 | "有多少人离开了服务器" | Churn list (Chinese) |

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

## Real User Feedback Prompts

These prompts are extracted from actual user sessions (Luo, 2026-01-18):

### Chinese (Original)
```
看下medeo discord社区今天新增了多少用户
没发言的用户有统计到吗？我想要详细的用户名单
```

### English (Translated Intent)
```
Check how many new users joined the Medeo Discord community today
Do you have stats on users who haven't spoken? I want a detailed user list
```

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
