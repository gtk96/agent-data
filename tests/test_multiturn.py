"""Tests for multi-turn conversation support."""
import tempfile, os, json
from agent_data.nl2sql.memory import ConversationTurn, SQLiteConversationMemory, ConversationMemory


def test_context_string_short_session():
    """3 turns or fewer: all shown in detail."""
    mem = ConversationMemory(max_turns=10)
    for i in range(3):
        mem.add_turn("s1", ConversationTurn(question=f"q{i}", sql=f"SELECT {i}", answer=f"a{i}"))
    ctx = mem.get_context_string("s1")
    assert "Turn 1" in ctx
    assert "Turn 3" in ctx
    assert "q0" in ctx
    assert "q2" in ctx
    assert "Earlier context" not in ctx


def test_context_string_long_session_summarized():
    """More than 3 turns: older turns summarized, recent in detail."""
    mem = ConversationMemory(max_turns=10)
    for i in range(5):
        mem.add_turn("s1", ConversationTurn(
            question=f"查{['用户','订单','产品'][i%3]}表",
            sql=f"SELECT * FROM {['users','orders','products'][i%3]}",
            answer=f"结果{i}",
        ))
    ctx = mem.get_context_string("s1")
    assert "Earlier context (2 turns ago)" in ctx
    assert "users" in ctx  # tables mentioned in older turns
    assert "orders" in ctx
    assert "Turn 1" in ctx  # recent turns still in detail
    assert "Turn 3" in ctx
    assert "查产品表" in ctx  # turn 3 question


def test_list_sessions_sqlite():
    """list_sessions returns session summaries."""
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        mem.add_turn("s2", ConversationTurn(question="q2", sql="SELECT 2", answer="a2"))
        sessions = mem.list_sessions()
        assert len(sessions) == 2
        ids = {s["session_id"] for s in sessions}
        assert ids == {"s1", "s2"}
        for s in sessions:
            assert "turn_count" in s
            assert "last_question" in s


def test_list_sessions_memory():
    """list_sessions works on in-memory ConversationMemory."""
    mem = ConversationMemory(max_turns=10)
    mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
    mem.add_turn("s2", ConversationTurn(question="q2", sql="SELECT 2", answer="a2"))
    sessions = mem.list_sessions()
    assert len(sessions) == 2
    assert sessions[0]["session_id"] in {"s1", "s2"}


def test_context_string_empty_session():
    mem = ConversationMemory(max_turns=10)
    ctx = mem.get_context_string("nonexistent")
    assert ctx == ""


def test_sqlite_context_string_summary():
    """SQLite version also summarizes older turns."""
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        for i in range(5):
            mem.add_turn("s1", ConversationTurn(
                question=f"查{['用户','订单'][i%2]}",
                sql=f"SELECT * FROM {['users','orders'][i%2]}",
                answer=f"结果{i}",
            ))
        ctx = mem.get_context_string("s1")
        assert "Earlier context" in ctx
        assert "users" in ctx
        assert "Turn 1" in ctx  # recent
