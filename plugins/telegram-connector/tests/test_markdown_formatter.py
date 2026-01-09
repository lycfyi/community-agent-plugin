"""Tests for markdown_formatter module."""

import pytest
from datetime import datetime

from lib.markdown_formatter import (
    format_message_header,
    format_reply_indicator,
    format_forward_indicator,
    format_attachment,
    format_reactions,
    format_message,
    format_group_header,
    format_date_header,
    group_messages_by_date,
)


class TestFormatMessageHeader:
    """Tests for format_message_header function."""

    def test_basic_header(self):
        """Test basic header with name and ID."""
        result = format_message_header(
            timestamp="2026-01-06T10:30:00+00:00",
            sender_name="Alice",
            sender_id=123456,
        )
        assert "10:30 AM" in result
        assert "Alice" in result
        assert "123456" in result

    def test_header_with_username(self):
        """Test header with username takes precedence."""
        result = format_message_header(
            timestamp="2026-01-06T10:30:00+00:00",
            sender_name="Alice Smith",
            sender_id=123456,
            sender_username="alice",
        )
        assert "@alice" in result
        assert "Alice Smith" not in result

    def test_header_pm_time(self):
        """Test PM time formatting."""
        result = format_message_header(
            timestamp="2026-01-06T14:30:00+00:00",
            sender_name="Bob",
            sender_id=789,
        )
        assert "2:30 PM" in result


class TestFormatReplyIndicator:
    """Tests for format_reply_indicator function."""

    def test_reply_format(self):
        """Test reply indicator formatting."""
        result = format_reply_indicator("alice")
        assert result == "↳ replying to @alice:"


class TestFormatForwardIndicator:
    """Tests for format_forward_indicator function."""

    def test_forward_format(self):
        """Test forward indicator formatting."""
        result = format_forward_indicator("@news_channel")
        assert result == "↪ forwarded from @news_channel:"


class TestFormatAttachment:
    """Tests for format_attachment function."""

    def test_photo_attachment(self):
        """Test photo attachment formatting."""
        result = format_attachment({"type": "photo"})
        assert "[photo]" in result

    def test_photo_with_filename(self):
        """Test photo with filename and size."""
        result = format_attachment({
            "type": "photo",
            "filename": "vacation.jpg",
            "size": 1258291,  # ~1.2MB
        })
        assert "[photo:" in result
        assert "vacation.jpg" in result
        assert "1.2MB" in result

    def test_video_with_duration(self):
        """Test video with duration."""
        result = format_attachment({
            "type": "video",
            "duration": 30,
        })
        assert "[video:" in result
        assert "30s" in result

    def test_voice_message(self):
        """Test voice message formatting."""
        result = format_attachment({
            "type": "voice",
            "duration": 15,
        })
        assert "[voice: 15s]" in result

    def test_sticker_with_emoji(self):
        """Test sticker with emoji."""
        result = format_attachment({
            "type": "sticker",
            "emoji": "👋",
        })
        assert "[sticker: 👋]" in result

    def test_document_with_size(self):
        """Test document with filename and size."""
        result = format_attachment({
            "type": "document",
            "filename": "report.pdf",
            "size": 250880,  # ~245KB
        })
        assert "[file:" in result
        assert "report.pdf" in result
        assert "245KB" in result


class TestFormatReactions:
    """Tests for format_reactions function."""

    def test_empty_reactions(self):
        """Test empty reactions list."""
        result = format_reactions([])
        assert result == ""

    def test_single_reaction(self):
        """Test single reaction formatting."""
        result = format_reactions([{"emoji": "❤️", "count": 5}])
        assert "Reactions:" in result
        assert "❤️ 5" in result

    def test_multiple_reactions(self):
        """Test multiple reactions formatting."""
        result = format_reactions([
            {"emoji": "❤️", "count": 5},
            {"emoji": "👍", "count": 3},
        ])
        assert "❤️ 5" in result
        assert "👍 3" in result
        assert "|" in result


class TestFormatMessage:
    """Tests for format_message function."""

    def test_simple_message(self):
        """Test simple text message."""
        msg = {
            "timestamp": "2026-01-06T10:30:00+00:00",
            "sender_name": "Alice",
            "sender_id": 123456,
            "content": "Hello everyone!",
        }
        result = format_message(msg)
        assert "10:30 AM" in result
        assert "Alice" in result
        assert "Hello everyone!" in result

    def test_message_with_reply(self):
        """Test message with reply indicator."""
        msg = {
            "timestamp": "2026-01-06T10:31:00+00:00",
            "sender_name": "Bob",
            "sender_id": 789,
            "content": "Hey Alice!",
            "reply_to_author": "alice",
        }
        result = format_message(msg)
        assert "↳ replying to @alice:" in result

    def test_message_with_forward(self):
        """Test forwarded message."""
        msg = {
            "timestamp": "2026-01-06T10:32:00+00:00",
            "sender_name": "Charlie",
            "sender_id": 456,
            "content": "Breaking news...",
            "forward_from": "@news_channel",
        }
        result = format_message(msg)
        assert "↪ forwarded from @news_channel:" in result

    def test_message_with_attachment(self):
        """Test message with attachment."""
        msg = {
            "timestamp": "2026-01-06T10:33:00+00:00",
            "sender_name": "Dave",
            "sender_id": 111,
            "content": "Check this out",
            "attachments": [{"type": "photo", "filename": "pic.jpg", "size": 102400}],
        }
        result = format_message(msg)
        assert "[photo:" in result

    def test_message_with_reactions(self):
        """Test message with reactions."""
        msg = {
            "timestamp": "2026-01-06T10:34:00+00:00",
            "sender_name": "Eve",
            "sender_id": 222,
            "content": "Great idea!",
            "reactions": [{"emoji": "👍", "count": 10}],
        }
        result = format_message(msg)
        assert "Reactions:" in result
        assert "👍 10" in result


class TestFormatGroupHeader:
    """Tests for format_group_header function."""

    def test_basic_header(self):
        """Test basic group header."""
        result = format_group_header(
            group_name="My Group",
            group_id=1234567890,
            group_type="supergroup",
        )
        assert "# My Group" in result
        assert "1234567890" in result
        assert "supergroup" in result

    def test_header_with_topic(self):
        """Test header with topic info."""
        result = format_group_header(
            group_name="My Group",
            group_id=1234567890,
            group_type="supergroup",
            topic_name="general",
            topic_id=1,
        )
        assert "Topic: general (1)" in result


class TestFormatDateHeader:
    """Tests for format_date_header function."""

    def test_date_header(self):
        """Test date header formatting."""
        result = format_date_header("2026-01-06")
        assert result == "## 2026-01-06"


class TestGroupMessagesByDate:
    """Tests for group_messages_by_date function."""

    def test_group_single_date(self):
        """Test grouping messages from single date."""
        messages = [
            {"timestamp": "2026-01-06T10:30:00+00:00", "content": "msg1"},
            {"timestamp": "2026-01-06T11:30:00+00:00", "content": "msg2"},
        ]
        result = group_messages_by_date(messages)
        assert "2026-01-06" in result
        assert len(result["2026-01-06"]) == 2

    def test_group_multiple_dates(self):
        """Test grouping messages from multiple dates."""
        messages = [
            {"timestamp": "2026-01-05T10:30:00+00:00", "content": "msg1"},
            {"timestamp": "2026-01-06T11:30:00+00:00", "content": "msg2"},
        ]
        result = group_messages_by_date(messages)
        assert "2026-01-05" in result
        assert "2026-01-06" in result
        assert len(result["2026-01-05"]) == 1
        assert len(result["2026-01-06"]) == 1

    def test_skip_empty_timestamps(self):
        """Test skipping messages without timestamps."""
        messages = [
            {"timestamp": "2026-01-06T10:30:00+00:00", "content": "msg1"},
            {"content": "msg2"},  # No timestamp
        ]
        result = group_messages_by_date(messages)
        assert len(result["2026-01-06"]) == 1
