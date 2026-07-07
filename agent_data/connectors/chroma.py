"""
Chroma vector store connector.
"""

import time
from typing import Any, Dict, List, Optional

from agent_data.core.connector import BaseConnector
from agent_data.core.errors import format_error
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)
from agent_data.core.redact import redact


class ChromaConnector(BaseConnector):
    """Chroma vector store connector."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._client = None
        self._collection = None
        self._collection_name = config.metadata.get("collection", "default")
        self._persist_directory = config.metadata.get("persist_directory", None)

    async def connect(self) -> None:
        """Establish connection to Chroma."""
        try:
            import chromadb
            from chromadb.config import Settings

            if self._persist_directory:
                self._client = chromadb.PersistentClient(path=self._persist_directory)
            else:
                self._client = chromadb.Client()

            self._collection = self._client.get_or_create_collection(
                name=self._collection_name, metadata={"hnsw:space": "cosine"}
            )
            self._connected = True
        except ImportError:
            raise ImportError(
                "chromadb is required for Chroma connector. "
                "Install it with: pip install chromadb"
            )

    async def disconnect(self) -> None:
        """Close Chroma connection."""
        self._client = None
        self._collection = None
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a Chroma query."""
        if not self._connected or not self._collection:
            raise RuntimeError("Not connected to Chroma")

        start_time = time.time()

        try:
            if query.query_type == QueryType.SEARCH:
                return await self._similarity_search(query)
            elif query.query_type == QueryType.INSERT:
                return await self._add_documents(query)
            elif query.query_type == QueryType.DELETE:
                return await self._delete_documents(query)
            elif query.query_type == QueryType.SELECT:
                return await self._get_documents(query)
            else:
                return QueryResult(
                    source=self.name,
                    error=f"Unsupported query type: {query.query_type}",
                    query_time_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            return QueryResult(
                source=self.name,
                error=redact(format_error(e)),
                query_time_ms=(time.time() - start_time) * 1000,
            )

    async def _similarity_search(self, query: Query) -> QueryResult:
        """Perform similarity search."""
        import time

        start_time = time.time()
        query_text = query.query or ""
        query_embedding = query.metadata.get("embedding", None)
        n_results = query.limit or 10

        # Build where filter
        where_filter = self._build_where_filter(query.filters)

        if query_embedding:
            # Search by embedding
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        elif query_text:
            # Search by text
            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
        else:
            return QueryResult(
                source=self.name,
                error="No query text or embedding provided",
                query_time_ms=(time.time() - start_time) * 1000,
            )

        # Format results
        data = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                item = {
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1 - results["distances"][0][i] if results["distances"] else 0,
                }
                data.append(item)

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"collection": self._collection_name},
        )

    async def _add_documents(self, query: Query) -> QueryResult:
        """Add documents to Chroma."""
        documents = query.metadata.get("documents", [])
        ids = query.metadata.get("ids", None)
        metadatas = query.metadata.get("metadatas", None)
        embeddings = query.metadata.get("embeddings", None)

        if not documents:
            return QueryResult(
                source=self.name,
                error="No documents provided",
            )

        # Generate IDs if not provided
        if not ids:
            import uuid

            ids = [str(uuid.uuid4()) for _ in documents]

        # Add to collection
        self._collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        return QueryResult(
            data=[{"id": doc_id} for doc_id in ids],
            source=self.name,
            metadata={"added_count": len(ids)},
        )

    async def _delete_documents(self, query: Query) -> QueryResult:
        """Delete documents from Chroma."""
        ids = query.metadata.get("ids", [])
        where_filter = self._build_where_filter(query.filters)

        if ids:
            self._collection.delete(ids=ids)
            deleted_count = len(ids)
        elif where_filter:
            self._collection.delete(where=where_filter)
            deleted_count = -1  # Unknown count
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

    async def _get_documents(self, query: Query) -> QueryResult:
        """Get documents from Chroma."""
        ids = query.metadata.get("ids", None)
        where_filter = self._build_where_filter(query.filters)
        n_results = query.limit or 100

        if ids:
            results = self._collection.get(ids=ids, include=["documents", "metadatas"])
        else:
            results = self._collection.get(
                where=where_filter, limit=n_results, include=["documents", "metadatas"]
            )

        # Format results
        data = []
        if results and results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                item = {
                    "id": doc_id,
                    "text": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                }
                data.append(item)

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"collection": self._collection_name},
        )

    def _build_where_filter(self, filters: List[QueryFilter]) -> Optional[Dict]:
        """Build Chroma where filter from QueryFilter list."""
        if not filters:
            return None

        if len(filters) == 1:
            return self._build_single_filter(filters[0])

        # Multiple filters - use $and
        return {"$and": [self._build_single_filter(f) for f in filters]}

    def _build_single_filter(self, f: QueryFilter) -> Dict:
        """Build a single Chroma filter."""
        if f.operator == "eq":
            return {f.field: {"$eq": f.value}}
        elif f.operator == "ne":
            return {f.field: {"$ne": f.value}}
        elif f.operator == "gt":
            return {f.field: {"$gt": f.value}}
        elif f.operator == "lt":
            return {f.field: {"$lt": f.value}}
        elif f.operator == "gte":
            return {f.field: {"$gte": f.value}}
        elif f.operator == "lte":
            return {f.field: {"$lte": f.value}}
        elif f.operator == "in":
            return {f.field: {"$in": f.value}}
        elif f.operator == "nin":
            return {f.field: {"$nin": f.value}}
        else:
            raise ValueError(f"Unsupported operator: {f.operator}")

    async def health_check(self) -> bool:
        """Check Chroma health."""
        try:
            # Try to get collection info
            self._collection.count()
            return True
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get Chroma collection schema."""
        return {
            "type": "chroma",
            "collection": self._collection_name,
            "persist_directory": self._persist_directory,
            "document_count": self._collection.count() if self._collection else 0,
        }

    async def get_collection_info(self) -> Dict[str, Any]:
        """Get detailed collection information."""
        if not self._collection:
            return {}

        return {
            "name": self._collection_name,
            "count": self._collection.count(),
            "metadata": self._collection.metadata,
        }
