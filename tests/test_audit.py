"""Tests for SQL audit logging."""
import glob
import json
import os
import tempfile

from agent_data.nl2sql.audit import SQLAuditor


def test_log_creates_file():
    with tempfile.TemporaryDirectory() as d:
        aud = SQLAuditor(audit_dir=d)
        aud.log(session_id="s1", sql="SELECT 1", row_count=1, success=True, query_time_ms=5.0)
        files = glob.glob(os.path.join(d, "*.json"))
        assert len(files) == 1
        with open(files[0]) as f:
            entry = json.load(f)
        assert entry["session_id"] == "s1"
        assert entry["sql"] == "SELECT 1"
        assert entry["success"] is True
        assert entry["row_count"] == 1


def test_log_failure():
    with tempfile.TemporaryDirectory() as d:
        aud = SQLAuditor(audit_dir=d)
        aud.log(
            session_id="s2",
            sql="BAD SQL",
            row_count=0,
            success=False,
            query_time_ms=1.0,
            error="syntax error",
        )
        files = glob.glob(os.path.join(d, "*.json"))
        with open(files[0]) as f:
            entry = json.load(f)
        assert entry["success"] is False
        assert entry["error"] == "syntax error"
