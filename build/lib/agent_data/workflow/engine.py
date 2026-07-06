"""
Workflow execution engine.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from agent_data.workflow.step import WorkflowStep, StepResult, StepStatus
from agent_data.workflow.state import WorkflowState


class WorkflowEngine:
    """Workflow execution engine."""

    def __init__(self, max_concurrent: int = 5):
        self._max_concurrent = max_concurrent

    async def execute(
        self,
        steps: List[WorkflowStep],
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow.

        Args:
            steps: List of workflow steps
            initial_state: Initial workflow state

        Returns:
            Final workflow state
        """
        state = WorkflowState(
            workflow_id="default",
            data=initial_state or {},
        )

        results: List[StepResult] = []

        for i, step in enumerate(steps):
            # Check if step should be skipped
            if step.should_skip(state.data):
                continue

            # Execute step
            result = await step.execute(state.data)
            results.append(result)

            # Update state
            state.add_history(step.name, {
                "status": result.status.value,
                "output": result.output,
                "error": result.error,
            })

            # Update data with step output
            if result.status == StepStatus.COMPLETED and result.output:
                if isinstance(result.output, dict):
                    state.data.update(result.output)
                else:
                    state.data[step.name] = result.output

            state.next_step()

            # Stop on failure
            if result.status == StepStatus.FAILED:
                break

        return {
            "state": state.data,
            "history": state.history,
            "results": [r.dict() for r in results],
        }

    async def execute_parallel(
        self,
        steps: List[WorkflowStep],
        state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute steps in parallel.

        Args:
            steps: List of workflow steps
            state: Initial state

        Returns:
            Execution results
        """
        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def execute_with_semaphore(step: WorkflowStep) -> StepResult:
            async with semaphore:
                return await step.execute(state or {})

        results = await asyncio.gather(
            *[execute_with_semaphore(step) for step in steps],
            return_exceptions=True,
        )

        return {
            "results": [
                r.dict() if isinstance(r, StepResult) else {"error": str(r)}
                for r in results
            ]
        }