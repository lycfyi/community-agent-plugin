#!/usr/bin/env python3
"""Generate Telegram session string for authentication.

This script helps you generate a session string that can be used
to authenticate with Telegram without interactive login.

Usage:
    python generate_session.py

Prerequisites:
    1. Go to https://my.telegram.org/apps
    2. Create an application to get API_ID and API_HASH
    3. Run this script and follow the prompts

The session string will be printed at the end. Save it to your .env file:
    TELEGRAM_SESSION=<session_string>
"""

import sys

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Error: Telethon is not installed.")
    print("Install it with: pip install telethon")
    sys.exit(1)


def main():
    print("=" * 60)
    print("Telegram Session String Generator")
    print("=" * 60)
    print()
    print("This will generate a session string for the telegram-agent plugin.")
    print("You'll need your API credentials from https://my.telegram.org/apps")
    print()

    # Get API credentials
    api_id = input("Enter your API ID: ").strip()
    if not api_id.isdigit():
        print("Error: API ID must be a number")
        sys.exit(1)

    api_hash = input("Enter your API Hash: ").strip()
    if len(api_hash) != 32:
        print("Warning: API Hash is usually 32 characters long")

    print()
    print("Connecting to Telegram...")
    print("You will be prompted for your phone number and verification code.")
    print()

    try:
        with TelegramClient(StringSession(), int(api_id), api_hash) as client:
            session_string = client.session.save()

            print()
            print("=" * 60)
            print("SUCCESS! Your session string is:")
            print("=" * 60)
            print()
            print(session_string)
            print()
            print("=" * 60)
            print()
            print("Add this to your .env file:")
            print()
            print(f"TELEGRAM_API_ID={api_id}")
            print(f"TELEGRAM_API_HASH={api_hash}")
            print(f"TELEGRAM_SESSION={session_string}")
            print()
            print("WARNING: Keep your session string secret!")
            print("Anyone with this string can access your Telegram account.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
