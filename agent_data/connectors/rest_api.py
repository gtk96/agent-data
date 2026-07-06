"""
REST API connector.
"""

import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from agent_data.core.connector import BaseConnector
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)


class RESTAPIConnector(BaseConnector):
    """REST API connector for calling external APIs."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._base_url = config.connection.rstrip("/")
        self._headers = config.metadata.get("headers", {})
        self._auth = config.metadata.get("auth", None)
        self._timeout = config.metadata.get("timeout", 30)
        self._session = None

    async def connect(self) -> None:
        """Initialize HTTP session."""
        try:
            import aiohttp

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                headers=self._headers,
            )
            self._connected = True
        except ImportError:
            raise ImportError(
                "aiohttp is required for REST API connector. "
                "Install it with: pip install aiohttp"
            )

    async def disconnect(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a REST API query."""
        if not self._connected or not self._session:
            raise RuntimeError("Not connected to REST API")

        start_time = time.time()

        try:
            # Build URL
            endpoint = query.metadata.get("endpoint", "")
            url = urljoin(self._base_url + "/", endpoint.lstrip("/"))

            # Get HTTP method
            method = query.metadata.get("method", "GET").upper()

            # Get request body
            body = query.metadata.get("body", None)
            params = query.metadata.get("params", None)
            headers = query.metadata.get("headers", {})

            # Execute request
            if method == "GET":
                async with self._session.get(url, params=params, headers=headers) as response:
                    return await self._handle_response(response, query, start_time)
            elif method == "POST":
                async with self._session.post(
                    url, json=body, params=params, headers=headers
                ) as response:
                    return await self._handle_response(response, query, start_time)
            elif method == "PUT":
                async with self._session.put(
                    url, json=body, params=params, headers=headers
                ) as response:
                    return await self._handle_response(response, query, start_time)
            elif method == "PATCH":
                async with self._session.patch(
                    url, json=body, params=params, headers=headers
                ) as response:
                    return await self._handle_response(response, query, start_time)
            elif method == "DELETE":
                async with self._session.delete(url, params=params, headers=headers) as response:
                    return await self._handle_response(response, query, start_time)
            else:
                return QueryResult(
                    source=self.name,
                    error=f"Unsupported HTTP method: {method}",
                    query_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            return QueryResult(
                source=self.name,
                error=str(e),
                query_time_ms=(time.time() - start_time) * 1000,
            )

    async def _handle_response(self, response, query: Query, start_time: float) -> QueryResult:
        """Handle HTTP response."""
        try:
            # Get response body
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                data = await response.json()
            else:
                text = await response.text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = {"text": text}

            # Handle list or single object
            if isinstance(data, list):
                result_data = data
            elif isinstance(data, dict):
                # Check if there's a nested data key
                data_key = query.metadata.get("data_key", None)
                if data_key and data_key in data:
                    result_data = (
                        data[data_key] if isinstance(data[data_key], list) else [data[data_key]]
                    )
                else:
                    result_data = [data]
            else:
                result_data = [{"value": data}]

            # Apply client-side filtering if needed
            if query.filters:
                result_data = self._apply_filters(result_data, query.filters)

            # Apply limit
            if query.limit:
                result_data = result_data[: query.limit]

            return QueryResult(
                data=result_data,
                total_count=len(result_data),
                source=self.name,
                metadata={
                    "url": str(response.url),
                    "status": response.status,
                    "method": query.metadata.get("method", "GET"),
                },
            )
        except Exception as e:
            return QueryResult(
                source=self.name,
                error=f"Failed to parse response: {str(e)}",
                query_time_ms=(time.time() - start_time) * 1000,
            )

    def _apply_filters(self, data: List[Dict], filters: List[QueryFilter]) -> List[Dict]:
        """Apply client-side filters to data."""
        result = data

        for f in filters:
            filtered = []
            for item in result:
                value = item.get(f.field)
                if value is None:
                    continue

                if f.operator == "eq" and value == f.value:
                    filtered.append(item)
                elif f.operator == "ne" and value != f.value:
                    filtered.append(item)
                elif f.operator == "gt" and value > f.value:
                    filtered.append(item)
                elif f.operator == "lt" and value < f.value:
                    filtered.append(item)
                elif f.operator == "gte" and value >= f.value:
                    filtered.append(item)
                elif f.operator == "lte" and value <= f.value:
                    filtered.append(item)
                elif f.operator == "in" and value in f.value:
                    filtered.append(item)
                elif f.operator == "like" and f.value in str(value):
                    filtered.append(item)

            result = filtered

        return result

    async def health_check(self) -> bool:
        """Check API health by calling health endpoint."""
        try:
            health_endpoint = self._metadata.get("health_endpoint", "/health")
            url = urljoin(self._base_url + "/", health_endpoint.lstrip("/"))
            async with self._session.get(url) as response:
                return response.status == 200
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get API schema (from metadata)."""
        return {
            "type": "rest_api",
            "base_url": self._base_url,
            "endpoints": self._metadata.get("endpoints", []),
            "auth_type": self._auth.get("type") if self._auth else None,
        }

    async def get(self, endpoint: str, params: Optional[Dict] = None) -> QueryResult:
        """Convenience method for GET requests."""
        query = Query(
            source=self.name,
            query_type=QueryType.SELECT,
            metadata={
                "endpoint": endpoint,
                "method": "GET",
                "params": params,
            },
        )
        return await self.execute(query)

    async def post(self, endpoint: str, data: Optional[Dict] = None) -> QueryResult:
        """Convenience method for POST requests."""
        query = Query(
            source=self.name,
            query_type=QueryType.INSERT,
            metadata={
                "endpoint": endpoint,
                "method": "POST",
                "body": data,
            },
        )
        return await self.execute(query)

    async def put(self, endpoint: str, data: Optional[Dict] = None) -> QueryResult:
        """Convenience method for PUT requests."""
        query = Query(
            source=self.name,
            query_type=QueryType.UPDATE,
            metadata={
                "endpoint": endpoint,
                "method": "PUT",
                "body": data,
            },
        )
        return await self.execute(query)

    async def delete(self, endpoint: str) -> QueryResult:
        """Convenience method for DELETE requests."""
        query = Query(
            source=self.name,
            query_type=QueryType.DELETE,
            metadata={
                "endpoint": endpoint,
                "method": "DELETE",
            },
        )
        return await self.execute(query)
