"""
Tests for workflow module.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data.workflow import WorkflowStep, FunctionStep, WorkflowState, WorkflowEngine


def run_async(coro):
    """Helper to run async functions."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_workflow_state():
    """Test workflow state."""
    state = WorkflowState(workflow_id="test")
    state.update("key1", "value1")
    assert state.get("key1") == "value1"
    assert state.get("key2", "default") == "default"


def test_function_step():
    """Test function step."""

    async def _test():
        async def my_step(state):
            return {"step_done": True}

        step = FunctionStep("test_step", my_step)
        result = await step.execute({})

        assert result.status.value == "completed"
        assert result.output["step_done"] == True

    run_async(_test())


def test_workflow_engine():
    """Test workflow engine."""

    async def _test():
        async def step1(state):
            return {"step1": True}

        async def step2(state):
            return {"step2": True}

        steps = [
            FunctionStep("step1", step1),
            FunctionStep("step2", step2),
        ]

        engine = WorkflowEngine()
        result = await engine.execute(steps)

        assert len(result["results"]) == 2
        assert result["results"][0]["status"] == "completed"
        assert result["results"][1]["status"] == "completed"

    run_async(_test())


def test_workflow_with_state():
    """Test workflow with shared state."""

    async def _test():
        async def step1(state):
            return {"data": "from_step1"}

        async def step2(state):
            # Should see data from step1
            return {"result": state.get("data")}

        steps = [
            FunctionStep("step1", step1),
            FunctionStep("step2", step2),
        ]

        engine = WorkflowEngine()
        result = await engine.execute(steps, {"initial": True})

        assert result["state"]["data"] == "from_step1"
        assert result["state"]["result"] == "from_step1"

    run_async(_test())
