#!/usr/bin/env python3
"""Discord profile tool - View and manage user profile.

Usage:
    python tools/discord_profile.py                    # Show profile
    python tools/discord_profile.py --json             # Output as JSON
    python tools/discord_profile.py --section interests
    python tools/discord_profile.py --add-interest "kubernetes"
    python tools/discord_profile.py --add-keyword "bug"
    python tools/discord_profile.py --reset
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.profile import ProfileManager


def show_profile(profile: ProfileManager, section: str | None = None) -> str:
    """Format profile for display."""
    data = profile.load()
    lines = []

    if section is None:
        # Show full profile summary
        lines.append("User Profile")
        lines.append("━" * 50)
        lines.append("")

        # Identity
        lines.append("Identity:")
        lines.append(f"  Name: {data.name or '(not set)'}")
        lines.append(f"  Role: {data.role or '(not set)'}")
        lines.append("")

        # Interests
        lines.append(f"Interests ({len(data.interests)}):")
        if data.interests:
            for interest in data.interests[:5]:
                lines.append(f"  • {interest}")
            if len(data.interests) > 5:
                lines.append(f"  ... and {len(data.interests) - 5} more")
        else:
            lines.append("  (none yet)")
        lines.append("")

        # Watch keywords
        lines.append(f"Watch Keywords ({len(data.watch_keywords)}):")
        if data.watch_keywords:
            lines.append(f"  {', '.join(data.watch_keywords[:10])}")
        else:
            lines.append("  (none yet)")
        lines.append("")

        # Preferences
        lines.append("Preferences:")
        lines.append(f"  Summary style: {data.summary_style}")
        lines.append(f"  Detail level: {data.detail_level}")
        lines.append(f"  Timezone: {data.timezone}")
        lines.append("")

        # Top engagement
        lines.append("Top Engagement:")
        if data.engagement:
            flat = []
            for server, channels in data.engagement.items():
                for channel, score in channels.items():
                    flat.append((server, channel, score))
            flat.sort(key=lambda x: x[2], reverse=True)
            for server, channel, score in flat[:3]:
                lines.append(f"  {server}/#{channel}: {score}")
        else:
            lines.append("  (no engagement data)")
        lines.append("")

        # Recent activity
        lines.append(f"Recent Activity ({len(data.activity)} entries):")
        if data.activity:
            for entry in data.activity[:3]:
                lines.append(f"  {entry['date']} - {entry['action']}: {entry['context']}")
        else:
            lines.append("  (no activity yet)")
        lines.append("")

        # Metadata
        lines.append(f"Last updated: {data.last_updated or 'never'}")
        lines.append(f"Profile path: {profile.path}")

    elif section == "interests":
        lines.append(f"Interests ({len(data.interests)}):")
        for interest in data.interests:
            lines.append(f"  • {interest}")

    elif section == "keywords":
        lines.append(f"Watch Keywords ({len(data.watch_keywords)}):")
        for kw in data.watch_keywords:
            lines.append(f"  • {kw}")

    elif section == "engagement":
        lines.append("Engagement Scores:")
        lines.append("")
        lines.append(f"{'Server':<25} {'Channel':<20} {'Score':<10}")
        lines.append("-" * 55)
        if data.engagement:
            flat = []
            for server, channels in data.engagement.items():
                for channel, score in channels.items():
                    flat.append((server, channel, score))
            flat.sort(key=lambda x: x[2], reverse=True)
            for server, channel, score in flat:
                lines.append(f"{server:<25} #{channel:<19} {score:<10}")
        else:
            lines.append("(no engagement data)")

    elif section == "activity":
        lines.append(f"Activity History ({len(data.activity)} entries):")
        lines.append("")
        lines.append(f"{'Date':<12} {'Action':<12} {'Context'}")
        lines.append("-" * 60)
        for entry in data.activity:
            lines.append(
                f"{entry['date']:<12} {entry['action']:<12} {entry['context']}"
            )

    elif section == "preferences":
        lines.append("Communication Preferences:")
        lines.append(f"  Summary style: {data.summary_style}")
        lines.append(f"  Detail level: {data.detail_level}")
        lines.append(f"  Timezone: {data.timezone}")

    elif section == "learned":
        lines.append("Learned Preferences:")
        if data.learned:
            for pref in data.learned:
                lines.append(f"  • {pref}")
        else:
            lines.append("  (learning in progress)")

    else:
        lines.append(f"Unknown section: {section}")
        lines.append("Available sections: interests, keywords, engagement, activity, preferences, learned")

    return "\n".join(lines)


def profile_to_json(profile: ProfileManager) -> str:
    """Convert profile to JSON."""
    data = profile.load()
    return json.dumps({
        "identity": {
            "name": data.name,
            "role": data.role
        },
        "interests": data.interests,
        "watch_keywords": data.watch_keywords,
        "preferences": {
            "summary_style": data.summary_style,
            "detail_level": data.detail_level,
            "timezone": data.timezone
        },
        "engagement": data.engagement,
        "frequent_topics": data.frequent_topics,
        "activity": data.activity,
        "learned": data.learned,
        "metadata": {
            "last_updated": data.last_updated,
            "version": data.version,
            "path": str(profile.path)
        }
    }, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="View and manage Discord user profile"
    )

    # Display options
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--section",
        choices=["interests", "keywords", "engagement", "activity", "preferences", "learned"],
        help="Show specific section only"
    )

    # Modification options
    parser.add_argument(
        "--add-interest",
        metavar="TOPIC",
        help="Add an interest topic"
    )
    parser.add_argument(
        "--add-keyword",
        metavar="KEYWORD",
        help="Add a watch keyword"
    )
    parser.add_argument(
        "--set-name",
        metavar="NAME",
        help="Set profile name"
    )
    parser.add_argument(
        "--set-role",
        metavar="ROLE",
        help="Set profile role"
    )
    parser.add_argument(
        "--set-style",
        choices=["brief", "detailed", "actionable"],
        help="Set summary style preference"
    )

    # Management options
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset profile to defaults"
    )
    parser.add_argument(
        "--create",
        action="store_true",
        help="Create profile if it doesn't exist"
    )

    args = parser.parse_args()

    profile = ProfileManager()

    # Handle reset first
    if args.reset:
        profile.reset()
        print("Profile reset to defaults.")
        return

    # Handle create
    if args.create:
        if profile.exists():
            print(f"Profile already exists at {profile.path}")
        else:
            profile.create_default()
            print(f"Created profile at {profile.path}")
        return

    # Handle modifications
    modified = False

    if args.add_interest:
        profile.add_interest(args.add_interest)
        print(f"Added interest: {args.add_interest}")
        modified = True

    if args.add_keyword:
        profile.add_watch_keyword(args.add_keyword)
        print(f"Added keyword: {args.add_keyword}")
        modified = True

    if args.set_name:
        data = profile.load()
        data.name = args.set_name
        profile.save()
        print(f"Set name: {args.set_name}")
        modified = True

    if args.set_role:
        data = profile.load()
        data.role = args.set_role
        profile.save()
        print(f"Set role: {args.set_role}")
        modified = True

    if args.set_style:
        profile.update_preference("summary_style", args.set_style)
        print(f"Set summary style: {args.set_style}")
        modified = True

    # Show profile if no modifications or explicitly requested
    if not modified:
        if not profile.exists():
            print("No profile found.")
            print("")
            print("To create a profile:")
            print("  python tools/discord_profile.py --create")
            print("")
            print("Or it will be auto-created during discord-init.")
            return

        if args.json:
            print(profile_to_json(profile))
        else:
            print(show_profile(profile, args.section))


if __name__ == "__main__":
    main()
