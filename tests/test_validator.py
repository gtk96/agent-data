"""Tests for SQL validator."""

import pytest
from agent_data.nl2sql.validator import SQLValidator, ValidatorConfig


class TestSQLValidator:
    """Tests for SQLValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SQLValidator()

    def test_valid_select(self):
        """Test valid SELECT query passes validation."""
        sql = "SELECT * FROM users WHERE id = 1"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is True
        assert error is None

    def test_insert_blocked(self):
        """Test INSERT query is blocked."""
        sql = "INSERT INTO users (name) VALUES ('test')"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "INSERT" in error

    def test_update_blocked(self):
        """Test UPDATE query is blocked."""
        sql = "UPDATE users SET name = 'test' WHERE id = 1"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "UPDATE" in error

    def test_delete_blocked(self):
        """Test DELETE query is blocked."""
        sql = "DELETE FROM users WHERE id = 1"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "DELETE" in error

    def test_drop_blocked(self):
        """Test DROP query is blocked."""
        sql = "DROP TABLE users"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "DROP" in error

    def test_multiple_statements_blocked(self):
        """Test multiple statements are blocked."""
        sql = "SELECT * FROM users; SELECT * FROM orders"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "Multiple" in error

    def test_union_blocked(self):
        """Test UNION is blocked by default."""
        sql = "SELECT id FROM users UNION SELECT id FROM orders"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "UNION" in error

    def test_union_allowed(self):
        """Test UNION is allowed when configured."""
        config = ValidatorConfig(allow_union=True)
        validator = SQLValidator(config)
        sql = "SELECT id FROM users UNION SELECT id FROM orders"
        is_valid, error = validator.validate(sql)
        assert is_valid is True

    def test_comments_blocked(self):
        """Test SQL comments are blocked."""
        sql = "SELECT * FROM users -- this is a comment"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False
        assert "comments" in error.lower()

    def test_empty_sql(self):
        """Test empty SQL is rejected."""
        sql = ""
        is_valid, error = self.validator.validate(sql)
        assert is_valid is False

    def test_select_with_join(self):
        """Test SELECT with JOIN is valid."""
        sql = "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is True

    def test_select_with_subquery(self):
        """Test SELECT with subquery is valid by default."""
        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"
        is_valid, error = self.validator.validate(sql)
        assert is_valid is True

    def test_blocked_table(self):
        """Test blocked table access is rejected."""
        config = ValidatorConfig(blocked_tables=["passwords"])
        validator = SQLValidator(config)
        sql = "SELECT * FROM passwords"
        is_valid, error = validator.validate(sql)
        assert is_valid is False
        assert "passwords" in error

    def test_sanitize(self):
        """Test SQL sanitization."""
        sql = "  SELECT   *   FROM   users  "
        sanitized = self.validator.sanitize(sql)
        assert sanitized == "SELECT * FROM users;"


class TestValidatorConfig:
    """Tests for ValidatorConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ValidatorConfig()
        assert config.readonly is True
        assert config.allow_union is False
        assert config.max_joins == 5
        assert config.max_rows == 100
