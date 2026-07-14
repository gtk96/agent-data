"""Tests for NL2SQL engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_data.nl2sql.engine import NL2SQLEngine
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


class TestParseLLMResponse:
    """Tests for _parse_llm_response strict behavior."""

    def _make_engine(self):
        """Build a minimal engine instance for calling _parse_llm_response."""
        llm = MagicMock()
        connector = MagicMock()
        return NL2SQLEngine(llm=llm, connector=connector)

    def test_valid_json(self):
        """Valid JSON returns parsed dict."""
        engine = self._make_engine()
        result = engine._parse_llm_response('{"sql": "SELECT 1", "explanation": "ok"}')
        assert result["sql"] == "SELECT 1"
        assert result["explanation"] == "ok"

    def test_json_in_markdown_block(self):
        """JSON inside ```json``` block is extracted."""
        engine = self._make_engine()
        content = '```json\n{"sql": "SELECT 2"}\n```'
        result = engine._parse_llm_response(content)
        assert result["sql"] == "SELECT 2"

    def test_empty_content_raises(self):
        """Empty content raises LLMResponseParseError."""
        from agent_data.nl2sql.engine import LLMResponseParseError

        engine = self._make_engine()
        with pytest.raises(LLMResponseParseError):
            engine._parse_llm_response("")

    def test_no_sql_field_raises(self):
        """JSON without 'sql' key raises LLMResponseParseError."""
        from agent_data.nl2sql.engine import LLMResponseParseError

        engine = self._make_engine()
        with pytest.raises(LLMResponseParseError):
            engine._parse_llm_response('{"explanation": "no sql here"}')

    def test_plain_text_no_select_raises(self):
        """Free-form text without any SQL or JSON raises LLMResponseParseError."""
        from agent_data.nl2sql.engine import LLMResponseParseError

        engine = self._make_engine()
        with pytest.raises(LLMResponseParseError):
            engine._parse_llm_response(
                "This is a natural language answer without any SQL or JSON. "
                "Just text explaining something."
            )

    def test_partial_json_raises(self):
        """Malformed JSON raises LLMResponseParseError (no silent fallback)."""
        from agent_data.nl2sql.engine import LLMResponseParseError

        engine = self._make_engine()
        with pytest.raises(LLMResponseParseError):
            engine._parse_llm_response('{"sql": "SELECT 1"')  # missing closing brace

    def test_error_message_contains_raw_response(self):
        """Parse error message includes raw response for debugging."""
        from agent_data.nl2sql.engine import LLMResponseParseError

        engine = self._make_engine()
        raw = "Some malformed response that means failure"
        with pytest.raises(LLMResponseParseError) as exc_info:
            engine._parse_llm_response(raw)
        assert raw in str(exc_info.value)


class TestEngineQueryErrorHandling:
    """End-to-end tests for engine.query() with a misbehaving LLM."""

    @pytest.mark.asyncio
    async def test_query_returns_clear_error_when_llm_never_returns_sql(self):
        """When the LLM keeps producing prose (no SQL), engine must return
        a clear error NL2SQLResult — not silently empty data with sql=None.
        """
        from agent_data.llm.base import LLMResponse, LLMUsage
        from agent_data.nl2sql.engine import NL2SQLEngine

        # Mock LLM: always returns prose, never SQL
        llm = MagicMock()
        prose = (
            "This is a friendly natural-language explanation of why the question "
            "cannot be answered. The database is empty, perhaps. No JSON here."
        )
        llm.complete = AsyncMock(
            return_value=LLMResponse(
                content=prose,
                model="mock",
                usage=LLMUsage(),
                finish_reason="stop",
            )
        )
        llm.health_check = AsyncMock(return_value=True)

        # Mock connector
        connector = MagicMock()
        connector._connection = None
        connector.health_check = AsyncMock(return_value=True)

        engine = NL2SQLEngine(llm=llm, connector=connector, config={"readonly": True})

        result = await engine.query("查询所有用户", session_id="s1")

        # Engine must surface the error explicitly, not silently return empty data
        assert result.sql == ""
        assert result.data == []
        assert result.confidence == 0.0
        assert "parse" in result.explanation.lower() or "llm" in result.explanation.lower()
        assert "Raw response" in result.answer or "couldn't" in result.answer

        # LLM should have been called exactly twice (initial + one retry)
        assert llm.complete.await_count == 2

    @pytest.mark.asyncio
    async def test_query_succeeds_on_retry_when_initial_response_is_prose(self):
        """When the first LLM response is prose but the retry returns valid SQL,
        engine should use the retry's result and not raise.
        """
        from agent_data.llm.base import LLMResponse, LLMUsage
        from agent_data.nl2sql.engine import NL2SQLEngine

        # Mock LLM: first call returns prose, subsequent calls return valid payloads.
        # (retry is the 2nd call; 3rd call formats the final answer)
        llm = MagicMock()
        valid_sql = '{"sql": "SELECT 1", "explanation": "ok"}'
        valid_answer = "The query returns 1."

        async def _side_effect(messages, **kwargs):
            # If this is the answer-format step, return a natural-language answer.
            if any("data analysis assistant" in m.content.lower() for m in messages):
                return LLMResponse(
                    content=valid_answer,
                    model="mock",
                    usage=LLMUsage(),
                )
            # Otherwise alternate: first call prose, then valid SQL.
            idx = llm.complete.call_count
            if idx == 0:
                return LLMResponse(
                    content="Just some prose without any SQL.",
                    model="mock",
                    usage=LLMUsage(),
                )
            return LLMResponse(
                content=valid_sql,
                model="mock",
                usage=LLMUsage(),
            )

        llm.complete = AsyncMock(side_effect=_side_effect)
        llm.health_check = AsyncMock(return_value=True)

        # Mock connector that returns a valid QueryResult
        from agent_data.core.models import QueryResult

        connector = MagicMock()
        connector._connection = MagicMock()
        connector._connection.execute = MagicMock(return_value=MagicMock(description=[]))
        connector.execute = AsyncMock(
            return_value=QueryResult(data=[], source="test", query_time_ms=1.0)
        )
        connector.health_check = AsyncMock(return_value=True)

        engine = NL2SQLEngine(llm=llm, connector=connector, config={"readonly": True})

        result = await engine.query("查询", session_id="s1")

        # Retry should have produced the SQL; final answer from format step.
        assert result.sql == "SELECT 1"
        assert "ok" in result.explanation
        # 3 LLM calls: initial + 1 retry + 1 answer-format
        assert llm.complete.await_count == 3
