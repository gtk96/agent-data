"""Tests for PII redaction in query results."""
from agent_data.core.redact import redact_pii


def test_email_redacted():
    assert "@example.com" not in redact_pii("联系 user@example.com 获取详情")


def test_phone_redacted():
    assert "13812345678" not in redact_pii("电话：13812345678")


def test_id_card_redacted():
    assert "110101199001011234" not in redact_pii("身份证：110101199001011234")


def test_normal_text_unchanged():
    assert redact_pii("普通文本 12345") == "普通文本 12345"


def test_redact_data_list():
    rows = [{"name": "张三", "email": "z@test.com", "phone": "13800001111"}]
    result = redact_pii(rows)
    assert "z@test.com" not in str(result)
    assert "13800001111" not in str(result)
    assert result[0]["name"] == "张三"
