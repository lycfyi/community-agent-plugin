#!/usr/bin/env python3
"""
Discord member export tool.

Export member data to CSV, JSON, or Markdown format.

Usage:
    python member_export.py --server SERVER_ID --format csv
    python member_export.py --server SERVER_ID --format json
    python member_export.py --server SERVER_ID --format md
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_storage import get_member_storage


def export_csv(members: list, output_path: Path, include_profiles: bool = False) -> None:
    """Export members to CSV format."""
    fieldnames = [
        "user_id",
        "username",
        "display_name",
        "joined_at",
        "tenure_days",
        "roles",
        "is_bot",
        "account_created_at",
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for member in members:
            row = {
                "user_id": member.user_id,
                "username": member.username,
                "display_name": member.display_name,
                "joined_at": member.joined_at.isoformat() if member.joined_at else "",
                "tenure_days": member.tenure_days,
                "roles": ";".join(member.roles),
                "is_bot": member.is_bot,
                "account_created_at": member.account_created_at.isoformat() if member.account_created_at else "",
            }
            writer.writerow(row)


def export_json(members: list, server_name: str, output_path: Path, include_profiles: bool = False) -> None:
    """Export members to JSON format."""
    data = {
        "server_name": server_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "member_count": len(members),
        "members": [
            {
                "user_id": m.user_id,
                "username": m.username,
                "display_name": m.display_name,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                "tenure_days": m.tenure_days,
                "roles": m.roles,
                "is_bot": m.is_bot,
                "avatar_url": m.avatar_url,
                "account_created_at": m.account_created_at.isoformat() if m.account_created_at else None,
            }
            for m in members
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_markdown(members: list, server_name: str, output_path: Path, include_profiles: bool = False) -> None:
    """Export members to Markdown report format."""
    now = datetime.now(timezone.utc)

    # Calculate stats
    total = len(members)
    humans = [m for m in members if not m.is_bot]
    bots = [m for m in members if m.is_bot]

    # Tenure distribution
    tenure_brackets = {
        "< 7 days": 0,
        "7-30 days": 0,
        "1-3 months": 0,
        "3-6 months": 0,
        "6-12 months": 0,
        "> 1 year": 0,
    }

    for m in humans:
        days = m.tenure_days
        if days < 7:
            tenure_brackets["< 7 days"] += 1
        elif days < 30:
            tenure_brackets["7-30 days"] += 1
        elif days < 90:
            tenure_brackets["1-3 months"] += 1
        elif days < 180:
            tenure_brackets["3-6 months"] += 1
        elif days < 365:
            tenure_brackets["6-12 months"] += 1
        else:
            tenure_brackets["> 1 year"] += 1

    # Role distribution (top 10)
    role_counts = {}
    for m in humans:
        for role in m.roles:
            if role.lower() not in ["@everyone", "member"]:
                role_counts[role] = role_counts.get(role, 0) + 1

    top_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Recent joins (last 7 days)
    week_ago = now - __import__('datetime').timedelta(days=7)
    recent_joins = [m for m in humans if m.joined_at and m.joined_at >= week_ago]

    lines = [
        f"# Member Report: {server_name}",
        "",
        f"**Generated**: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Summary",
        "",
        f"- **Total Members**: {total:,}",
        f"- **Humans**: {len(humans):,}",
        f"- **Bots**: {len(bots):,}",
        f"- **New this week**: {len(recent_joins):,}",
        "",
        "## Tenure Distribution",
        "",
        "| Bracket | Count | % |",
        "|---------|-------|---|",
    ]

    for bracket, count in tenure_brackets.items():
        pct = (count / len(humans) * 100) if humans else 0
        lines.append(f"| {bracket} | {count:,} | {pct:.1f}% |")

    lines.extend([
        "",
        "## Top Roles",
        "",
        "| Role | Members |",
        "|------|---------|",
    ])

    for role, count in top_roles:
        lines.append(f"| {role} | {count:,} |")

    if recent_joins:
        lines.extend([
            "",
            "## Recent Joins (Last 7 Days)",
            "",
            "| Username | Joined | Roles |",
            "|----------|--------|-------|",
        ])

        for m in sorted(recent_joins, key=lambda x: x.joined_at or datetime.min, reverse=True)[:20]:
            joined = m.joined_at.strftime("%Y-%m-%d") if m.joined_at else "-"
            roles = ", ".join(m.roles[:3]) or "-"
            lines.append(f"| {m.username} | {joined} | {roles} |")

        if len(recent_joins) > 20:
            lines.append(f"| ... | ... | ({len(recent_joins) - 20} more) |")

    lines.extend([
        "",
        "---",
        "",
        f"*Export includes {total:,} total member records.*",
    ])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export Discord member data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--server", required=True, help="Discord server ID")
    parser.add_argument("--format", required=True, choices=["csv", "json", "md"],
                        help="Export format")
    parser.add_argument("--output", help="Output file path (auto-generated if not specified)")
    parser.add_argument("--include-profiles", action="store_true",
                        help="Include unified profile data in export")
    parser.add_argument("--data-dir", default="./data")

    args = parser.parse_args()

    storage = get_member_storage(args.data_dir)

    # Load current members
    current = storage.load_current_members(args.server)
    if not current:
        print(f"Error: No synced data for server {args.server}", file=sys.stderr)
        print("Run 'discord members sync' first.", file=sys.stderr)
        return 1

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Auto-generate path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = Path("reports/discord/exports")
        export_dir.mkdir(parents=True, exist_ok=True)

        ext = {"csv": "csv", "json": "json", "md": "md"}[args.format]
        output_path = export_dir / f"members_{timestamp}.{ext}"

    # Export
    print(f"Exporting members from {current.server_name}...")

    if args.format == "csv":
        export_csv(current.members, output_path, args.include_profiles)
    elif args.format == "json":
        export_json(current.members, current.server_name, output_path, args.include_profiles)
    elif args.format == "md":
        export_markdown(current.members, current.server_name, output_path, args.include_profiles)

    # Get file size
    file_size = output_path.stat().st_size
    if file_size > 1024 * 1024:
        size_str = f"{file_size / 1024 / 1024:.1f} MB"
    elif file_size > 1024:
        size_str = f"{file_size / 1024:.1f} KB"
    else:
        size_str = f"{file_size} bytes"

    print()
    print(f"Exported {current.member_count:,} members to:")
    print(f"  {output_path} ({size_str})")

    if args.format == "csv":
        print()
        print("Columns: user_id, username, display_name, joined_at, tenure_days, roles, is_bot, account_created_at")

    return 0


if __name__ == "__main__":
    sys.exit(main())
