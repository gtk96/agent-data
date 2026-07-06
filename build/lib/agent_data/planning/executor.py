"""
Task executor for Agent planning.
"""

from abc import ABC, abstractmethod
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from agent_data.planning.task import Task, TaskPlan, TaskResult, TaskStatus


class TaskExecutor(ABC):
    """Base class for task executors."""

    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task to execute

        Returns:
            TaskResult with execution results
        """
        pass


class FunctionTaskExecutor(TaskExecutor):
    """
    Task executor that uses registered functions.
    """

    def __init__(self):
        self._executors: Dict[str, Callable] = {}

    def register(self, task_name: str, executor: Callable) -> None:
        """
        Register an executor function for a task name.

        Args:
            task_name: Task name to match
            executor: Async function to execute the task
        """
        self._executors[task_name] = executor

    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task using registered function.

        Args:
            task: Task to execute

        Returns:
            TaskResult
        """
        executor = self._executors.get(task.name)
        if executor is None:
            return task.fail(f"No executor registered for task: {task.name}")

        task.start()
        start_time = time.time()

        try:
            # Execute with timeout if specified
            if task.timeout_seconds:
                result = await asyncio.wait_for(
                    executor(task.input_data),
                    timeout=task.timeout_seconds,
                )
            else:
                result = await executor(task.input_data)

            duration_ms = (time.time() - start_time) * 1000
            return task.complete(output=result, metadata={"duration_ms": duration_ms})

        except asyncio.TimeoutError:
            return task.fail(f"Task timed out after {task.timeout_seconds}s")

        except Exception as e:
            return task.fail(str(e))


class PlanExecutor:
    """
    Executor for task plans.
    """

    def __init__(self, task_executor: TaskExecutor, max_concurrent: int = 5):
        """
        Initialize plan executor.

        Args:
            task_executor: Executor for individual tasks
            max_concurrent: Maximum concurrent task executions
        """
        self._task_executor = task_executor
        self._max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, plan: TaskPlan) -> Dict[str, TaskResult]:
        """
        Execute all tasks in a plan.

        Args:
            plan: Task plan to execute

        Returns:
            Dictionary mapping task IDs to results
        """
        results: Dict[str, TaskResult] = {}

        while not plan.is_complete:
            # Get ready tasks
            ready_tasks = plan.get_ready_tasks()

            if not ready_tasks:
                # Check if we're stuck (no ready tasks but plan not complete)
                if len(plan.in_progress_tasks) == 0:
                    break
                # Wait for in-progress tasks
                await asyncio.sleep(0.1)
                continue

            # Execute ready tasks concurrently (up to limit)
            tasks_to_execute = ready_tasks[: self._max_concurrent]

            # Create execution tasks
            execution_tasks = []
            for task in tasks_to_execute:
                execution_tasks.append(self._execute_with_semaphore(task, results, plan))

            # Wait for all to complete
            await asyncio.gather(*execution_tasks)

        return results

    async def _execute_with_semaphore(
        self, task: Task, results: Dict[str, TaskResult], plan: TaskPlan
    ) -> None:
        """Execute a task with semaphore control."""
        async with self._semaphore:
            result = await self._task_executor.execute(task)
            results[task.id] = result

    async def execute_sequential(self, plan: TaskPlan) -> Dict[str, TaskResult]:
        """
        Execute tasks sequentially in dependency order.

        Args:
            plan: Task plan to execute

        Returns:
            Dictionary mapping task IDs to results
        """
        results: Dict[str, TaskResult] = {}

        while not plan.is_complete:
            # Get ready tasks
            ready_tasks = plan.get_ready_tasks()

            if not ready_tasks:
                break

            # Execute each task sequentially
            for task in ready_tasks:
                result = await self._task_executor.execute(task)
                results[task.id] = result

                # Stop if task failed and no retries left
                if result.status == TaskStatus.FAILED and task.retry_count >= task.max_retries:
                    # Mark dependent tasks as blocked
                    for t in plan.tasks:
                        if task.id in t.dependencies:
                            t.block(f"Dependency {task.id} failed")

        return results