"""Query history storage for NL2SQL."""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class QueryHistoryItem:
    """Single query history item."""

    id: str
    question: str
    sql: str
    answer: str
    data: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    query_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    session_id: str = "default"
    favorite: bool = False
    tags: List[str] = field(default_factory=list)


class QueryHistoryStorage:
    """Query history storage manager.

    Stores query history in JSON files for persistence.
    """

    def __init__(self, storage_dir: str = "./data/history", max_items: int = 1000):
        """Initialize history storage.

        Args:
            storage_dir: Directory to store history files.
            max_items: Maximum number of history items to keep.
        """
        self.storage_dir = Path(storage_dir)
        self.max_items = max_items
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """Create storage directory if it doesn't exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_history_file(self, session_id: str) -> Path:
        """Get history file path for a session."""
        return self.storage_dir / f"{session_id}.json"

    def _load_history(self, session_id: str) -> List[QueryHistoryItem]:
        """Load history from file."""
        history_file = self._get_history_file(session_id)
        if not history_file.exists():
            return []

        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [QueryHistoryItem(**item) for item in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _save_history(self, session_id: str, history: List[QueryHistoryItem]):
        """Save history to file."""
        history_file = self._get_history_file(session_id)
        data = [asdict(item) for item in history]

        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_item(self, item: QueryHistoryItem) -> QueryHistoryItem:
        """Add a new history item.

        Args:
            item: History item to add.

        Returns:
            The added item with generated ID.
        """
        # Generate ID if not provided
        if not item.id:
            item.id = f"hist_{int(time.time() * 1000)}_{os.urandom(4).hex()}"

        # Load existing history
        history = self._load_history(item.session_id)

        # Add new item at the beginning
        history.insert(0, item)

        # Trim if exceeds max items
        if len(history) > self.max_items:
            history = history[: self.max_items]

        # Save
        self._save_history(item.session_id, history)

        return item

    def get_history(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
        favorite_only: bool = False,
    ) -> List[QueryHistoryItem]:
        """Get query history for a session.

        Args:
            session_id: Session identifier.
            limit: Maximum number of items to return.
            offset: Number of items to skip.
            favorite_only: Only return favorite items.

        Returns:
            List of history items.
        """
        history = self._load_history(session_id)

        # Filter favorites if needed
        if favorite_only:
            history = [item for item in history if item.favorite]

        # Apply pagination
        return history[offset : offset + limit]

    def get_item(self, session_id: str, item_id: str) -> Optional[QueryHistoryItem]:
        """Get a specific history item.

        Args:
            session_id: Session identifier.
            item_id: History item ID.

        Returns:
            History item if found, None otherwise.
        """
        history = self._load_history(session_id)
        for item in history:
            if item.id == item_id:
                return item
        return None

    def update_item(
        self,
        session_id: str,
        item_id: str,
        updates: Dict[str, Any],
    ) -> Optional[QueryHistoryItem]:
        """Update a history item.

        Args:
            session_id: Session identifier.
            item_id: History item ID.
            updates: Fields to update.

        Returns:
            Updated item if found, None otherwise.
        """
        history = self._load_history(session_id)

        for i, item in enumerate(history):
            if item.id == item_id:
                # Update fields
                for key, value in updates.items():
                    if hasattr(item, key):
                        setattr(item, key, value)
                history[i] = item

                # Save
                self._save_history(session_id, history)
                return item

        return None

    def delete_item(self, session_id: str, item_id: str) -> bool:
        """Delete a history item.

        Args:
            session_id: Session identifier.
            item_id: History item ID.

        Returns:
            True if deleted, False if not found.
        """
        history = self._load_history(session_id)
        original_length = len(history)

        history = [item for item in history if item.id != item_id]

        if len(history) < original_length:
            self._save_history(session_id, history)
            return True

        return False

    def toggle_favorite(self, session_id: str, item_id: str) -> Optional[QueryHistoryItem]:
        """Toggle favorite status of a history item.

        Args:
            session_id: Session identifier.
            item_id: History item ID.

        Returns:
            Updated item if found, None otherwise.
        """
        history = self._load_history(session_id)

        for i, item in enumerate(history):
            if item.id == item_id:
                item.favorite = not item.favorite
                history[i] = item
                self._save_history(session_id, history)
                return item

        return None

    def search(
        self,
        session_id: str,
        query: str,
        limit: int = 50,
    ) -> List[QueryHistoryItem]:
        """Search history items by question or SQL.

        Args:
            session_id: Session identifier.
            query: Search query.
            limit: Maximum number of results.

        Returns:
            Matching history items.
        """
        history = self._load_history(session_id)
        query_lower = query.lower()

        results = []
        for item in history:
            if query_lower in item.question.lower() or query_lower in item.sql.lower():
                results.append(item)
                if len(results) >= limit:
                    break

        return results

    def clear_history(self, session_id: str):
        """Clear all history for a session.

        Args:
            session_id: Session identifier.
        """
        history_file = self._get_history_file(session_id)
        if history_file.exists():
            history_file.unlink()

    def get_stats(self, session_id: str) -> Dict[str, Any]:
        """Get history statistics.

        Args:
            session_id: Session identifier.

        Returns:
            Statistics dictionary.
        """
        history = self._load_history(session_id)

        total_queries = len(history)
        favorite_count = sum(1 for item in history if item.favorite)

        avg_query_time = 0
        if history:
            avg_query_time = sum(item.query_time_ms for item in history) / len(history)

        return {
            "total_queries": total_queries,
            "favorite_count": favorite_count,
            "avg_query_time_ms": round(avg_query_time, 2),
        }
