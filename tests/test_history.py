"""Tests for Query History Storage."""

import pytest
import tempfile
import shutil
from pathlib import Path
from agent_data.nl2sql.history import QueryHistoryItem, QueryHistoryStorage


class TestQueryHistoryItem:
    """Tests for QueryHistoryItem dataclass."""

    def test_item_creation(self):
        """Test creating a history item."""
        item = QueryHistoryItem(
            id="test-1",
            question="SELECT * FROM users",
            sql="SELECT * FROM users",
            answer="Found 10 users",
        )
        assert item.id == "test-1"
        assert item.question == "SELECT * FROM users"
        assert item.favorite is False
        assert item.tags == []

    def test_item_with_data(self):
        """Test creating item with data."""
        item = QueryHistoryItem(
            id="test-2",
            question="Count users",
            sql="SELECT COUNT(*) as count FROM users",
            answer="100 users",
            data=[{"count": 100}],
            columns=["count"],
            row_count=1,
        )
        assert item.data == [{"count": 100}]
        assert item.row_count == 1


class TestQueryHistoryStorage:
    """Tests for QueryHistoryStorage."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create storage with temp directory."""
        return QueryHistoryStorage(storage_dir=str(tmp_path / "history"))

    def test_add_item(self, storage):
        """Test adding an item."""
        item = QueryHistoryItem(
            id="",
            question="Test question",
            sql="SELECT 1",
            answer="Test answer",
        )

        saved = storage.add_item(item)
        assert saved.id != ""
        assert "hist_" in saved.id

    def test_get_history(self, storage):
        """Test getting history."""
        # Add items
        for i in range(5):
            item = QueryHistoryItem(
                id="",
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            storage.add_item(item)

        history = storage.get_history("default")
        assert len(history) == 5
        # Most recent first
        assert history[0].question == "Question 4"

    def test_get_history_with_limit(self, storage):
        """Test getting history with limit."""
        for i in range(10):
            item = QueryHistoryItem(
                id="",
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            storage.add_item(item)

        history = storage.get_history("default", limit=3)
        assert len(history) == 3

    def test_get_history_with_offset(self, storage):
        """Test getting history with offset."""
        for i in range(5):
            item = QueryHistoryItem(
                id="",
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            storage.add_item(item)

        history = storage.get_history("default", offset=2, limit=2)
        assert len(history) == 2
        assert history[0].question == "Question 2"

    def test_get_item(self, storage):
        """Test getting specific item."""
        item = QueryHistoryItem(
            id="test-id",
            question="Test",
            sql="SELECT 1",
            answer="Answer",
        )
        storage.add_item(item)

        retrieved = storage.get_item("default", "test-id")
        # ID might be regenerated, so check content
        assert retrieved is not None
        assert retrieved.question == "Test"

    def test_delete_item(self, storage):
        """Test deleting an item."""
        item = QueryHistoryItem(
            id="delete-me",
            question="Delete me",
            sql="SELECT 1",
            answer="Answer",
        )
        storage.add_item(item)

        deleted = storage.delete_item("default", "delete-me")
        assert deleted is True

        # Verify deleted
        history = storage.get_history("default")
        assert len(history) == 0

    def test_toggle_favorite(self, storage):
        """Test toggling favorite."""
        item = QueryHistoryItem(
            id="fav-test",
            question="Favorite test",
            sql="SELECT 1",
            answer="Answer",
        )
        storage.add_item(item)

        # Toggle on
        updated = storage.toggle_favorite("default", "fav-test")
        assert updated is not None
        assert updated.favorite is True

        # Toggle off
        updated = storage.toggle_favorite("default", "fav-test")
        assert updated.favorite is False

    def test_search(self, storage):
        """Test searching history."""
        items = [
            QueryHistoryItem(id="", question="User count", sql="SELECT COUNT(*)", answer="100"),
            QueryHistoryItem(
                id="", question="Order total", sql="SELECT SUM(amount)", answer="1000"
            ),
            QueryHistoryItem(id="", question="User list", sql="SELECT * FROM users", answer="List"),
        ]
        for item in items:
            storage.add_item(item)

        results = storage.search("default", "user")
        assert len(results) == 2

    def test_clear_history(self, storage):
        """Test clearing all history."""
        for i in range(3):
            item = QueryHistoryItem(
                id="",
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            storage.add_item(item)

        storage.clear_history("default")
        history = storage.get_history("default")
        assert len(history) == 0

    def test_get_stats(self, storage):
        """Test getting statistics."""
        for i in range(5):
            item = QueryHistoryItem(
                id="",
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
                query_time_ms=float(i * 10),
            )
            if i < 2:
                item.favorite = True
            storage.add_item(item)

        stats = storage.get_stats("default")
        assert stats["total_queries"] == 5
        assert stats["favorite_count"] == 2
        assert stats["avg_query_time_ms"] > 0

    def test_max_items_limit(self, storage):
        """Test max items limit."""
        storage.max_items = 3

        for i in range(5):
            item = QueryHistoryItem(
                id="",
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            storage.add_item(item)

        history = storage.get_history("default")
        assert len(history) == 3

    def test_favorite_only_filter(self, storage):
        """Test filtering by favorites."""
        items = [
            QueryHistoryItem(id="", question="Q1", sql="SELECT 1", answer="A1", favorite=True),
            QueryHistoryItem(id="", question="Q2", sql="SELECT 2", answer="A2", favorite=False),
            QueryHistoryItem(id="", question="Q3", sql="SELECT 3", answer="A3", favorite=True),
        ]
        for item in items:
            storage.add_item(item)

        favorites = storage.get_history("default", favorite_only=True)
        assert len(favorites) == 2
        assert all(item.favorite for item in favorites)
