"""Tests for Schema Manager."""

import pytest
from unittest.mock import MagicMock
from agent_data.nl2sql.schema_manager import SchemaManager, TableInfo, ColumnInfo


class TestSchemaManager:
    """Tests for SchemaManager."""

    @pytest.fixture
    def mock_connector(self):
        """Create mock connector with schema."""
        connector = MagicMock()
        connector.get_schema.return_value = {
            "users": {
                "columns": [
                    {"name": "id", "type": "INTEGER", "primary_key": True},
                    {"name": "name", "type": "TEXT", "nullable": False},
                    {"name": "email", "type": "TEXT", "nullable": True},
                ],
                "row_count": 1000,
                "comment": "User accounts table",
            },
            "orders": {
                "columns": [
                    {"name": "id", "type": "INTEGER", "primary_key": True},
                    {"name": "user_id", "type": "INTEGER", "nullable": False},
                    {"name": "amount", "type": "REAL", "nullable": False},
                ],
                "row_count": 5000,
            },
        }
        return connector

    @pytest.mark.asyncio
    async def test_get_schema(self, mock_connector):
        """Test getting schema from connector."""
        manager = SchemaManager(mock_connector)
        schema = await manager.get_schema()

        assert "users" in schema
        assert "orders" in schema
        assert isinstance(schema["users"], TableInfo)
        assert len(schema["users"].columns) == 3

    @pytest.mark.asyncio
    async def test_get_table_info(self, mock_connector):
        """Test getting specific table info."""
        manager = SchemaManager(mock_connector)
        await manager.get_schema()

        table_info = await manager.get_table_info("users")
        assert table_info is not None
        assert table_info.name == "users"
        assert table_info.row_count == 1000

    @pytest.mark.asyncio
    async def test_get_table_info_not_found(self, mock_connector):
        """Test getting non-existent table."""
        manager = SchemaManager(mock_connector)
        await manager.get_schema()

        table_info = await manager.get_table_info("nonexistent")
        assert table_info is None

    @pytest.mark.asyncio
    async def test_format_schema_for_prompt(self, mock_connector):
        """Test schema formatting for prompts."""
        manager = SchemaManager(mock_connector)
        await manager.get_schema()

        formatted = manager.format_schema_for_prompt()
        assert "users" in formatted
        assert "orders" in formatted
        assert "INTEGER" in formatted
        assert "TEXT" in formatted
        assert "PK" in formatted

    @pytest.mark.asyncio
    async def test_format_schema_for_specific_tables(self, mock_connector):
        """Test formatting specific tables."""
        manager = SchemaManager(mock_connector)
        await manager.get_schema()

        formatted = manager.format_schema_for_prompt(tables=["users"])
        assert "users" in formatted
        assert "orders" not in formatted

    @pytest.mark.asyncio
    async def test_schema_caching(self, mock_connector):
        """Test schema caching."""
        manager = SchemaManager(mock_connector)

        # First call
        schema1 = await manager.get_schema()
        # Second call (should use cache)
        schema2 = await manager.get_schema()

        assert schema1 == schema2
        # Connector should only be called once
        assert mock_connector.get_schema.call_count == 1

    @pytest.mark.asyncio
    async def test_refresh_schema(self, mock_connector):
        """Test schema refresh."""
        manager = SchemaManager(mock_connector)

        await manager.get_schema()
        assert mock_connector.get_schema.call_count == 1

        await manager.refresh()
        assert mock_connector.get_schema.call_count == 2


class TestColumnInfo:
    """Tests for ColumnInfo dataclass."""

    def test_column_info_creation(self):
        """Test creating ColumnInfo."""
        col = ColumnInfo(name="id", type="INTEGER", primary_key=True)
        assert col.name == "id"
        assert col.type == "INTEGER"
        assert col.primary_key is True
        assert col.nullable is True  # default

    def test_column_info_with_comment(self):
        """Test ColumnInfo with comment."""
        col = ColumnInfo(name="name", type="TEXT", comment="User name")
        assert col.comment == "User name"


class TestTableInfo:
    """Tests for TableInfo dataclass."""

    def test_table_info_creation(self):
        """Test creating TableInfo."""
        table = TableInfo(name="users", row_count=100)
        assert table.name == "users"
        assert table.row_count == 100
        assert table.columns == []  # default

    def test_table_info_with_columns(self):
        """Test TableInfo with columns."""
        cols = [ColumnInfo(name="id", type="INTEGER")]
        table = TableInfo(name="users", columns=cols)
        assert len(table.columns) == 1
