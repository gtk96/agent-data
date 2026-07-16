"""Conversation history export/import.

Wraps any memory backend (SQLite or in-memory) to provide
JSON-based export and import for backup, migration, or sharing.

Format: agent-data.conversation/v1
{
  "format": "agent-data.conversation/v1",
  "exported_at": "2026-07-16T00:00:00Z",
  "session_count": 2,
  "sessions": [
    {
      "session_id": "...",
      "turns": [
        {"question": "...", "sql": "...", "answer": "...",
         "timestamp": 1234567890.0, "metadata": {}}
      ]
    }
  ]
}
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_data.nl2sql.memory import ConversationTurn, SQLiteConversationMemory


FORMAT_VERSION = "agent-data.conversation/v1"


class ConversationExporter:
    """Export and import conversation history as JSON."""

    def __init__(self, memory: SQLiteConversationMemory):
        self.memory = memory

    def export_session(self, session_id: str) -> Dict[str, Any]:
        """Export a single session's turns as a dict."""
        history = self.memory.get_history(session_id)
        return {
            "session_id": session_id,
            "turns": [
                {
                    "question": turn.question,
                    "sql": turn.sql,
                    "answer": turn.answer,
                    "timestamp": turn.timestamp,
                    "metadata": turn.metadata,
                }
                for turn in history
            ],
        }

    def export_to_json_string(self, session_id: str) -> str:
        """Export a session as a JSON string."""
        return json.dumps(
            self.export_session(session_id),
            ensure_ascii=False,
            indent=2,
        )

    def export_to_file(self, session_id: str, path: str) -> None:
        """Export a session to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.export_session(session_id), f, ensure_ascii=False, indent=2)

    def export_all_sessions(self) -> Dict[str, Any]:
        """Export all sessions as a single dict.

        Returns:
            Dict with format, exported_at, session_count, sessions list.
        """
        sessions_meta = self.memory.list_sessions()
        sessions = []
        for meta in sessions_meta:
            sid = meta["session_id"]
            history = self.memory.get_history(sid)
            sessions.append({
                "session_id": sid,
                "turns": [
                    {
                        "question": turn.question,
                        "sql": turn.sql,
                        "answer": turn.answer,
                        "timestamp": turn.timestamp,
                        "metadata": turn.metadata,
                    }
                    for turn in history
                ],
            })
        return {
            "format": FORMAT_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session_count": len(sessions),
            "sessions": sessions,
        }

    def export_all_to_file(self, path: str) -> None:
        """Export all sessions to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.export_all_sessions(), f, ensure_ascii=False, indent=2)

    def import_session(
        self,
        target_memory: SQLiteConversationMemory,
        data: Dict[str, Any],
        new_session_id: Optional[str] = None,
    ) -> str:
        """Import a single session's turns into target memory.

        Skips turns that already exist (by question+sql+answer hash).

        Args:
            target_memory: Target SQLiteConversationMemory to import into.
            data: Dict from export_session() / loaded JSON.
            new_session_id: If set, override the session_id. If None, use data["session_id"].

        Returns:
            The actual session_id used in target.
        """
        sid = new_session_id or data["session_id"]

        # Build set of existing turn signatures for dedup
        existing = target_memory.get_history(sid)
        existing_sigs = {
            self._turn_signature(t.question, t.sql, t.answer)
            for t in existing
        }

        imported_count = 0
        for turn_data in data.get("turns", []):
            sig = self._turn_signature(
                turn_data["question"],
                turn_data["sql"],
                turn_data["answer"],
            )
            if sig in existing_sigs:
                continue
            turn = ConversationTurn(
                question=turn_data["question"],
                sql=turn_data["sql"],
                answer=turn_data["answer"],
                timestamp=turn_data.get("timestamp", 0.0),
                metadata=turn_data.get("metadata", {}),
            )
            target_memory.add_turn(sid, turn)
            existing_sigs.add(sig)
            imported_count += 1

        return sid

    def import_all_sessions(
        self,
        target_memory: SQLiteConversationMemory,
        data: Dict[str, Any],
    ) -> int:
        """Import all sessions from export_all_sessions() output.

        Returns:
            Number of sessions imported.
        """
        sessions = data.get("sessions", [])
        for session_data in sessions:
            self.import_session(target_memory, session_data)
        return len(sessions)

    @staticmethod
    def _turn_signature(question: str, sql: str, answer: str) -> str:
        """Generate a signature for dedup of turns."""
        return f"{question}::{sql}::{answer}"
