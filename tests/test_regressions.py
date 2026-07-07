"""测试核心安全/并发修复的回归覆盖。

每个测试对应 plan §1-§6 中的一个具体修改点。
"""

import asyncio
import os
import time

import pytest

from agent_data.core.client import AgentDataClient
from agent_data.core.errors import AgentDataError, format_error
from agent_data.core.redact import redact, scrub_mapping, REDACT_KEYS
from agent_data.core.sql_utils import escape_like, validate_identifier
from agent_data.loop import SimpleAgentLoop
from agent_data.multi_agent import AgentMessage, AgentRole, WorkerAgent
from agent_data.multi_agent.orchestrator import AgentOrchestrator


# ---------- sql_utils ----------


class TestSqlUtils:
    def test_validate_identifier_accepts_normal(self):
        assert validate_identifier("users") == "users"
        assert validate_identifier("_t1") == "_t1"

    @pytest.mark.parametrize("bad", ["", "1abc", "drop table", "a;b", "a b", '"x"'])
    def test_validate_identifier_rejects_injection(self, bad):
        with pytest.raises(ValueError):
            validate_identifier(bad)

    def test_escape_like_escapes_wildcards(self):
        assert escape_like("hello") == "hello"
        assert escape_like("a%b") == "a\\%b"
        assert escape_like("a_b") == "a\\_b"
        # 反斜杠要先 escape 自身
        assert escape_like("a\\b") == "a\\\\b"


# ---------- redact ----------


class TestRedact:
    def test_redact_url_credentials(self):
        out = redact("postgresql://user:pass@host:5432/db")
        assert "user:pass" not in out
        assert "***" in out
        assert "host:5432/db" in out

    def test_redact_kv_token(self):
        assert "abc123" not in redact("token=abc123")
        assert "?token=***" in redact("?token=abc123")

    def test_redact_truncates_long(self):
        long = "x" * 5000
        out = redact(long)
        assert len(out) <= 1024

    def test_scrub_mapping_removes_keys(self):
        m = {"query": "x", "api_key": "y", "name": "z"}
        out = scrub_mapping(m)
        assert "api_key" not in out
        assert out["query"] == "x"


# ---------- errors ----------


class TestErrors:
    def test_format_error_includes_class_and_message(self):
        try:
            raise ValueError("bad")
        except ValueError as e:
            s = format_error(e)
        assert "ValueError" in s and "bad" in s


# ---------- SQL connector security ----------


class TestSQLConnectorSecurity:
    @pytest.mark.asyncio
    async def test_invalid_identifier_returns_error(self):
        from agent_data import DataSource, DataSourceConfig, DataSourceType, Query, QueryType

        client = AgentDataClient(
            data_sources=[
                DataSource(
                    config=DataSourceConfig(
                        name="db", type=DataSourceType.SQL, connection=":memory:"
                    )
                )
            ]
        )
        connector = await client._get_connector("db")
        connector._connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        # SQL connector 在 to_thread 路径下用 try/except 吞掉底层 ValueError
        # 并写入 QueryResult.error(redact + format_error)。这是有意行为,
        # 重要的是 error 字段存在且不暴露原始 SQL 片段。
        result = await connector.execute(
            Query(
                source="users; DROP TABLE users;--",
                query_type=QueryType.SELECT,
            )
        )
        assert result.error
        assert "ValueError" in result.error
        # 数据库仍然完好
        rows = connector._connection.execute("SELECT COUNT(*) FROM users").fetchone()
        assert rows[0] == 0

    @pytest.mark.asyncio
    async def test_like_escapes_user_wildcards(self):
        from agent_data import DataSource, DataSourceConfig, DataSourceType, Query, QueryType

        client = AgentDataClient(
            data_sources=[
                DataSource(
                    config=DataSourceConfig(
                        name="db", type=DataSourceType.SQL, connection=":memory:"
                    )
                )
            ]
        )
        connector = await client._get_connector("db")
        connector._connection.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        connector._connection.execute("INSERT INTO t (name) VALUES ('100%_pure')")
        # 关键字 "100%_pure" 必须能精确匹配,不被通配符"_" 误判为单个字符
        result = await connector.execute(
            Query(
                source="t",
                query_type=QueryType.SEARCH,
                query="100%_pure",
            )
        )
        assert any(row.get("name") == "100%_pure" for row in result.data)


# ---------- REST SSRF ----------


class TestRestAPIConnectorSSRF:
    @pytest.mark.asyncio
    async def test_absolute_url_in_endpoint_rejected(self):
        from agent_data import (
            DataSource,
            DataSourceConfig,
            Query,
            QueryType,
        )
        from agent_data.connectors import RESTAPIConnector

        # 直接构造 connector,绕过 type→class 映射(注册名是 "rest_api",
        # 与 DataSourceType.API 值不同)。
        config = DataSourceConfig(
            name="api",
            type="api",
            connection="https://api.example.com",
        )
        connector = RESTAPIConnector(config)
        await connector.connect()
        # 绝对 URL 走 urljoin 会被覆盖 — 应当被 _build_url 拒绝
        result = await connector.execute(
            Query(
                source="api",
                query_type=QueryType.SELECT,
                metadata={"endpoint": "http://169.254.169.254/latest/meta-data/"},
            )
        )
        assert result.error  # 包含 ValueError 提示

    @pytest.mark.asyncio
    async def test_scrub_api_key_in_params(self):
        from agent_data.connectors.rest_api import RESTAPIConnector

        # _scrub_auth_keys 直接测
        out = RESTAPIConnector._scrub_auth_keys(RESTAPIConnector, {"q": "x", "api_key": "secret"})
        assert "api_key" not in out
        assert out["q"] == "x"


# ---------- MCP auth & ACL ----------


class TestMCPServerAuth:
    @pytest.mark.asyncio
    async def test_no_auth_when_tokens_not_set(self):
        from agent_data import MCPServer, MCPTool

        server = MCPServer()
        server.register_tool(MCPTool(name="echo", description="echo"), lambda x: x)
        resp = await server.handle_request({"method": "tools/list", "params": {}})
        assert "tools" in resp

    @pytest.mark.asyncio
    async def test_missing_token_rejected_with_jsonrpc_code(self):
        from agent_data import MCPServer, MCPTool

        server = MCPServer(tokens={"secret-token"})
        server.register_tool(MCPTool(name="echo", description="echo"), lambda x: x)
        resp = await server.handle_request({"method": "tools/list", "params": {}})
        assert resp["error"]["code"] == -32001

    @pytest.mark.asyncio
    async def test_correct_token_accepted(self):
        from agent_data import MCPServer, MCPTool

        server = MCPServer(tokens={"secret-token"})
        server.register_tool(MCPTool(name="echo", description="echo"), lambda x: x)
        resp = await server.handle_request(
            {
                "method": "tools/list",
                "params": {},
                "_headers": {"authorization": "Bearer secret-token"},
            }
        )
        assert "tools" in resp

    @pytest.mark.asyncio
    async def test_acl_blocks_disallowed_tool(self):
        from agent_data import MCPServer, MCPTool

        server = MCPServer(allowed_tools={"alpha"})
        server.register_tool(MCPTool(name="alpha", description="a"), lambda x: "A")
        server.register_tool(MCPTool(name="beta", description="b"), lambda x: "B")
        resp = await server.handle_request(
            {"method": "tools/call", "params": {"name": "beta", "arguments": {}}}
        )
        assert resp["error"]["code"] == -32003

    @pytest.mark.asyncio
    async def test_unknown_method_returns_jsonrpc_method_not_found(self):
        from agent_data import MCPServer

        server = MCPServer()
        resp = await server.handle_request({"method": "wat", "params": {}})
        assert resp["error"]["code"] == -32601


# ---------- Multi-agent sender allowlist ----------


class TestMultiAgentSenderAllowlist:
    @pytest.mark.asyncio
    async def test_unauthorized_sender_silently_skipped(self):
        async def noop(payload):
            return "executed"

        worker = WorkerAgent("w", noop, capabilities=["x"])
        # 只允许 coordinator 这个 sender_id 调用
        worker.allowed_senders = {"coordinator"}

        orch = AgentOrchestrator()
        orch.register(worker)

        msg = AgentMessage(sender="attacker", receiver=worker.id, content="x")
        resp = await orch.send_message(msg)
        assert resp is None  # 未授权

    @pytest.mark.asyncio
    async def test_authorized_sender_reaches(self):
        async def noop(payload):
            return "done"

        worker = WorkerAgent("w", noop, capabilities=["x"])
        worker.allowed_senders = {"coordinator"}

        orch = AgentOrchestrator()
        orch.register(worker)

        msg = AgentMessage(
            sender="coordinator",
            receiver=worker.id,
            content="x",
            message_type="task",
        )
        resp = await orch.send_message(msg)
        assert resp is not None
        assert resp.content == "done"


# ---------- Concurrency: connector 懒初始化互斥 ----------


class TestConnectorConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_first_access_creates_one_connector(self):
        from agent_data import DataSource, DataSourceConfig, DataSourceType

        # 10 个并发请求同一 source
        client = AgentDataClient(
            data_sources=[
                DataSource(
                    config=DataSourceConfig(
                        name="db", type=DataSourceType.SQL, connection=":memory:"
                    )
                )
            ]
        )

        async def access():
            return await client._get_connector("db")

        connectors = await asyncio.gather(*[access() for _ in range(10)])
        # 全部应当是同一对象
        first = connectors[0]
        for c in connectors[1:]:
            assert c is first
        assert len(client._connectors) == 1


# ---------- LoopRunner 单步超时 ----------


class TestLoopRunnerTimeout:
    @pytest.mark.asyncio
    async def test_slow_step_is_cut_by_wait_for(self):
        async def slow_step(state):
            await asyncio.sleep(2)
            return state

        def never(state):
            return False

        loop = SimpleAgentLoop(slow_step, never)
        runner = SimpleAgentLoop  # 用 client 的方式构造 LoopRunner
        from agent_data import LoopRunner

        runner = LoopRunner(max_iterations=5, timeout_seconds=0.2)
        start = time.time()
        result = await runner.run(loop, {})
        elapsed = time.time() - start
        assert elapsed < 1.0  # 不应等待 2s
        assert result.status.value == "timeout"


# ---------- Trace id 传播 ----------


class TestTraceIdPropagation:
    @pytest.mark.asyncio
    async def test_nested_spans_share_top_level_trace_id(self):
        from agent_data.tracing.memory import (
            MemoryTracer,
            _active_trace_id,
            set_active_trace_id,
        )

        tracer = MemoryTracer()
        top = await tracer.start_span(name="top")
        token = set_active_trace_id(top.trace_id)
        try:
            inner = await tracer.start_span(name="inner")
            assert inner.trace_id == top.trace_id
        finally:
            _active_trace_id.reset(token)

        # 离开上下文后再开 span,应获得新的 trace_id
        outer = await tracer.start_span(name="outer")
        assert outer.trace_id != top.trace_id
