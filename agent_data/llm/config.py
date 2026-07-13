"""LLM configuration models."""

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM connection configuration."""

    provider: str = Field(..., description="LLM provider name, e.g. 'agnes', 'openai'")
    api_url: str = Field(..., description="API base URL")
    api_key: str = Field(..., description="API key")
    model: str = Field(default="agnes-2.0-flash", description="Model name")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)
    timeout: int = Field(default=30, gt=0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, description="Max retry attempts")
    retry_delay: float = Field(default=1.0, ge=0, description="Initial retry delay in seconds")
