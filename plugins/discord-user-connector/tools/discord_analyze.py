#!/usr/bin/env python3
"""Discord analyze tool - Generate community health reports.

Usage:
    python tools/discord_analyze.py                       # Analyze default server
    python tools/discord_analyze.py --server SERVER_ID   # Analyze specific server
    python tools/discord_analyze.py --days 30            # Analyze last 30 days
    python tools/discord_analyze.py --format yaml        # Output in YAML format
    python tools/discord_analyze.py --compare SERVER_ID  # Compare with another server
    python tools/discord_analyze.py --verbose            # Show progress
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config import get_config, ConfigError
from lib.storage import get_storage
from lib.analytics.report import generate_health_report, save_health_report
from lib.analytics.benchmarks import load_custom_benchmarks, compare_servers


# Exit codes
EXIT_SUCCESS = 0
EXIT_CONFIG_ERROR = 1
EXIT_DATA_ERROR = 2
EXIT_ANALYSIS_ERROR = 3


def main():
    parser = argparse.ArgumentParser(
        description="Generate Discord community health reports"
    )

    parser.add_argument(
        "--server",
        metavar="SERVER_ID",
        help="Server ID to analyze (uses config default if not specified)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of history to analyze (default: 30)"
    )
    parser.add_argument(
        "--compare",
        metavar="SERVER_ID",
        help="Server ID to compare against"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "yaml", "json"],
        default="markdown",
        help="Output format (default: markdown)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed progress"
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Custom output path (default: server directory)"
    )

    args = parser.parse_args()

    try:
        # Get configuration
        config = get_config()
        storage = get_storage()

        # Determine server ID
        server_id = args.server or config.server_id
        if not server_id:
            print("Error: No server specified and no default in config", file=sys.stderr)
            print("\nUse --server SERVER_ID or set discord.server_id in config/agents.yaml", file=sys.stderr)
            sys.exit(EXIT_CONFIG_ERROR)

        # Find server directory
        server_dir = _find_server_dir(storage, server_id)
        if not server_dir:
            print(f"Error: No synced data found for server {server_id}", file=sys.stderr)
            print(f"\nRun 'discord-sync --server {server_id}' first.", file=sys.stderr)
            sys.exit(EXIT_DATA_ERROR)

        # Get server name from sync state
        sync_state = storage.get_sync_state(server_id)
        server_name = sync_state.get("server_name", f"Server {server_id}")

        # Check for minimum data
        total_messages = _count_total_messages(server_dir)
        if total_messages == 0:
            print("Error: No messages found in synced data", file=sys.stderr)
            print("\nCheck that sync completed successfully.", file=sys.stderr)
            sys.exit(EXIT_DATA_ERROR)

        # Load custom benchmarks from config
        custom_benchmarks = None
        try:
            community_config = config._community_config._config
            custom_benchmarks = load_custom_benchmarks(community_config)
        except Exception:
            pass  # Use defaults if config loading fails

        # Generate report
        if args.verbose:
            print(f"Analyzing community health for {server_name}...")

        try:
            report = generate_health_report(
                server_dir=server_dir,
                server_id=server_id,
                server_name=server_name,
                days=args.days,
                custom_benchmarks=custom_benchmarks,
                verbose=args.verbose,
            )
        except Exception as e:
            print(f"Error: Failed to parse messages: {e}", file=sys.stderr)
            sys.exit(EXIT_ANALYSIS_ERROR)

        # Handle comparison
        comparison_data = None
        if args.compare:
            compare_dir = _find_server_dir(storage, args.compare)
            if compare_dir:
                compare_state = storage.get_sync_state(args.compare)
                compare_name = compare_state.get("server_name", f"Server {args.compare}")

                compare_report = generate_health_report(
                    server_dir=compare_dir,
                    server_id=args.compare,
                    server_name=compare_name,
                    days=args.days,
                    custom_benchmarks=custom_benchmarks,
                    verbose=False,
                )
                comparison_data = compare_servers(report, compare_report)
            else:
                print(f"Warning: Comparison server {args.compare} not found", file=sys.stderr)

        # Save report
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = server_dir

        md_path, yaml_path = save_health_report(report, output_dir)

        # Print summary
        _print_summary(report, md_path, args.format, comparison_data)

        sys.exit(EXIT_SUCCESS)

    except ConfigError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        print("\nMake sure you have created .env and config/agents.yaml", file=sys.stderr)
        sys.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ANALYSIS_ERROR)


def _find_server_dir(storage, server_id: str) -> Optional[Path]:
    """Find server directory by ID.

    Args:
        storage: Storage instance.
        server_id: Server ID to find.

    Returns:
        Path to server directory, or None if not found.
    """
    base_dir = storage._base_dir

    # Try to find directory matching server_id
    for server_dir in base_dir.iterdir():
        if not server_dir.is_dir():
            continue
        if server_dir.name.startswith(server_id):
            return server_dir

    return None


def _count_total_messages(server_dir: Path) -> int:
    """Count total messages in server directory.

    Args:
        server_dir: Path to server directory.

    Returns:
        Total message count.
    """
    count = 0
    for messages_file in server_dir.glob("*/messages.md"):
        with open(messages_file, 'r') as f:
            for line in f:
                if line.startswith("### "):
                    count += 1
    return count


def _print_summary(report, md_path: Path, format: str, comparison_data=None):
    """Print analysis summary to stdout.

    Args:
        report: HealthReport object.
        md_path: Path to saved markdown report.
        format: Output format.
        comparison_data: Optional comparison data.
    """
    # Status emoji
    if report.health_scores.overall >= 60:
        status_emoji = "✅"
        status_text = "Healthy"
    elif report.health_scores.overall >= 40:
        status_emoji = "⚠️"
        status_text = "Warning"
    else:
        status_emoji = "❌"
        status_text = "Critical"

    print("")
    print(f"{status_emoji} Health report generated!")
    print("")
    print(f"Overall Score: {report.health_scores.overall}/100 ({status_text})")
    print("")
    print("Summary:")
    print(f"- {report.message_count:,} messages from {report.engagement.unique_authors:,} members")
    print(f"- Daily active: {report.engagement.daily_active_members_percentage:.1f}%", end="")
    if report.engagement.daily_active_members_percentage >= 10:
        print(" (above healthy threshold)")
    else:
        print(" (below healthy threshold)")
    print(f"- Response rate: {report.engagement.reply_rate:.1f}%")
    print("")

    # Key findings
    if report.recommendations:
        print("Key Findings:")
        for i, rec in enumerate(report.recommendations[:3], 1):
            priority_emoji = "🔴" if rec.priority.value == "high" else ("🟡" if rec.priority.value == "medium" else "🟢")
            print(f"{i}. {priority_emoji} {rec.title}")
        print("")

    # Comparison
    if comparison_data:
        print("Comparison:")
        for metric, values in list(comparison_data.items())[:3]:
            print(f"- {metric.replace('_', ' ').title()}: ", end="")
            for name, value in values.items():
                print(f"{name}={value:.1f} ", end="")
            print("")
        print("")

    print(f"Report saved to: {md_path}")
    print("")
    print(f"Run 'cat {md_path}' for full report.")


if __name__ == "__main__":
    main()
