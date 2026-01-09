# Telegram Session String Generation

This guide explains how to generate the session string required for the telegram-agent plugin.

## What is a Session String?

A session string is an encoded authentication token that allows the plugin to access your Telegram account without requiring interactive login (phone number, verification code, 2FA) each time.

## Prerequisites

1. **Python 3.11+** installed
2. **Telethon** library: `pip install telethon`
3. **Telegram API credentials** from https://my.telegram.org/apps

## Getting API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click on "API development tools"
4. Create a new application (any name/description)
5. Note your **API ID** (a number) and **API Hash** (32-character string)

## Generating the Session String

### Method 1: Using the Provided Script

```bash
cd plugins/telegram-agent
pip install telethon
python scripts/generate_session.py
```

Follow the prompts:
1. Enter your API ID
2. Enter your API Hash
3. Enter your phone number (with country code, e.g., +1234567890)
4. Enter the verification code sent to your Telegram
5. Enter your 2FA password (if enabled)

The script will output your session string.

### Method 2: Manual Generation

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = YOUR_API_ID  # Replace with your API ID
api_hash = "YOUR_API_HASH"  # Replace with your API Hash

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Your session string:")
    print(client.session.save())
```

## Setting Up Your Environment

Add these to your `.env` file:

```bash
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
TELEGRAM_SESSION=1ABCD2EFGH3IJKL4MNOP5QRST...
```

## Security Considerations

### Keep Your Session String Secret

- **Never share** your session string with anyone
- **Never commit** it to version control
- Anyone with your session string can access your Telegram account
- Store it only in `.env` files that are gitignored

### Session Expiration

Sessions may expire if:
- You log out from all devices in Telegram settings
- You revoke the session from "Active Sessions" in Telegram
- Telegram detects suspicious activity

If your session expires, generate a new one.

### Revoking Access

If you suspect your session string has been compromised:

1. Open Telegram on your phone
2. Go to Settings → Privacy and Security → Active Sessions
3. Terminate the suspicious session
4. Generate a new session string

## Troubleshooting

### "SessionExpiredError"

Your session has expired. Generate a new session string.

### "FloodWaitError"

You're being rate limited. Wait the specified time and try again.

### "AuthKeyUnregisteredError"

The session was revoked. Generate a new session string.

### "PhoneNumberInvalidError"

Make sure to include the country code (e.g., +1 for US).

## Terms of Service Warning

Using the Telegram API with a user account (not a bot) may violate Telegram's Terms of Service. This tool is intended for:

- Personal message archival
- Analyzing communities you participate in
- Personal automation

**Do not use for:**
- Scraping public groups at scale
- Spam or automated messaging
- Circumventing rate limits
- Any commercial purposes

Use at your own risk. The authors are not responsible for any account restrictions.
