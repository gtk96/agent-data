"""Agnes-2.0-flash LLM implementation."""

import asyncio
import logging
import time
from typing import List, Optional

import aiohttp

from agent_data.llm.base import BaseLLM, LLMResponse, LLMUsage, Message
from agent_data.llm.config import LLMConfig

logger = logging.getLogger(__name__)


class AgnesLLM(BaseLLM):
    """Agnes-2.0-flash LLM implementation with OpenAI-compatible API."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client: Optional[aiohttp.ClientSession] = None

    async def _get_client(self) -> aiohttp.ClientSession:
        """Get or create aiohttp client session."""
        if self._client is None or self._client.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._client = aiohttp.ClientSession(timeout=timeout)
        return self._client

    async def complete(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate completion using Agnes API (OpenAI-compatible format).

        Args:
            messages: List of chat messages.
            temperature: Override temperature from config.
            max_tokens: Override max_tokens from config.

        Returns:
            LLMResponse with generated content.

        Raises:
            RuntimeError: If API call fails after all retries.
        """
        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                start = time.monotonic()
                response = await self._call_api(payload)
                latency_ms = (time.monotonic() - start) * 1000

                return LLMResponse(
                    content=response["choices"][0]["message"]["content"],
                    model=response.get("model", self.config.model),
                    usage=LLMUsage(
                        prompt_tokens=response.get("usage", {}).get("prompt_tokens", 0),
                        completion_tokens=response.get("usage", {}).get("completion_tokens", 0),
                        total_tokens=response.get("usage", {}).get("total_tokens", 0),
                    ),
                    finish_reason=response["choices"][0].get("finish_reason", "stop"),
                    latency_ms=latency_ms,
                )
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2**attempt)
                    logger.warning(
                        f"Agnes API call failed (attempt {attempt + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Agnes API call failed after {self.config.max_retries + 1} attempts: {last_error}"
        )

    async def _call_api(self, payload: dict) -> dict:
        """Call Agnes API endpoint."""
        client = await self._get_client()
        url = f"{self.config.api_url.rstrip('/')}/chat/completions"
        headers = self._build_headers()

        async with client.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Agnes API error {resp.status}: {error_text}")
            return await resp.json()

    async def health_check(self) -> bool:
        """Check if Agnes API is available."""
        try:
            client = await self._get_client()
            url = f"{self.config.api_url.rstrip('/')}/models"
            headers = self._build_headers()

            async with client.get(url, headers=headers) as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Agnes health check failed: {e}")
            return False

    async def close(self):
        """Close the HTTP client session."""
        if self._client and not self._client.closed:
            await self._client.close()
