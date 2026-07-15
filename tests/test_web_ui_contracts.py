"""API 契约稳定性测试 — 与前端 UI 强耦合的字段顺序/类型校验。"""

import pytest
from fastapi.testclient import TestClient

from agent_data.web.app import create_app
from agent_data.core.models import DataSourceConfig, DataSourceType
from agent_data.connectors.sql import SQLConnector
from agent_data.nl2sql.engine import NL2SQLEngine
import asyncio


@pytest.fixture
def client():
    """Build a FastAPI TestClient with an in-memory SQLite engine (no LLM)."""

    async def setup():
        cfg = DataSourceConfig(name="x", type=DataSourceType.SQL, connection=":memory:")
        c = SQLConnector(cfg)
        await c.connect()
        c._connection.execute("CREATE TABLE users(id INT PRIMARY KEY)")
        c._connection.execute("INSERT INTO users VALUES (1)")
        return c

    c = asyncio.run(setup())
    engine = NL2SQLEngine(llm=None, connector=c)
    app = create_app(engine=engine, data_sources=[])
    return TestClient(app)


def test_health_field_types(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("llm"), bool)
    assert isinstance(body.get("database"), bool)
    assert body["status"] in {"healthy", "degraded", "no_engine"}


def test_query_response_shape(client):
    r = client.post(
        "/api/v1/query", json={"question": "select count from users", "session_id": "t1"}
    )
    assert r.status_code == 200
    body = r.json()
    for key in ("session_id", "question", "answer", "data", "confidence"):
        assert key in body, f"missing field {key}"
    assert isinstance(body["data"], list)
    assert isinstance(body["confidence"], (int, float))


def test_sql_validation_failure_explanation(client):
    """SQL 验证失败的 explanation 必须含 'validation' 串，前端据此显示折叠详情。"""
    r = client.post(
        "/api/v1/sql/execute",
        json={"sql": "DROP TABLE users"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "validation" in (body.get("error") or "").lower()
