#!/usr/bin/env python3
"""Member profile management CLI tool.

Manages community member profiles - save, retrieve, search, and list operations.

Usage:
    python member_profile.py save --platform discord --member-id 123 --name "Alice" --observation "Developer"
    python member_profile.py get --platform discord --member-id 123
    python member_profile.py add-observation --platform discord --member-id 123 --text "Interested in Python"
    python member_profile.py search --platform discord --query "python developer"
    python member_profile.py list --platform discord
    python member_profile.py count --platform discord
    python member_profile.py rebuild-index --platform discord
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_profile import (
    MAX_KEYWORDS,
    MAX_OBSERVATIONS,
    SUPPORTED_PLATFORMS,
    MemberProfile,
    Observation,
    ProfileStore,
    ProfileSummary,
    SearchResult,
    create_profile,
)


def format_profile(profile: MemberProfile, json_output: bool = False) -> str:
    """Format a profile for display.

    Args:
        profile: Profile to format
        json_output: If True, return JSON format

    Returns:
        Formatted string
    """
    if json_output:
        return json.dumps(profile.to_dict(), indent=2, default=str)

    lines = [
        f"Member Profile: {profile.display_name}",
        f"{'=' * 50}",
        f"ID:       {profile.member_id}",
        f"Platform: {profile.platform}",
        f"First Seen:    {profile.first_seen.strftime('%Y-%m-%d %H:%M')}",
        f"Last Updated:  {profile.last_updated.strftime('%Y-%m-%d %H:%M')}",
    ]

    if profile.keywords:
        lines.append(f"Keywords: {', '.join(profile.keywords)}")

    if profile.notes:
        lines.append(f"\nNotes:\n  {profile.notes}")

    if profile.observations:
        lines.append(f"\nObservations ({len(profile.observations)}):")
        for obs in profile.observations[:10]:  # Show first 10
            lines.append(f"  [{obs.timestamp.strftime('%Y-%m-%d')}] {obs.text}")
        if len(profile.observations) > 10:
            lines.append(f"  ... and {len(profile.observations) - 10} more")

    return "\n".join(lines)


def format_summary(summary: ProfileSummary, json_output: bool = False) -> str:
    """Format a profile summary for display.

    Args:
        summary: Summary to format
        json_output: If True, return JSON format

    Returns:
        Formatted string
    """
    if json_output:
        return json.dumps(summary.to_dict(), indent=2)

    keywords = f" [{', '.join(summary.keywords[:3])}]" if summary.keywords else ""
    return f"{summary.member_id}: {summary.display_name}{keywords} (updated: {summary.last_updated})"


def format_search_result(result: SearchResult, json_output: bool = False) -> str:
    """Format a search result for display.

    Args:
        result: Search result to format
        json_output: If True, return JSON format

    Returns:
        Formatted string
    """
    if json_output:
        return json.dumps(
            {"profile": result.profile.to_dict(), "match_reason": result.match_reason},
            indent=2,
            default=str,
        )

    return f"{result.profile.member_id}: {result.profile.display_name} - {result.match_reason}"


def cmd_save(args: argparse.Namespace) -> int:
    """Handle save command."""
    store = ProfileStore()

    # Check if profile exists
    existing = store.get(args.platform, args.member_id)

    if existing:
        # Update existing profile
        if args.name:
            existing.display_name = args.name
        if args.observation:
            existing.observations.append(
                Observation(timestamp=datetime.now(), text=args.observation)
            )
        if args.notes:
            existing.notes = args.notes
        if args.keywords:
            existing.keywords = args.keywords

        store.save(existing)
        profile = existing
        action = "Updated"
    else:
        # Create new profile
        if not args.name:
            print("Error: --name required when creating new profile", file=sys.stderr)
            return 1

        profile = create_profile(
            platform=args.platform,
            member_id=args.member_id,
            display_name=args.name,
            initial_observation=args.observation,
        )
        if args.notes:
            profile.notes = args.notes
        if args.keywords:
            profile.keywords = args.keywords

        store.save(profile)
        action = "Created"

    if args.json:
        print(json.dumps({"status": "ok", "action": action.lower(), "profile": profile.to_dict()}, indent=2, default=str))
    else:
        print(f"{action} profile for {profile.display_name} ({profile.member_id})")

    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """Handle get command."""
    store = ProfileStore()
    profile = store.get(args.platform, args.member_id)

    if profile is None:
        if args.json:
            print(json.dumps({"status": "not_found", "member_id": args.member_id}))
        else:
            print(f"Profile not found: {args.member_id}")
        return 1

    print(format_profile(profile, args.json))
    return 0


def cmd_add_observation(args: argparse.Namespace) -> int:
    """Handle add-observation command."""
    store = ProfileStore()

    try:
        profile = store.add_observation(
            platform=args.platform,
            member_id=args.member_id,
            text=args.text,
            display_name=args.name,
        )

        if args.json:
            print(json.dumps({"status": "ok", "observations": len(profile.observations)}, indent=2))
        else:
            print(f"Added observation to {profile.display_name} (total: {len(profile.observations)})")

        return 0
    except ValueError as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_search(args: argparse.Namespace) -> int:
    """Handle search command."""
    store = ProfileStore()
    results = store.search(args.platform, args.query, limit=args.limit)

    if args.json:
        output = {
            "status": "ok",
            "query": args.query,
            "count": len(results),
            "results": [
                {"profile": r.profile.to_dict(), "match_reason": r.match_reason}
                for r in results
            ],
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        if not results:
            print(f"No profiles found matching '{args.query}'")
        else:
            print(f"Found {len(results)} profile(s) matching '{args.query}':\n")
            for result in results:
                print(format_search_result(result, json_output=False))

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Handle list command."""
    store = ProfileStore()
    summaries = store.list_all(args.platform, offset=args.offset, limit=args.limit)
    total = store.count(args.platform)

    if args.json:
        output = {
            "status": "ok",
            "total": total,
            "offset": args.offset,
            "limit": args.limit,
            "count": len(summaries),
            "profiles": [s.to_dict() | {"member_id": s.member_id} for s in summaries],
        }
        print(json.dumps(output, indent=2))
    else:
        if not summaries:
            print(f"No profiles found for {args.platform}")
        else:
            print(f"Profiles ({args.offset + 1}-{args.offset + len(summaries)} of {total}):\n")
            for summary in summaries:
                print(format_summary(summary, json_output=False))

    return 0


def cmd_count(args: argparse.Namespace) -> int:
    """Handle count command."""
    store = ProfileStore()
    count = store.count(args.platform)

    if args.json:
        print(json.dumps({"status": "ok", "platform": args.platform, "count": count}))
    else:
        print(f"{args.platform}: {count} profile(s)")

    return 0


def cmd_rebuild_index(args: argparse.Namespace) -> int:
    """Handle rebuild-index command."""
    store = ProfileStore()
    count = store.rebuild_index(args.platform)

    if args.json:
        print(json.dumps({"status": "ok", "platform": args.platform, "indexed": count}))
    else:
        print(f"Rebuilt index for {args.platform}: {count} profile(s)")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage community member profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s save --platform discord --member-id 123 --name "Alice" --observation "Developer"
  %(prog)s get --platform discord --member-id 123
  %(prog)s add-observation --platform discord --member-id 123 --text "Interested in Python"
  %(prog)s search --platform discord --query "python developer"
  %(prog)s list --platform discord --limit 20
  %(prog)s count --platform discord
  %(prog)s rebuild-index --platform discord
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # save command
    save_parser = subparsers.add_parser("save", help="Save or update a profile")
    save_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform (discord or telegram)",
    )
    save_parser.add_argument("--member-id", required=True, help="Member ID")
    save_parser.add_argument("--name", help="Display name (required for new profiles)")
    save_parser.add_argument("--observation", help="Initial observation")
    save_parser.add_argument("--notes", help="Profile notes")
    save_parser.add_argument(
        "--keywords", nargs="+", help="Keywords for search"
    )
    save_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    save_parser.set_defaults(func=cmd_save)

    # get command
    get_parser = subparsers.add_parser("get", help="Get a profile by ID")
    get_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform",
    )
    get_parser.add_argument("--member-id", required=True, help="Member ID")
    get_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    get_parser.set_defaults(func=cmd_get)

    # add-observation command
    add_obs_parser = subparsers.add_parser(
        "add-observation", help="Add observation to a profile"
    )
    add_obs_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform",
    )
    add_obs_parser.add_argument("--member-id", required=True, help="Member ID")
    add_obs_parser.add_argument("--text", required=True, help="Observation text")
    add_obs_parser.add_argument(
        "--name", help="Display name (required if profile doesn't exist)"
    )
    add_obs_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    add_obs_parser.set_defaults(func=cmd_add_observation)

    # search command
    search_parser = subparsers.add_parser("search", help="Search profiles")
    search_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform",
    )
    search_parser.add_argument("--query", required=True, help="Search query")
    search_parser.add_argument(
        "--limit", type=int, default=20, help="Max results (default: 20)"
    )
    search_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    search_parser.set_defaults(func=cmd_search)

    # list command
    list_parser = subparsers.add_parser("list", help="List all profiles")
    list_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform",
    )
    list_parser.add_argument(
        "--offset", type=int, default=0, help="Offset (default: 0)"
    )
    list_parser.add_argument(
        "--limit", type=int, default=50, help="Max results (default: 50)"
    )
    list_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    list_parser.set_defaults(func=cmd_list)

    # count command
    count_parser = subparsers.add_parser("count", help="Count profiles")
    count_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform",
    )
    count_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    count_parser.set_defaults(func=cmd_count)

    # rebuild-index command
    rebuild_parser = subparsers.add_parser(
        "rebuild-index", help="Rebuild profile index"
    )
    rebuild_parser.add_argument(
        "--platform",
        required=True,
        choices=SUPPORTED_PLATFORMS,
        help="Platform",
    )
    rebuild_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    rebuild_parser.set_defaults(func=cmd_rebuild_index)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
