"""Tests for chart suggestion logic."""
from agent_data.nl2sql.chart import suggest_chart


def test_bar_chart():
    rows = [
        {"category": "电子产品", "count": 5},
        {"category": "家具", "count": 2},
        {"category": "服装", "count": 3},
        {"category": "食品", "count": 8},
        {"category": "图书", "count": 4},
        {"category": "运动", "count": 6},
    ]
    columns = ["category", "count"]
    chart = suggest_chart(rows, columns)
    assert chart is not None
    assert chart["type"] == "bar"
    assert chart["labels"] == ["电子产品", "家具", "服装", "食品", "图书", "运动"]
    assert chart["datasets"][0]["data"] == [5, 2, 3, 8, 4, 6]


def test_line_chart():
    rows = [
        {"month": "1月", "amount": 100},
        {"month": "2月", "amount": 200},
        {"month": "3月", "amount": 150},
    ]
    columns = ["month", "amount"]
    chart = suggest_chart(rows, columns)
    assert chart is not None
    assert chart["type"] == "line"


def test_pie_chart():
    rows = [
        {"status": "待处理", "count": 10},
        {"status": "进行中", "count": 5},
        {"status": "已完成", "count": 15},
    ]
    columns = ["status", "count"]
    chart = suggest_chart(rows, columns)
    assert chart is not None
    assert chart["type"] == "pie"


def test_single_value_no_chart():
    rows = [{"count": 42}]
    columns = ["count"]
    chart = suggest_chart(rows, columns)
    assert chart is None


def test_too_many_rows_no_chart():
    rows = [{"id": i, "value": i * 10} for i in range(50)]
    columns = ["id", "value"]
    chart = suggest_chart(rows, columns)
    assert chart is None


def test_empty_rows():
    chart = suggest_chart([], ["a", "b"])
    assert chart is None


def test_all_string_values():
    rows = [{"name": "Alice"}, {"name": "Bob"}]
    columns = ["name"]
    chart = suggest_chart(rows, columns)
    assert chart is None
