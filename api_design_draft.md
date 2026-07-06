# Agent Data Orchestration Framework - API 设计草案

## 一、设计原则

1. **简洁性**: 最小化 API 表面，易于学习和使用
2. **可组合性**: 模块化设计，支持灵活组合
3. **类型安全**: Python Type Hints + Pydantic 数据验证
4. **异步原生**: 全面 async/await 支持
5. **框架无关**: 可与 LangChain、LlamaIndex 等框架集成

---

## 二、核心数据模型

### 2.1 DataSource（数据源）

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum

class DataSourceType(str, Enum):
    """数据源类型"""
    SQL = "sql"
    NOSQL = "nosql"
    VECTOR = "vector"
    API = "api"
    FILE = "file"
    GRAPH = "graph"

class DataSourceConfig(BaseModel):
    """数据源配置"""
    name: str = Field(..., description="数据源名称")
    type: DataSourceType = Field(..., description="数据源类型")
    connection: str = Field(..., description="连接字符串或配置")
    schema: Optional[str] = Field(None, description="Schema 名称")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")

class DataSource(BaseModel):
    """数据源定义"""
    config: DataSourceConfig
    description: Optional[str] = Field(None, description="数据源描述")
    tags: List[str] = Field(default_factory=list, description="标签")
    
    class Config:
        use_enum_values = True
```

### 2.2 Query（查询）

```python
class QueryType(str, Enum):
    """查询类型"""
    SELECT = "select"
    SEARCH = "search"
    AGGREGATE = "aggregate"
    JOIN = "join"

class QueryFilter(BaseModel):
    """查询过滤器"""
    field: str = Field(..., description="字段名")
    operator: str = Field(..., description="操作符: eq, ne, gt, lt, gte, lte, in, like")
    value: Any = Field(..., description="值")

class Query(BaseModel):
    """数据查询"""
    source: str = Field(..., description="数据源名称")
    query_type: QueryType = Field(..., description="查询类型")
    filters: List[QueryFilter] = Field(default_factory=list, description="过滤条件")
    limit: Optional[int] = Field(None, description="返回数量限制")
    offset: Optional[int] = Field(None, description="偏移量")
    order_by: Optional[str] = Field(None, description="排序字段")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="查询元数据")
```

### 2.3 QueryResult（查询结果）

```python
class QueryResult(BaseModel):
    """查询结果"""
    data: List[Dict[str, Any]] = Field(..., description="结果数据")
    total_count: Optional[int] = Field(None, description="总数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="结果元数据")
    source: str = Field(..., description="数据源名称")
    query_time_ms: float = Field(..., description="查询耗时（毫秒）")
    cached: bool = Field(False, description="是否来自缓存")
```

### 2.4 AgentContext（Agent 上下文）

```python
class AgentContext(BaseModel):
    """Agent 上下文"""
    agent_id: str = Field(..., description="Agent ID")
    session_id: Optional[str] = Field(None, description="会话 ID")
    task_id: Optional[str] = Field(None, description="任务 ID")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="对话历史")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="上下文元数据")
```

---

## 三、核心 API 接口

### 3.1 AgentDataClient（客户端）

```python
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager

class AgentDataClient:
    """Agent 数据访问客户端"""
    
    def __init__(
        self,
        data_sources: List[DataSource],
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
        trace_enabled: bool = True
    ):
        """
        初始化客户端
        
        Args:
            data_sources: 数据源列表
            cache_enabled: 是否启用缓存
            cache_ttl: 缓存过期时间（秒）
            trace_enabled: 是否启用链路追踪
        """
        pass
    
    async def query(
        self,
        query: Union[Query, str],
        context: Optional[AgentContext] = None,
        timeout: Optional[float] = None
    ) -> QueryResult:
        """
        执行查询
        
        Args:
            query: 查询对象或自然语言查询
            context: Agent 上下文（用于上下文感知缓存）
            timeout: 超时时间（秒）
            
        Returns:
            QueryResult: 查询结果
        """
        pass
    
    async def batch_query(
        self,
        queries: List[Union[Query, str]],
        context: Optional[AgentContext] = None,
        parallel: bool = True
    ) -> List[QueryResult]:
        """
        批量查询
        
        Args:
            queries: 查询列表
            context: Agent 上下文
            parallel: 是否并行执行
            
        Returns:
            List[QueryResult]: 查询结果列表
        """
        pass
    
    async def get_data_sources(self) -> List[DataSource]:
        """获取所有数据源"""
        pass
    
    async def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        pass
```

### 3.2 自然语言查询支持

```python
# 自然语言查询示例
client = AgentDataClient(data_sources=[...])

# 自然语言查询 - 自动转换为结构化查询
result = await client.query(
    "获取最近7天的活跃用户",
    context=agent_context
)

# 混合查询 - 结构化 + 自然语言
result = await client.query(
    Query(
        source="user_database",
        query_type=QueryType.SEARCH,
        filters=[
            QueryFilter(field="status", operator="eq", value="active")
        ]
    ),
    context=agent_context
)
```

### 3.3 上下文感知缓存

```python
# 缓存策略
client = AgentDataClient(
    data_sources=[...],
    cache_enabled=True,
    cache_ttl=3600,
    cache_strategy="context_aware"  # 上下文感知缓存
)

# 相同上下文的查询会命中缓存
result1 = await client.query("获取用户信息", context=agent_context)
result2 = await client.query("获取用户信息", context=agent_context)  # 命中缓存

# 不同上下文的查询不会命中缓存
result3 = await client.query("获取用户信息", context=different_context)  # 重新查询
```

---

## 四、数据源连接器

### 4.1 连接器协议

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class BaseConnector(ABC):
    """连接器基类"""
    
    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    @abstractmethod
    async def execute(self, query: Query) -> QueryResult:
        """执行查询"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """获取数据源 Schema"""
        pass
```

### 4.2 内置连接器

```python
# SQL 连接器
from agent_data.connectors import PostgreSQLConnector, MySQLConnector, SQLiteConnector

# NoSQL 连接器
from agent_data.connectors import MongoDBConnector, RedisConnector

# 向量存储连接器
from agent_data.connectors import ChromaConnector, QdrantConnector, PineconeConnector

# API 连接器
from agent_data.connectors import RESTConnector, GraphQLConnector

# 文件连接器
from agent_data.connectors import FileConnector, S3Connector
```

### 4.3 自定义连接器

```python
from agent_data.connectors import BaseConnector

class CustomConnector(BaseConnector):
    """自定义连接器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def connect(self) -> None:
        # 实现连接逻辑
        pass
    
    async def execute(self, query: Query) -> QueryResult:
        # 实现查询逻辑
        pass
    
    # ... 其他方法

# 注册自定义连接器
from agent_data import register_connector
register_connector("custom", CustomConnector)
```

---

## 五、链路追踪

### 5.1 追踪配置

```python
from agent_data.tracing import TracerConfig

# 配置追踪
tracer_config = TracerConfig(
    enabled=True,
    export_endpoint="http://localhost:4317",  # OpenTelemetry endpoint
    sample_rate=0.1,  # 采样率
    attributes={
        "service.name": "my-agent",
        "environment": "production"
    }
)

client = AgentDataClient(
    data_sources=[...],
    tracer_config=tracer_config
)
```

### 5.2 追踪数据

```python
# 自动追踪所有查询
result = await client.query("获取用户信息", context=agent_context)

# 追踪数据包含：
# - 查询内容
# - 执行时间
# - 缓存命中情况
# - 数据源连接信息
# - Agent 上下文
```

---

## 六、使用示例

### 6.1 基础用法

```python
import asyncio
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType

# 定义数据源
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="user_db",
            type=DataSourceType.SQL,
            connection="postgresql://user:pass@localhost:5432/mydb"
        ),
        description="用户数据库"
    ),
    DataSource(
        config=DataSourceConfig(
            name="vector_store",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8000"
        ),
        description="向量存储"
    )
]

# 创建客户端
client = AgentDataClient(data_sources=data_sources)

# 执行查询
async def main():
    result = await client.query("获取所有活跃用户")
    print(f"查询结果: {result.data}")
    print(f"查询耗时: {result.query_time_ms}ms")

asyncio.run(main())
```

### 6.2 与 LangChain 集成

```python
from langchain.agents import initialize_agent
from agent_data.integrations.langchain import AgentDataTool

# 创建 LangChain 工具
tool = AgentDataTool(
    client=client,
    name="data_query",
    description="查询数据源获取信息"
)

# 创建 Agent
agent = initialize_agent(
    tools=[tool],
    llm=llm,
    agent="zero-shot-react-description"
)

# Agent 自动使用数据查询工具
result = agent.run("获取最近7天的活跃用户数量")
```

### 6.3 与 LlamaIndex 集成

```python
from llama_index.core import VectorStoreIndex
from agent_data.integrations.llamaindex import AgentDataReader

# 创建 LlamaIndex Reader
reader = AgentDataReader(client=client)

# 加载数据
documents = reader.load_data(source="user_db", query="SELECT * FROM users")

# 创建索引
index = VectorStoreIndex.from_documents(documents)
```

---

## 七、配置文件示例

```yaml
# agent_data.yaml
version: "1.0"

data_sources:
  - name: user_database
    type: sql
    connection: postgresql://user:pass@localhost:5432/mydb
    schema: public
    description: 用户数据库
    
  - name: vector_store
    type: vector
    connection: http://localhost:8000
    description: 文档向量存储

cache:
  enabled: true
  ttl: 3600
  strategy: context_aware

tracing:
  enabled: true
  endpoint: http://localhost:4317
  sample_rate: 0.1

logging:
  level: info
  format: json
```

---

## 八、实际使用场景示例

### 场景一：客服 Agent - 多数据源整合

**背景**: 客服 Agent 需要同时访问用户数据库、订单系统、知识库来回答用户问题。

```python
import asyncio
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType
from agent_data.integrations.langchain import AgentDataTool

# 配置多数据源
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="user_db",
            type=DataSourceType.SQL,
            connection="postgresql://user:pass@localhost:5432/users",
            schema="public"
        ),
        description="用户信息数据库",
        tags=["user", "profile"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="order_db",
            type=DataSourceType.SQL,
            connection="postgresql://user:pass@localhost:5432/orders",
            schema="public"
        ),
        description="订单数据库",
        tags=["order", "transaction"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="knowledge_base",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8000",
            metadata={"collection": "faq_docs"}
        ),
        description="FAQ 知识库",
        tags=["faq", "knowledge"]
    )
]

# 创建客户端
client = AgentDataClient(
    data_sources=data_sources,
    cache_enabled=True,
    cache_ttl=1800,  # 30 分钟缓存
    trace_enabled=True
)

# 场景 1: 用户查询订单状态
async def handle_order_inquiry():
    """处理订单查询"""
    context = {
        "agent_id": "customer_service_agent",
        "session_id": "session_123",
        "user_id": "user_456"
    }
    
    # 自然语言查询 - 自动路由到合适的数据源
    result = await client.query(
        "用户 user_456 最近的订单状态",
        context=context
    )
    
    return result.data

# 场景 2: 用户咨询产品问题
async def handle_product_question():
    """处理产品咨询"""
    context = {
        "agent_id": "customer_service_agent",
        "session_id": "session_124",
        "user_id": "user_789"
    }
    
    # 从知识库检索相关文档
    result = await client.query(
        "如何重置密码",
        context=context
    )
    
    return result.data

# 场景 3: 批量查询 - 获取用户完整信息
async def get_user_full_profile():
    """获取用户完整画像"""
    context = {
        "agent_id": "customer_service_agent",
        "session_id": "session_125",
        "user_id": "user_456"
    }
    
    # 批量查询多个数据源
    results = await client.batch_query(
        queries=[
            "用户基本信息",
            "用户最近订单",
            "用户历史工单"
        ],
        context=context,
        parallel=True  # 并行查询提高效率
    )
    
    # 合并结果
    user_profile = {
        "info": results[0].data,
        "recent_orders": results[1].data,
        "tickets": results[2].data
    }
    
    return user_profile

# 创建 LangChain 工具
tool = AgentDataTool(
    client=client,
    name="customer_data_query",
    description="查询用户、订单、知识库数据"
)

# 使用示例
async def main():
    # 处理订单查询
    order_info = await handle_order_inquiry()
    print(f"订单信息: {order_info}")
    
    # 处理产品咨询
    faq_info = await handle_product_question()
    print(f"FAQ 信息: {faq_info}")
    
    # 获取用户完整画像
    profile = await get_user_full_profile()
    print(f"用户画像: {profile}")

asyncio.run(main())
```

### 场景二：数据分析 Agent - 结构化数据查询

**背景**: 数据分析 Agent 需要从数据仓库查询数据，支持自然语言到 SQL 的转换。

```python
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType
from agent_data.query import NaturalLanguageToSQL

# 配置数据仓库
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="data_warehouse",
            type=DataSourceType.SQL,
            connection="snowflake://user:pass@account/db/warehouse",
            metadata={
                "type": "snowflake",
                "schema_info": {
                    "sales": ["date", "product_id", "amount", "region"],
                    "users": ["user_id", "signup_date", "plan", "status"],
                    "products": ["product_id", "name", "category", "price"]
                }
            }
        ),
        description="数据仓库",
        tags=["analytics", "dw"]
    )
]

# 创建客户端
client = AgentDataClient(data_sources=data_sources)

# 创建自然语言到 SQL 转换器
nl_to_sql = NaturalLanguageToSQL(
    client=client,
    model="gpt-4",  # 用于 SQL 生成的模型
    schema_cache_ttl=3600  # Schema 缓存 1 小时
)

# 场景 1: 自然语言查询
async def analyze_sales():
    """分析销售数据"""
    # 自然语言 → SQL → 查询结果
    result = await nl_to_sql.query(
        "上个月每个地区的销售额是多少？",
        source="data_warehouse"
    )
    
    print(f"生成的 SQL: {result.metadata.get('generated_sql')}")
    print(f"查询结果: {result.data}")
    
    return result

# 场景 2: 复杂分析查询
async def analyze_user_retention():
    """分析用户留存"""
    result = await nl_to_sql.query(
        "计算最近 30 天新用户的 7 天留存率",
        source="data_warehouse"
    )
    
    return result

# 场景 3: 带过滤条件的查询
async def analyze_product_performance():
    """分析产品表现"""
    result = await nl_to_sql.query(
        "查看电子产品类别中，销售额排名前 10 的产品",
        source="data_warehouse"
    )
    
    return result

# 使用示例
async def main():
    # 销售分析
    sales_data = await analyze_sales()
    
    # 留存分析
    retention_data = await analyze_user_retention()
    
    # 产品分析
    product_data = await analyze_product_performance()
    
    # 可以将结果传递给可视化工具或报告生成器
    return {
        "sales": sales_data.data,
        "retention": retention_data.data,
        "products": product_data.data
    }

asyncio.run(main())
```

### 场景三：文档检索 Agent - RAG 应用

**背景**: 文档检索 Agent 需要从多个文档源检索信息，支持语义搜索和关键词搜索。

```python
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType
from agent_data.retrieval import HybridRetriever, Reranker

# 配置多文档源
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="technical_docs",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8000",
            metadata={
                "collection": "tech_docs",
                "embedding_model": "text-embedding-3-small"
            }
        ),
        description="技术文档",
        tags=["docs", "technical"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="product_manuals",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8001",
            metadata={
                "collection": "manuals",
                "embedding_model": "text-embedding-3-small"
            }
        ),
        description="产品手册",
        tags=["manual", "product"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="internal_knowledge",
            type=DataSourceType.FILE,
            connection="/data/internal_docs",
            metadata={
                "file_types": ["pdf", "docx", "md"],
                "recursive": True
            }
        ),
        description="内部知识库",
        tags=["internal", "knowledge"]
    )
]

# 创建客户端
client = AgentDataClient(data_sources=data_sources)

# 创建混合检索器
retriever = HybridRetriever(
    client=client,
    vector_weight=0.7,  # 语义搜索权重
    keyword_weight=0.3,  # 关键词搜索权重
    top_k=10
)

# 创建重排序器
reranker = Reranker(
    model="cross-encoder/ms-marco-MiniLM-L-6-v2",
    top_k=5
)

# 场景 1: 语义搜索
async def semantic_search():
    """语义搜索文档"""
    results = await retriever.search(
        query="如何配置数据库连接池",
        search_type="semantic",
        filters={"tags": ["technical"]}
    )
    
    # 重排序
    reranked = await reranker.rerank(
        query="如何配置数据库连接池",
        documents=results
    )
    
    return reranked

# 场景 2: 关键词搜索
async def keyword_search():
    """关键词搜索"""
    results = await retriever.search(
        query="MySQL 连接池配置",
        search_type="keyword",
        filters={"source": "technical_docs"}
    )
    
    return results

# 场景 3: 混合搜索
async def hybrid_search():
    """混合搜索 - 结合语义和关键词"""
    results = await retriever.search(
        query="数据库性能优化",
        search_type="hybrid",
        filters={"tags": ["technical", "performance"]}
    )
    
    return results

# 场景 4: 多轮对话检索
async def conversational_search():
    """多轮对话中的上下文感知检索"""
    context = {
        "agent_id": "doc_assistant",
        "session_id": "session_200",
        "history": [
            {"role": "user", "content": "我想了解数据库配置"},
            {"role": "assistant", "content": "您想了解哪方面的配置？连接池、超时设置还是其他？"}
        ]
    }
    
    # 上下文感知查询 - 会考虑对话历史
    results = await client.query(
        "连接池大小怎么设置",
        context=context
    )
    
    return results

# 使用示例
async def main():
    # 语义搜索
    semantic_results = await semantic_search()
    print(f"语义搜索结果: {semantic_results}")
    
    # 关键词搜索
    keyword_results = await keyword_search()
    print(f"关键词搜索结果: {keyword_results}")
    
    # 混合搜索
    hybrid_results = await hybrid_search()
    print(f"混合搜索结果: {hybrid_results}")
    
    # 多轮对话检索
    conv_results = await conversational_search()
    print(f"对话检索结果: {conv_results}")

asyncio.run(main())
```

### 场景四：实时监控 Agent - 流式数据处理

**背景**: 监控 Agent 需要实时查询系统指标和日志，支持流式数据处理。

```python
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType
from agent_data.streaming import StreamingQuery, StreamProcessor

# 配置实时数据源
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="metrics_db",
            type=DataSourceType.SQL,
            connection="postgresql://user:pass@localhost:5432/metrics",
            metadata={
                "type": "timeseries",
                "retention_days": 30
            }
        ),
        description="系统指标数据库",
        tags=["metrics", "realtime"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="log_stream",
            type=DataSourceType.API,
            connection="kafka://localhost:9092",
            metadata={
                "topic": "app_logs",
                "consumer_group": "monitor_agent"
            }
        ),
        description="日志流",
        tags=["logs", "streaming"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="alert_store",
            type=DataSourceType.NOSQL,
            connection="redis://localhost:6379",
            metadata={
                "prefix": "alerts:",
                "ttl": 86400
            }
        ),
        description="告警存储",
        tags=["alerts", "cache"]
    )
]

# 创建客户端
client = AgentDataClient(data_sources=data_sources)

# 创建流式查询
streaming_query = StreamingQuery(client=client)

# 创建流处理器
stream_processor = StreamProcessor(
    client=client,
    buffer_size=100,  # 缓冲区大小
    flush_interval=1.0  # 刷新间隔（秒）
)

# 场景 1: 实时指标查询
async def get_realtime_metrics():
    """获取实时系统指标"""
    result = await client.query(
        Query(
            source="metrics_db",
            query_type=QueryType.AGGREGATE,
            filters=[
                QueryFilter(field="timestamp", operator="gte", value="now()-5m"),
                QueryFilter(field="metric_name", operator="in", value=["cpu_usage", "memory_usage", "request_count"])
            ],
            metadata={"aggregation": "avg", "group_by": "metric_name"}
        )
    )
    
    return result.data

# 场景 2: 流式日志查询
async def stream_logs():
    """流式查询日志"""
    async for log_batch in streaming_query.stream(
        source="log_stream",
        filters=[
            QueryFilter(field="level", operator="eq", value="ERROR")
        ],
        batch_size=50
    ):
        # 处理日志批次
        print(f"收到 {len(log_batch)} 条错误日志")
        
        # 可以在这里进行实时分析或告警
        for log in log_batch:
            await process_log(log)

# 场景 3: 异常检测
async def detect_anomalies():
    """检测系统异常"""
    # 查询最近 1 小时的指标
    result = await client.query(
        "最近 1 小时的 CPU 使用率",
        context={"agent_id": "monitor_agent"}
    )
    
    # 分析异常
    anomalies = []
    for metric in result.data:
        if metric["value"] > 90:  # 阈值
            anomalies.append({
                "metric": metric["metric_name"],
                "value": metric["value"],
                "timestamp": metric["timestamp"]
            })
    
    # 存储告警
    if anomalies:
        await client.query(
            Query(
                source="alert_store",
                query_type=QueryType.SELECT,
                metadata={
                    "action": "set",
                    "key": f"anomaly:{datetime.now().isoformat()}",
                    "value": anomalies
                }
            )
        )
    
    return anomalies

# 场景 4: 告警处理
async def process_alerts():
    """处理告警"""
    result = await client.query(
        Query(
            source="alert_store",
            query_type=QueryType.SELECT,
            filters=[
                QueryFilter(field="status", operator="eq", value="pending")
            ]
        )
    )
    
    alerts = result.data
    
    for alert in alerts:
        # 处理告警
        await handle_alert(alert)
    
    return alerts

# 辅助函数
async def process_log(log):
    """处理单条日志"""
    # 实现日志处理逻辑
    pass

async def handle_alert(alert):
    """处理告警"""
    # 实现告警处理逻辑
    pass

# 使用示例
async def main():
    # 获取实时指标
    metrics = await get_realtime_metrics()
    print(f"实时指标: {metrics}")
    
    # 检测异常
    anomalies = await detect_anomalies()
    print(f"检测到异常: {anomalies}")
    
    # 处理告警
    alerts = await process_alerts()
    print(f"处理告警: {len(alerts)} 个")

asyncio.run(main())
```

### 场景五：电商推荐 Agent - 用户画像构建

**背景**: 电商推荐 Agent 需要从多个数据源构建用户画像，支持个性化推荐。

```python
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType
from agent_data.profiles import UserProfileBuilder, ProfileMerger

# 配置电商数据源
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="user_profiles",
            type=DataSourceType.SQL,
            connection="postgresql://user:pass@localhost:5432/users",
            schema="public"
        ),
        description="用户基础信息",
        tags=["user", "profile"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="order_history",
            type=DataSourceType.SQL,
            connection="postgresql://user:pass@localhost:5432/orders",
            schema="public"
        ),
        description="订单历史",
        tags=["order", "history"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="browsing_behavior",
            type=DataSourceType.NOSQL,
            connection="mongodb://localhost:27017",
            metadata={"database": "analytics", "collection": "page_views"}
        ),
        description="浏览行为",
        tags=["behavior", "browsing"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="product_catalog",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8000",
            metadata={"collection": "products"}
        ),
        description="商品知识库",
        tags=["product", "catalog"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="reviews",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8001",
            metadata={"collection": "reviews"}
        ),
        description="用户评价",
        tags=["review", "feedback"]
    )
]

# 创建客户端
client = AgentDataClient(data_sources=data_sources)

# 创建用户画像构建器
profile_builder = UserProfileBuilder(client=client)

# 创建画像合并器
profile_merger = ProfileMerger(
    weights={
        "demographics": 0.2,  # 人口统计
        "purchases": 0.3,     # 购买行为
        "browsing": 0.25,     # 浏览行为
        "preferences": 0.25   # 偏好
    }
)

# 场景 1: 构建用户画像
async def build_user_profile(user_id: str):
    """构建完整用户画像"""
    # 并行获取多维度数据
    profile_data = await client.batch_query(
        queries=[
            f"用户 {user_id} 的基础信息",
            f"用户 {user_id} 最近 90 天的订单",
            f"用户 {user_id} 最近 7 天的浏览记录",
            f"用户 {user_id} 的商品评价"
        ],
        context={"agent_id": "recommendation_agent", "user_id": user_id}
    )
    
    # 合并成统一画像
    profile = profile_merger.merge({
        "demographics": profile_data[0].data,
        "purchases": profile_data[1].data,
        "browsing": profile_data[2].data,
        "reviews": profile_data[3].data
    })
    
    return profile

# 场景 2: 基于画像的推荐
async def get_recommendations(user_id: str, context_query: str = None):
    """基于用户画像获取推荐"""
    # 获取用户画像
    profile = await build_user_profile(user_id)
    
    # 构建推荐查询
    if context_query:
        # 上下文感知推荐
        result = await client.query(
            f"推荐与 {context_query} 相关的商品",
            context={
                "agent_id": "recommendation_agent",
                "user_id": user_id,
                "user_profile": profile
            }
        )
    else:
        # 个性化推荐
        result = await client.query(
            "推荐用户可能感兴趣的商品",
            context={
                "agent_id": "recommendation_agent",
                "user_id": user_id,
                "user_profile": profile
            }
        )
    
    return result.data

# 场景 3: 相似用户发现
async def find_similar_users(user_id: str, limit: int = 10):
    """找到相似用户"""
    # 获取目标用户画像
    target_profile = await build_user_profile(user_id)
    
    # 查询相似用户
    result = await client.query(
        Query(
            source="user_profiles",
            query_type=QueryType.SEARCH,
            filters=[
                QueryFilter(field="user_id", operator="ne", value=user_id)
            ],
            limit=limit,
            metadata={
                "similarity_target": target_profile,
                "similarity_fields": ["purchases", "browsing"]
            }
        )
    )
    
    return result.data

# 场景 4: 实时行为追踪
async def track_user_behavior(user_id: str, event: dict):
    """追踪用户实时行为"""
    # 记录行为事件
    await client.query(
        Query(
            source="browsing_behavior",
            query_type=QueryType.SELECT,
            metadata={
                "action": "insert",
                "data": {
                    "user_id": user_id,
                    "event_type": event["type"],
                    "product_id": event.get("product_id"),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": event.get("metadata", {})
                }
            }
        )
    )
    
    # 实时更新用户画像
    await profile_builder.update_profile(
        user_id=user_id,
        event=event
    )

# 使用示例
async def main():
    user_id = "user_12345"
    
    # 构建用户画像
    profile = await build_user_profile(user_id)
    print(f"用户画像: {profile}")
    
    # 获取推荐
    recommendations = await get_recommendations(user_id)
    print(f"推荐商品: {recommendations}")
    
    # 上下文感知推荐
    context_recs = await get_recommendations(user_id, "无线耳机")
    print(f"上下文推荐: {context_recs}")
    
    # 相似用户
    similar_users = await find_similar_users(user_id)
    print(f"相似用户: {similar_users}")

asyncio.run(main())
```

### 场景六：代码助手 Agent - 多代码库检索

**背景**: 代码助手 Agent 需要从多个代码库检索代码片段，支持语义搜索和结构化查询。

```python
from agent_data import AgentDataClient, DataSource, DataSourceConfig, DataSourceType
from agent_data.code import CodeRetriever, CodeAnalyzer

# 配置代码库数据源
data_sources = [
    DataSource(
        config=DataSourceConfig(
            name="github_repos",
            type=DataSourceType.API,
            connection="github://api.github.com",
            metadata={
                "repos": ["org/repo1", "org/repo2"],
                "token": "${GITHUB_TOKEN}"
            }
        ),
        description="GitHub 代码库",
        tags=["code", "github"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="code_embeddings",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8000",
            metadata={
                "collection": "code_chunks",
                "embedding_model": "codellama-7b"
            }
        ),
        description="代码向量索引",
        tags=["code", "embeddings"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="api_docs",
            type=DataSourceType.VECTOR,
            connection="http://localhost:8001",
            metadata={"collection": "api_documentation"}
        ),
        description="API 文档",
        tags=["docs", "api"]
    ),
    DataSource(
        config=DataSourceConfig(
            name="issue_tracker",
            type=DataSourceType.API,
            connection="github://api.github.com",
            metadata={
                "repos": ["org/repo1", "org/repo2"],
                "type": "issues"
            }
        ),
        description="Issue 跟踪",
        tags=["issues", "bugs"]
    )
]

# 创建客户端
client = AgentDataClient(data_sources=data_sources)

# 创建代码检索器
code_retriever = CodeRetriever(
    client=client,
    languages=["python", "javascript", "go"],
    min_similarity=0.7
)

# 创建代码分析器
code_analyzer = CodeAnalyzer(client=client)

# 场景 1: 语义代码搜索
async def semantic_code_search():
    """语义搜索代码"""
    results = await code_retriever.search(
        query="实现一个带有重试机制的 HTTP 客户端",
        languages=["python"],
        repo_filter="org/repo1"
    )
    
    return results

# 场景 2: 基于上下文的代码检索
async def context_aware_search():
    """基于上下文的代码检索"""
    context = {
        "agent_id": "code_assistant",
        "session_id": "session_300",
        "current_file": "src/utils/http_client.py",
        "recent_changes": [
            {"file": "src/utils/http_client.py", "action": "modified"}
        ]
    }
    
    # 上下文感知查询
    results = await client.query(
        "添加请求超时处理",
        context=context
    )
    
    return results

# 场景 3: 代码片段聚合
async def aggregate_code_patterns():
    """聚合代码模式"""
    # 查找所有重试机制的实现
    retry_patterns = await code_retriever.search(
        query="重试机制实现",
        limit=20
    )
    
    # 分析常见模式
    patterns = await code_analyzer.analyze_patterns(
        code_chunks=retry_patterns,
        pattern_type="retry"
    )
    
    return patterns

# 场景 4: Issue 关联代码
async def find_related_code_for_issue():
    """为 Issue 找到相关代码"""
    issue = await client.query(
        Query(
            source="issue_tracker",
            query_type=QueryType.SELECT,
            filters=[
                QueryFilter(field="number", operator="eq", value=1234)
            ]
        )
    )
    
    issue_data = issue.data[0]
    
    # 根据 Issue 描述搜索相关代码
    related_code = await code_retriever.search(
        query=issue_data["title"] + " " + issue_data["body"],
        limit=5
    )
    
    return {
        "issue": issue_data,
        "related_code": related_code
    }

# 场景 5: API 文档查询
async def search_api_docs():
    """搜索 API 文档"""
    result = await client.query(
        "如何使用认证中间件",
        context={"source": "api_docs"}
    )
    
    return result.data

# 使用示例
async def main():
    # 语义代码搜索
    code_results = await semantic_code_search()
    print(f"代码搜索结果: {code_results}")
    
    # 上下文感知搜索
    context_results = await context_aware_search()
    print(f"上下文搜索结果: {context_results}")
    
    # 代码模式分析
    patterns = await aggregate_code_patterns()
    print(f"代码模式: {patterns}")
    
    # Issue 关联代码
    issue_code = await find_related_code_for_issue()
    print(f"Issue 关联代码: {issue_code}")

asyncio.run(main())
```

---

## 九、配置文件示例（扩展版）

```yaml
# agent_data.yaml
version: "1.0"

# 数据源配置
data_sources:
  - name: user_database
    type: sql
    connection: postgresql://user:pass@localhost:5432/mydb
    schema: public
    description: 用户数据库
    tags: ["user", "profile"]
    
  - name: vector_store
    type: vector
    connection: http://localhost:8000
    description: 文档向量存储
    tags: ["docs", "knowledge"]
    
  - name: log_stream
    type: api
    connection: kafka://localhost:9092
    description: 日志流
    tags: ["logs", "streaming"]
    metadata:
      topic: app_logs
      consumer_group: agent_group

# 缓存配置
cache:
  enabled: true
  ttl: 3600
  strategy: context_aware  # context_aware | simple | disabled
  max_size: 10000  # 最大缓存条目数

# 追踪配置
tracing:
  enabled: true
  endpoint: http://localhost:4317  # OpenTelemetry endpoint
  sample_rate: 0.1
  attributes:
    service.name: my-agent
    environment: production

# 日志配置
logging:
  level: info
  format: json
  file: /var/log/agent_data.log

# 性能配置
performance:
  max_concurrent_queries: 100
  query_timeout: 30  # 秒
  batch_size: 100

# 安全配置
security:
  encryption_enabled: true
  audit_log: true
  allowed_sources: ["user_database", "vector_store"]  # 允许访问的数据源
```

---

## 十、下一步

1. **完善 API 设计**: 根据反馈迭代
2. **实现核心功能**: 优先实现 SQL 和向量存储连接器
3. **编写文档**: API 文档和使用指南
4. **发布 PoC**: 在 GitHub 发布早期版本

---

*最后更新: 2026-07-06*