"""
MCP Server implementation.
"""

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional

from agent_data.mcp.tool import MCPTool, DataQueryTool


class MCPServer:
    """MCP Server for exposing tools to AI models."""

    def __init__(self, name: str = "agent-data-mcp"):
        """
        Initialize MCP server.

        Args:
            name: Server name
        """
        self.name = name
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_tool(self, tool: MCPTool, handler: Callable) -> None:
        """
        Register a tool with its handler.

        Args:
            tool: Tool definition
            handler: Async function to handle tool calls
        """
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def register_data_tools(self, client) -> None:
        """
        Register data query tools from an AgentDataClient.

        Args:
            client: AgentDataClient instance
        """
        from agent_data import AgentDataClient, Query, QueryType

        for source_name in client.data_sources:

            async def query_handler(input_data: Dict[str, Any], _src: str = source_name) -> Any:
                query_text = input_data.get("query", "")
                limit = input_data.get("limit", 10)

                result = await client.query(
                    Query(
                        source=_src,
                        query_type=QueryType.SEARCH,
                        query=query_text,
                        limit=limit,
                    )
                )

                return {
                    "data": result.data,
                    "total_count": result.total_count,
                    "error": result.error,
                }

            tool = DataQueryTool(source_name)
            self.register_tool(tool, query_handler)

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an MCP request.

        Args:
            request: MCP request

        Returns:
            MCP response
        """
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return self._list_tools()

        elif method == "tools/call":
            return await self._call_tool(params)

        elif method == "initialize":
            return self._initialize(params)

        else:
            return {"error": f"Unknown method: {method}"}

    def _initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": self.name,
                "version": "0.1.0",
            },
        }

    def _list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        tools = [tool.to_dict() for tool in self._tools.values()]
        return {"tools": tools}

    async def _call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self._tools:
            return {"error": f"Tool not found: {tool_name}"}

        handler = self._handlers[tool_name]

        try:
            result = await handler(arguments)
            return {"content": [{"type": "text", "text": json.dumps(result)}]}
        except Exception as e:
            return {"error": str(e)}
