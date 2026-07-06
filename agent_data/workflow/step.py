"""
Workflow step definitions.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Step execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    """Result of step execution."""

    step_id: str = Field(..., description="Step ID")
    status: StepStatus = Field(..., description="Execution status")
    output: Any = Field(None, description="Step output")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")


class WorkflowStep(ABC):
    """Base class for workflow steps."""

    def __init__(self, name: str, description: str = ""):
        self.id = str(uuid4())
        self.name = name
        self.description = description
        self.status = StepStatus.PENDING

    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> StepResult:
        """
        Execute the step.

        Args:
            state: Current workflow state

        Returns:
            StepResult with execution results
        """
        pass

    def should_skip(self, state: Dict[str, Any]) -> bool:
        """
        Determine if this step should be skipped.

        Args:
            state: Current workflow state

        Returns:
            True if step should be skipped
        """
        return False


class FunctionStep(WorkflowStep):
    """
    Step that executes a function.
    """

    def __init__(
        self,
        name: str,
        func: Callable,
        description: str = "",
        timeout: Optional[float] = None,
    ):
        """
        Initialize function step.

        Args:
            name: Step name
            func: Async function to execute
            description: Step description
            timeout: Execution timeout in seconds
        """
        super().__init__(name, description)
        self.func = func
        self.timeout = timeout

    async def execute(self, state: Dict[str, Any]) -> StepResult:
        """
        Execute the function.

        Args:
            state: Current workflow state

        Returns:
            StepResult
        """
        self.status = StepStatus.IN_PROGRESS

        try:
            import asyncio

            if self.timeout:
                result = await asyncio.wait_for(
                    self.func(state),
                    timeout=self.timeout,
                )
            else:
                result = await self.func(state)

            self.status = StepStatus.COMPLETED
            return StepResult(
                step_id=self.id,
                status=StepStatus.COMPLETED,
                output=result,
            )

        except asyncio.TimeoutError:
            self.status = StepStatus.FAILED
            return StepResult(
                step_id=self.id,
                status=StepStatus.FAILED,
                error=f"Step timed out after {self.timeout}s",
            )

        except Exception as e:
            self.status = StepStatus.FAILED
            return StepResult(
                step_id=self.id,
                status=StepStatus.FAILED,
                error=str(e),
            )


class ConditionalStep(WorkflowStep):
    """
    Step that executes conditionally based on state.
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        true_step: WorkflowStep,
        false_step: Optional[WorkflowStep] = None,
        description: str = "",
    ):
        """
        Initialize conditional step.

        Args:
            name: Step name
            condition: Function that returns True/False based on state
            true_step: Step to execute if condition is True
            false_step: Step to execute if condition is False (optional)
            description: Step description
        """
        super().__init__(name, description)
        self.condition = condition
        self.true_step = true_step
        self.false_step = false_step

    async def execute(self, state: Dict[str, Any]) -> StepResult:
        """
        Execute the appropriate step based on condition.

        Args:
            state: Current workflow state

        Returns:
            StepResult from the executed step
        """
        self.status = StepStatus.IN_PROGRESS

        try:
            if self.condition(state):
                return await self.true_step.execute(state)
            elif self.false_step:
                return await self.false_step.execute(state)
            else:
                self.status = StepStatus.SKIPPED
                return StepResult(
                    step_id=self.id,
                    status=StepStatus.SKIPPED,
                    output="Condition not met, no false step",
                )
        except Exception as e:
            self.status = StepStatus.FAILED
            return StepResult(
                step_id=self.id,
                status=StepStatus.FAILED,
                error=str(e),
            )
