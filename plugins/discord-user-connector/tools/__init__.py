"""Discord tools for Claude Code.

Available tools:
- discord_init: Initialize configuration from Discord account
- discord_list: List servers and channels
- discord_sync: Sync messages to local storage
- discord_read: Read and search synced messages
- discord_send: Send messages to Discord
- discord_manifest: Get or create data manifest
"""

__all__ = [
    "discord_init",
    "discord_list",
    "discord_manifest",
    "discord_read",
    "discord_send",
    "discord_sync",
]
