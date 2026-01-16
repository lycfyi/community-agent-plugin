#!/usr/bin/env python3
"""Profile extraction CLI tool.

Extracts member profiles from synced Discord/Telegram messages.

Usage:
    python extract_profiles.py extract --server 1092630146143506494 [--full] [--dry-run]
    python extract_profiles.py status --server 1092630146143506494
    python extract_profiles.py reset --server 1092630146143506494
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.member_profile import ProfileStore, SUPPORTED_PLATFORMS
from lib.profile_extractor import (
    ExtractionState,
    ProfileExtractor,
)


def progress_callback(stage: str, current: int, total: int) -> None:
    """Print progress updates."""
    if total > 0:
        pct = (current / total) * 100
        print(f"\r{stage.capitalize()}: {current}/{total} ({pct:.1f}%)", end="", flush=True)
        if current == total:
            print()  # Newline at end


def cmd_extract(args: argparse.Namespace) -> int:
    """Handle extract command."""
    store = ProfileStore()
    extractor = ProfileExtractor(store)

    print(f"Extracting profiles from {args.platform} server {args.server}...")
    if args.dry_run:
        print("(DRY RUN - no profiles will be saved)")
    if args.full:
        print("(FULL mode - reprocessing all messages)")

    callback = progress_callback if not args.json else None

    result = extractor.extract_from_server(
        platform=args.platform,
        server_id=args.server,
        incremental=not args.full,
        dry_run=args.dry_run,
        min_messages=args.min_messages,
        progress_callback=callback,
    )

    if args.json:
        output = {
            "status": "ok" if not result.errors else "partial",
            "server_id": result.server_id,
            "platform": result.platform,
            "dry_run": result.dry_run,
            "messages_processed": result.messages_processed,
            "members_found": result.members_found,
            "profiles_created": result.profiles_created,
            "profiles_updated": result.profiles_updated,
            "skipped_insufficient_messages": result.skipped_insufficient_messages,
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nExtraction Results:")
        print(f"  Messages processed: {result.messages_processed}")
        print(f"  Members found: {result.members_found}")
        print(f"  Profiles created: {result.profiles_created}")
        print(f"  Profiles updated: {result.profiles_updated}")
        print(f"  Skipped (< {args.min_messages} messages): {result.skipped_insufficient_messages}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for err in result.errors[:5]:
                print(f"  - {err}")
            if len(result.errors) > 5:
                print(f"  ... and {len(result.errors) - 5} more")

    return 0 if not result.errors else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Handle status command."""
    store = ProfileStore()
    extractor = ProfileExtractor(store)

    status = extractor.get_extraction_status(args.platform, args.server)

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"Extraction Status for {args.platform} server {args.server}")
        print("=" * 50)

        if not status["server_found"]:
            print(f"Server directory not found!")
            print(f"Expected: data/{args.platform}/servers/{args.server}-*/")
            return 1

        print(f"Server directory: {status.get('server_dir', 'N/A')}")
        print(f"Last extraction: {status['last_extraction'] or 'Never'}")
        print(f"Channels processed: {status['channels_processed']}")

        if status["channel_details"]:
            print(f"\nChannel Details:")
            total_new = 0
            for ch_name, ch_info in sorted(status["channel_details"].items()):
                new_msgs = ch_info.get("new_messages", 0)
                total_new += new_msgs
                marker = " *" if new_msgs > 0 else ""
                print(
                    f"  {ch_name}: {ch_info['current_messages']} messages "
                    f"(+{new_msgs} new){marker}"
                )
            print(f"\nTotal new messages: {total_new}")

    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    """Handle reset command."""
    if not args.force:
        response = input(
            f"Reset extraction state for {args.platform} server {args.server}? "
            f"This will cause full re-extraction on next run. [y/N] "
        )
        if response.lower() != "y":
            print("Aborted.")
            return 0

    ExtractionState.reset(args.platform, args.server)

    if args.json:
        print(json.dumps({"status": "ok", "action": "reset", "server_id": args.server}))
    else:
        print(f"Reset extraction state for {args.platform} server {args.server}")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract member profiles from synced messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s extract --server 1092630146143506494
  %(prog)s extract --server 1092630146143506494 --dry-run
  %(prog)s extract --server 1092630146143506494 --full --min-messages 5
  %(prog)s status --server 1092630146143506494
  %(prog)s reset --server 1092630146143506494 --force
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract profiles from synced messages",
    )
    extract_parser.add_argument(
        "--server",
        required=True,
        help="Server ID (numeric portion, e.g., 1092630146143506494)",
    )
    extract_parser.add_argument(
        "--platform",
        default="discord",
        choices=SUPPORTED_PLATFORMS,
        help="Platform (default: discord)",
    )
    extract_parser.add_argument(
        "--full",
        action="store_true",
        help="Process all messages (ignore incremental state)",
    )
    extract_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without saving profiles",
    )
    extract_parser.add_argument(
        "--min-messages",
        type=int,
        default=3,
        help="Minimum messages to create a profile (default: 3)",
    )
    extract_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    extract_parser.set_defaults(func=cmd_extract)

    # status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show extraction status for a server",
    )
    status_parser.add_argument(
        "--server",
        required=True,
        help="Server ID (numeric portion)",
    )
    status_parser.add_argument(
        "--platform",
        default="discord",
        choices=SUPPORTED_PLATFORMS,
        help="Platform (default: discord)",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    status_parser.set_defaults(func=cmd_status)

    # reset command
    reset_parser = subparsers.add_parser(
        "reset",
        help="Reset extraction state for a server",
    )
    reset_parser.add_argument(
        "--server",
        required=True,
        help="Server ID (numeric portion)",
    )
    reset_parser.add_argument(
        "--platform",
        default="discord",
        choices=SUPPORTED_PLATFORMS,
        help="Platform (default: discord)",
    )
    reset_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    reset_parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    reset_parser.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
