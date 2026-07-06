"""
Base connector interface for data sources.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from agent_data.core.models import (
    DataSource,
    DataSourceConfig,
    DataSourceType,
    Query,
    QueryResult,
)


class BaseConnector(ABC):
    """Base class for all data source connectors."""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self._connected = False

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def type(self) -> DataSourceType:
        return self.config.type

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the data source."""
        pass

    @abstractmethod
    async def execute(self, query: Query) -> QueryResult:
        """Execute a query against the data source."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the data source is healthy."""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get the schema of the data source."""
        pass

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False


# Connector registry
_connector_registry: Dict[str, Type[BaseConnector]] = {}


def register_connector(name: str, connector_class: Type[BaseConnector]) -> None:
    """Register a connector class."""
    _connector_registry[name] = connector_class


def get_connector(name: str) -> Optional[Type[BaseConnector]]:
    """Get a registered connector class by name."""
    return _connector_registry.get(name)


def list_connectors() -> List[str]:
    """List all registered connector names."""
    return list(_connector_registry.keys())
