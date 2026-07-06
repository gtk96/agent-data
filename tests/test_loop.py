"""
Tests for loop module.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data.loop.agent_loop import SimpleAgentLoop, LoopRunner, AgentResult, LoopStatus


def run_async(coro):
    """Helper to run async functions."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_simple_agent_loop():
    """Test simple agent loop."""

    async def _test():
        iteration = 0

        async def step(state):
            nonlocal iteration
            iteration += 1
            state["count"] = iteration
            return state

        def is_complete(state):
            return state.get("count", 0) >= 3

        loop = SimpleAgentLoop(step, is_complete)
        runner = LoopRunner(max_iterations=10)
        result = await runner.run(loop, {"count": 0})

        assert result.status == LoopStatus.COMPLETED
        assert result.iterations == 3

    run_async(_test())


def test_loop_timeout():
    """Test loop timeout."""

    async def _test():
        async def slow_step(state):
            await asyncio.sleep(0.1)
            state["count"] = state.get("count", 0) + 1
            return state

        def never_complete(state):
            return False

        loop = SimpleAgentLoop(slow_step, never_complete)
        runner = LoopRunner(max_iterations=100, timeout_seconds=0.3)
        result = await runner.run(loop, {"count": 0})

        assert result.status == LoopStatus.TIMEOUT

    run_async(_test())


def test_loop_max_iterations():
    """Test loop max iterations."""

    async def _test():
        async def step(state):
            state["count"] = state.get("count", 0) + 1
            return state

        def never_complete(state):
            return False

        loop = SimpleAgentLoop(step, never_complete)
        runner = LoopRunner(max_iterations=5)
        result = await runner.run(loop, {"count": 0})

        assert result.status == LoopStatus.MAX_ITERATIONS
        assert result.iterations == 5

    run_async(_test())