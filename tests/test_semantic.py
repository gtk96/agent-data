"""Tests for business semantic layer."""
import os
import tempfile

from agent_data.nl2sql.semantic import SemanticLayer


def test_load_and_get():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("users:\n  id: '用户ID'\n  name: '用户名'\n")
        f.flush()
        sl = SemanticLayer(f.name)
    assert sl.get_column_semantic("users", "id") == "用户ID"
    assert sl.get_column_semantic("users", "missing") == ""
    assert sl.get_column_semantic("no_table", "id") == ""
    os.unlink(f.name)


def test_format_for_prompt():
    sl = SemanticLayer()
    sl._defs = {"users": {"id": "用户ID", "name": "用户名"}}
    out = sl.format_for_prompt()
    assert "## Business Semantics" in out
    assert "### users" in out
    assert "id" in out
    assert "用户ID" in out
    assert "name" in out
    assert "用户名" in out


def test_format_empty():
    sl = SemanticLayer()
    assert sl.format_for_prompt() == ""


def test_format_specific_tables():
    sl = SemanticLayer()
    sl._defs = {
        "users": {"id": "用户ID"},
        "orders": {"amount": "订单金额"},
    }
    out = sl.format_for_prompt(tables=["users"])
    assert "users" in out
    assert "orders" not in out
