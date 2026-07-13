"""Tests for LLM module."""

import pytest
from agent_data.llm.config import LLMConfig
from agent_data.llm.base import Message, LLMResponse, LLMUsage


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_config_creation(self):
        """Test LLMConfig creation with required fields."""
        config = LLMConfig(
            provider="agnes",
            api_url="https://api.example.com/v1",
            api_key="test-key",
        )
        assert config.provider == "agnes"
        assert config.api_url == "https://api.example.com/v1"
        assert config.api_key == "test-key"
        assert config.model == "agnes-2.0-flash"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096

    def test_config_defaults(self):
        """Test LLMConfig default values."""
        config = LLMConfig(
            provider="openai",
            api_url="https://api.openai.com/v1",
            api_key="sk-test",
        )
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_delay == 1.0


class TestMessage:
    """Tests for Message model."""

    def test_message_creation(self):
        """Test Message creation."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_response_creation(self):
        """Test LLMResponse creation."""
        response = LLMResponse(
            content="Test response",
            model="test-model",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert response.content == "Test response"
        assert response.model == "test-model"
        assert response.usage.total_tokens == 15
        assert response.finish_reason == "stop"
