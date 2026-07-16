"""Tests for natural language answer generation."""
import pytest
from agent_data.nl2sql.answer import (
    AnswerStyle,
    build_answer_messages,
    detect_answer_style,
    score_answer_quality,
)


def test_detect_brief():
    data = [{"count": 42}]
    assert detect_answer_style("有多少用户", "SELECT COUNT(*)", data) == AnswerStyle.BRIEF


def test_detect_comparison():
    data = [{"cat": "A", "v": 10}, {"cat": "B", "v": 20}]
    assert detect_answer_style("A 和 B 哪个销量高", "SELECT *", data) == AnswerStyle.COMPARISON


def test_detect_summary():
    data = [{"id": i, "v": i} for i in range(15)]
    assert detect_answer_style("统计各用户订单", "SELECT *", data) == AnswerStyle.SUMMARY


def test_detect_detailed():
    data = [{"cat": "X", "cnt": 5}, {"cat": "Y", "cnt": 3}]
    assert detect_answer_style("各类别数量", "SELECT category, COUNT(*)", data) == AnswerStyle.DETAILED


def test_build_messages():
    data = [{"count": 5}]
    msgs = build_answer_messages("有多少用户", "SELECT COUNT(*)", data)
    assert len(msgs) == 2
    assert "用户问题" in msgs[1]["content"]
    assert "有多少用户" in msgs[1]["content"]
    # BRIEF style doesn't include SQL, so just check question is present


def test_build_messages_auto_style():
    data = [{"a": 1}, {"a": 2}, {"a": 3}]
    msgs = build_answer_messages("统计各组", "SELECT a, COUNT(*)", data)
    # Should be DETECTED as DETAILED (SQL has COUNT)
    assert len(msgs) == 2


def test_score_quality_good():
    data = [{"sales": 1000}]
    score = score_answer_quality("销售额多少", "销售额为 1000 元", data)
    assert score >= 0.8


def test_score_quality_no_number():
    data = [{"sales": 1000}]
    score = score_answer_quality("销售额多少", "请查看数据", data)
    assert score <= 0.7


def test_score_quality_too_short():
    data = [{"v": 1}]
    score = score_answer_quality("数据", "1", data)
    assert score <= 0.7


def test_score_quality_bad_prefix():
    data = [{"v": 1}]
    score = score_answer_quality("数据", "根据查询结果，数据为 1", data)
    assert score <= 0.9


def test_score_quality_empty_data():
    score = score_answer_quality("问题", "无数据", [])
    assert 0.0 <= score <= 1.0
