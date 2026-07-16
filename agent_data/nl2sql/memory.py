"""Conversation memory management for NL2SQL."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConversationTurn:
    """Single conversation turn."""

    question: str
    sql: str
    answer: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class ConversationMemory:
    """Conversation memory manager.

    Stores conversation history for follow-up questions.
    """

    def __init__(self, max_turns: int = 10, ttl_seconds: int = 3600):
        """Initialize memory manager.

        Args:
            max_turns: Maximum number of turns to keep per session.
            ttl_seconds: Time-to-live for sessions in seconds.
        """
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, deque] = {}

    def add_turn(self, session_id: str, turn: ConversationTurn):
        """Add a conversation turn.

        Args:
            session_id: Session identifier.
            turn: Conversation turn to add.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self.max_turns)

        self._sessions[session_id].append(turn)

    def get_history(self, session_id: str, n: Optional[int] = None) -> List[ConversationTurn]:
        """Get recent conversation history.

        Args:
            session_id: Session identifier.
            n: Number of recent turns to return. None for all.

        Returns:
            List of conversation turns.
        """
        if session_id not in self._sessions:
            return []

        history = list(self._sessions[session_id])
        if n is not None:
            history = history[-n:]
        return history

    def get_context_string(self, session_id: str, recent_turns: int = 3) -> str:
        """Format conversation history as context string for LLM.

        Args:
            session_id: Session identifier.
            recent_turns: Number of recent turns to keep in full detail.

        Returns:
            Formatted context string.
        """
        history = self.get_history(session_id)
        if not history:
            return ""

        lines = ["## Conversation History"]
        if len(history) <= recent_turns:
            for i, turn in enumerate(history, 1):
                lines.append(f"\n### Turn {i}")
                lines.append(f"User: {turn.question}")
                lines.append(f"SQL: {turn.sql}")
                lines.append(f"Answer: {turn.answer}")
        else:
            older_turns = history[:-recent_turns]
            recent = history[-recent_turns:]

            tables_mentioned = set()
            question_patterns = []
            for turn in older_turns:
                import re
                tables = re.findall(r"FROM\s+(\w+)", turn.sql.upper())
                tables_mentioned.update(tables)
                question_patterns.append(turn.question)

            if tables_mentioned:
                lines.append(f"\n### Earlier context ({len(older_turns)} turns ago)")
                lines.append(
                    f"Previously asked about: {', '.join(sorted(tables_mentioned))} tables. "
                    f"Questions included: {'; '.join(question_patterns[-3:])}"
                )

            for i, turn in enumerate(recent, 1):
                lines.append(f"\n### Turn {i}")
                lines.append(f"User: {turn.question}")
                lines.append(f"SQL: {turn.sql}")
                lines.append(f"Answer: {turn.answer}")

        return "\n".join(lines)

    def clear_session(self, session_id: str):
        """Clear a session's memory.

        Args:
            session_id: Session identifier to clear.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]

    def cleanup_expired(self):
        """Clean up expired sessions."""
        current_time = time.time()
        expired_sessions = []

        for session_id, turns in self._sessions.items():
            if turns:
                last_turn_time = turns[-1].timestamp
                if current_time - last_turn_time > self.ttl_seconds:
                    expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self._sessions[session_id]

    def get_session_count(self) -> int:
        """Get number of active sessions.

        Returns:
            Number of active sessions.
        """
        return len(self._sessions)

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List active sessions with their last question and turn count.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of dicts with session_id, last_question, turn_count, last_timestamp.
        """
        sessions = []
        for sid, turns in self._sessions.items():
            if turns:
                last = turns[-1]
                sessions.append({
                    "session_id": sid,
                    "last_question": last.question,
                    "turn_count": len(turns),
                    "last_timestamp": last.timestamp,
                })
        sessions.sort(key=lambda x: x["last_timestamp"], reverse=True)
        return sessions[:limit]


class SQLiteConversationMemory:
    """SQLite-backed conversation memory. Drop-in replacement for ConversationMemory."""

    def __init__(
        self,
        db_path: str = "./data/conversations.db",
        max_turns: int = 10,
        ttl_seconds: int = 3600,
    ):
        self.db_path = db_path
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        from pathlib import Path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                sql TEXT NOT NULL,
                answer TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id, timestamp)"
        )
        conn.close()

    def _conn(self):
        import sqlite3
        return sqlite3.connect(self.db_path)

    def add_turn(self, session_id: str, turn: ConversationTurn):
        import json
        conn = self._conn()
        conn.execute(
            "INSERT INTO conversations (session_id, question, sql, answer, timestamp, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                turn.question,
                turn.sql,
                turn.answer,
                turn.timestamp,
                json.dumps(turn.metadata, ensure_ascii=False),
            ),
        )
        # Trim to max_turns: delete oldest rows beyond the limit
        # SQLite doesn't support LIMIT in DELETE, use subquery instead
        conn.execute(
            """
            DELETE FROM conversations WHERE id IN (
                SELECT c1.id FROM conversations c1
                JOIN (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY timestamp DESC) as rn
                    FROM conversations WHERE session_id = ?
                ) c2 ON c1.id = c2.id
                WHERE c2.rn > ?
            )
            """,
            (session_id, self.max_turns),
        )
        conn.commit()
        conn.close()

    def get_history(self, session_id: str, n: Optional[int] = None) -> List[ConversationTurn]:
        import json
        conn = self._conn()
        limit = n or self.max_turns
        rows = conn.execute(
            "SELECT question, sql, answer, timestamp, metadata_json "
            "FROM conversations WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        conn.close()
        return [
            ConversationTurn(
                question=r[0],
                sql=r[1],
                answer=r[2],
                timestamp=r[3],
                metadata=json.loads(r[4]),
            )
            for r in reversed(rows)
        ]

    def get_context_string(self, session_id: str, recent_turns: int = 3) -> str:
        """Format conversation history as context string for LLM.

        When conversation has more than `recent_turns` turns, the older turns
        are compressed into a one-line summary, while the most recent turns
        are kept in full detail.

        Args:
            session_id: Session identifier.
            recent_turns: Number of recent turns to keep in full detail (default 3).

        Returns:
            Formatted context string.
        """
        history = self.get_history(session_id)
        if not history:
            return ""
        lines = ["## Conversation History"]

        if len(history) <= recent_turns:
            # Few turns: show all in detail
            for i, turn in enumerate(history, 1):
                lines.append(f"\n### Turn {i}")
                lines.append(f"User: {turn.question}")
                lines.append(f"SQL: {turn.sql}")
                lines.append(f"Answer: {turn.answer}")
        else:
            # Many turns: summarize older ones, show recent in detail
            older_turns = history[:-recent_turns]
            recent = history[-recent_turns:]

            # Compress older turns into a summary
            tables_mentioned = set()
            question_patterns = []
            for turn in older_turns:
                # Extract table names from SQL
                import re
                tables = re.findall(r"FROM\s+(\w+)", turn.sql.upper())
                tables_mentioned.update(tables)
                # Keep first question of each older turn as pattern
                question_patterns.append(turn.question)

            if tables_mentioned:
                lines.append(f"\n### Earlier context ({len(older_turns)} turns ago)")
                lines.append(
                    f"Previously asked about: {', '.join(sorted(tables_mentioned))} tables. "
                    f"Questions included: {'; '.join(question_patterns[-3:])}"
                )

            # Show recent turns in full detail
            for i, turn in enumerate(recent, 1):
                lines.append(f"\n### Turn {i}")
                lines.append(f"User: {turn.question}")
                lines.append(f"SQL: {turn.sql}")
                lines.append(f"Answer: {turn.answer}")

        return "\n".join(lines)

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List active sessions with their last question and turn count.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of dicts with session_id, last_question, turn_count, last_timestamp.
        """
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT session_id, question, timestamp,
                   (SELECT COUNT(*) FROM conversations c2 WHERE c2.session_id = c1.session_id) as turn_count
            FROM conversations c1
            WHERE id IN (
                SELECT id FROM conversations GROUP BY session_id
                HAVING id = MAX(id)
            )
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                "session_id": r[0],
                "last_question": r[1],
                "turn_count": r[3],
                "last_timestamp": r[2],
            }
            for r in rows
        ]

    def clear_session(self, session_id: str):
        conn = self._conn()
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def cleanup_expired(self):
        cutoff = time.time() - self.ttl_seconds
        conn = self._conn()
        conn.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()

    def get_session_count(self) -> int:
        conn = self._conn()
        count = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM conversations"
        ).fetchone()[0]
        conn.close()
        return count
