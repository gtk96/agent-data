"""
MCP Tool definitions.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPToolInput(BaseModel):
    """MCP tool input schema."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type")
    description: str = Field("", description="Parameter description")
    required: bool = Field(True, description="Is parameter required")
    default: Any = Field(None, description="Default value")


class MCPTool(BaseModel):
    """MCP tool definition."""

    name: str = Field(..., description="Tool name")
    description: str = Field("", description="Tool description")
    input_schema: List[MCPToolInput] = Field(default_factory=list, description="Input schema")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    inp.name: {
                        "type": inp.type,
                        "description": inp.description,
                    }
                    for inp in self.input_schema
                },
                "required": [inp.name for inp in self.input_schema if inp.required],
            },
        }


class DataQueryTool(MCPTool):
    """MCP tool for querying data sources."""

    source_name: str = Field(..., description="Data source name")

    def __init__(self, source_name: str, **kwargs):
        super().__init__(
            name=f"query_{source_name}",
            description=f"Query data from {source_name}",
            source_name=source_name,
            input_schema=[
                MCPToolInput(
                    name="query", type="string", description="SQL query or natural language"
                ),
                MCPToolInput(
                    name="limit",
                    type="integer",
                    description="Result limit",
                    required=False,
                    default=10,
                ),
            ],
            **kwargs,
        )
