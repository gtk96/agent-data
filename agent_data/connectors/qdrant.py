"""
Qdrant vector store connector.
"""

import time
from typing import Any, Dict, List, Optional

from agent_data.core.connector import BaseConnector
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)


class QdrantConnector(BaseConnector):
    """Qdrant vector store connector."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._client = None
        self._collection_name = config.metadata.get("collection", "default")
        self._url = config.connection

    async def connect(self) -> None:
        """Establish connection to Qdrant."""
        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self._url)
            self._connected = True
        except ImportError:
            raise ImportError(
                "qdrant-client is required for Qdrant connector. "
                "Install it with: pip install qdrant-client"
            )

    async def disconnect(self) -> None:
        """Close Qdrant connection."""
        self._client = None
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a Qdrant query."""
        if not self._connected or not self._client:
            raise RuntimeError("Not connected to Qdrant")

        start_time = time.time()

        try:
            if query.query_type == QueryType.SEARCH:
                return await self._similarity_search(query)
            elif query.query_type == QueryType.INSERT:
                return await self._upsert(query)
            elif query.query_type == QueryType.DELETE:
                return await self._delete(query)
            elif query.query_type == QueryType.SELECT:
                return await self._scroll(query)
            else:
                return QueryResult(
                    source=self.name,
                    error=f"Unsupported query type: {query.query_type}",
                    query_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            return QueryResult(
                source=self.name,
                error=str(e),
                query_time_ms=(time.time() - start_time) * 1000,
            )

    async def _similarity_search(self, query: Query) -> QueryResult:
        """Perform similarity search."""
        import time
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        start_time = time.time()
        query_vector = query.metadata.get("vector", None)
        query_text = query.query or ""
        n_results = query.limit or 10

        # Build filter
        qdrant_filter = self._build_filter(query.filters)

        if query_vector:
            results = self._client.search(
                collection_name=self._collection_name,
                query_vector=query_vector,
                limit=n_results,
                query_filter=qdrant_filter,
            )
        elif query_text:
            # For text search, we need to embed first
            # This is a placeholder - in production, use an embedding model
            return QueryResult(
                source=self.name,
                error="Text search requires embedding model integration",
                query_time_ms=(time.time() - start_time) * 1000,
            )
        else:
            return QueryResult(
                source=self.name,
                error="No query vector or text provided",
                query_time_ms=(time.time() - start_time) * 1000,
            )

        # Format results
        data = []
        for hit in results:
            item = {
                "id": hit.id,
                "score": hit.score,
                "payload": hit.payload or {},
            }
            data.append(item)

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"collection": self._collection_name},
        )

    async def _upsert(self, query: Query) -> QueryResult:
        """Upsert vectors."""
        from qdrant_client.models import PointStruct

        points_data = query.metadata.get("points", [])

        if not points_data:
            # Single point upsert
            point_id = query.metadata.get("id")
            vector = query.metadata.get("vector")
            payload = query.metadata.get("payload", {})

            if point_id and vector:
                points_data = [{"id": point_id, "vector": vector, "payload": payload}]

        if not points_data:
            return QueryResult(
                source=self.name,
                error="No points provided for upsert",
            )

        points = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points_data
        ]

        self._client.upsert(
            collection_name=self._collection_name,
            points=points,
        )

        return QueryResult(
            data=[{"id": p["id"]} for p in points_data],
            source=self.name,
            metadata={"upserted_count": len(points_data)},
        )

    async def _delete(self, query: Query) -> QueryResult:
        """Delete points."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        ids = query.metadata.get("ids", [])

        if ids:
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=ids,
            )
            deleted_count = len(ids)
        else:
            qdrant_filter = self._build_filter(query.filters)
            if qdrant_filter:
                self._client.delete(
                    collection_name=self._collection_name,
                    points_selector=qdrant_filter,
                )
                deleted_count = -1
            else:
                return QueryResult(
                    source=self.name,
                    error="No IDs or filters provided for deletion",
                )

        return QueryResult(
            data=[{"deleted_count": deleted_count}],
            source=self.name,
            metadata={"deleted_count": deleted_count},
        )

    async def _scroll(self, query: Query) -> QueryResult:
        """Scroll through points."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant_filter = self._build_filter(query.filters)
        limit = query.limit or 100

        result = self._client.scroll(
            collection_name=self._collection_name,
            scroll_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )

        points = result[0]
        data = []
        for point in points:
            item = {
                "id": point.id,
                "payload": point.payload or {},
            }
            data.append(item)

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"collection": self._collection_name},
        )

    def _build_filter(self, filters: List[QueryFilter]) -> Optional[Any]:
        """Build Qdrant filter from QueryFilter list."""
        if not filters:
            return None

        from qdrant_client.models import (
            Filter,
            FieldCondition,
            MatchValue,
            MatchAny,
            Range,
        )

        conditions = []
        for f in filters:
            if f.operator == "eq":
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        match=MatchValue(value=f.value),
                    )
                )
            elif f.operator == "ne":
                # Qdrant doesn't have direct neq, use must_not
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        match=MatchValue(value=f.value),
                    )
                )
            elif f.operator == "gt":
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        range=Range(gt=f.value),
                    )
                )
            elif f.operator == "gte":
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        range=Range(gte=f.value),
                    )
                )
            elif f.operator == "lt":
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        range=Range(lt=f.value),
                    )
                )
            elif f.operator == "lte":
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        range=Range(lte=f.value),
                    )
                )
            elif f.operator == "in":
                conditions.append(
                    FieldCondition(
                        key=f.field,
                        match=MatchAny(any=f.value),
                    )
                )

        if not conditions:
            return None

        return Filter(must=conditions)

    async def health_check(self) -> bool:
        """Check Qdrant health."""
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get Qdrant schema."""
        return {
            "type": "qdrant",
            "url": self._url,
            "collection": self._collection_name,
        }
