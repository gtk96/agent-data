# API 参考文档

## 核心模块

### AgentDataClient

主客户端类，提供统一的数据访问接口。

```python
from agent_data import AgentDataClient

client = AgentDataClient(
    data_sources: List[DataSource],      # 数据源列表
    cache_enabled: bool = True,          # 是否启用缓存
    cache_ttl: int = 3600,              # 缓存过期时间（秒）
    cache_max_size: int = 10000,        # 缓存最大条目数
    trace_enabled: bool = True,         # 是否启用追踪
    cache: Optional[BaseCache] = None,  # 自定义缓存实现
    tracer: Optional[BaseTracer] = None # 自定义追踪实现
)
```

**方法**:

| 方法 | 说明 |
|------|------|
| `query(query, context, timeout)` | 执行查询 |
| `batch_query(queries, context, parallel)` | 批量查询 |
| `execute_task(task, executor, context)` | 执行任务 |
| `execute_plan(plan, executor, parallel, context)` | 执行计划 |
| `execute_workflow(steps, initial_state, context)` | 执行工作流 |
| `agent_loop(loop, initial_state, max_iterations, timeout_seconds, context)` | 运行 Agent Loop |
| `create_orchestrator()` | 创建多 Agent 编排器 |
| `add_data_source(data_source)` | 添加数据源 |
| `remove_data_source(name)` | 移除数据源 |
| `get_data_sources()` | 获取所有数据源 |
| `health_check()` | 健康检查 |
| `close()` | 关闭连接 |

---

## 数据模型

### DataSource

数据源定义。

```python
from agent_data import DataSource, DataSourceConfig, DataSourceType

data_source = DataSource(
    config=DataSourceConfig(
        name="my_db",
        type=DataSourceType.SQL,
        connection="postgresql://user:pass@localhost/db",
        db_schema="public",
        metadata={"key": "value"}
    ),
    description="My database",
    tags=["database", "sql"]
)
```

### DataSourceType

数据源类型枚举。

```python
class DataSourceType(str, Enum):
    SQL = "sql"
    NOSQL = "nosql"
    VECTOR = "vector"
    API = "api"
    FILE = "file"
    GRAPH = "graph"
    STREAM = "stream"
```

### Query

数据查询定义。

```python
from agent_data import Query, QueryType, QueryFilter

query = Query(
    source="my_db",
    query_type=QueryType.SELECT,
    filters=[
        QueryFilter(field="status", operator="eq", value="active"),
        QueryFilter(field="age", operator="gte", value=18),
    ],
    fields=["id", "name", "email"],
    limit=10,
    offset=0,
    order_by="name",
    order_desc=False,
    query="SELECT * FROM users",
    metadata={"key": "value"}
)
```

### QueryType

查询类型枚举。

```python
class QueryType(str, Enum):
    SELECT = "select"
    SEARCH = "search"
    AGGREGATE = "aggregate"
    JOIN = "join"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
```

### QueryResult

查询结果。

```python
@dataclass
class QueryResult:
    data: List[Dict[str, Any]]      # 结果数据
    total_count: Optional[int]      # 总数
    metadata: Dict[str, Any]        # 元数据
    source: str                     # 数据源名称
    query_time_ms: float            # 查询耗时（毫秒）
    cached: bool                    # 是否来自缓存
    error: Optional[str]            # 错误信息
```

### AgentContext

Agent 上下文。

```python
from agent_data import AgentContext

context = AgentContext(
    agent_id="my_agent",
    session_id="session_123",
    task_id="task_456",
    user_id="user_789",
    history=[{"role": "user", "content": "hello"}],
    metadata={"key": "value"}
)
```

---

## Planning 模块

### Task

任务定义。

```python
from agent_data import Task, TaskStatus

task = Task(
    name="my_task",
    description="Task description",
    priority=1,
    dependencies=["task_1", "task_2"],
    input_data={"key": "value"},
    max_retries=3,
    timeout_seconds=30.0,
    metadata={"key": "value"}
)

# 状态转换
task.start()                    # pending → in_progress
task.complete(output={"result": "success"})  # in_progress → completed
task.fail("error")              # in_progress → failed
task.retry()                    # failed → pending
task.cancel()                   # any → cancelled
task.block("reason")            # pending → blocked
task.unblock()                  # blocked → pending
```

### TaskPlan

任务计划。

```python
from agent_data import TaskPlan

plan = TaskPlan(
    goal="Process data",
    tasks=[task1, task2, task3],
    metadata={"key": "value"}
)

# 查询
plan.completed_tasks  # 已完成的任务
plan.pending_tasks    # 待执行的任务
plan.progress         # 进度 (0.0 - 1.0)
plan.is_complete      # 是否完成
plan.get_ready_tasks()  # 获取可执行的任务
```

### TaskPlanner

任务规划器。

```python
from agent_data import SimpleTaskPlanner

planner = SimpleTaskPlanner()
plan = await planner.plan("查询用户数据", context={"key": "value"})
```

### TaskExecutor

任务执行器。

```python
from agent_data.planning.executor import FunctionTaskExecutor, PlanExecutor

# 函数执行器
executor = FunctionTaskExecutor()
executor.register("task_name", my_async_function)
result = await executor.execute(task)

# 计划执行器
plan_executor = PlanExecutor(task_executor, max_concurrent=5)
results = await plan_executor.execute(plan)
```

---

## Workflow 模块

### WorkflowStep

工作流步骤基类。

```python
from agent_data import FunctionStep

async def my_step(state: Dict[str, Any]) -> Dict[str, Any]:
    # 处理逻辑
    return {"result": "success"}

step = FunctionStep(
    name="my_step",
    func=my_step,
    description="Step description",
    timeout=30.0
)
```

### WorkflowEngine

工作流引擎。

```python
from agent_data import WorkflowEngine

engine = WorkflowEngine(max_concurrent=5)

# 顺序执行
result = await engine.execute(
    steps=[step1, step2, step3],
    initial_state={"key": "value"}
)

# 并行执行
result = await engine.execute_parallel(steps, state)
```

### WorkflowState

工作流状态。

```python
from agent_data import WorkflowState

state = WorkflowState(workflow_id="my_workflow")
state.update("key", "value")
value = state.get("key", default=None)
```

---

## Loop 模块

### AgentLoop

Agent 循环基类。

```python
from agent_data.loop.agent_loop import SimpleAgentLoop

async def step(state: Dict[str, Any]) -> Dict[str, Any]:
    state["count"] = state.get("count", 0) + 1
    return state

def is_complete(state: Dict[str, Any]) -> bool:
    return state.get("count", 0) >= 10

loop = SimpleAgentLoop(step, is_complete)
```

### LoopRunner

循环运行器。

```python
from agent_data.loop.agent_loop import LoopRunner

runner = LoopRunner(
    max_iterations=100,
    timeout_seconds=60.0
)

result = await runner.run(loop, initial_state={"count": 0})
# result.status: LoopStatus
# result.iterations: int
# result.output: Any
# result.history: List[Dict]
```

### AgentResult

循环结果。

```python
@dataclass
class AgentResult:
    loop_id: str
    status: LoopStatus  # running, completed, failed, timeout, max_iterations
    output: Any
    iterations: int
    history: List[Dict[str, Any]]
    error: Optional[str]
    metadata: Dict[str, Any]
    duration_ms: float
```

---

## Multi-Agent 模块

### Agent

Agent 基类。

```python
from agent_data import WorkerAgent

async def execute_task(input_data: Dict[str, Any]) -> Dict[str, Any]:
    return {"result": "processed"}

agent = WorkerAgent(
    name="worker_1",
    executor=execute_task,
    capabilities=["data_process", "analysis"]
)
```

### AgentOrchestrator

Agent 编排器。

```python
from agent_data import AgentOrchestrator

orchestrator = AgentOrchestrator()
orchestrator.register(agent)

# 执行任务
result = await orchestrator.execute_task(
    task={"query": "SELECT * FROM users"},
    task_type="data_process",
    sender_id="coordinator"
)

# 广播消息
responses = await orchestrator.broadcast(
    sender_id="coordinator",
    content={"announcement": "System update"},
    message_type="broadcast"
)
```

---

## MCP 模块

### MCPServer

MCP 服务器。

```python
from agent_data.mcp import MCPServer

server = MCPServer("my-server")
server.register_data_tools(client)

# 处理请求
response = await server.handle_request({
    "method": "tools/list",
    "params": {}
})
```

### MCPTool

MCP 工具定义。

```python
from agent_data.mcp import MCPTool

tool = MCPTool(
    name="my_tool",
    description="Tool description",
    input_schema=[
        {"name": "param1", "type": "string", "description": "Parameter 1", "required": True}
    ]
)
```

---

## 连接器

### SQL 连接器

```python
from agent_data.connectors.sql import SQLConnector

connector = SQLConnector(config)
await connector.connect()
result = await connector.execute(query)
await connector.disconnect()
```

### PostgreSQL 连接器

```python
from agent_data.connectors.postgresql import PostgreSQLConnector

connector = PostgreSQLConnector(config)
await connector.connect()
result = await connector.execute(query)
await connector.disconnect()
```

### Chroma 连接器

```python
from agent_data.connectors.chroma import ChromaConnector

connector = ChromaConnector(config)
await connector.connect()
result = await connector.execute(query)
await connector.disconnect()
```

### Qdrant 连接器

```python
from agent_data.connectors.qdrant import QdrantConnector

connector = QdrantConnector(config)
await connector.connect()
result = await connector.execute(query)
await connector.disconnect()
```

### REST API 连接器

```python
from agent_data.connectors.rest_api import RESTAPIConnector

connector = RESTAPIConnector(config)
await connector.connect()
result = await connector.execute(query)
await connector.disconnect()
```

---

## 缓存

### MemoryCache

内存缓存实现。

```python
from agent_data.cache.memory import MemoryCache

cache = MemoryCache(max_size=10000)
await cache.set("key", "value", ttl=3600)
value = await cache.get("key")
await cache.delete("key")
await cache.clear()
```

---

## 追踪

### MemoryTracer

内存追踪器。

```python
from agent_data.tracing.memory import MemoryTracer

tracer = MemoryTracer()
span = await tracer.start_span("operation")
span.set_attribute("key", "value")
await tracer.finish_span(span)
```

### OpenTelemetryTracer

OpenTelemetry 追踪器。

```python
from agent_data.tracing.opentelemetry import OpenTelemetryTracer

tracer = OpenTelemetryTracer(
    service_name="my-service",
    endpoint="http://localhost:4317",
    sample_rate=0.1
)
```