"""
File system connector.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_data.core.connector import BaseConnector
from agent_data.core.models import (
    DataSourceConfig,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)


class FileConnector(BaseConnector):
    """File system connector for reading files as data sources."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._base_path = Path(config.connection)
        self._file_types = config.metadata.get("file_types", [])
        self._recursive = config.metadata.get("recursive", True)

    async def connect(self) -> None:
        """Validate base path exists."""
        if not self._base_path.exists():
            raise FileNotFoundError(f"Path not found: {self._base_path}")
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect (no-op for file system)."""
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a file query."""
        start_time = time.time()

        try:
            if query.query_type == QueryType.SELECT:
                return await self._list_files(query)
            elif query.query_type == QueryType.SEARCH:
                return await self._search_files(query)
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

    async def _list_files(self, query: Query) -> QueryResult:
        """List files in the directory."""
        files = []

        if self._recursive:
            for item in self._base_path.rglob("*"):
                if item.is_file():
                    if self._matches_file_type(item):
                        files.append(self._get_file_info(item))
        else:
            for item in self._base_path.glob("*"):
                if item.is_file():
                    if self._matches_file_type(item):
                        files.append(self._get_file_info(item))

        # Apply filters
        if query.filters:
            files = [f for f in files if self._matches_filters(f, query.filters)]

        # Apply limit
        if query.limit:
            files = files[:query.limit]

        return QueryResult(
            data=files,
            total_count=len(files),
            source=self.name,
            metadata={"base_path": str(self._base_path)},
        )

    async def _search_files(self, query: Query) -> QueryResult:
        """Search for files by name or content."""
        search_text = query.query or ""
        results = []

        if self._recursive:
            for item in self._base_path.rglob("*"):
                if item.is_file():
                    if self._matches_file_type(item):
                        file_info = self._get_file_info(item)
                        # Search in filename
                        if search_text.lower() in item.name.lower():
                            results.append(file_info)
                        # Search in file content (for text files)
                        elif self._is_text_file(item):
                            try:
                                content = item.read_text(encoding="utf-8")
                                if search_text.lower() in content.lower():
                                    file_info["content_preview"] = content[:500]
                                    results.append(file_info)
                            except Exception:
                                pass
        else:
            for item in self._base_path.glob("*"):
                if item.is_file():
                    if self._matches_file_type(item):
                        file_info = self._get_file_info(item)
                        if search_text.lower() in item.name.lower():
                            results.append(file_info)

        # Apply limit
        if query.limit:
            results = results[:query.limit]

        return QueryResult(
            data=results,
            total_count=len(results),
            source=self.name,
            metadata={"search_text": search_text},
        )

    def _matches_file_type(self, path: Path) -> bool:
        """Check if file matches configured file types."""
        if not self._file_types:
            return True
        return path.suffix.lower() in [ft.lower() for ft in self._file_types]

    def _is_text_file(self, path: Path) -> bool:
        """Check if file is a text file."""
        text_extensions = {
            ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
            ".xml", ".html", ".css", ".sql", ".sh", ".bash", ".csv",
            ".log", ".ini", ".cfg", ".conf", ".toml",
        }
        return path.suffix.lower() in text_extensions

    def _get_file_info(self, path: Path) -> Dict[str, Any]:
        """Get file information."""
        stat = path.stat()
        return {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix,
            "size": stat.st_size,
            "modified_time": stat.st_mtime,
            "created_time": stat.st_ctime,
            "is_text": self._is_text_file(path),
        }

    def _matches_filters(self, file_info: Dict[str, Any], filters: List[QueryFilter]) -> bool:
        """Check if file info matches filters."""
        for f in filters:
            value = file_info.get(f.field)
            if value is None:
                return False

            if f.operator == "eq" and value != f.value:
                return False
            elif f.operator == "ne" and value == f.value:
                return False
            elif f.operator == "gt" and value <= f.value:
                return False
            elif f.operator == "lt" and value >= f.value:
                return False
            elif f.operator == "gte" and value < f.value:
                return False
            elif f.operator == "lte" and value > f.value:
                return False
            elif f.operator == "in" and value not in f.value:
                return False
            elif f.operator == "like" and f.value not in str(value):
                return False

        return True

    async def health_check(self) -> bool:
        """Check if path is accessible."""
        try:
            return self._base_path.exists() and os.access(self._base_path, os.R_OK)
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get file system schema."""
        return {
            "base_path": str(self._base_path),
            "file_types": self._file_types,
            "recursive": self._recursive,
            "exists": self._base_path.exists(),
        }