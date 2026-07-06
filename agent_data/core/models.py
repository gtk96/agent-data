"""
Core data models for Agent Data framework.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class DataSourceType(str, Enum):
    """Data source types."""

    SQL = "sql"
    NOSQL = "nosql"
    VECTOR = "vector"
    API = "api"
    FILE = "file"
    GRAPH = "graph"
    STREAM = "stream"


class DataSourceConfig(BaseModel):
    """Data source configuration."""

    name: str = Field(..., description="Data source name")
    type: DataSourceType = Field(..., description="Data source type")
    connection: str = Field(..., description="Connection string or config")
    db_schema: Optional[str] = Field(None, description="Schema name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class DataSource(BaseModel):
    """Data source definition."""

    model_config = {"use_enum_values": True}

    config: DataSourceConfig
    description: Optional[str] = Field(None, description="Data source description")
    tags: List[str] = Field(default_factory=list, description="Tags")

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def type(self) -> DataSourceType:
        return self.config.type


class QueryType(str, Enum):
    """Query types."""

    SELECT = "select"
    SEARCH = "search"
    AGGREGATE = "aggregate"
    JOIN = "join"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


class QueryFilter(BaseModel):
    """Query filter condition."""

    field: str = Field(..., description="Field name")
    operator: str = Field(
        ...,
        description="Operator: eq, ne, gt, lt, gte, lte, in, like, contains",
    )
    value: Any = Field(..., description="Filter value")


class Query(BaseModel):
    """Data query definition."""

    source: str = Field(..., description="Data source name")
    query_type: QueryType = Field(QueryType.SELECT, description="Query type")
    filters: List[QueryFilter] = Field(default_factory=list, description="Filter conditions")
    fields: Optional[List[str]] = Field(None, description="Fields to select")
    limit: Optional[int] = Field(None, description="Result limit")
    offset: Optional[int] = Field(None, description="Result offset")
    order_by: Optional[str] = Field(None, description="Order by field")
    order_desc: bool = Field(False, description="Descending order")
    query: Optional[str] = Field(None, description="Raw query string (SQL, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Query metadata")


class QueryResult(BaseModel):
    """Query result."""

    data: List[Dict[str, Any]] = Field(default_factory=list, description="Result data")
    total_count: Optional[int] = Field(None, description="Total count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Result metadata")
    source: str = Field(..., description="Data source name")
    query_time_ms: float = Field(0.0, description="Query execution time in milliseconds")
    cached: bool = Field(False, description="Whether result is from cache")
    error: Optional[str] = Field(None, description="Error message if query failed")


class AgentContext(BaseModel):
    """Agent execution context."""

    agent_id: str = Field(..., description="Agent ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    task_id: Optional[str] = Field(None, description="Task ID")
    user_id: Optional[str] = Field(None, description="User ID")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Conversation history")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Context metadata")
    timestamp: datetime = Field(default_factory=datetime.now, description="Context timestamp")
