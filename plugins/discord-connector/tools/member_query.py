#!/usr/bin/env python3
"""
Discord member query tool.

Query synced member data for new members, growth stats, silent members, and engagement analysis.

Usage:
    python member_query.py new --server SERVER_ID --since 7d
    python member_query.py growth --server SERVER_ID --period week
    python member_query.py silent --server SERVER_ID
    python member_query.py engagement --server SERVER_ID
    python member_query.py find "search query" --server SERVER_ID
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_storage import get_member_storage
from lib.profile_index import get_profile_manager
from lib.fuzzy_search import (
    FuzzySearchEngine,
    SearchQuery,
    SearchResult,
    search_basic_members,
)
from lib.analytics.parser import MessageParser
from lib.member_models import EngagementTier


def get_message_author_counts(server_id: str, data_dir: str = "./data") -> dict[str, int]:
    """
    Extract message counts per author from synced messages.

    Args:
        server_id: Discord server ID
        data_dir: Base data directory

    Returns:
        Dict mapping author_id to message count
    """
    from lib.storage import Storage

    storage = Storage(base_dir=Path(data_dir))
    parser = MessageParser()

    author_counts: dict[str, int] = {}

    # Get server directory - search in the servers directory for matching server_id
    servers_dir = storage._servers_dir
    if not servers_dir.exists():
        return author_counts

    # Find server directory (may have slug suffix like {server_id}-{name})
    server_dir = None
    for candidate in servers_dir.iterdir():
        if candidate.is_dir() and candidate.name.startswith(server_id):
            server_dir = candidate
            break

    if not server_dir or not server_dir.exists():
        return author_counts

    # Find all messages.md files
    for messages_file in server_dir.rglob("messages.md"):
        try:
            channel_name = messages_file.parent.name
            for msg in parser.parse_file(messages_file, channel_name):
                author_id = msg.author_id
                author_counts[author_id] = author_counts.get(author_id, 0) + 1
        except Exception:
            # Skip files that can't be parsed
            continue

    return author_counts


def calculate_engagement_tier(message_count: int, has_mod_role: bool = False) -> EngagementTier:
    """
    Calculate engagement tier based on message count.

    Tiers:
    - Champion: 100+ messages OR moderator role
    - Active: 21-100 messages
    - Occasional: 5-20 messages
    - Lurker: 1-4 messages
    - Silent: 0 messages
    """
    if has_mod_role or message_count >= 100:
        return EngagementTier.CHAMPION
    elif message_count >= 21:
        return EngagementTier.ACTIVE
    elif message_count >= 5:
        return EngagementTier.OCCASIONAL
    elif message_count >= 1:
        return EngagementTier.LURKER
    else:
        return EngagementTier.SILENT


def parse_date_string(date_str: str) -> datetime:
    """
    Parse a date string into a datetime.

    Supports:
    - "today", "yesterday"
    - "7d", "30d" (days ago)
    - ISO date format "2026-01-15"
    """
    date_str = date_str.lower().strip()

    now = datetime.now(timezone.utc)

    if date_str == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_str == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_str.endswith("d"):
        # Parse "7d", "30d" etc.
        try:
            days = int(date_str[:-1])
            return now - timedelta(days=days)
        except ValueError:
            pass

    # Try ISO format
    try:
        # Try with time
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    try:
        # Try date only
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"Cannot parse date: {date_str}")


def format_table(headers: list[str], rows: list[list], max_width: int = 100) -> str:
    """Format data as an ASCII table."""
    if not rows:
        return ""

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    # Build table
    lines = []

    # Header
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines.append(header_line)

    # Separator
    sep_line = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    lines.append(sep_line)

    # Rows
    for row in rows:
        row_line = "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)) + " |"
        lines.append(row_line)

    return "\n".join(lines)


def cmd_new_members(args) -> int:
    """List members who joined within a date range."""
    storage = get_member_storage(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        print("Run 'discord members sync' first.", file=sys.stderr)
        return 1

    # Parse dates
    try:
        since = parse_date_string(args.since)
    except ValueError as e:
        print(f"Error parsing --since: {e}", file=sys.stderr)
        return 1

    until = datetime.now(timezone.utc)
    if args.until:
        try:
            until = parse_date_string(args.until)
        except ValueError as e:
            print(f"Error parsing --until: {e}", file=sys.stderr)
            return 1

    # Filter members by join date
    new_members = []
    for member in current.members:
        if member.joined_at and since <= member.joined_at <= until:
            new_members.append(member)

    # Sort by join date (newest first)
    new_members.sort(key=lambda m: m.joined_at or datetime.min, reverse=True)

    # Limit results
    if args.limit:
        new_members = new_members[:args.limit]

    # Format output
    since_str = since.strftime("%Y-%m-%d")
    until_str = until.strftime("%Y-%m-%d")

    if args.format == "json":
        output = {
            "server_id": args.server,
            "server_name": current.server_name,
            "period": {
                "since": since.isoformat(),
                "until": until.isoformat(),
            },
            "total_count": len(new_members),
            "members": [
                {
                    "user_id": m.user_id,
                    "username": m.username,
                    "display_name": m.display_name,
                    "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    "roles": m.roles,
                }
                for m in new_members
            ]
        }
        print(json.dumps(output, indent=2))
    elif args.format == "csv":
        print("user_id,username,display_name,joined_at,roles")
        for m in new_members:
            roles_str = ";".join(m.roles)
            joined = m.joined_at.isoformat() if m.joined_at else ""
            print(f"{m.user_id},{m.username},{m.display_name},{joined},{roles_str}")
    else:
        # Table format
        print(f"New members in {current.server_name} since {since_str}")
        print()
        print(f"Total: {len(new_members)} new members")
        print()

        if new_members:
            headers = ["#", "Username", "Display Name", "Joined At", "Roles"]
            rows = []
            for i, m in enumerate(new_members[:50], 1):  # Limit table display
                joined = m.joined_at.strftime("%Y-%m-%d %H:%M") if m.joined_at else "-"
                roles = ", ".join(m.roles[:3]) + ("..." if len(m.roles) > 3 else "")
                rows.append([i, m.username, m.display_name, joined, roles])

            print(format_table(headers, rows))

            if len(new_members) > 50:
                print(f"\n... and {len(new_members) - 50} more (use --format json for full list)")
        else:
            print("No new members in this period.")

    return 0


def cmd_growth(args) -> int:
    """Show member join statistics over time."""
    storage = get_member_storage(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        return 1

    # Determine period
    now = datetime.now(timezone.utc)
    period_days = {
        "day": 1,
        "week": 7,
        "month": 30,
        "year": 365,
    }.get(args.period, 7)

    start_date = now - timedelta(days=period_days)

    # Group members by join date
    daily_joins = {}
    for member in current.members:
        if member.joined_at and member.joined_at >= start_date:
            date_key = member.joined_at.strftime("%Y-%m-%d")
            daily_joins[date_key] = daily_joins.get(date_key, 0) + 1

    # Generate all dates in range
    dates = []
    current_date = start_date
    while current_date <= now:
        date_key = current_date.strftime("%Y-%m-%d")
        dates.append((date_key, daily_joins.get(date_key, 0)))
        current_date += timedelta(days=1)

    if args.format == "json":
        output = {
            "server_id": args.server,
            "server_name": current.server_name,
            "period": args.period,
            "daily_joins": [{"date": d, "count": c} for d, c in dates],
            "total": sum(c for _, c in dates),
            "average": sum(c for _, c in dates) / len(dates) if dates else 0,
        }
        print(json.dumps(output, indent=2))
    elif args.format == "table":
        print(f"Member growth for {current.server_name} (last {period_days} days)")
        print()

        headers = ["Date", "Joins"]
        rows = [[d, c] for d, c in dates]
        print(format_table(headers, rows))

        total = sum(c for _, c in dates)
        avg = total / len(dates) if dates else 0
        print(f"\nTotal: {total} new members")
        print(f"Average: {avg:.1f}/day")
    else:
        # Chart format
        print(f"Member growth for {current.server_name} (last {period_days} days)")
        print()
        print("Daily joins:")

        max_count = max(c for _, c in dates) if dates else 1
        bar_width = 40

        for date_str, count in dates:
            bar_length = int((count / max_count) * bar_width) if max_count > 0 else 0
            bar = '=' * bar_length
            day_name = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %Y-%m-%d")
            print(f"  {day_name}: {bar} {count}")

        total = sum(c for _, c in dates)
        avg = total / len(dates) if dates else 0
        peak_date, peak_count = max(dates, key=lambda x: x[1]) if dates else ("N/A", 0)

        print()
        print(f"Total: {total} new members this {args.period}")
        print(f"Average: {avg:.1f}/day")
        print(f"Peak: {peak_date} ({peak_count} joins)")

    return 0


def cmd_silent(args) -> int:
    """List members who have never posted a message."""
    storage = get_member_storage(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        return 1

    # Get message author counts
    author_counts = get_message_author_counts(args.server, args.data_dir)

    if not author_counts:
        print(f"Silent members in {current.server_name}")
        print()
        print("Note: No synced messages found. Run 'discord sync' to sync messages first.")
        print("Without message data, all members appear silent.")
        print()
        print(f"Total members: {current.member_count:,}")
        return 0

    # Find members who have never posted
    author_ids = set(author_counts.keys())
    silent_members = []

    for member in current.members:
        if member.is_bot:
            continue

        if member.user_id not in author_ids:
            # Apply joined_before filter if specified
            if args.joined_before:
                try:
                    cutoff = parse_date_string(args.joined_before)
                    if member.joined_at and member.joined_at > cutoff:
                        continue
                except ValueError:
                    pass

            silent_members.append(member)

    # Sort by join date (oldest first - these are "persistent lurkers")
    silent_members.sort(key=lambda m: m.joined_at or datetime.min)

    # Limit results
    if args.limit:
        silent_members = silent_members[:args.limit]

    # Calculate stats
    total_humans = sum(1 for m in current.members if not m.is_bot)
    silent_count = len(silent_members)
    silent_pct = (silent_count / total_humans * 100) if total_humans > 0 else 0

    if args.format == "json":
        output = {
            "server_id": args.server,
            "server_name": current.server_name,
            "total_members": total_humans,
            "silent_count": silent_count,
            "silent_percentage": round(silent_pct, 1),
            "members": [
                {
                    "user_id": m.user_id,
                    "username": m.username,
                    "display_name": m.display_name,
                    "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    "tenure_days": m.tenure_days,
                    "roles": m.roles,
                }
                for m in silent_members
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"Silent members in {current.server_name}")
        print()
        print(f"Total human members: {total_humans:,}")
        print(f"Never posted: {silent_count:,} ({silent_pct:.1f}%)")
        print(f"Active posters: {len(author_ids):,}")
        print()

        if silent_members:
            headers = ["#", "Username", "Joined", "Tenure", "Roles"]
            rows = []
            for i, m in enumerate(silent_members[:50], 1):
                joined = m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "-"
                tenure = f"{m.tenure_days}d"
                roles = ", ".join(m.roles[:2]) + ("..." if len(m.roles) > 2 else "")
                rows.append([i, m.username, joined, tenure, roles])

            print(format_table(headers, rows))

            if len(silent_members) > 50:
                print(f"\n... and {len(silent_members) - 50} more")
        else:
            print("No silent members found (everyone has posted at least once!).")

    return 0


def cmd_engagement(args) -> int:
    """Show engagement breakdown by tier."""
    storage = get_member_storage(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        return 1

    # Get message author counts
    author_counts = get_message_author_counts(args.server, args.data_dir)

    # Define moderator keywords
    mod_keywords = ["moderator", "mod", "admin", "staff", "owner"]

    def has_mod_role(roles: list[str]) -> bool:
        for role in roles:
            if any(kw in role.lower() for kw in mod_keywords):
                return True
        return False

    # Calculate engagement tiers for all human members
    tier_counts: dict[EngagementTier, int] = {tier: 0 for tier in EngagementTier}
    tier_members: dict[EngagementTier, list] = {tier: [] for tier in EngagementTier}

    for member in current.members:
        if member.is_bot:
            continue

        msg_count = author_counts.get(member.user_id, 0)
        is_mod = has_mod_role(member.roles)
        tier = calculate_engagement_tier(msg_count, is_mod)

        tier_counts[tier] += 1
        tier_members[tier].append((member, msg_count))

    total_humans = sum(tier_counts.values())

    # Filter by tier if specified
    if args.tier:
        try:
            filter_tier = EngagementTier(args.tier.lower())
        except ValueError:
            print(f"Error: Invalid tier '{args.tier}'", file=sys.stderr)
            return 1
    else:
        filter_tier = None

    if args.format == "json":
        output = {
            "server_id": args.server,
            "server_name": current.server_name,
            "total_members": total_humans,
            "breakdown": {
                tier.value: {
                    "count": tier_counts[tier],
                    "percentage": round(tier_counts[tier] / total_humans * 100, 1) if total_humans > 0 else 0,
                }
                for tier in EngagementTier
            },
            "tier_thresholds": {
                "champion": "100+ messages or moderator role",
                "active": "21-100 messages",
                "occasional": "5-20 messages",
                "lurker": "1-4 messages",
                "silent": "0 messages",
            }
        }

        # Include member list if filtering by tier
        if filter_tier:
            output["filtered_tier"] = filter_tier.value
            output["members"] = [
                {
                    "user_id": m.user_id,
                    "username": m.username,
                    "message_count": msg_count,
                }
                for m, msg_count in tier_members[filter_tier][:100]
            ]

        print(json.dumps(output, indent=2))
    elif args.format == "table" and filter_tier:
        # Show members in the specified tier
        members_list = tier_members[filter_tier]
        members_list.sort(key=lambda x: x[1], reverse=True)  # Sort by message count

        print(f"Members with '{filter_tier.value}' engagement in {current.server_name}")
        print()
        print(f"Total: {len(members_list):,} members")
        print()

        if members_list:
            headers = ["#", "Username", "Messages", "Joined"]
            rows = []
            for i, (m, msg_count) in enumerate(members_list[:50], 1):
                joined = m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "-"
                rows.append([i, m.username, msg_count, joined])

            print(format_table(headers, rows))

            if len(members_list) > 50:
                print(f"\n... and {len(members_list) - 50} more")
    else:
        # Summary format
        print(f"Engagement breakdown for {current.server_name}")
        print()
        print(f"Total human members: {total_humans:,}")
        print()

        if not author_counts:
            print("Note: No synced messages found. Run 'discord sync' first.")
            print("Without message data, all members appear as 'silent'.")
            print()

        # Show tier breakdown
        headers = ["Tier", "Count", "Percentage", "Threshold"]
        rows = []
        thresholds = {
            EngagementTier.CHAMPION: "100+ msgs or mod",
            EngagementTier.ACTIVE: "21-100 msgs",
            EngagementTier.OCCASIONAL: "5-20 msgs",
            EngagementTier.LURKER: "1-4 msgs",
            EngagementTier.SILENT: "0 msgs",
        }

        for tier in EngagementTier:
            count = tier_counts[tier]
            pct = (count / total_humans * 100) if total_humans > 0 else 0
            rows.append([tier.value.title(), count, f"{pct:.1f}%", thresholds[tier]])

        print(format_table(headers, rows))
        print()
        print("Use --tier <tier_name> to list members in a specific tier.")

    return 0


def cmd_find(args) -> int:
    """Search members by description using fuzzy matching."""
    storage = get_member_storage(args.data_dir)
    profile_manager = get_profile_manager(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        return 1

    # Parse query with filters
    search_query = SearchQuery.from_natural_language(args.query)
    search_query.max_results = args.limit

    # Apply explicit filters from args
    if args.role:
        search_query.role_filter = args.role
    if args.joined_since:
        try:
            search_query.joined_since = parse_date_string(args.joined_since)
        except ValueError as e:
            print(f"Error parsing --joined-since: {e}", file=sys.stderr)
            return 1
    if args.engagement:
        search_query.engagement_tier = args.engagement

    # Try profile-based search first (richer data)
    profiles = profile_manager.list_all_profiles()

    if profiles:
        # Use profile-based fuzzy search
        engine = FuzzySearchEngine(profiles)
        results: list[SearchResult] = engine.search(search_query)

        if args.format == "json":
            output = {
                "server_id": args.server,
                "query": args.query,
                "filters": {
                    "role": search_query.role_filter,
                    "joined_since": search_query.joined_since.isoformat() if search_query.joined_since else None,
                    "engagement": search_query.engagement_tier,
                },
                "total_count": len(results),
                "search_type": "profile",
                "members": [
                    {
                        "user_id": r.profile.user_id,
                        "username": r.profile.username,
                        "display_name": r.profile.display_name,
                        "relevance_score": round(r.relevance_score, 1),
                        "match_reasons": [str(m) for m in r.match_reasons[:3]],
                        "engagement_tier": r.profile.derived_insights.engagement_tier.value,
                        "value_score": r.profile.derived_insights.member_value_score,
                    }
                    for r in results
                ]
            }
            print(json.dumps(output, indent=2))
        else:
            _print_profile_results(results, args.query, current.server_name, search_query)
    else:
        # Fallback to basic member search
        matches = search_basic_members(
            members=current.members,
            query=args.query,
            max_results=args.limit,
        )

        if args.format == "json":
            output = {
                "server_id": args.server,
                "query": args.query,
                "total_count": len(matches),
                "search_type": "basic",
                "members": [
                    {
                        "user_id": m.user_id,
                        "username": m.username,
                        "display_name": m.display_name,
                        "match_score": round(score, 1),
                        "match_reasons": reasons,
                    }
                    for m, score, reasons in matches
                ]
            }
            print(json.dumps(output, indent=2))
        else:
            _print_basic_results(matches, args.query, current.server_name)

    return 0


def _print_profile_results(
    results: list[SearchResult],
    query: str,
    server_name: str,
    search_query: SearchQuery
) -> None:
    """Pretty print profile search results."""
    print(f"Search results for \"{query}\" in {server_name}")
    print()

    # Show active filters
    filters = []
    if search_query.role_filter:
        filters.append(f"role:{search_query.role_filter}")
    if search_query.engagement_tier:
        filters.append(f"tier:{search_query.engagement_tier}")
    if search_query.joined_since:
        filters.append(f"joined after:{search_query.joined_since.strftime('%Y-%m-%d')}")

    if filters:
        print(f"Filters: {', '.join(filters)}")
        print()

    print(f"Found {len(results)} matching members (profile search)")
    print()

    if results:
        headers = ["#", "Username", "Match Reason", "Score", "Tier"]
        rows = []
        for i, r in enumerate(results[:20], 1):
            # Get top match reason
            if r.match_reasons:
                top_reason = r.top_match_reason
                reason_str = f"{top_reason.field.value}: {top_reason.matched_term}" if top_reason else "-"
            else:
                reason_str = "filter match"

            tier = r.profile.derived_insights.engagement_tier.value[:3].title()
            rows.append([i, r.profile.username, reason_str, f"{r.relevance_score:.0f}", tier])

        print(format_table(headers, rows))

        if len(results) > 20:
            print(f"\n... and {len(results) - 20} more")
    else:
        print("No matches found.")
        print("\nTip: Try searching for:")
        print("  - Keywords like 'gamers', 'developers', 'artists'")
        print("  - Role names: 'moderator', 'admin'")
        print("  - Compound queries: 'active developers joined last month'")


def _print_basic_results(
    matches: list[tuple],
    query: str,
    server_name: str
) -> None:
    """Pretty print basic member search results."""
    print(f"Search results for \"{query}\" in {server_name}")
    print()
    print(f"Found {len(matches)} matching members (basic search)")
    print()
    print("Note: For richer search, sync with --enrich-profiles to enable profile-based search.")
    print()

    if matches:
        headers = ["#", "Username", "Match Reason", "Score"]
        rows = []
        for i, (m, score, reasons) in enumerate(matches[:20], 1):
            reason_str = ", ".join(reasons[:2])
            rows.append([i, m.username, reason_str, f"{score:.0f}"])

        print(format_table(headers, rows))

        if len(matches) > 20:
            print(f"\n... and {len(matches) - 20} more")
    else:
        print("No matches found.")
        print("\nTip: Try searching for:")
        print("  - Usernames or display names")
        print("  - Role names")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Query Discord member data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # new command
    new_parser = subparsers.add_parser("new", help="List new members by date range")
    new_parser.add_argument("--server", required=True, help="Discord server ID")
    new_parser.add_argument("--since", default="7d", help="Start date (today, yesterday, 7d, 30d, or ISO date)")
    new_parser.add_argument("--until", help="End date (default: now)")
    new_parser.add_argument("--format", choices=["table", "json", "csv"], default="table")
    new_parser.add_argument("--limit", type=int, default=100, help="Max results")
    new_parser.add_argument("--data-dir", default="./data")

    # growth command
    growth_parser = subparsers.add_parser("growth", help="Show join statistics over time")
    growth_parser.add_argument("--server", required=True, help="Discord server ID")
    growth_parser.add_argument("--period", choices=["day", "week", "month", "year"], default="week")
    growth_parser.add_argument("--format", choices=["chart", "table", "json"], default="chart")
    growth_parser.add_argument("--data-dir", default="./data")

    # silent command
    silent_parser = subparsers.add_parser("silent", help="List members who never posted")
    silent_parser.add_argument("--server", required=True, help="Discord server ID")
    silent_parser.add_argument("--joined-before", help="Only members who joined before date")
    silent_parser.add_argument("--format", choices=["table", "json"], default="table")
    silent_parser.add_argument("--limit", type=int, default=100)
    silent_parser.add_argument("--data-dir", default="./data")

    # engagement command
    engagement_parser = subparsers.add_parser("engagement", help="Show engagement tier breakdown")
    engagement_parser.add_argument("--server", required=True, help="Discord server ID")
    engagement_parser.add_argument("--tier", help="Filter by tier: silent, lurker, occasional, active, champion")
    engagement_parser.add_argument("--format", choices=["summary", "table", "json"], default="summary")
    engagement_parser.add_argument("--data-dir", default="./data")

    # find command
    find_parser = subparsers.add_parser("find", help="Search members by description")
    find_parser.add_argument("query", help="Search query (supports natural language)")
    find_parser.add_argument("--server", required=True, help="Discord server ID")
    find_parser.add_argument("--role", help="Filter by role name")
    find_parser.add_argument("--joined-since", help="Filter by join date (7d, 30d, or ISO date)")
    find_parser.add_argument("--engagement", choices=["silent", "lurker", "occasional", "active", "champion"],
                             help="Filter by engagement tier")
    find_parser.add_argument("--limit", type=int, default=50, help="Max results")
    find_parser.add_argument("--format", choices=["table", "json"], default="table")
    find_parser.add_argument("--data-dir", default="./data")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    commands = {
        "new": cmd_new_members,
        "growth": cmd_growth,
        "silent": cmd_silent,
        "engagement": cmd_engagement,
        "find": cmd_find,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
