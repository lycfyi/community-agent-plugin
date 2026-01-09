"""Tests for storage module."""

import pytest
import tempfile
from pathlib import Path

from lib.storage import Storage, StorageError


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Storage(base_dir=Path(tmpdir))


class TestStorageSyncState:
    """Tests for sync state operations."""

    def test_get_sync_state_nonexistent(self, temp_storage):
        """Test getting sync state for non-existent group."""
        result = temp_storage.get_sync_state(123456)
        assert result == {}

    def test_save_and_get_sync_state(self, temp_storage):
        """Test saving and retrieving sync state."""
        state = {
            "group_id": 123456,
            "group_name": "Test Group",
            "last_sync": "2026-01-06T10:00:00Z",
            "channels": {},
        }
        temp_storage.save_sync_state(123456, state, "Test Group")

        result = temp_storage.get_sync_state(123456)
        assert result["group_id"] == 123456
        assert result["group_name"] == "Test Group"

    def test_get_last_message_id_none(self, temp_storage):
        """Test getting last message ID when not synced."""
        result = temp_storage.get_last_message_id(123456)
        assert result is None

    def test_update_channel_sync_state(self, temp_storage):
        """Test updating channel sync state."""
        temp_storage.update_channel_sync_state(
            group_id=123456,
            group_name="Test Group",
            topic_name="general",
            topic_id=None,
            last_message_id=999,
            message_count=50,
        )

        last_id = temp_storage.get_last_message_id(123456, "general")
        assert last_id == 999

        state = temp_storage.get_sync_state(123456)
        assert state["channels"]["general"]["message_count"] == 50


class TestStorageMessages:
    """Tests for message storage operations."""

    def test_append_messages_creates_file(self, temp_storage):
        """Test that appending messages creates the file."""
        messages = [
            {
                "id": 1,
                "timestamp": "2026-01-06T10:30:00+00:00",
                "sender_name": "Alice",
                "sender_id": 111,
                "content": "Hello!",
            },
        ]

        temp_storage.append_messages(
            group_id=123456,
            group_name="Test Group",
            topic_id=None,
            topic_name="general",
            messages=messages,
        )

        file_path = temp_storage.get_messages_file(123456)
        assert file_path.exists()

    def test_read_messages_nonexistent(self, temp_storage):
        """Test reading messages from non-existent file."""
        with pytest.raises(StorageError):
            temp_storage.read_messages(999999)

    def test_read_messages_content(self, temp_storage):
        """Test reading message content."""
        messages = [
            {
                "id": 1,
                "timestamp": "2026-01-06T10:30:00+00:00",
                "sender_name": "Alice",
                "sender_id": 111,
                "content": "Hello!",
            },
            {
                "id": 2,
                "timestamp": "2026-01-06T10:31:00+00:00",
                "sender_name": "Bob",
                "sender_id": 222,
                "content": "Hi there!",
            },
        ]

        temp_storage.append_messages(
            group_id=123456,
            group_name="Test Group",
            topic_id=None,
            topic_name="general",
            messages=messages,
        )

        content = temp_storage.read_messages(123456)
        assert "Hello!" in content
        assert "Hi there!" in content
        assert "Alice" in content
        assert "Bob" in content

    def test_read_messages_last_n(self, temp_storage):
        """Test reading last N messages."""
        messages = [
            {
                "id": i,
                "timestamp": f"2026-01-06T10:{30+i:02d}:00+00:00",
                "sender_name": f"User{i}",
                "sender_id": i,
                "content": f"Message {i}",
            }
            for i in range(5)
        ]

        temp_storage.append_messages(
            group_id=123456,
            group_name="Test Group",
            topic_id=None,
            topic_name="general",
            messages=messages,
        )

        content = temp_storage.read_messages(123456, last_n=2)
        assert "Message 3" in content
        assert "Message 4" in content

    def test_search_messages(self, temp_storage):
        """Test searching messages."""
        messages = [
            {
                "id": 1,
                "timestamp": "2026-01-06T10:30:00+00:00",
                "sender_name": "Alice",
                "sender_id": 111,
                "content": "I love Python programming!",
            },
            {
                "id": 2,
                "timestamp": "2026-01-06T10:31:00+00:00",
                "sender_name": "Bob",
                "sender_id": 222,
                "content": "JavaScript is also great.",
            },
        ]

        temp_storage.append_messages(
            group_id=123456,
            group_name="Test Group",
            topic_id=None,
            topic_name="general",
            messages=messages,
        )

        results = temp_storage.search_messages(123456, "general", "Python")
        assert len(results) == 1
        assert "Python" in results[0]


class TestStorageMetadata:
    """Tests for group metadata operations."""

    def test_save_group_metadata(self, temp_storage):
        """Test saving group metadata."""
        temp_storage.save_group_metadata(
            group_id=123456,
            group_name="Test Group",
            group_type="supergroup",
            username="testgroup",
            member_count=100,
            has_topics=False,
        )

        # Verify file exists
        group_dir = temp_storage._get_group_dir(123456, "Test Group")
        metadata_file = group_dir / "group.yaml"
        assert metadata_file.exists()


class TestStorageManifest:
    """Tests for manifest operations."""

    def test_update_manifest_empty(self, temp_storage):
        """Test updating manifest with no data."""
        manifest = temp_storage.update_manifest()
        assert manifest["summary"]["total_groups"] == 0
        assert manifest["summary"]["total_messages"] == 0
        assert manifest["summary"]["platform"] == "telegram"

    def test_update_manifest_with_data(self, temp_storage):
        """Test updating manifest with synced data."""
        # Create some sync data
        temp_storage.update_channel_sync_state(
            group_id=123456,
            group_name="Test Group",
            topic_name="general",
            topic_id=None,
            last_message_id=100,
            message_count=50,
        )

        manifest = temp_storage.update_manifest()
        assert manifest["summary"]["total_groups"] == 1
        assert manifest["summary"]["total_messages"] == 50
        assert len(manifest["groups"]) == 1
        assert manifest["groups"][0]["name"] == "Test Group"

    def test_get_manifest_creates_if_missing(self, temp_storage):
        """Test that get_manifest creates manifest if missing."""
        manifest = temp_storage.get_manifest()
        assert "generated_at" in manifest
        assert "summary" in manifest


class TestStorageDirectoryNaming:
    """Tests for directory naming conventions."""

    def test_slugify_basic(self, temp_storage):
        """Test basic slugification."""
        slug = temp_storage._slugify("My Test Group")
        assert slug == "my-test-group"

    def test_slugify_special_chars(self, temp_storage):
        """Test slugification with special characters."""
        slug = temp_storage._slugify("Test@Group#123!")
        assert "testgroup123" in slug

    def test_get_group_dir_with_name(self, temp_storage):
        """Test group directory naming with name."""
        group_dir = temp_storage._get_group_dir(123456, "My Group")
        assert "123456-my-group" in str(group_dir)

    def test_get_group_dir_without_name(self, temp_storage):
        """Test group directory naming without name."""
        group_dir = temp_storage._get_group_dir(123456)
        assert "123456" in str(group_dir)
