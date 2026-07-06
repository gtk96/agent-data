"""
性能基准测试
"""

import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data import (
    AgentDataClient,
    DataSource,
    DataSourceConfig,
    DataSourceType,
    Query,
    QueryType,
    QueryFilter,
    Task,
    FunctionStep,
    WorkflowEngine,
)
from agent_data.loop.agent_loop import SimpleAgentLoop, LoopRunner


def run_async(coro):
    """Helper to run async functions."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def benchmark(name, func, iterations=100):
    """运行基准测试"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        run_async(func())
        times.append(time.perf_counter() - start)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    ops_per_sec = 1 / avg_time if avg_time > 0 else 0

    print(f"{name}:")
    print(f"  平均: {avg_time*1000:.2f}ms")
    print(f"  最小: {min_time*1000:.2f}ms")
    print(f"  最大: {max_time*1000:.2f}ms")
    print(f"  吞吐量: {ops_per_sec:.0f} ops/sec")
    print()

    return {"avg": avg_time, "min": min_time, "max": max_time, "ops": ops_per_sec}


# ==================== 测试函数 ====================

async def setup_client():
    """创建测试客户端"""
    data_sources = [
        DataSource(
            config=DataSourceConfig(
                name="test_db",
                type=DataSourceType.SQL,
                connection=":memory:",
            ),
        )
    ]
    client = AgentDataClient(data_sources=data_sources, cache_enabled=True)

    # 初始化数据库
    connector = await client._get_connector("test_db")
    connector._connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            status TEXT
        )
    """)

    # 插入测试数据
    for i in range(1000):
        connector._connection.execute(
            "INSERT INTO users (name, email, status) VALUES (?, ?, ?)",
            (f"user_{i}", f"user_{i}@test.com", "active" if i % 2 == 0 else "inactive"),
        )

    return client


async def test_query_performance():
    """测试查询性能"""
    client = await setup_client()

    result = await client.query(
        Query(source="test_db", query_type=QueryType.SELECT, limit=100)
    )
    return result


async def test_filtered_query_performance():
    """测试带过滤器的查询性能"""
    client = await setup_client()

    result = await client.query(
        Query(
            source="test_db",
            query_type=QueryType.SELECT,
            filters=[QueryFilter(field="status", operator="eq", value="active")],
            limit=50,
        )
    )
    return result


async def test_cached_query_performance():
    """测试缓存查询性能"""
    client = await setup_client()

    # 第一次查询（无缓存）
    await client.query(Query(source="test_db", query_type=QueryType.SELECT, limit=100))

    # 第二次查询（有缓存）
    result = await client.query(Query(source="test_db", query_type=QueryType.SELECT, limit=100))
    return result


async def test_batch_query_performance():
    """测试批量查询性能"""
    client = await setup_client()

    results = await client.batch_query(
        queries=[
            Query(source="test_db", query_type=QueryType.SELECT, limit=10)
            for _ in range(10)
        ],
        parallel=True,
    )
    return results


async def test_task_execution_performance():
    """测试任务执行性能"""
    client = await setup_client()

    async def my_task(input_data):
        return {"result": "success"}

    task = Task(name="test_task", input_data={"key": "value"})
    result = await client.execute_task(task, my_task)
    return result


async def test_workflow_performance():
    """测试工作流性能"""
    client = await setup_client()

    async def step1(state):
        return {"step1": True}

    async def step2(state):
        return {"step2": True}

    async def step3(state):
        return {"step3": True}

    workflow = [
        FunctionStep("step1", step1),
        FunctionStep("step2", step2),
        FunctionStep("step3", step3),
    ]

    result = await client.execute_workflow(workflow)
    return result


async def test_agent_loop_performance():
    """测试 Agent Loop 性能"""
    client = await setup_client()

    async def step(state):
        state["count"] = state.get("count", 0) + 1
        return state

    def is_complete(state):
        return state.get("count", 0) >= 10

    loop = SimpleAgentLoop(step, is_complete)
    result = await client.agent_loop(loop, {"count": 0}, max_iterations=100)
    return result


# ==================== 运行基准测试 ====================

def run_benchmarks():
    """运行所有基准测试"""
    print("=" * 60)
    print("Agent Data Framework 性能基准测试")
    print("=" * 60)
    print()

    results = {}

    print("1. 查询性能")
    results["query"] = benchmark("基础查询", test_query_performance, iterations=100)

    print("2. 过滤查询性能")
    results["filtered_query"] = benchmark("过滤查询", test_filtered_query_performance, iterations=100)

    print("3. 缓存查询性能")
    results["cached_query"] = benchmark("缓存查询", test_cached_query_performance, iterations=100)

    print("4. 批量查询性能")
    results["batch_query"] = benchmark("批量查询(10并行)", test_batch_query_performance, iterations=50)

    print("5. 任务执行性能")
    results["task"] = benchmark("任务执行", test_task_execution_performance, iterations=100)

    print("6. 工作流性能")
    results["workflow"] = benchmark("工作流(3步骤)", test_workflow_performance, iterations=100)

    print("7. Agent Loop 性能")
    results["loop"] = benchmark("Agent Loop(10迭代)", test_agent_loop_performance, iterations=50)

    # 汇总
    print("=" * 60)
    print("汇总")
    print("=" * 60)
    print()

    for name, data in results.items():
        print(f"{name}: {data['ops']:.0f} ops/sec, avg {data['avg']*1000:.2f}ms")

    print()
    print("测试完成!")


if __name__ == "__main__":
    run_benchmarks()