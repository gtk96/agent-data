"""
Base cache interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseCache(ABC):
    """Base class for all cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value with optional TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value by key."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached values."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get number of cached items."""
        pass
