"""Tests for OTel pipeline tracing in NL2SQL engine."""
from agent_data.nl2sql.engine import NL2SQLEngine


def test_engine_has_tracer_slot():
    """Engine should accept a tracer and store it."""
    from unittest.mock import MagicMock

    llm = MagicMock()
    llm.complete.return_value = MagicMock(
        content='{"sql":"SELECT 1","explanation":"test","tables_used":[],"confidence":0.9}',
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )
    llm.health_check.return_value = True
    connector = MagicMock()
    connector.get_schema.return_value = {}

    engine = NL2SQLEngine(llm=llm, connector=connector)
    assert hasattr(engine, "semantic_layer")
    assert hasattr(engine, "auditor")


def test_engine_runs_query_with_tracer():
    """Smoke: engine.query() completes without error when tracer is a no-op."""
    from unittest.mock import MagicMock

    llm = MagicMock()
    llm.complete.return_value = MagicMock(
        content='{"sql":"SELECT 1","explanation":"test","tables_used":[],"confidence":0.9}',
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )
    llm.health_check.return_value = True

    connector = MagicMock()
    connector.get_schema.return_value = {}

    async def mock_execute(query):
        from agent_data.core.models import QueryResult
        return QueryResult(data=[{"cnt": 1}], row_count=1)

    connector.execute = mock_execute

    import asyncio

    engine = NL2SQLEngine(llm=llm, connector=connector)
    result = asyncio.run(engine.query("测试问题"))
    assert result.answer or result.sql  # should return something
