"""
REST API connector.
"""

import json
import re
import ssl
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from agent_data.core.connector import BaseConnector
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)

# Endpoint must be a relative path; absolute URLs are rejected to prevent SSRF.
_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")

# Disallow these names as keys in params/headers to avoid leaking secrets in URLs.
_FORBIDDEN_AUTH_KEYS = {"api_key", "token", "authorization", "password", "secret"}

# Cap response body to prevent memory exhaustion (10 MB).
MAX_BODY_SIZE = 10 * 1024 * 1024

# aiohttp TCPConnector pool size; default 100 is too loose for shared clients.
_MAX_CONNECTIONS = 50


class RESTAPIConnector(BaseConnector):
    """REST API connector for calling external APIs."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._base_url = config.connection.rstrip("/")
        self._headers = config.metadata.get("headers", {})
        self._auth = config.metadata.get("auth", None)
        self._timeout = config.metadata.get("timeout", 30)
        self._metadata = config.metadata
        self._session = None

    async def connect(self) -> None:
        """Initialize HTTP session."""
        try:
            import aiohttp

            ssl_ctx = ssl.create_default_context()
            connector = aiohttp.TCPConnector(
                ssl=ssl_ctx,
                limit=_MAX_CONNECTIONS,
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
                headers=self._headers,
            )
            self._connected = True
        except ImportError:
            raise ImportError(
                "aiohttp is required for REST API connector. "
                "Install it with: pip install aiohttp"
            )

    def _validate_endpoint(self, endpoint: str) -> str:
        """Reject absolute URLs and other shapes that enable SSRF."""
        if not isinstance(endpoint, str) or not _ENDPOINT_RE.match(endpoint):
            raise ValueError(f"Invalid endpoint: {endpoint!r}. Must match {_ENDPOINT_RE.pattern}.")
        if endpoint.startswith("//") or "://" in endpoint:
            raise ValueError(f"Absolute URL not allowed in endpoint: {endpoint!r}")
        return endpoint

    def _build_url(self, endpoint: str) -> str:
        """Build the final URL and verify the host matches the configured base."""
        endpoint = self._validate_endpoint(endpoint)
        base = self._base_url if self._base_url.endswith("/") else self._base_url + "/"
        url = urljoin(base, endpoint)
        # urljoin with an absolute ref returns the ref verbatim — double-check host.
        final_host = urlparse(url).netloc
        base_host = urlparse(self._base_url).netloc
        if final_host != base_host:
            raise ValueError(
                f"Endpoint host mismatch: endpoint resolves to {final_host!r}, "
                f"but base is {base_host!r}."
            )
        return url

    def _build_auth_headers(self) -> Dict[str, str]:
        """Translate the configured auth dict into headers."""
        if not self._auth:
            return {}
        auth_type = (self._auth.get("type") or "").lower()
        if auth_type == "bearer":
            token = self._auth.get("token", "")
            return {"Authorization": f"Bearer {token}"} if token else {}
        if auth_type == "basic":
            username = self._auth.get("username", "")
            password = self._auth.get("password", "")
            import base64

            raw = f"{username}:{password}".encode("utf-8")
            return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}
        return {}

    def _scrub_auth_keys(self, mapping: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Drop keys that would put credentials into URLs."""
        if not mapping:
            return {}
        return {
            k: v
            for k, v in mapping.items()
            if not isinstance(k, str) or k.lower() not in _FORBIDDEN_AUTH_KEYS
        }

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
            # Build URL with SSRF guard.
            endpoint = query.metadata.get("endpoint", "")
            url = self._build_url(endpoint)

            # Get HTTP method
            method = query.metadata.get("method", "GET").upper()

            # Merge auth into headers and reject keys that would put creds in URL.
            auth_headers = self._build_auth_headers()
            merged_headers = {**self._headers, **auth_headers}
            merged_headers.update(self._scrub_auth_keys(query.metadata.get("headers", {})))

            # Get request body
            body = query.metadata.get("body", None)
            params = self._scrub_auth_keys(query.metadata.get("params", None))

            # Execute request — redirects disabled to keep SSRF surface minimal.
            request = getattr(self._session, method.lower(), None)
            if request is None:
                return QueryResult(
                    source=self.name,
                    error=f"Unsupported HTTP method: {method}",
                    query_time_ms=(time.time() - start_time) * 1000,
                )
            async with request(
                url,
                json=body,
                params=params,
                headers=merged_headers,
                allow_redirects=False,
            ) as response:
                return await self._handle_response(response, query, start_time)
        except ValueError as e:
            return QueryResult(
                source=self.name,
                error=str(e),
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
            # Cap response size to prevent memory exhaustion.
            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_SIZE:
                return QueryResult(
                    source=self.name,
                    error=f"Response too large: {content_length} bytes",
                    query_time_ms=(time.time() - start_time) * 1000,
                )

            # Get response body
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                data = await response.json(content_type=None)
            else:
                text = await response.text()
                if len(text) > MAX_BODY_SIZE:
                    return QueryResult(
                        source=self.name,
                        error=f"Response too large: {len(text)} bytes",
                        query_time_ms=(time.time() - start_time) * 1000,
                    )
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
            url = self._build_url(health_endpoint)
            async with self._session.get(url, allow_redirects=False) as response:
                return response.status == 200
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get API schema (from metadata). Never expose credentials or full base URL."""
        parsed = urlparse(self._base_url)
        return {
            "type": "rest_api",
            "host": parsed.hostname or "",
            "port": parsed.port,
            "endpoints": self._metadata.get("endpoints", []),
            "auth_type": (self._auth.get("type") if self._auth else None),
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
