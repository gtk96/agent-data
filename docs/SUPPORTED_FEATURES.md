# 已实现 / 规划中 / 不支持

这份文档是项目对外能力的唯一真相源。README 中关于功能/连接器的表格与
本文件保持一致;如有冲突,以本文为准。

最近一次基线:2026-07-07,见 PR #2 (`chore/full-code-review-fixes`)。

## 数据源连接器

| 类型 | 连接器 | 实现状态 | 备注 |
|------|--------|---------|------|
| SQL | SQLite | ✅ | `sqlite3` (同步),`aiosqlite` 计划中 |
| SQL | PostgreSQL | ✅ | `asyncpg` 0.27+ |
| SQL | MySQL | 🚧 | 待贡献:基于 `aiomysql` |
| 向量库 | Chroma | ✅ | `chromadb` ≥0.4.24 |
| 向量库 | Qdrant | ✅ | `qdrant-client` ≥1.7 |
| 向量库 | Pinecone | ✅ | `pinecone-client` 2.x |
| 向量库 | InMemory | ✅ | numpy cosine |
| API | REST | ✅ | `aiohttp` ≥3.9.2;SSRF 防护 + Bearer/Basic |
| 文件 | 本地文件 | ✅ | 受限 base_path |

## 框架能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 任务规划 (SimpleTaskPlanner) | ✅ | 模板匹配 |
| 任务规划 (CompositeTaskPlanner) | ✅ | 多 planner 串联 |
| 任务执行 (PlanExecutor) | ✅ | 信号量并发,可调 `max_concurrent` |
| 工作流引擎 | ✅ | `FunctionStep` + `ConditionalStep`,串行 |
| Agent Loop | ✅ | `LoopRunner` 支持 max_iter + 单步超时(wait_for) |
| 多 Agent 协作 | ✅ | `WorkerAgent` + `AgentOrchestrator`,sender allowlist |
| MCP 协议 | ✅ | Bearer 鉴权 + 工具 ACL + JSON-RPC 2.0 错误码 |
| OpenTelemetry | ✅ | trace_id 通过 contextvars 传播 |
| Memory Tracer | ✅ | 测试 / 本地开发用 |

## 安全特性

| 特性 | 状态 |
|------|------|
| SQL 标识符白名单 | ✅ |
| SQL LIKE 通配符转义 | ✅ |
| REST SSRF 白名单 | ✅ |
| REST 鉴权真正生效 (Bearer/Basic) | ✅ |
| REST 响应体大小限制 (10MB) | ✅ |
| REST 重定向禁用 | ✅ |
| MCP Bearer Token 鉴权 | ✅ |
| MCP 工具 ACL | ✅ |
| Multi-agent sender allowlist | ✅ |
| 异常字符串脱敏 (redact) | ✅ |
| 共享状态并发锁 | ✅ (InMemoryVector, connector 懒初始化, MemoryTracer) |

## 规划中 / 暂未实现

下列能力出现在 `api_design_draft.md` 但当前源码中**没有**实现,用户在
尝试 import 时会遇到 `ImportError`,后续 PR 单独推进:

- `HybridRetriever` — 跨向量库的混合检索
- `NaturalLanguageToSQL` — LLM 驱动的自然语言转 SQL
- `StreamingQuery` — 大结果集流式返回
- `UserProfileBuilder` — 用户画像构建器
- `CodeRetriever` — 代码语义检索
- `Reranker` — 重排序模型包装
- `TracerConfig` — Tracer 配置抽象
- `get_schema` async — 当前仍是同步(各 connector 实现差异大)
- `aiosqlite` 全面替换 `sqlite3` — 计划中

## 不在 scope

- LLM SDK 抽象(请使用 LangChain / LlamaIndex,本项目只提供集成点)
- 复杂工作流可视化 UI
- 多租户隔离(由上层应用处理)
