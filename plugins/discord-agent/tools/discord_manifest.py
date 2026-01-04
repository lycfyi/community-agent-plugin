#!/usr/bin/env python3
"""Get or create the Discord data manifest."""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.storage import get_storage


def main():
    parser = argparse.ArgumentParser(
        description="Get or create the Discord data manifest"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of YAML"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh the manifest from sync data"
    )
    args = parser.parse_args()

    try:
        storage = get_storage()

        # Force refresh if requested
        if args.refresh:
            manifest = storage.update_manifest()
        else:
            manifest = storage.get_manifest()

        # Check if there's any data
        if not manifest or not manifest.get("servers"):
            # Create empty manifest structure
            manifest = storage.update_manifest()

            if not manifest.get("servers"):
                print("No Discord data found.")
                print("")
                print("To get started:")
                print("1. Create .env file with DISCORD_USER_TOKEN=your_token")
                print("2. Run: python ${CLAUDE_PLUGIN_ROOT}/tools/discord_sync.py --server SERVER_ID")
                print("")
                print("Use discord-list to find your server IDs:")
                print("  python ${CLAUDE_PLUGIN_ROOT}/tools/discord_list.py --servers")
                return

        # Output manifest
        if args.json:
            print(json.dumps(manifest, indent=2, default=str))
        else:
            import yaml
            print(yaml.safe_dump(manifest, default_flow_style=False, sort_keys=False))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
