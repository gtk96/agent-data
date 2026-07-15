"""Tests for SQLite-backed conversation memory."""
import os
import tempfile

from agent_data.nl2sql.memory import ConversationTurn, SQLiteConversationMemory


def test_add_and_get():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        hist = mem.get_history("s1")
        assert len(hist) == 1
        assert hist[0].question == "q1"
        assert hist[0].sql == "SELECT 1"
        assert hist[0].answer == "a1"


def test_persistence():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem1 = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem1.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        # Simulate restart
        mem2 = SQLiteConversationMemory(db_path=db, max_turns=10)
        hist = mem2.get_history("s1")
        assert len(hist) == 1
        assert hist[0].question == "q1"


def test_max_turns():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=3)
        for i in range(5):
            mem.add_turn("s1", ConversationTurn(question=f"q{i}", sql=f"SELECT {i}", answer=f"a{i}"))
        hist = mem.get_history("s1")
        assert len(hist) == 3
        assert hist[0].question == "q2"


def test_clear_session():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        mem.clear_session("s1")
        assert mem.get_history("s1") == []


def test_context_string():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        ctx = mem.get_context_string("s1")
        assert "## Conversation History" in ctx
        assert "q1" in ctx
