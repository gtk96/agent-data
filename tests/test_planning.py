"""
Tests for planning module.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data.planning import Task, TaskStatus, SimpleTaskPlanner
from agent_data.planning.executor import FunctionTaskExecutor, PlanExecutor


def run_async(coro):
    """Helper to run async functions."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_task_creation():
    """Test task creation."""
    task = Task(name="test_task", description="Test task")
    assert task.name == "test_task"
    assert task.status == TaskStatus.PENDING
    assert task.retry_count == 0


def test_task_lifecycle():
    """Test task status transitions."""
    task = Task(name="test_task")

    # Start
    task.start()
    assert task.status == TaskStatus.IN_PROGRESS

    # Complete
    result = task.complete(output={"data": "test"})
    assert task.status == TaskStatus.COMPLETED
    assert result.status == TaskStatus.COMPLETED
    assert result.output == {"data": "test"}


def test_task_fail():
    """Test task failure."""
    task = Task(name="test_task")
    task.start()
    result = task.fail("Error occurred")
    assert task.status == TaskStatus.FAILED
    assert result.error == "Error occurred"


def test_task_retry():
    """Test task retry."""
    task = Task(name="test_task", max_retries=2)
    task.start()

    # First retry
    assert task.retry() == True
    assert task.status == TaskStatus.PENDING
    assert task.retry_count == 1

    # Second retry
    assert task.retry() == True
    assert task.retry_count == 2

    # Max retries reached
    assert task.retry() == False


def test_task_plan():
    """Test task plan."""
    from agent_data.planning.task import TaskPlan

    plan = TaskPlan(goal="test goal")
    task1 = Task(name="task1")
    task2 = Task(name="task2", dependencies=[task1.id])

    plan.add_task(task1)
    plan.add_task(task2)

    assert len(plan.tasks) == 2
    assert plan.get_task(task1.id) is not None
    assert plan.get_task(task2.id) is not None


def test_task_executor():
    """Test function task executor."""

    async def _test():
        async def my_task(input_data):
            return {"result": "success", "input": input_data}

        executor = FunctionTaskExecutor()
        executor.register("test", my_task)

        task = Task(name="test", input_data={"query": "test"})
        result = await executor.execute(task)

        assert result.status == TaskStatus.COMPLETED
        assert result.output["result"] == "success"

    run_async(_test())


def test_simple_planner():
    """Test simple task planner."""

    async def _test():
        planner = SimpleTaskPlanner()
        plan = await planner.plan("查询用户数据")

        assert plan.goal == "查询用户数据"
        assert len(plan.tasks) > 0

    run_async(_test())
