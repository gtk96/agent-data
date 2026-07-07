"""
Agent orchestrator for multi-agent collaboration.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from agent_data.multi_agent.agent import Agent, AgentMessage, AgentRole


class AgentOrchestrator:
    """Orchestrates multiple agents.

    Sender authorization: when an agent has ``allowed_senders`` set, the
    orchestrator rejects messages from senders not in that set. This prevents
    arbitrary agents from triggering expensive operations on workers that
    were only meant to receive coordinator-issued tasks.
    """

    def __init__(self):
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent."""
        self._agents[agent.id] = agent

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent."""
        self._agents.pop(agent_id, None)

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def find_agent_for_task(self, task_type: str) -> Optional[Agent]:
        """Find an agent that can handle a task type."""
        for agent in self._agents.values():
            if agent.can_handle(task_type):
                return agent
        return None

    @staticmethod
    def _is_authorized(agent: Agent, sender_id: str) -> bool:
        """Check if sender_id is allowed to dispatch to this agent."""
        allowed = agent.allowed_senders
        if allowed is None:
            return True
        return sender_id in allowed

    async def send_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Send message to an agent and get response."""
        agent = self._agents.get(message.receiver)
        if agent is None:
            return None

        if not self._is_authorized(agent, message.sender):
            return None

        agent.receive(message)
        return await agent.process(message)

    async def broadcast(
        self, sender_id: str, content: Any, message_type: str = "broadcast"
    ) -> List[AgentMessage]:
        """Broadcast message to all agents except sender.

        Sender authorization: agents whose ``allowed_senders`` set excludes
        ``sender_id`` are silently skipped (not delivered to).
        """
        responses = []
        for agent_id, agent in self._agents.items():
            if agent_id == sender_id:
                continue
            if not self._is_authorized(agent, sender_id):
                continue
            message = AgentMessage(
                sender=sender_id,
                receiver=agent_id,
                content=content,
                message_type=message_type,
            )
            response = await agent.process(message)
            if response:
                responses.append(response)
        return responses

    async def execute_task(
        self,
        task: Dict[str, Any],
        task_type: str,
        sender_id: str,
    ) -> Optional[AgentMessage]:
        """Execute a task using the appropriate agent."""
        agent = self.find_agent_for_task(task_type)
        if agent is None:
            return None

        message = AgentMessage(
            sender=sender_id,
            receiver=agent.id,
            content=task,
            message_type="task",
        )
        return await self.send_message(message)

    async def execute_workflow(
        self,
        steps: List[Dict[str, Any]],
        sender_id: str,
    ) -> List[Dict[str, Any]]:
        """Execute a workflow with multiple agents."""
        results = []

        for step in steps:
            task_type = step.get("type")
            task = step.get("task")

            result = await self.execute_task(task, task_type, sender_id)
            results.append(
                {
                    "step": step,
                    "result": result.content if result else None,
                    "success": result is not None,
                }
            )

        return results
