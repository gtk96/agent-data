"""
Task models for Agent planning.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskResult(BaseModel):
    """Result of task execution."""

    task_id: str = Field(..., description="Task ID")
    status: TaskStatus = Field(..., description="Execution status")
    output: Any = Field(None, description="Task output")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    duration_ms: float = Field(0.0, description="Execution duration in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="Result timestamp")


class Task(BaseModel):
    """Task definition for Agent planning."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Task ID")
    name: str = Field(..., description="Task name")
    description: str = Field("", description="Task description")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Task status")
    priority: int = Field(0, description="Task priority (higher = more important)")

    # Dependencies
    dependencies: List[str] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )

    # Execution context
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data for the task")
    output_data: Dict[str, Any] = Field(
        default_factory=dict, description="Output data from the task"
    )

    # Execution control
    max_retries: int = Field(3, description="Maximum retry count")
    retry_count: int = Field(0, description="Current retry count")
    timeout_seconds: Optional[float] = Field(None, description="Execution timeout")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    @property
    def is_ready(self) -> bool:
        """Check if task is ready to execute (all dependencies completed)."""
        return self.status == TaskStatus.PENDING and len(self.dependencies) == 0

    @property
    def duration_ms(self) -> float:
        """Get task duration in milliseconds."""
        if self.started_at is None:
            return 0.0
        if self.completed_at is None:
            return (datetime.now() - self.started_at).total_seconds() * 1000
        return (self.completed_at - self.started_at).total_seconds() * 1000

    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now()

    def complete(self, output: Any = None, metadata: Optional[Dict[str, Any]] = None) -> TaskResult:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.output_data = output if output is not None else {}

        return TaskResult(
            task_id=self.id,
            status=TaskStatus.COMPLETED,
            output=output,
            metadata=metadata or {},
            duration_ms=self.duration_ms,
        )

    def fail(self, error: str, metadata: Optional[Dict[str, Any]] = None) -> TaskResult:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()

        return TaskResult(
            task_id=self.id,
            status=TaskStatus.FAILED,
            error=error,
            metadata=metadata or {},
            duration_ms=self.duration_ms,
        )

    def retry(self) -> bool:
        """Retry the task if possible."""
        if self.retry_count >= self.max_retries:
            return False

        self.retry_count += 1
        self.status = TaskStatus.PENDING
        self.started_at = None
        self.completed_at = None
        return True

    def cancel(self) -> None:
        """Cancel the task."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()

    def block(self, reason: str = "") -> None:
        """Block the task."""
        self.status = TaskStatus.BLOCKED
        if reason:
            self.metadata["block_reason"] = reason

    def unblock(self) -> None:
        """Unblock the task."""
        if self.status == TaskStatus.BLOCKED:
            self.status = TaskStatus.PENDING


class TaskPlan(BaseModel):
    """Execution plan for a set of tasks."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Plan ID")
    goal: str = Field(..., description="Plan goal")
    tasks: List[Task] = Field(default_factory=list, description="Tasks in the plan")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Plan metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")

    @property
    def completed_tasks(self) -> List[Task]:
        """Get completed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]

    @property
    def failed_tasks(self) -> List[Task]:
        """Get failed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]

    @property
    def pending_tasks(self) -> List[Task]:
        """Get pending tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    @property
    def in_progress_tasks(self) -> List[Task]:
        """Get in-progress tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.IN_PROGRESS]

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        return len(self.pending_tasks) == 0 and len(self.in_progress_tasks) == 0

    @property
    def progress(self) -> float:
        """Get plan progress (0.0 to 1.0)."""
        if len(self.tasks) == 0:
            return 1.0
        return len(self.completed_tasks) / len(self.tasks)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def add_task(self, task: Task) -> None:
        """Add a task to the plan."""
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the plan."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                return True
        return False

    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to execute."""
        ready = []
        for task in self.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_met = all(
                dep.status == TaskStatus.COMPLETED
                for dep in self.tasks
                if dep.id in task.dependencies
            )
            if deps_met:
                ready.append(task)

        return ready
