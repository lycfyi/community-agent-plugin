#!/usr/bin/env python3
"""Discord recommend tool - Suggest servers to sync based on user profile.

Analyzes servers against user's configured interests and priority servers.
Falls back to member count heuristics if no profile configured.

Usage:
    python tools/discord_recommend.py
    python tools/discord_recommend.py --json
    python tools/discord_recommend.py --limit 5
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.discord_client import DiscordUserClient, AuthenticationError, DiscordClientError
from lib.storage import get_storage
from lib.config import get_config
from lib.profile import get_profile


# Ideal member range for active communities (used when no profile configured)
IDEAL_MIN_MEMBERS = 500
IDEAL_MAX_MEMBERS = 200_000

# Default AI/tech keywords for zero-config recommendations
# Used when no user profile is configured to help identify relevant servers
DEFAULT_AI_KEYWORDS = [
    "claude", "anthropic", "ai", "ml", "llm", "gpt", "openai",
    "dev", "developer", "code", "api", "agent", "browser",
    "automation", "cursor", "bolt", "windsurf", "hugging",
    "copilot", "codeium", "replit", "vercel", "supabase",
    "langchain", "ollama", "mistral", "gemini", "chatgpt"
]


def get_profile_keywords() -> list[str]:
    """Extract keywords from user profile.

    Returns:
        List of keywords from interests and watch_keywords, lowercased
    """
    profile = get_profile()

    if not profile.exists():
        return []

    keywords = []

    # Get interests from profile.md
    interests = profile.get_interests()
    for interest in interests:
        if interest:
            # Split multi-word interests into individual words
            words = str(interest).lower().split()
            keywords.extend(words)

    # Get watch keywords from profile.md
    watch = profile.get_watch_keywords()
    for keyword in watch:
        if keyword:
            keywords.append(str(keyword).lower())

    return keywords


def get_priority_server_ids() -> set[str]:
    """Get server IDs from priority_servers config.

    Returns:
        Set of server IDs that user has marked as priority
    """
    config = get_config()
    priority_servers = config.priority_servers

    ids = set()
    for server in priority_servers:
        if isinstance(server, dict) and server.get("id"):
            ids.add(str(server["id"]))
        elif isinstance(server, str):
            ids.add(server)

    return ids


def score_server(server: dict, keywords: list[str], priority_ids: set[str]) -> tuple[int, str]:
    """Score a server based on profile match.

    Args:
        server: Server info dict with id, name, member_count
        keywords: User's profile keywords (lowercased)
        priority_ids: Set of priority server IDs from config

    Returns:
        (score, reason) - Higher score = more relevant
    """
    name_lower = server["name"].lower()
    server_id = server["id"]
    member_count = server.get("member_count", 0)

    score = 0
    reasons = []

    # Highest priority: explicitly configured priority servers
    if server_id in priority_ids:
        score += 100
        reasons.append("priority server")

    # Match against profile keywords (if provided)
    if keywords:
        matched = []
        for keyword in keywords:
            if keyword in name_lower:
                matched.append(keyword)
                score += 10
        if matched:
            reasons.append(f"matches: {', '.join(matched[:3])}")

    # If no profile keywords, use default AI/tech keyword matching
    # This ensures AI/dev communities rank higher even without profile setup
    if not keywords and not reasons:
        matched_defaults = []
        for keyword in DEFAULT_AI_KEYWORDS:
            if keyword in name_lower:
                matched_defaults.append(keyword)
                score += 15  # Higher score than member count heuristic
        if matched_defaults:
            reasons.append(f"AI/dev server: {', '.join(matched_defaults[:3])}")

    # Heuristic: medium-sized communities (only if no other match)
    if not reasons:
        if IDEAL_MIN_MEMBERS <= member_count <= IDEAL_MAX_MEMBERS:
            score += 3
            reasons.append("active community size")
        elif member_count > IDEAL_MAX_MEMBERS:
            score += 1
            reasons.append("large community")

    # Penalty for very small servers (might be inactive)
    if member_count < 100 and not reasons:
        score -= 5

    reason = ", ".join(reasons) if reasons else "no specific match"
    return score, reason


async def get_recommendations(limit: int = 5) -> dict:
    """Get server recommendations based on user profile.

    Args:
        limit: Maximum number of recommendations

    Returns:
        Dict with recommended, already_synced, other servers, and profile_status
    """
    client = DiscordUserClient()
    try:
        guilds = await client.list_guilds()
    finally:
        await client.close()

    if not guilds:
        return {
            "recommended": [],
            "already_synced": [],
            "other": [],
            "total_servers": 0,
            "profile_configured": False,
            "keywords_used": []
        }

    # Get profile data
    keywords = get_profile_keywords()
    priority_ids = get_priority_server_ids()
    profile_configured = bool(keywords or priority_ids)

    # Get already synced servers
    storage = get_storage()
    manifest = storage.get_manifest()
    synced_ids = set()
    if manifest and manifest.get("servers"):
        synced_ids = {s["id"] for s in manifest["servers"]}

    # Score all servers
    scored = []
    for server in guilds:
        score, reason = score_server(server, keywords, priority_ids)
        scored.append({
            "id": server["id"],
            "name": server["name"],
            "members": server.get("member_count", 0),
            "score": score,
            "reason": reason,
            "synced": server["id"] in synced_ids
        })

    # Sort by score descending
    scored.sort(key=lambda s: s["score"], reverse=True)

    # Split into categories
    recommended = []
    already_synced = []
    other = []

    for server in scored:
        if server["synced"]:
            already_synced.append(server)
        elif server["score"] > 0:
            if len(recommended) < limit:
                recommended.append(server)
            else:
                other.append(server)
        else:
            other.append(server)

    return {
        "recommended": recommended,
        "already_synced": already_synced,
        "other": other,
        "total_servers": len(guilds),
        "profile_configured": profile_configured,
        "keywords_used": keywords[:10] if keywords else []  # Show up to 10
    }


def format_recommendations(data: dict, as_json: bool = False) -> str:
    """Format recommendations for output."""

    if as_json:
        return json.dumps(data, indent=2)

    lines = []

    if not data["recommended"] and not data["already_synced"]:
        lines.append("No servers found.")
        lines.append("")
        lines.append("Make sure your Discord account has joined some servers.")
        return "\n".join(lines)

    lines.append("Server Recommendations")
    lines.append("━" * 50)
    lines.append("")

    # Show profile status
    if data["profile_configured"]:
        keywords = data.get("keywords_used", [])
        if keywords:
            lines.append(f"Using profile keywords: {', '.join(keywords[:5])}...")
        else:
            lines.append("Using priority_servers from config")
    else:
        lines.append("No profile configured - using default AI/tech keywords")
        lines.append("Tip: Run /discord-profile to set up custom interests")
    lines.append("")

    # Already synced
    if data["already_synced"]:
        lines.append(f"Already Synced ({len(data['already_synced'])}):")
        for server in data["already_synced"][:3]:
            members = f"{server['members']:,}" if server['members'] else "?"
            lines.append(f"  ✓ {server['name'][:30]} ({members} members)")
        if len(data["already_synced"]) > 3:
            lines.append(f"  ... and {len(data['already_synced']) - 3} more")
        lines.append("")

    # Recommendations
    if data["recommended"]:
        lines.append(f"Recommended to Sync ({len(data['recommended'])}):")
        for i, server in enumerate(data["recommended"], 1):
            members = f"{server['members']:,}" if server['members'] else "?"
            reason = server["reason"]
            lines.append(f"  {i}. {server['name'][:30]}")
            lines.append(f"     {members} members | {reason}")
        lines.append("")

        # Command hint
        if len(data["recommended"]) == 1:
            server_id = data["recommended"][0]["id"]
            lines.append(f"To sync: python tools/discord_sync.py --server {server_id}")
        else:
            lines.append("To sync all recommended:")
            ids = " ".join(s["id"] for s in data["recommended"][:3])
            lines.append(f"  python tools/discord_sync.py --server {ids.split()[0]}")
    else:
        lines.append("No specific recommendations based on your profile.")
        lines.append("You can sync any server manually with:")
        lines.append("  python tools/discord_list.py --servers")

    # Stats
    lines.append("")
    lines.append(f"Total: {data['total_servers']} servers accessible")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(
        description="Recommend Discord servers to sync based on user profile"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum recommendations (default: 5)"
    )
    args = parser.parse_args()

    try:
        data = await get_recommendations(limit=args.limit)
        print(format_recommendations(data, as_json=args.json))

    except AuthenticationError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DiscordClientError as e:
        print(f"Discord Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
