"""Pydantic models for web API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Chat completion request (OpenAI-compatible format)."""

    model: str = Field(default="agnes-2.0-flash", description="Model name")
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    temperature: Optional[float] = Field(default=None, description="Temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens")
    stream: bool = Field(default=False, description="Stream response")
    session_id: Optional[str] = Field(default=None, description="Session ID for memory")


class QueryResponse(BaseModel):
    """Chat completion response (OpenAI-compatible format)."""

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int] = Field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )


class NL2SQLQueryRequest(BaseModel):
    """NL2SQL specific query request."""

    question: str = Field(
        ..., min_length=1, max_length=2000, description="Natural language question"
    )
    session_id: Optional[str] = Field(default=None, description="Session ID")
    data_source: Optional[str] = Field(default=None, description="Data source name")
    show_sql: bool = Field(default=False, description="Show generated SQL")


class NL2SQLQueryResponse(BaseModel):
    """NL2SQL specific query response."""

    session_id: str
    question: str
    sql: Optional[str] = None
    explanation: Optional[str] = None
    answer: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    row_count: int = 0
    confidence: float = 0.0
    query_time_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SchemaResponse(BaseModel):
    """Schema information response."""

    tables: List[Dict[str, Any]]


class HistoryResponse(BaseModel):
    """Conversation history response."""

    session_id: str
    turns: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    llm: bool
    database: bool
    version: str


class DataSourceInfo(BaseModel):
    """Data source information."""

    name: str
    type: str
    description: str = ""
    status: str = "active"


class SqlExecuteRequest(BaseModel):
    """SQL execution request."""

    sql: str = Field(..., min_length=1, description="SQL query to execute")
    max_rows: Optional[int] = Field(default=100, description="Maximum rows to return")
    timeout: Optional[int] = Field(default=30, description="Query timeout in seconds")


class SqlExecuteResponse(BaseModel):
    """SQL execution response."""

    success: bool
    sql: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    row_count: int = 0
    query_time_ms: float = 0.0
    error: Optional[str] = None


class QueryHistoryRequest(BaseModel):
    """Query history save request."""

    question: str = Field(..., description="Original question")
    sql: str = Field(..., description="Generated SQL")
    answer: str = Field(default="", description="Query answer")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="Query result data")
    columns: List[str] = Field(default_factory=list, description="Result columns")
    row_count: int = Field(default=0, description="Number of rows returned")
    query_time_ms: float = Field(default=0.0, description="Query execution time")
    session_id: Optional[str] = Field(default="default", description="Session ID")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")


class QueryHistoryItemResponse(BaseModel):
    """Query history item response."""

    id: str
    question: str
    sql: str
    answer: str
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    row_count: int = 0
    query_time_ms: float = 0.0
    timestamp: float = 0.0
    session_id: str = "default"
    favorite: bool = False
    tags: List[str] = Field(default_factory=list)


class QueryHistoryResponse(BaseModel):
    """Query history list response."""

    session_id: str
    items: List[QueryHistoryItemResponse]
    total: int


class QueryHistoryStatsResponse(BaseModel):
    """Query history statistics response."""

    session_id: str
    total_queries: int
    favorite_count: int
    avg_query_time_ms: float
