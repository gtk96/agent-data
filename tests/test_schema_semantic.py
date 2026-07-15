"""Tests for semantic layer integration into SchemaManager."""
from agent_data.nl2sql.semantic import SemanticLayer
from agent_data.nl2sql.schema_manager import SchemaManager, TableInfo, ColumnInfo


def test_format_with_semantics():
    sm = SchemaManager.__new__(SchemaManager)
    sm._cache = {"users": TableInfo(
        name="users",
        columns=[
            ColumnInfo(name="id", type="int"),
            ColumnInfo(name="name", type="text"),
        ],
    )}
    sl = SemanticLayer()
    sl._defs = {"users": {"id": "用户ID", "name": "用户名"}}
    out = sm.format_schema_with_semantics(sl)
    assert "## Business Semantics" in out
    assert "id" in out
    assert "用户ID" in out
    assert "name" in out
    assert "用户名" in out
    assert "### users" in out


def test_format_with_none_semantics():
    sm = SchemaManager.__new__(SchemaManager)
    sm._cache = {"users": TableInfo(name="users", columns=[])}
    out = sm.format_schema_with_semantics(None)
    assert "users" in out
    assert "Business Semantics" not in out


def test_format_with_empty_semantics():
    sm = SchemaManager.__new__(SchemaManager)
    sm._cache = {"users": TableInfo(name="users", columns=[])}
    sl = SemanticLayer()
    out = sm.format_schema_with_semantics(sl)
    assert "users" in out
    assert "Business Semantics" not in out
