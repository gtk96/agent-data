"""Multi-agent collaboration module."""

from agent_data.multi_agent.agent import Agent, AgentMessage, AgentRole, WorkerAgent
from agent_data.multi_agent.orchestrator import AgentOrchestrator

__all__ = ["Agent", "AgentMessage", "AgentRole", "WorkerAgent", "AgentOrchestrator"]
