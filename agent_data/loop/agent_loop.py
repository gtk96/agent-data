"""
Agent Loop implementation for continuous execution.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LoopStatus(str, Enum):
    """Agent loop status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MAX_ITERATIONS = "max_iterations"


class AgentResult(BaseModel):
    """Result of agent loop execution."""

    loop_id: str = Field(..., description="Loop ID")
    status: LoopStatus = Field(..., description="Execution status")
    output: Any = Field(None, description="Final output")
    iterations: int = Field(0, description="Number of iterations")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Execution history")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    duration_ms: float = Field(0.0, description="Total execution duration")


class AgentLoop(ABC):
    """Base class for agent loops."""

    @abstractmethod
    async def step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute one iteration of the loop.

        Args:
            state: Current state

        Returns:
            Updated state
        """
        pass

    @abstractmethod
    def is_complete(self, state: Dict[str, Any]) -> bool:
        """
        Check if the loop should terminate.

        Args:
            state: Current state

        Returns:
            True if loop should stop
        """
        pass


class SimpleAgentLoop(AgentLoop):
    """
    Simple agent loop with step function and completion check.
    """

    def __init__(
        self,
        step_func: Callable[[Dict[str, Any]], Dict[str, Any]],
        complete_check: Callable[[Dict[str, Any]], bool],
    ):
        """
        Initialize simple agent loop.

        Args:
            step_func: Function to execute each iteration
            complete_check: Function to check if loop should stop
        """
        self._step_func = step_func
        self._complete_check = complete_check

    async def step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one step."""
        return await self._step_func(state)

    def is_complete(self, state: Dict[str, Any]) -> bool:
        """Check if complete."""
        return self._complete_check(state)


class LoopRunner:
    """
    Runner for agent loops.
    """

    def __init__(
        self,
        max_iterations: int = 100,
        timeout_seconds: Optional[float] = None,
    ):
        """
        Initialize loop runner.

        Args:
            max_iterations: Maximum number of iterations
            timeout_seconds: Timeout in seconds
        """
        self._max_iterations = max_iterations
        self._timeout_seconds = timeout_seconds

    async def run(
        self,
        loop: AgentLoop,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Run an agent loop.

        Args:
            loop: Agent loop to run
            initial_state: Initial state

        Returns:
            AgentResult with execution results
        """
        loop_id = str(uuid4())
        state = initial_state or {}
        history: List[Dict[str, Any]] = []
        start_time = time.time()

        for i in range(self._max_iterations):
            # Check timeout
            if self._timeout_seconds:
                elapsed = time.time() - start_time
                if elapsed >= self._timeout_seconds:
                    return AgentResult(
                        loop_id=loop_id,
                        status=LoopStatus.TIMEOUT,
                        iterations=i,
                        history=history,
                        error=f"Timed out after {self._timeout_seconds}s",
                        duration_ms=(time.time() - start_time) * 1000,
                    )

            # Execute step
            try:
                step_start = time.time()
                state = await loop.step(state)
                step_duration = (time.time() - step_start) * 1000

                history.append(
                    {
                        "iteration": i,
                        "duration_ms": step_duration,
                        "state_keys": list(state.keys()),
                    }
                )

                # Check completion
                if loop.is_complete(state):
                    return AgentResult(
                        loop_id=loop_id,
                        status=LoopStatus.COMPLETED,
                        output=state.get("output"),
                        iterations=i + 1,
                        history=history,
                        duration_ms=(time.time() - start_time) * 1000,
                    )

            except Exception as e:
                return AgentResult(
                    loop_id=loop_id,
                    status=LoopStatus.FAILED,
                    iterations=i,
                    history=history,
                    error=str(e),
                    duration_ms=(time.time() - start_time) * 1000,
                )

        return AgentResult(
            loop_id=loop_id,
            status=LoopStatus.MAX_ITERATIONS,
            output=state.get("output"),
            iterations=self._max_iterations,
            history=history,
            error=f"Max iterations ({self._max_iterations}) exceeded",
            duration_ms=(time.time() - start_time) * 1000,
        )
