# Changelog

## [Unreleased]

### Security
- SQL 注入面加固:标识符白名单、LIKE 转义
- REST SSRF 防护:endpoint 白名单、host 校验、`allow_redirects=False`、响应体大小限制
- MCP 鉴权:可选 Bearer Token + 工具 ACL + JSON-RPC 2.0 错误码
- Multi-agent sender allowlist
- 异常字符串脱敏:新增 `core/redact.py` + `format_error`

### Changed
- `MemoryTracer` 引入 trace_id 传播(`contextvars`),顶层 span 通过
  `set_active_trace_id` 共享给嵌套 span
- `AgentDataClient._get_connector` 加双层锁,防止并发首次访问同 source
  创建两个 connector;connect 失败时清理 half-built connector
- `LoopRunner` 单步超时改 `asyncio.wait_for(loop.step, timeout=remaining)`
- `agent_data` 顶层与各子模块 `__all__` 对齐 README
- `_generate_cache_key`:自然语言查询不 hash 原文(只 bucket source+query_type)
- `execute_plan`:暴露 `max_concurrent: int = 5` 参数
- `connectors/__init__.py`:失败日志由 `debug` 升至 `warning`;
  新增 `available_connectors()` 工具
- 依赖锁版本:`aiohttp>=3.9.2`、`chromadb>=0.4.24`、`langchain>=0.3`、
  `qdrant-client>=1.7`、`opentelemetry>=1.27`、`llama-index>=0.12`
- 新增 `[sqlite]` extra(`aiosqlite`)

### Added
- `agent_data/core/errors.py` — 异常层级 + `format_error`
- `agent_data/core/redact.py` — 敏感字段脱敏 + `redact_attributes`
- `agent_data/core/sql_utils.py` — 共享 `validate_identifier` /
  `escape_like` / `quote_identifier_pg`
- `Agent.allowed_senders` + `MCPServer(tokens=...)` + `from_env()`
- `.github/workflows/ci.yml` — Python 3.9/3.10/3.11 matrix + `pip-audit`

### Fixed
- MCP `register_data_tools` 闭包陷阱(用默认参数 `_src=source_name` 立即绑定)
- `_get_connector` connect 失败时不留半成品

### Docs
- README 同步实际支持清单(MySQL 改 🚧、tests 41 passed)
- 新增 `docs/SUPPORTED_FEATURES.md`(对外能力唯一真相源)
- 新增本文件
