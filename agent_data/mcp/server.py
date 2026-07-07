"""
MCP Server implementation.
"""

import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional, Set

from agent_data.core.errors import MCPAuthError, MCPMethodError, format_error
from agent_data.core.redact import redact
from agent_data.mcp.tool import DataQueryTool, MCPTool

# Max accepted request body size, in bytes. Larger payloads are rejected
# before parsing to prevent memory DoS.
_MAX_REQUEST_BYTES = 64 * 1024

# JSON-RPC 2.0 error codes used by this server.
_ERR_METHOD_NOT_FOUND = -32601
_ERR_INVALID_PARAMS = -32602
_ERR_INTERNAL = -32603
_ERR_AUTH_REQUIRED = -32001
_ERR_AUTH_FORBIDDEN = -32003


class MCPServer:
    """MCP Server for exposing tools to AI models.

    Optional authorization: pass ``tokens`` (set of allowed bearer tokens,
    typically loaded from the ``AGENT_DATA_MCP_TOKENS`` environment variable)
    and/or ``allowed_tools`` (subset of registered tool names). Requests
    without a matching ``Authorization: Bearer <token>`` header are rejected
    with ``-32001``. Tool calls to non-allowed tools get ``-32003``.

    When ``tokens`` is empty/None, the server accepts all requests — useful
    for local development.
    """

    def __init__(
        self,
        name: str = "agent-data-mcp",
        tokens: Optional[Set[str]] = None,
        allowed_tools: Optional[Set[str]] = None,
    ):
        """
        Initialize MCP server.

        Args:
            name: Server name
            tokens: Allowed bearer tokens. ``None`` disables auth.
            allowed_tools: Subset of tool names that may be called. ``None``
                means all registered tools are callable.
        """
        self.name = name
        self._tools: Dict[str, MCPTool] = {}
        self._handlers: Dict[str, Callable] = {}
        # When tokens is None, accept everything. When set, only listed tokens.
        self._tokens = tokens
        self._allowed_tools = allowed_tools

    @classmethod
    def from_env(cls, name: str = "agent-data-mcp") -> "MCPServer":
        """Build a server with tokens loaded from ``AGENT_DATA_MCP_TOKENS``.

        The env var is a comma-separated list. Empty / unset -> auth disabled.
        """
        raw = os.environ.get("AGENT_DATA_MCP_TOKENS", "").strip()
        tokens = {t.strip() for t in raw.split(",") if t.strip()} or None
        return cls(name=name, tokens=tokens)

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

    @staticmethod
    def _jsonrpc_error(code: int, message: str, data: Any = None) -> Dict[str, Any]:
        """Build a JSON-RPC 2.0 error envelope."""
        err: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"error": err}

    def _check_auth(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate the request's bearer token. Returns an error response or None."""
        if self._tokens is None:
            return None
        headers = request.get("_headers") or {}
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        token = ""
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token or token not in self._tokens:
            return self._jsonrpc_error(_ERR_AUTH_REQUIRED, "Missing or invalid bearer token")
        return None

    async def handle_request(
        self,
        request: Dict[str, Any],
        *,
        raw_body_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Handle an MCP request.

        Args:
            request: Parsed MCP request dict.
            raw_body_size: Optional size of the raw HTTP body in bytes; when
                larger than ``_MAX_REQUEST_BYTES`` the request is rejected
                without dispatching. Callers that proxy HTTP should pass this.

        Returns:
            MCP response (success or JSON-RPC 2.0 error envelope).
        """
        if raw_body_size is not None and raw_body_size > _MAX_REQUEST_BYTES:
            return self._jsonrpc_error(
                _ERR_INVALID_PARAMS,
                f"Request too large: {raw_body_size} > {_MAX_REQUEST_BYTES}",
            )

        # Auth — applied to all methods (initialize, list, call).
        auth_err = self._check_auth(request)
        if auth_err is not None:
            return auth_err

        method = request.get("method")
        params = request.get("params") or {}

        if not isinstance(method, str):
            return self._jsonrpc_error(_ERR_INVALID_PARAMS, "method must be a string")

        if method == "tools/list":
            return self._list_tools()

        elif method == "tools/call":
            return await self._call_tool(params)

        elif method == "initialize":
            return self._initialize(params)

        else:
            return self._jsonrpc_error(_ERR_METHOD_NOT_FOUND, f"Unknown method: {method}")

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
        arguments = params.get("arguments") or {}

        if not isinstance(tool_name, str):
            return self._jsonrpc_error(_ERR_INVALID_PARAMS, "params.name must be a string")

        if tool_name not in self._tools:
            return self._jsonrpc_error(_ERR_METHOD_NOT_FOUND, f"Tool not found: {tool_name}")

        if self._allowed_tools is not None and tool_name not in self._allowed_tools:
            return self._jsonrpc_error(_ERR_AUTH_FORBIDDEN, f"Tool not allowed: {tool_name}")

        handler = self._handlers[tool_name]

        try:
            result = await handler(arguments)
            return {"content": [{"type": "text", "text": json.dumps(result)}]}
        except Exception as e:
            return self._jsonrpc_error(_ERR_INTERNAL, redact(format_error(e)))
