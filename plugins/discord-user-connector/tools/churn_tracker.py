#!/usr/bin/env python3
"""
Discord churn tracker tool.

Identify and analyze members who left the server.

Usage:
    python churn_tracker.py --server SERVER_ID
    python churn_tracker.py --server SERVER_ID --with-activity
    python churn_tracker.py --server SERVER_ID --summary
    python churn_tracker.py --server SERVER_ID --period week
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_storage import get_member_storage


def format_table(headers: list[str], rows: list[list]) -> str:
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


def cmd_churned(args) -> int:
    """List churned members."""
    storage = get_member_storage(args.data_dir)

    # Load churned members
    churned = storage.list_churned_members(args.server)

    if not churned:
        # Check if we have any sync data at all
        current = storage.load_current_members(args.server)
        if not current:
            print(f"Error: No synced data for server {args.server}", file=sys.stderr)
            print("Run 'discord members sync' first.", file=sys.stderr)
            return 1

        # Check if we have multiple snapshots
        snapshots = storage.list_snapshots(args.server)
        if len(snapshots) < 2:
            print(f"No churned members detected yet.")
            print()
            print("Churn detection requires at least two sync operations to compare.")
            print(f"Current syncs: {len(snapshots)}")
            print()
            print("Run 'discord members sync' again later to detect members who left.")
            return 0

        print(f"No members departed since last sync.")
        return 0

    # Filter by period if specified
    if args.period and args.period != "all":
        now = datetime.now(timezone.utc)
        period_days = {
            "day": 1,
            "week": 7,
            "month": 30,
        }.get(args.period, 0)

        if period_days > 0:
            cutoff = now - timedelta(days=period_days)
            churned = [c for c in churned if c.departure_detected_at and c.departure_detected_at >= cutoff]

    if args.summary:
        return cmd_summary(churned, args)

    # Get server name from metadata
    metadata = storage.load_server_metadata(args.server)
    server_name = metadata.name if metadata else args.server

    if args.format == "json":
        output = {
            "server_id": args.server,
            "server_name": server_name,
            "period": args.period,
            "total_count": len(churned),
            "members": [
                {
                    "user_id": c.user_id,
                    "username": c.username,
                    "display_name": c.display_name,
                    "joined_at": c.joined_at.isoformat() if c.joined_at else None,
                    "departure_detected_at": c.departure_detected_at.isoformat() if c.departure_detected_at else None,
                    "tenure_days": c.tenure_days,
                    "was_active": c.was_active,
                    "activity": c.activity.to_dict() if c.activity else None,
                    "roles_at_departure": c.roles_at_departure,
                }
                for c in churned
            ]
        }
        print(json.dumps(output, indent=2))
    else:
        # Table format
        print(f"Churned members from {server_name}")
        print()
        print(f"Total: {len(churned)} members departed")
        print()

        if churned:
            if args.with_activity:
                headers = ["#", "Username", "Tenure", "Messages", "Last Message", "Channels Active"]
                rows = []
                for i, c in enumerate(churned[:50], 1):
                    tenure = f"{c.tenure_days}d"
                    if c.activity:
                        msg_count = c.activity.message_count
                        last_msg = c.activity.last_message_at.strftime("%Y-%m-%d") if c.activity.last_message_at else "-"
                        channels = ", ".join(c.activity.channels_active[:3])
                        if len(c.activity.channels_active) > 3:
                            channels += "..."
                    else:
                        msg_count = "-"
                        last_msg = "-"
                        channels = "-"
                    rows.append([i, c.username, tenure, msg_count, last_msg, channels])
            else:
                headers = ["#", "Username", "Tenure", "Departed (detected)", "Was Active"]
                rows = []
                for i, c in enumerate(churned[:50], 1):
                    tenure = f"{c.tenure_days}d"
                    departed = c.departure_detected_at.strftime("%Y-%m-%d") if c.departure_detected_at else "-"
                    if c.activity and c.activity.message_count > 0:
                        active_str = f"Yes ({c.activity.message_count} msgs)"
                    elif c.was_active:
                        active_str = "Yes"
                    else:
                        active_str = "No (silent)"
                    rows.append([i, c.username, tenure, departed, active_str])

            print(format_table(headers, rows))

            if len(churned) > 50:
                print(f"\n... and {len(churned) - 50} more")
        else:
            print("No churned members in this period.")

    return 0


def cmd_summary(churned: list, args) -> int:
    """Show churn summary statistics."""
    storage = get_member_storage(args.data_dir)

    # Get server name
    metadata = storage.load_server_metadata(args.server)
    server_name = metadata.name if metadata else args.server

    period_str = args.period if args.period else "all time"

    print(f"Churn Summary for {server_name} ({period_str})")
    print()

    if not churned:
        print("No churned members in this period.")
        return 0

    # Calculate stats
    total = len(churned)
    avg_tenure = sum(c.tenure_days for c in churned) / total if total > 0 else 0

    active_count = sum(1 for c in churned if c.was_active or (c.activity and c.activity.message_count > 0))
    silent_count = total - active_count

    active_pct = (active_count / total * 100) if total > 0 else 0
    silent_pct = (silent_count / total * 100) if total > 0 else 0

    # Average message count for active members
    msg_counts = []
    for c in churned:
        if c.activity:
            msg_counts.append(c.activity.message_count)
    avg_messages = sum(msg_counts) / len(msg_counts) if msg_counts else 0

    # Most common last-active channels
    channel_counts = {}
    for c in churned:
        if c.activity and c.activity.channels_active:
            for channel in c.activity.channels_active:
                channel_counts[channel] = channel_counts.get(channel, 0) + 1

    top_channels = sorted(channel_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f"- Total departed: {total}")
    print(f"- Average tenure: {avg_tenure:.0f} days")
    print(f"- Posted at least once: {active_count} ({active_pct:.0f}%)")
    print(f"- Silent churners: {silent_count} ({silent_pct:.0f}%)")
    print(f"- Average message count: {avg_messages:.0f}")

    if top_channels:
        print()
        print("Most common last-active channels:")
        for i, (channel, count) in enumerate(top_channels, 1):
            print(f"  {i}. #{channel} ({count} members)")

    return 0


def cmd_churned_history(args) -> int:
    """Show message history for a specific churned member."""
    storage = get_member_storage(args.data_dir)

    # Load churned member
    churned = storage.load_churned_member(args.server, args.user_id)
    if not churned:
        print(f"Error: No churned member record for user {args.user_id}", file=sys.stderr)
        return 1

    print(f"Churned Member: {churned.display_name} (@{churned.username})")
    print()
    print(f"User ID: {churned.user_id}")
    print(f"Joined: {churned.joined_at.strftime('%Y-%m-%d') if churned.joined_at else 'Unknown'}")
    print(f"Departed: {churned.departure_detected_at.strftime('%Y-%m-%d') if churned.departure_detected_at else 'Unknown'}")
    print(f"Tenure: {churned.tenure_days} days")
    print()

    if churned.roles_at_departure:
        print(f"Roles at departure: {', '.join(churned.roles_at_departure)}")
        print()

    if churned.activity:
        print(f"Messages: {churned.activity.message_count}")
        if churned.activity.last_message_at:
            print(f"Last message: {churned.activity.last_message_at.strftime('%Y-%m-%d %H:%M')}")
        if churned.activity.channels_active:
            print(f"Active in: {', '.join(churned.activity.channels_active)}")
    else:
        print("No activity data available.")

    print()
    print("Note: Full message history retrieval requires cross-referencing with synced messages.")
    print("This feature will be available in a future update.")

    return 0


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Track and analyze churned Discord members",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--server", required=True, help="Discord server ID")
    parser.add_argument("--period", choices=["day", "week", "month", "all"], default="all",
                        help="Time period to filter")
    parser.add_argument("--with-activity", action="store_true",
                        help="Include message activity info")
    parser.add_argument("--summary", action="store_true",
                        help="Show aggregate statistics only")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--user-id", help="Show details for specific churned user")
    parser.add_argument("--data-dir", default="./data")

    args = parser.parse_args()

    if args.user_id:
        return cmd_churned_history(args)
    else:
        return cmd_churned(args)


if __name__ == "__main__":
    sys.exit(main())
