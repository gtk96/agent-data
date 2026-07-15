"""Tests for token cost tracking in NL2SQL pipeline."""
from agent_data.nl2sql.engine import NL2SQLResult


def test_result_has_token_fields():
    r = NL2SQLResult(question="q", sql="SELECT 1", answer="ok")
    assert r.input_tokens == 0
    assert r.output_tokens == 0
    r.input_tokens = 100
    r.output_tokens = 50
    assert r.input_tokens == 100
    assert r.output_tokens == 50
