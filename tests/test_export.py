"""Tests for conversation history export/import."""
import json
import os
import tempfile
from agent_data.nl2sql.memory import ConversationTurn, SQLiteConversationMemory
from agent_data.nl2sql.export import ConversationExporter


def test_export_empty_session():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        exporter = ConversationExporter(mem)
        data = exporter.export_session("nonexistent")
        assert data["session_id"] == "nonexistent"
        assert data["turns"] == []


def test_export_session_with_turns():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        mem.add_turn("s1", ConversationTurn(question="q2", sql="SELECT 2", answer="a2"))

        exporter = ConversationExporter(mem)
        data = exporter.export_session("s1")
        assert data["session_id"] == "s1"
        assert len(data["turns"]) == 2
        assert data["turns"][0]["question"] == "q1"
        assert data["turns"][1]["question"] == "q2"


def test_export_to_json_string():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        exporter = ConversationExporter(mem)
        json_str = exporter.export_to_json_string("s1")
        data = json.loads(json_str)
        assert data["session_id"] == "s1"
        assert len(data["turns"]) == 1


def test_export_to_file():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        path = os.path.join(d, "export.json")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))

        exporter = ConversationExporter(mem)
        exporter.export_to_file("s1", path)

        with open(path) as f:
            data = json.load(f)
        assert data["session_id"] == "s1"
        assert len(data["turns"]) == 1


def test_import_session_round_trip():
    with tempfile.TemporaryDirectory() as d:
        # Source memory
        src_db = os.path.join(d, "src.db")
        src_mem = SQLiteConversationMemory(db_path=src_db, max_turns=10)
        src_mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        src_mem.add_turn("s1", ConversationTurn(question="q2", sql="SELECT 2", answer="a2"))

        # Target memory (empty)
        tgt_db = os.path.join(d, "tgt.db")
        tgt_mem = SQLiteConversationMemory(db_path=tgt_db, max_turns=10)

        # Export from source, import to target
        exporter = ConversationExporter(src_mem)
        data = exporter.export_session("s1")
        new_session_id = exporter.import_session(tgt_mem, data, new_session_id="s1-imported")

        # Verify target has the data
        history = tgt_mem.get_history("s1-imported")
        assert len(history) == 2
        assert history[0].question == "q1"
        assert history[1].answer == "a2"


def test_import_skips_duplicates():
    """Importing same session twice should not duplicate rows."""
    with tempfile.TemporaryDirectory() as d:
        src_db = os.path.join(d, "src.db")
        src_mem = SQLiteConversationMemory(db_path=src_db, max_turns=10)
        src_mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))

        tgt_db = os.path.join(d, "tgt.db")
        tgt_mem = SQLiteConversationMemory(db_path=tgt_db, max_turns=10)

        exporter = ConversationExporter(src_mem)
        data = exporter.export_session("s1")

        exporter.import_session(tgt_mem, data, new_session_id="s1")
        exporter.import_session(tgt_mem, data, new_session_id="s1")  # duplicate

        history = tgt_mem.get_history("s1")
        assert len(history) == 1


def test_export_all_sessions():
    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "test.db")
        mem = SQLiteConversationMemory(db_path=db, max_turns=10)
        mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        mem.add_turn("s2", ConversationTurn(question="q2", sql="SELECT 2", answer="a2"))

        exporter = ConversationExporter(mem)
        data = exporter.export_all_sessions()
        assert data["format"] == "agent-data.conversation/v1"
        assert data["session_count"] == 2
        assert len(data["sessions"]) == 2


def test_round_trip_all_sessions():
    with tempfile.TemporaryDirectory() as d:
        src_db = os.path.join(d, "src.db")
        src_mem = SQLiteConversationMemory(db_path=src_db, max_turns=10)
        src_mem.add_turn("s1", ConversationTurn(question="q1", sql="SELECT 1", answer="a1"))
        src_mem.add_turn("s2", ConversationTurn(question="q2", sql="SELECT 2", answer="a2"))

        tgt_db = os.path.join(d, "tgt.db")
        tgt_mem = SQLiteConversationMemory(db_path=tgt_db, max_turns=10)

        exporter = ConversationExporter(src_mem)
        data = exporter.export_all_sessions()
        new_count = exporter.import_all_sessions(tgt_mem, data)
        assert new_count == 2
