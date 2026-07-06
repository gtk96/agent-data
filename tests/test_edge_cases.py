"""
边界测试 - 异常处理、空输入、并发等场景
"""

import asyncio
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
    TaskStatus,
    FunctionStep,
    WorkflowEngine,
)
from agent_data.planning.executor import FunctionTaskExecutor
from agent_data.loop.agent_loop import SimpleAgentLoop, LoopRunner


def run_async(coro):
    """Helper to run async functions."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ==================== Task 边界测试 ====================


def test_task_empty_name():
    """测试空名称任务"""
    task = Task(name="")
    assert task.name == ""


def test_task_max_retries_zero():
    """测试最大重试次数为0"""
    task = Task(name="test", max_retries=0)
    task.start()
    assert task.retry() == False


def test_task_complete_after_fail():
    """测试失败后完成"""
    task = Task(name="test")
    task.start()
    task.fail("error")
    assert task.status == TaskStatus.FAILED

    # 重新开始并完成
    task.retry()
    task.start()
    result = task.complete()
    assert task.status == TaskStatus.COMPLETED


def test_task_cancel():
    """测试取消任务"""
    task = Task(name="test")
    task.start()
    task.cancel()
    assert task.status == TaskStatus.CANCELLED


def test_task_block_unblock():
    """测试阻塞和解除阻塞"""
    task = Task(name="test")
    task.block("waiting for dependency")
    assert task.status == TaskStatus.BLOCKED
    assert task.metadata.get("block_reason") == "waiting for dependency"

    task.unblock()
    assert task.status == TaskStatus.PENDING


# ==================== Query 边界测试 ====================


def test_query_empty_filters():
    """测试空过滤器"""
    query = Query(source="test", query_type=QueryType.SELECT, filters=[])
    assert len(query.filters) == 0


def test_query_default_values():
    """测试默认值"""
    query = Query(source="test")
    assert query.query_type == QueryType.SELECT
    assert query.limit is None
    assert query.offset is None


# ==================== Executor 边界测试 ====================


def test_executor_no_handler():
    """测试没有注册处理器的任务"""

    async def _test():
        executor = FunctionTaskExecutor()
        task = Task(name="unknown_task")
        result = await executor.execute(task)
        assert result.status == TaskStatus.FAILED
        assert "No executor registered" in result.error

    run_async(_test())


def test_executor_timeout():
    """测试任务超时"""

    async def _test():
        async def slow_task(input_data):
            await asyncio.sleep(10)
            return {"result": "slow"}

        executor = FunctionTaskExecutor()
        executor.register("slow", slow_task)

        task = Task(name="slow", timeout_seconds=0.1)
        result = await executor.execute(task)
        assert result.status == TaskStatus.FAILED
        assert "timed out" in result.error.lower()

    run_async(_test())


def test_executor_exception():
    """测试任务异常"""

    async def _test():
        async def failing_task(input_data):
            raise ValueError("Test error")

        executor = FunctionTaskExecutor()
        executor.register("failing", failing_task)

        task = Task(name="failing")
        result = await executor.execute(task)
        assert result.status == TaskStatus.FAILED
        assert "Test error" in result.error

    run_async(_test())


# ==================== Workflow 边界测试 ====================


def test_workflow_empty_steps():
    """测试空工作流"""

    async def _test():
        engine = WorkflowEngine()
        result = await engine.execute([])
        assert len(result["results"]) == 0

    run_async(_test())


def test_workflow_step_failure():
    """测试步骤失败"""

    async def _test():
        async def failing_step(state):
            raise RuntimeError("Step failed")

        async def success_step(state):
            return {"success": True}

        steps = [
            FunctionStep("failing", failing_step),
            FunctionStep("success", success_step),
        ]

        engine = WorkflowEngine()
        result = await engine.execute(steps)

        # 第一步失败，第二步不应执行
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "failed"

    run_async(_test())


def test_workflow_state_sharing():
    """测试状态共享"""

    async def _test():
        async def step1(state):
            return {"key1": "value1"}

        async def step2(state):
            # 应该能看到 step1 的结果
            return {"key2": state.get("key1")}

        steps = [
            FunctionStep("step1", step1),
            FunctionStep("step2", step2),
        ]

        engine = WorkflowEngine()
        result = await engine.execute(steps)

        assert result["state"]["key1"] == "value1"
        assert result["state"]["key2"] == "value1"

    run_async(_test())


# ==================== Loop 边界测试 ====================


def test_loop_immediate_complete():
    """测试立即完成"""

    async def _test():
        async def step(state):
            return state

        def is_complete(state):
            return True

        loop = SimpleAgentLoop(step, is_complete)
        runner = LoopRunner(max_iterations=10)
        result = await runner.run(loop, {})

        assert result.status.value == "completed"
        assert result.iterations == 1

    run_async(_test())


def test_loop_exception_in_step():
    """测试步骤异常"""

    async def _test():
        async def failing_step(state):
            raise RuntimeError("Step failed")

        def is_complete(state):
            return False

        loop = SimpleAgentLoop(failing_step, is_complete)
        runner = LoopRunner(max_iterations=10)
        result = await runner.run(loop, {})

        assert result.status.value == "failed"
        assert "Step failed" in result.error

    run_async(_test())


# ==================== Client 边界测试 ====================


def test_client_empty_data_sources():
    """测试空数据源"""

    async def _test():
        client = AgentDataClient(data_sources=[])
        sources = await client.get_data_sources()
        assert len(sources) == 0

    run_async(_test())


def test_client_unknown_source():
    """测试未知数据源"""

    async def _test():
        client = AgentDataClient(data_sources=[])
        try:
            await client._get_connector("unknown")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not found" in str(e)

    run_async(_test())


def test_client_health_check_empty():
    """测试空数据源健康检查"""

    async def _test():
        client = AgentDataClient(data_sources=[])
        health = await client.health_check()
        assert len(health) == 0

    run_async(_test())
