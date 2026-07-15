"""Tests for follow-up question context resolution."""
from agent_data.nl2sql.prompt import PromptManager


def test_followup_template_has_placeholders():
    """Follow-up template must accept {history} and {question}."""
    out = PromptManager.FOLLOWUP_TEMPLATE.format(
        history="## Turn 1\nUser: 笔记本多少钱\nAnswer: 5999",
        question="那它的价格是多少",
    )
    assert "那它的价格是多少" in out
    assert "Turn 1" in out
    assert "笔记本" in out


def test_build_sql_generation_messages_with_context():
    """SQL generation messages should include conversation context."""
    msgs = PromptManager.build_sql_generation_messages(
        schema_info="## Schema\nusers(id INT, name TEXT)",
        question="统计用户数",
        conversation_context="## Turn 1\nUser: 有哪些用户\nAnswer: 有5个用户",
    )
    assert len(msgs) == 2
    assert "统计用户数" in msgs[1]["content"]
    assert "Turn 1" in msgs[1]["content"]
    assert "有哪些用户" in msgs[1]["content"]
