"""Base LLM abstract class and models."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Chat message."""

    role: str  # "system" | "user" | "assistant"
    content: str


class LLMUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """LLM response."""

    content: str
    model: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    finish_reason: str = "stop"
    latency_ms: float = 0.0


class BaseLLM(ABC):
    """Abstract base class for LLM implementations."""

    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate completion for given messages.

        Args:
            messages: List of chat messages.
            temperature: Override temperature from config.
            max_tokens: Override max_tokens from config.

        Returns:
            LLMResponse with generated content.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if LLM service is available."""
        ...

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP request headers. Subclasses can override."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
