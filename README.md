# Agent Data Orchestration Framework

为 AI Agent 应用提供统一的数据访问和任务编排能力。

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-23%20passed-brightgreen)]()

## 核心功能

| 功能 | 说明 |
|------|------|
| 统一数据访问 | SQL、向量库、API、文件，一个接口搞定 |
| 任务规划引擎 | 自动拆分任务、选择执行路径 |
| 工作流引擎 | 多步骤任务编排，状态管理 |
| Agent Loop | 循环执行、错误重试、终止控制 |
| 多 Agent 协作 | Agent 间通信、任务分发 |
| MCP 协议 | Model Context Protocol 支持 |
| 可观测性 | OpenTelemetry 分布式追踪 |

## 快速开始

### 安装

```bash
# 基础安装
pip install agent-data

# 带可选依赖
pip install agent-data[all]           # 全部功能
pip install agent-data[postgres]      # PostgreSQL
pip install agent-data[chroma]        # Chroma 向量库
pip install agent-data[qdrant]        # Qdrant 向量库
pip install agent-data[api]           # REST API
pip install agent-data[tracing]       # OpenTelemetry
```

### 最小示例

```python
import asyncio
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType, Query, QueryType

# 创建客户端
client = AgentDataClient(data_sources=[
    DataSource(
        config=DataSourceConfig(
            name="users",
            type=DataSourceType.SQL,
            connection=":memory:",
        ),
    )
])

async def main():
    # 初始化数据库
    connector = await client._get_connector("users")
    connector._connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    connector._connection.execute("INSERT INTO users (name) VALUES ('Alice')")

    # 查询
    result = await client.query(Query(source="users", query_type=QueryType.SELECT))
    print(result.data)  # [{'id': 1, 'name': 'Alice'}]

asyncio.run(main())
```

## 支持的数据源

| 类型 | 连接器 | 状态 |
|------|--------|------|
| SQL | SQLite | ✅ |
| SQL | PostgreSQL | ✅ |
| SQL | MySQL | ✅ |
| 向量库 | Chroma | ✅ |
| 向量库 | Qdrant | ✅ |
| 向量库 | InMemory | ✅ |
| API | REST | ✅ |
| 文件 | 本地文件 | ✅ |

## 功能示例

### 1. 任务执行

```python
from agent_data import Task

async def my_task(input_data):
    return {"result": "success"}

task = Task(name="my_task", input_data={"query": "test"})
result = await client.execute_task(task, my_task)
print(result.status)  # completed
```

### 2. 工作流编排

```python
from agent_data import FunctionStep

async def step1(state):
    return {"step1_done": True}

async def step2(state):
    return {"step2_done": True}

workflow = [
    FunctionStep("step1", step1),
    FunctionStep("step2", step2),
]

result = await client.execute_workflow(workflow)
```

### 3. Agent Loop

```python
from agent_data.loop.agent_loop import SimpleAgentLoop

async def step(state):
    state["count"] = state.get("count", 0) + 1
    return state

def is_complete(state):
    return state.get("count", 0) >= 3

loop = SimpleAgentLoop(step, is_complete)
result = await client.agent_loop(loop, {"count": 0})
print(result.iterations)  # 3
```

### 4. 多 Agent 协作

```python
from agent_data import WorkerAgent, AgentOrchestrator

async def data_agent(input_data):
    return {"data": "fetched"}

async def analysis_agent(input_data):
    return {"analysis": "complete"}

# 创建 Agents
orchestrator = client.create_orchestrator()
orchestrator.register(WorkerAgent("data", data_agent, capabilities=["fetch"]))
orchestrator.register(WorkerAgent("analysis", analysis_agent, capabilities=["analyze"]))

# 执行
result = await orchestrator.execute_task({"action": "fetch"}, "fetch", "coordinator")
```

### 5. MCP 协议

```python
from agent_data.mcp import MCPServer

server = MCPServer("my-server")
server.register_data_tools(client)

# 处理 MCP 请求
response = await server.handle_request({
    "method": "tools/list",
    "params": {}
})
```

## 架构

```
agent_data/
├── core/           # 核心客户端和模型
├── connectors/     # 数据源连接器
├── cache/          # 缓存模块
├── tracing/        # 追踪模块
├── planning/       # 任务规划引擎
├── workflow/       # 工作流引擎
├── loop/           # Agent Loop
├── multi_agent/    # 多 Agent 协作
├── mcp/            # MCP 协议
└── integrations/   # 框架集成
```

## 开发

```bash
# 克隆仓库
git clone https://github.com/your-org/agent-data.git
cd agent-data

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 代码格式化
black agent_data/ tests/

# 运行示例
python examples/integration_example.py
python examples/real_world_case.py
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行带覆盖率
pytest tests/ --cov=agent_data

# 运行特定模块
pytest tests/test_planning.py -v
pytest tests/test_workflow.py -v
pytest tests/test_loop.py -v
```

## 文档

- [JD 需求分析](docs/jd_analysis.md)
- [项目路线图](docs/roadmap.md)
- [需求文档](docs/requirements.md)
- [代码质量报告](docs/code_quality_report.md)
- [示例代码](examples/)

## 贡献

欢迎贡献！请先阅读贡献指南。

## 许可证

MIT License - 详见 [LICENSE](LICENSE)