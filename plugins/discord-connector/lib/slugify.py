"""
Slugify utilities for creating human-readable filenames.

Provides hybrid {id}_{slug} naming for Discord entities.
"""

import re
import unicodedata


def slugify(text: str, max_length: int = 30) -> str:
    """
    Convert text to a URL/filename-safe slug.

    Rules:
    - Convert to lowercase
    - Replace spaces and special chars with hyphens
    - Remove emoji and non-ASCII (keep alphanumeric + hyphen only)
    - Truncate to max_length chars
    - Remove leading/trailing hyphens

    Args:
        text: The text to slugify
        max_length: Maximum length of the slug (default 30)

    Returns:
        A slug string safe for filenames

    Examples:
        >>> slugify("Dubbing AI")
        'dubbing-ai'
        >>> slugify("John's Server")
        'johns-server'
        >>> slugify("Server with emoji ===")
        'server-with-emoji'
    """
    if not text:
        return "unnamed"

    # Normalize unicode (decompose accented chars)
    text = unicodedata.normalize('NFKD', text)

    # Convert to lowercase
    text = text.lower()

    # Remove emoji and other non-ASCII characters
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Replace spaces and common separators with hyphens
    text = re.sub(r'[\s_\-\.]+', '-', text)

    # Keep only alphanumeric and hyphens
    text = re.sub(r'[^a-z0-9\-]', '', text)

    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    # Truncate to max length
    if len(text) > max_length:
        # Try to cut at a hyphen boundary
        truncated = text[:max_length]
        last_hyphen = truncated.rfind('-')
        if last_hyphen > max_length // 2:
            text = truncated[:last_hyphen]
        else:
            text = truncated.rstrip('-')

    return text or "unnamed"


def make_hybrid_name(id_value: str, display_name: str, max_slug_length: int = 30) -> str:
    """
    Create a hybrid {id}_{slug} name for directories/files.

    Args:
        id_value: The unique ID (e.g., Discord snowflake)
        display_name: Human-readable name to slugify
        max_slug_length: Maximum length of the slug portion

    Returns:
        A hybrid name like "1234567890_dubbing-ai"

    Examples:
        >>> make_hybrid_name("1234567890", "Dubbing AI")
        '1234567890_dubbing-ai'
        >>> make_hybrid_name("111222333", "John Doe")
        '111222333_john-doe'
    """
    slug = slugify(display_name, max_length=max_slug_length)
    return f"{id_value}_{slug}"


def parse_hybrid_name(hybrid_name: str) -> tuple[str, str]:
    """
    Parse a hybrid {id}_{slug} name back into components.

    Args:
        hybrid_name: A hybrid name like "1234567890_dubbing-ai"

    Returns:
        Tuple of (id, slug)

    Examples:
        >>> parse_hybrid_name("1234567890_dubbing-ai")
        ('1234567890', 'dubbing-ai')
        >>> parse_hybrid_name("111222333_john-doe.yaml")
        ('111222333', 'john-doe')
    """
    # Remove file extension if present
    if '.' in hybrid_name:
        hybrid_name = hybrid_name.rsplit('.', 1)[0]

    # Split on first underscore
    parts = hybrid_name.split('_', 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    return (hybrid_name, "")


def extract_id_from_hybrid(hybrid_name: str) -> str:
    """
    Extract just the ID portion from a hybrid name.

    Args:
        hybrid_name: A hybrid name like "1234567890_dubbing-ai"

    Returns:
        The ID portion
    """
    id_value, _ = parse_hybrid_name(hybrid_name)
    return id_value
