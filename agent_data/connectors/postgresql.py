"""
PostgreSQL database connector.
"""

import asyncio
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


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL database connector using asyncpg."""

    def __init__(self, config: DataSourceConfig):
        super().__init__(config)
        self._pool = None
        self._connection_string = config.connection

    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60,
            )
            self._connected = True
        except ImportError:
            raise ImportError(
                "asyncpg is required for PostgreSQL connector. "
                "Install it with: pip install asyncpg"
            )

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        self._connected = False

    async def execute(self, query: Query) -> QueryResult:
        """Execute a PostgreSQL query."""
        if not self._connected or not self._pool:
            raise RuntimeError("Not connected to PostgreSQL")

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

        async with self._pool.acquire() as conn:
            stmt = await conn.prepare(sql)
            records = await stmt.fetch(*params)
            columns = [attr.name for attr in stmt.get_attributes()]

            data = [dict(zip(columns, record)) for record in records]
            # Convert any non-serializable types
            for row in data:
                for key, value in row.items():
                    if hasattr(value, "isoformat"):
                        row[key] = value.isoformat()

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"sql": sql, "params": params},
        )

    async def _execute_search(self, query: Query) -> QueryResult:
        """Execute a search query (text search)."""
        search_text = query.query or ""

        # Get text columns for search
        text_columns = await self._get_text_columns(query.source)

        if not text_columns or not search_text:
            # Fallback to regular select
            return await self._execute_select(query)

        # Build LIKE query for text search
        like_pattern = f"%{search_text}%"
        where_parts = []
        params = []

        for col in text_columns:
            where_parts.append(f"{col} ILIKE $1")
            params.append(like_pattern)

        sql = f"SELECT * FROM {query.source} WHERE {' OR '.join(where_parts)}"

        if query.limit:
            sql += f" LIMIT {query.limit}"

        async with self._pool.acquire() as conn:
            records = await conn.fetch(sql, *params)
            if records:
                columns = list(records[0].keys())
                data = [dict(zip(columns, record)) for record in records]
            else:
                data = []

        return QueryResult(
            data=data,
            total_count=len(data),
            source=self.name,
            metadata={"sql": sql, "search_text": search_text},
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
        placeholders = ", ".join([f"${i+1}" for i in range(len(data))])
        sql = f"INSERT INTO {query.source} ({columns}) VALUES ({placeholders}) RETURNING id"

        async with self._pool.acquire() as conn:
            record = await conn.fetchrow(sql, *data.values())
            inserted_id = record["id"] if record else None

        return QueryResult(
            data=[{"id": inserted_id}],
            source=self.name,
            metadata={"sql": sql, "rows_affected": 1},
        )

    async def _execute_update(self, query: Query) -> QueryResult:
        """Execute an UPDATE query."""
        data = query.metadata.get("data", {})
        if not data:
            return QueryResult(
                source=self.name,
                error="No data provided for UPDATE",
            )

        set_parts = []
        params = []
        param_idx = 1

        for key, value in data.items():
            set_parts.append(f"{key} = ${param_idx}")
            params.append(value)
            param_idx += 1

        where_clause, where_params = self._build_where_clause(query.filters, param_idx)
        params.extend(where_params)

        sql = f"UPDATE {query.source} SET {', '.join(set_parts)}"
        if where_clause:
            sql += f" WHERE {where_clause}"

        async with self._pool.acquire() as conn:
            result = await conn.execute(sql, *params)
            # Parse result to get rows affected
            rows_affected = int(result.split()[-1]) if result else 0

        return QueryResult(
            data=[{"rows_affected": rows_affected}],
            source=self.name,
            metadata={"sql": sql, "rows_affected": rows_affected},
        )

    async def _execute_delete(self, query: Query) -> QueryResult:
        """Execute a DELETE query."""
        where_clause, params = self._build_where_clause(query.filters)

        sql = f"DELETE FROM {query.source}"
        if where_clause:
            sql += f" WHERE {where_clause}"

        async with self._pool.acquire() as conn:
            result = await conn.execute(sql, *params)
            rows_affected = int(result.split()[-1]) if result else 0

        return QueryResult(
            data=[{"rows_affected": rows_affected}],
            source=self.name,
            metadata={"sql": sql, "rows_affected": rows_affected},
        )

    def _build_where_clause(self, filters: List[QueryFilter], start_idx: int = 1) -> tuple:
        """Build WHERE clause from filters."""
        if not filters:
            return "", []

        conditions = []
        params = []
        param_idx = start_idx

        for f in filters:
            if f.operator == "eq":
                conditions.append(f"{f.field} = ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "ne":
                conditions.append(f"{f.field} != ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "gt":
                conditions.append(f"{f.field} > ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "lt":
                conditions.append(f"{f.field} < ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "gte":
                conditions.append(f"{f.field} >= ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "lte":
                conditions.append(f"{f.field} <= ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "in":
                placeholders = ", ".join([f"${param_idx + i}" for i in range(len(f.value))])
                conditions.append(f"{f.field} IN ({placeholders})")
                params.extend(f.value)
                param_idx += len(f.value)
            elif f.operator == "like":
                conditions.append(f"{f.field} LIKE ${param_idx}")
                params.append(f.value)
                param_idx += 1
            elif f.operator == "ilike":
                conditions.append(f"{f.field} ILIKE ${param_idx}")
                params.append(f.value)
                param_idx += 1
            else:
                raise ValueError(f"Unsupported operator: {f.operator}")

        return " AND ".join(conditions), params

    async def _get_text_columns(self, table_name: str) -> List[str]:
        """Get text columns from a table."""
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = $1
            AND data_type IN ('text', 'varchar', 'character varying')
        """

        async with self._pool.acquire() as conn:
            records = await conn.fetch(sql, table_name)
            return [record["column_name"] for record in records]

    async def health_check(self) -> bool:
        """Check PostgreSQL connection health."""
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    def get_schema(self) -> Dict[str, Any]:
        """Get database schema (requires connection)."""
        # This is a placeholder - actual implementation would query information_schema
        return {
            "type": "postgresql",
            "connection": (
                self._connection_string.split("@")[-1]
                if "@" in self._connection_string
                else "localhost"
            ),
        }

    async def get_tables(self) -> List[str]:
        """Get list of tables in the database."""
        sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """

        async with self._pool.acquire() as conn:
            records = await conn.fetch(sql)
            return [record["table_name"] for record in records]

    async def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Get columns for a specific table."""
        sql = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = $1
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """

        async with self._pool.acquire() as conn:
            records = await conn.fetch(sql, table_name)
            return [
                {
                    "name": record["column_name"],
                    "type": record["data_type"],
                    "nullable": record["is_nullable"] == "YES",
                    "default": record["column_default"],
                }
                for record in records
            ]
