"""
SQL database connector.
"""

import sqlite3
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


class SQLConnector(BaseConnector):
    """SQL database connector (SQLite for development, extensible to PostgreSQL/MySQL)."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._connection: Optional[sqlite3.Connection] = None
        self._db_path = config.connection

    async def connect(self) -> None:
        """Establish database connection."""
        self._connection = sqlite3.connect(self._db_path)
        self._connection.row_factory = sqlite3.Row
        self._connected = True

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a SQL query."""
        if not self._connected or not self._connection:
            raise RuntimeError("Not connected to database")

        start_time = time.time()

        try:
            if query.query_type == QueryType.SELECT:
                return await self._execute_select(query)
            elif query.query_type == QueryType.INSERT:
                return await self._execute_insert(query)
            elif query.query_type == QueryType.UPDATE:
                return await self._execute_update(query)
            elif query.query_type == QueryType.DELETE:
                return await self._execute_delete(query)
            elif query.query_type == QueryType.SEARCH:
                return await self._execute_search(query)
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

    async def _execute_select(self, query: Query) -> QueryResult:
        """Execute a SELECT query."""
        sql_parts = ["SELECT"]

        # Fields
        if query.fields:
            sql_parts.append(", ".join(query.fields))
        else:
            sql_parts.append("*")

        # FROM
        sql_parts.append(f"FROM {query.source}")

        # WHERE
        where_clause, params = self._build_where_clause(query.filters)
        if where_clause:
            sql_parts.append(f"WHERE {where_clause}")

        # ORDER BY
        if query.order_by:
            order = "DESC" if query.order_desc else "ASC"
            sql_parts.append(f"ORDER BY {query.order_by} {order}")

        # LIMIT
        if query.limit:
            sql_parts.append(f"LIMIT {query.limit}")

        # OFFSET
        if query.offset:
            sql_parts.append(f"OFFSET {query.offset}")

        sql = " ".join(sql_parts)

        cursor = self._connection.execute(sql, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []

        data = [dict(zip(columns, row)) for row in rows]

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"sql": sql, "params": params},
        )

    async def _execute_search(self, query: Query) -> QueryResult:
        """Execute a search query (simple LIKE-based search)."""
        # For search queries, try to find text to search for
        search_text = query.query or ""

        # Build a simple LIKE query
        sql = f"SELECT * FROM {query.source}"
        params = []

        if search_text:
            # Search in all text columns
            like_clause = f"%{search_text}%"
            where_parts = []
            for col in self._get_text_columns(query.source):
                where_parts.append(f"{col} LIKE ?")
                params.append(like_clause)
            if where_parts:
                sql += f" WHERE {' OR '.join(where_parts)}"

        if query.limit:
            sql += f" LIMIT {query.limit}"

        cursor = self._connection.execute(sql, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description] if cursor.description else []

        data = [dict(zip(columns, row)) for row in rows]

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"sql": sql, "params": params},
        )

    async def _execute_insert(self, query: Query) -> QueryResult:
        """Execute an INSERT query."""
        data = query.metadata.get("data", {})
        if not data:
            return QueryResult(
                source=self.name,
                error="No data provided for INSERT",
            )

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {query.source} ({columns}) VALUES ({placeholders})"

        cursor = self._connection.execute(sql, list(data.values()))
        self._connection.commit()

        return QueryResult(
            data=[{"rowid": cursor.lastrowid}],
            source=self.name,
            metadata={"sql": sql, "rows_affected": cursor.rowcount},
        )

    async def _execute_update(self, query: Query) -> QueryResult:
        """Execute an UPDATE query."""
        data = query.metadata.get("data", {})
        if not data:
            return QueryResult(
                source=self.name,
                error="No data provided for UPDATE",
            )

        set_parts = [f"{k} = ?" for k in data.keys()]
        where_clause, params = self._build_where_clause(query.filters)

        sql = f"UPDATE {query.source} SET {', '.join(set_parts)}"
        if where_clause:
            sql += f" WHERE {where_clause}"
            params = list(data.values()) + params
        else:
            params = list(data.values())

        cursor = self._connection.execute(sql, params)
        self._connection.commit()

        return QueryResult(
            data=[{"rows_affected": cursor.rowcount}],
            source=self.name,
            metadata={"sql": sql, "rows_affected": cursor.rowcount},
        )

    async def _execute_delete(self, query: Query) -> QueryResult:
        """Execute a DELETE query."""
        where_clause, params = self._build_where_clause(query.filters)

        sql = f"DELETE FROM {query.source}"
        if where_clause:
            sql += f" WHERE {where_clause}"

        cursor = self._connection.execute(sql, params)
        self._connection.commit()

        return QueryResult(
            data=[{"rows_affected": cursor.rowcount}],
            source=self.name,
            metadata={"sql": sql, "rows_affected": cursor.rowcount},
        )

    def _build_where_clause(self, filters: List[QueryFilter]) -> tuple:
        """Build WHERE clause from filters."""
        if not filters:
            return "", []

        conditions = []
        params = []

        for f in filters:
            if f.operator == "eq":
                conditions.append(f"{f.field} = ?")
                params.append(f.value)
            elif f.operator == "ne":
                conditions.append(f"{f.field} != ?")
                params.append(f.value)
            elif f.operator == "gt":
                conditions.append(f"{f.field} > ?")
                params.append(f.value)
            elif f.operator == "lt":
                conditions.append(f"{f.field} < ?")
                params.append(f.value)
            elif f.operator == "gte":
                conditions.append(f"{f.field} >= ?")
                params.append(f.value)
            elif f.operator == "lte":
                conditions.append(f"{f.field} <= ?")
                params.append(f.value)
            elif f.operator == "in":
                placeholders = ", ".join(["?"] * len(f.value))
                conditions.append(f"{f.field} IN ({placeholders})")
                params.extend(f.value)
            elif f.operator == "like":
                conditions.append(f"{f.field} LIKE ?")
                params.append(f.value)
            elif f.operator == "contains":
                conditions.append(f"{f.field} LIKE ?")
                params.append(f"%{f.value}%")
            else:
                raise ValueError(f"Unsupported operator: {f.operator}")

        return " AND ".join(conditions), params

    def _get_text_columns(self, table_name: str) -> List[str]:
        """Get text columns from a table."""
        cursor = self._connection.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return [
            col[1]
            for col in columns
            if col[2].upper() in ("TEXT", "VARCHAR", "CHAR", "STRING")
        ]

    async def health_check(self) -> bool:
        """Check database health."""
        try:
            cursor = self._connection.execute("SELECT 1")
            cursor.fetchone()
            return True
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get database schema."""
        cursor = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            cursor = self._connection.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            schema[table] = {
                "columns": [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default": col[4],
                        "primary_key": bool(col[5]),
                    }
                    for col in columns
                ]
            }

        return schema