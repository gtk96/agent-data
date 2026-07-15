"""Schema manager for extracting database metadata."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """Column information."""

    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    comment: Optional[str] = None
    sample_values: List[Any] = field(default_factory=list)


@dataclass
class TableInfo:
    """Table information."""

    name: str
    schema_name: Optional[str] = None
    comment: Optional[str] = None
    columns: List[ColumnInfo] = field(default_factory=list)
    row_count: Optional[int] = None
    sample_data: List[Dict[str, Any]] = field(default_factory=list)


class SchemaManager:
    """Database schema manager.

    Extracts and formats schema information for LLM prompts.
    """

    def __init__(self, connector):
        """Initialize with a database connector.

        Args:
            connector: BaseConnector instance (SQL/PostgreSQL).
        """
        self._connector = connector
        self._cache: Optional[Dict[str, TableInfo]] = None

    async def get_schema(self, use_cache: bool = True) -> Dict[str, TableInfo]:
        """Get complete database schema.

        Args:
            use_cache: Whether to use cached schema.

        Returns:
            Dictionary mapping table names to TableInfo.
        """
        if use_cache and self._cache is not None:
            return self._cache

        try:
            raw_schema = self._connector.get_schema()
            tables = {}

            for table_name, table_data in raw_schema.items():
                columns = []
                for col in table_data.get("columns", []):
                    columns.append(
                        ColumnInfo(
                            name=col.get("name", ""),
                            type=col.get("type", "unknown"),
                            nullable=col.get("nullable", True),
                            primary_key=col.get("primary_key", False),
                            comment=col.get("comment"),
                            sample_values=col.get("sample_values", []),
                        )
                    )

                tables[table_name] = TableInfo(
                    name=table_name,
                    schema_name=table_data.get("schema"),
                    comment=table_data.get("comment"),
                    columns=columns,
                    row_count=table_data.get("row_count"),
                    sample_data=table_data.get("sample_data", []),
                )

            self._cache = tables
            return tables

        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            return {}

    async def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """Get detailed information for a specific table.

        Args:
            table_name: Name of the table.

        Returns:
            TableInfo if found, None otherwise.
        """
        schema = await self.get_schema()
        return schema.get(table_name)

    def format_schema_for_prompt(self, tables: Optional[List[str]] = None) -> str:
        """Format schema as text for LLM prompt.

        Args:
            tables: List of table names to include. None for all tables.

        Returns:
            Formatted schema string.
        """
        if self._cache is None:
            return "Schema not loaded. Please call get_schema() first."

        lines = ["## Database Schema", ""]

        target_tables = tables if tables else list(self._cache.keys())

        for table_name in target_tables:
            table = self._cache.get(table_name)
            if table is None:
                continue

            # Table header
            header = f"### {table_name}"
            if table.comment:
                header += f" ({table.comment})"
            lines.append(header)

            # Columns
            for col in table.columns:
                col_line = f"  - {col.name} {col.type}"
                if col.primary_key:
                    col_line += " [PK]"
                if not col.nullable:
                    col_line += " NOT NULL"
                if col.comment:
                    col_line += f" -- {col.comment}"
                lines.append(col_line)

                # Sample values
                if col.sample_values:
                    samples = ", ".join(str(v) for v in col.sample_values[:5])
                    lines.append(f"    Sample values: {samples}")

            # Row count
            if table.row_count is not None:
                lines.append(f"  Row count: ~{table.row_count}")

            lines.append("")

        return "\n".join(lines)

    def format_schema_with_semantics(self, semantic_layer=None) -> str:
        """Append business semantics to schema prompt.

        Args:
            semantic_layer: SemanticLayer instance, or None to skip.

        Returns:
            Schema text + semantics text.
        """
        schema_text = self.format_schema_for_prompt()
        if semantic_layer is None:
            return schema_text
        sem_text = semantic_layer.format_for_prompt()
        if sem_text:
            return schema_text + "\n" + sem_text
        return schema_text

    async def refresh(self):
        """Force refresh schema cache."""
        self._cache = None
        await self.get_schema(use_cache=False)
