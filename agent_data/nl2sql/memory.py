"""Conversation memory management for NL2SQL."""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional


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

    def get_context_string(self, session_id: str) -> str:
        """Format conversation history as context string for LLM.

        Args:
            session_id: Session identifier.

        Returns:
            Formatted context string.
        """
        history = self.get_history(session_id)
        if not history:
            return ""

        lines = ["## Conversation History"]
        for i, turn in enumerate(history[-3:], 1):  # Last 3 turns
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
