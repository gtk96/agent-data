"""Tests for NL2SQL engine."""

import pytest
from agent_data.nl2sql.memory import ConversationMemory, ConversationTurn
from agent_data.nl2sql.schema_manager import SchemaManager, TableInfo, ColumnInfo
from agent_data.nl2sql.formatter import ResultFormatter


class TestConversationMemory:
    """Tests for ConversationMemory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.memory = ConversationMemory(max_turns=5, ttl_seconds=3600)

    def test_add_turn(self):
        """Test adding a conversation turn."""
        turn = ConversationTurn(
            question="What is the total sales?",
            sql="SELECT SUM(amount) FROM sales",
            answer="Total sales is 1000",
        )
        self.memory.add_turn("session1", turn)

        history = self.memory.get_history("session1")
        assert len(history) == 1
        assert history[0].question == "What is the total sales?"

    def test_max_turns(self):
        """Test max turns limit."""
        for i in range(10):
            turn = ConversationTurn(
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            self.memory.add_turn("session1", turn)

        history = self.memory.get_history("session1")
        assert len(history) == 5  # max_turns = 5

    def test_get_history_n(self):
        """Test getting last n turns."""
        for i in range(5):
            turn = ConversationTurn(
                question=f"Question {i}",
                sql=f"SELECT {i}",
                answer=f"Answer {i}",
            )
            self.memory.add_turn("session1", turn)

        history = self.memory.get_history("session1", n=2)
        assert len(history) == 2
        assert history[0].question == "Question 3"
        assert history[1].question == "Question 4"

    def test_get_context_string(self):
        """Test context string generation."""
        turn = ConversationTurn(
            question="What is the total?",
            sql="SELECT SUM(amount) FROM sales",
            answer="Total is 1000",
        )
        self.memory.add_turn("session1", turn)

        context = self.memory.get_context_string("session1")
        assert "What is the total?" in context
        assert "SELECT SUM(amount)" in context

    def test_clear_session(self):
        """Test clearing a session."""
        turn = ConversationTurn(
            question="Test",
            sql="SELECT 1",
            answer="Test answer",
        )
        self.memory.add_turn("session1", turn)
        self.memory.clear_session("session1")

        history = self.memory.get_history("session1")
        assert len(history) == 0

    def test_multiple_sessions(self):
        """Test multiple sessions are isolated."""
        turn1 = ConversationTurn(question="Q1", sql="SELECT 1", answer="A1")
        turn2 = ConversationTurn(question="Q2", sql="SELECT 2", answer="A2")

        self.memory.add_turn("session1", turn1)
        self.memory.add_turn("session2", turn2)

        assert len(self.memory.get_history("session1")) == 1
        assert len(self.memory.get_history("session2")) == 1


class TestSchemaManager:
    """Tests for SchemaManager."""

    @pytest.mark.asyncio
    async def test_format_schema_for_prompt(self):
        """Test schema formatting for prompts."""

        # Create a mock connector
        class MockConnector:
            def get_schema(self):
                return {
                    "users": {
                        "columns": [
                            {"name": "id", "type": "INTEGER", "primary_key": True},
                            {"name": "name", "type": "TEXT", "nullable": False},
                        ],
                        "row_count": 100,
                    }
                }

        manager = SchemaManager(MockConnector())
        await manager.get_schema()
        formatted = manager.format_schema_for_prompt()

        assert "users" in formatted
        assert "id" in formatted
        assert "INTEGER" in formatted
        assert "PK" in formatted


class TestResultFormatter:
    """Tests for ResultFormatter."""

    def test_to_table_text(self):
        """Test table text formatting."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        result = ResultFormatter.to_table_text(data)

        assert "name" in result
        assert "age" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_to_table_text_empty(self):
        """Test empty data handling."""
        result = ResultFormatter.to_table_text([])
        assert "No results" in result

    def test_to_markdown_table(self):
        """Test Markdown table formatting."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        result = ResultFormatter.to_markdown_table(data)

        assert "| name | age |" in result
        assert "| --- | --- |" in result
        assert "| Alice | 30 |" in result

    def test_data_to_json_str(self):
        """Test JSON string formatting."""
        data = [{"name": "Alice", "age": 30}]
        result = ResultFormatter.data_to_json_str(data)

        assert "Alice" in result
        assert "30" in result

    def test_to_summary(self):
        """Test data summary generation."""
        data = [
            {"amount": 100.0},
            {"amount": 200.0},
            {"amount": 150.0},
        ]
        result = ResultFormatter.to_summary(data)

        assert "Total rows: 3" in result
        assert "amount" in result
