"""
Task planner for Agent planning.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from agent_data.planning.task import Task, TaskPlan


class TaskPlanner(ABC):
    """Base class for task planners."""

    @abstractmethod
    async def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """
        Create an execution plan for a goal.

        Args:
            goal: The goal to achieve
            context: Additional context for planning

        Returns:
            TaskPlan with tasks to execute
        """
        pass

    @abstractmethod
    async def replan(
        self, plan: TaskPlan, last_result: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """
        Replan based on execution results.

        Args:
            plan: Current execution plan
            last_result: Result of the last executed task

        Returns:
            Updated TaskPlan
        """
        pass


class SimpleTaskPlanner(TaskPlanner):
    """
    Simple task planner that creates a linear sequence of tasks.

    This is a basic planner that can be extended with LLM-based planning.
    """

    def __init__(self):
        self._task_templates: Dict[str, List[Dict[str, Any]]] = {}

    def register_template(self, goal_pattern: str, task_templates: List[Dict[str, Any]]) -> None:
        """
        Register a task template for a goal pattern.

        Args:
            goal_pattern: Pattern to match (e.g., "query:*", "analyze:*")
            task_templates: List of task templates
        """
        self._task_templates[goal_pattern] = task_templates

    async def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """
        Create a simple linear plan.

        Args:
            goal: The goal to achieve
            context: Additional context

        Returns:
            TaskPlan with tasks
        """
        # Try to match goal pattern
        tasks = []

        for pattern, templates in self._task_templates.items():
            if self._match_pattern(goal, pattern):
                for template in templates:
                    task = Task(
                        name=template.get("name", "task"),
                        description=template.get("description", ""),
                        input_data=template.get("input", {}),
                        priority=template.get("priority", 0),
                    )
                    tasks.append(task)
                break

        # Default plan if no template matched
        if not tasks:
            tasks = [
                Task(
                    name="execute",
                    description=f"Execute: {goal}",
                    input_data={"goal": goal, **(context or {})},
                )
            ]

        return TaskPlan(goal=goal, tasks=tasks, metadata=context or {})

    async def replan(
        self, plan: TaskPlan, last_result: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """
        Replan based on results.

        For the simple planner, this just returns the original plan.
        Override this method for more sophisticated replanning.

        Args:
            plan: Current plan
            last_result: Last execution result

        Returns:
            Updated plan
        """
        # Simple replanning: remove completed tasks and re-evaluate
        if last_result and last_result.get("status") == "failed":
            # Add a retry task if needed
            failed_task_id = last_result.get("task_id")
            if failed_task_id:
                task = plan.get_task(failed_task_id)
                if task and task.retry_count < task.max_retries:
                    task.retry()

        return plan

    def _match_pattern(self, goal: str, pattern: str) -> bool:
        """Check if goal matches pattern."""
        if pattern.endswith("*"):
            return goal.startswith(pattern[:-1])
        return goal == pattern


class CompositeTaskPlanner(TaskPlanner):
    """
    Composite planner that combines multiple planners.
    """

    def __init__(self):
        self._planners: List[TaskPlanner] = []

    def add_planner(self, planner: TaskPlanner) -> None:
        """Add a planner to the composite."""
        self._planners.append(planner)

    async def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """
        Plan using the first planner that can handle the goal.

        Args:
            goal: The goal to achieve
            context: Additional context

        Returns:
            TaskPlan from the first matching planner
        """
        for planner in self._planners:
            try:
                plan = await planner.plan(goal, context)
                if plan.tasks:
                    return plan
            except Exception:
                continue

        # Fallback to simple plan
        return TaskPlan(
            goal=goal,
            tasks=[
                Task(
                    name="execute",
                    description=f"Execute: {goal}",
                    input_data={"goal": goal, **(context or {})},
                )
            ],
            metadata=context or {},
        )

    async def replan(
        self, plan: TaskPlan, last_result: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """
        Replan using the first planner.

        Args:
            plan: Current plan
            last_result: Last execution result

        Returns:
            Updated plan
        """
        for planner in self._planners:
            try:
                return await planner.replan(plan, last_result)
            except Exception:
                continue

        return plan
