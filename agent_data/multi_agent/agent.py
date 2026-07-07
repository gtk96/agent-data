"""
Agent definition for multi-agent collaboration.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """Agent roles in multi-agent system."""

    WORKER = "worker"
    COORDINATOR = "coordinator"
    REVIEWER = "reviewer"
    SPECIALIST = "specialist"


class AgentMessage(BaseModel):
    """Message between agents.

    WARNING: ``content`` is typed ``Any`` for backward compatibility. Worker
    agents pass ``content`` straight into their executor — if the executor
    forwards content to an LLM as a prompt, this is a prompt injection surface.
    New code should define a Pydantic payload model (e.g. ``TaskPayload``) and
    validate before executing.
    """

    id: str = Field(default_factory=lambda: str(uuid4()), description="Message ID")
    sender: str = Field(..., description="Sender agent ID")
    receiver: str = Field(..., description="Receiver agent ID")
    content: Any = Field(..., description="Message content")
    message_type: str = Field("text", description="Message type")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")


class Agent(ABC):
    """Base class for agents in multi-agent system."""

    def __init__(
        self,
        name: str,
        role: AgentRole = AgentRole.WORKER,
        capabilities: Optional[List[str]] = None,
        allowed_senders: Optional[Set[str]] = None,
    ):
        """
        Initialize agent.

        Args:
            name: Agent name
            role: Agent role
            capabilities: List of agent capabilities
            allowed_senders: Optional set of sender IDs allowed to dispatch to
                this agent. ``None`` means "any sender"; ``{"coordinator"}``
                means only the coordinator may call. Enforced by
                ``AgentOrchestrator.send_message`` / ``broadcast``.
        """
        self.id = str(uuid4())
        self.name = name
        self.role = role
        self.capabilities = capabilities or []
        self.allowed_senders = allowed_senders
        self._inbox: List[AgentMessage] = []

    @abstractmethod
    async def process(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Process an incoming message.

        Args:
            message: Incoming message

        Returns:
            Response message or None
        """
        pass

    def receive(self, message: AgentMessage) -> None:
        """Add message to inbox."""
        self._inbox.append(message)

    def get_messages(self) -> List[AgentMessage]:
        """Get all messages in inbox."""
        return self._inbox.copy()

    def clear_messages(self) -> None:
        """Clear inbox."""
        self._inbox.clear()

    def can_handle(self, task_type: str) -> bool:
        """Check if agent can handle a task type."""
        return task_type in self.capabilities


class WorkerAgent(Agent):
    """Worker agent that executes tasks."""

    def __init__(
        self,
        name: str,
        executor,
        capabilities: Optional[List[str]] = None,
    ):
        super().__init__(name, AgentRole.WORKER, capabilities)
        self._executor = executor

    async def process(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process task message."""
        if message.message_type == "task":
            result = await self._executor(message.content)
            return AgentMessage(
                sender=self.id,
                receiver=message.sender,
                content=result,
                message_type="result",
            )
        return None
