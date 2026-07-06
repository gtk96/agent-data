"""
Tests for multi_agent module.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_data.multi_agent.agent import Agent, AgentRole, AgentMessage, WorkerAgent
from agent_data.multi_agent.orchestrator import AgentOrchestrator


def run_async(coro):
    """Helper to run async functions."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_worker_agent():
    """Test worker agent."""

    async def _test():
        async def execute_task(input_data):
            return {"processed": True, "input": input_data}

        worker = WorkerAgent("worker1", execute_task, capabilities=["data_process"])

        message = AgentMessage(
            sender="coordinator",
            receiver=worker.id,
            content={"query": "test"},
            message_type="task",
        )

        result = await worker.process(message)

        assert result is not None
        assert result.content["processed"] == True

    run_async(_test())


def test_agent_orchestrator():
    """Test agent orchestrator."""

    async def _test():
        async def execute_task(input_data):
            return {"result": "success"}

        worker = WorkerAgent("worker1", execute_task, capabilities=["query"])

        orchestrator = AgentOrchestrator()
        orchestrator.register(worker)

        result = await orchestrator.execute_task(
            {"query": "SELECT * FROM users"},
            "query",
            "coordinator",
        )

        assert result is not None
        assert result.content["result"] == "success"

    run_async(_test())


def test_orchestrator_find_agent():
    """Test orchestrator find agent."""

    async def _test():
        async def task1(input_data):
            return {"type": "data"}

        async def task2(input_data):
            return {"type": "analysis"}

        worker1 = WorkerAgent("worker1", task1, capabilities=["data_process"])
        worker2 = WorkerAgent("worker2", task2, capabilities=["analysis"])

        orchestrator = AgentOrchestrator()
        orchestrator.register(worker1)
        orchestrator.register(worker2)

        agent = orchestrator.find_agent_for_task("analysis")
        assert agent is not None
        assert agent.name == "worker2"

    run_async(_test())