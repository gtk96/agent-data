"""LLM integration module for agent-data."""

from agent_data.llm.base import BaseLLM, LLMResponse, Message
from agent_data.llm.config import LLMConfig

__all__ = [
    "BaseLLM",
    "LLMConfig",
    "LLMResponse",
    "Message",
]


def create_llm(config: LLMConfig) -> BaseLLM:
    """Factory function to create LLM instance based on config."""
    if config.provider == "agnes":
        from agent_data.llm.agnes import AgnesLLM

        return AgnesLLM(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")
