"""SQL validator for security checks."""

import re
from typing import List, Optional, Tuple

import sqlparse
from pydantic import BaseModel, Field


class ValidatorConfig(BaseModel):
    """SQL validator configuration."""

    readonly: bool = Field(default=True, description="Only allow SELECT queries")
    allow_union: bool = Field(default=False, description="Allow UNION queries")
    allow_subquery: bool = Field(default=True, description="Allow subqueries")
    max_joins: int = Field(default=5, description="Maximum number of JOINs")
    blocked_tables: List[str] = Field(default_factory=list, description="Blocked table names")
    allowed_tables: Optional[List[str]] = Field(
        default=None, description="Allowed table names (None=no restriction)"
    )
    query_timeout: int = Field(default=30, description="Query timeout in seconds")
    max_rows: int = Field(default=100, description="Maximum rows to return")


class SQLValidator:
    """SQL security validator.

    Validates SQL queries for safety before execution.
    """

    DANGEROUS_KEYWORDS = {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "REPLACE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "CALL",
        "MERGE",
        "UPSERT",
        "SET",
    }

    BLOCKED_TABLE_PATTERNS = [
        r"information_schema",
        r"pg_catalog",
        r"sys\.",
        r"mysql\.",
    ]

    def __init__(self, config: Optional[ValidatorConfig] = None):
        """Initialize validator.

        Args:
            config: Validator configuration. Uses defaults if not provided.
        """
        self.config = config or ValidatorConfig()

    def validate(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Validate SQL query for safety.

        Args:
            sql: SQL query string to validate.

        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if not sql or not sql.strip():
            return False, "Empty SQL query"

        # Step 1: Parse SQL
        try:
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False, "Failed to parse SQL"
        except Exception as e:
            return False, f"SQL syntax error: {e}"

        # Step 2: Check statement type (only SELECT allowed)
        if self.config.readonly:
            is_valid, error = self._check_statement_type(parsed)
            if not is_valid:
                return is_valid, error

        # Step 3: Check dangerous keywords
        is_valid, error = self._check_dangerous_keywords(sql)
        if not is_valid:
            return is_valid, error

        # Step 4: Check multiple statements
        is_valid, error = self._check_multiple_statements(sql)
        if not is_valid:
            return is_valid, error

        # Step 5: Check injection patterns
        is_valid, error = self._check_injection_patterns(sql)
        if not is_valid:
            return is_valid, error

        # Step 6: Check blocked tables
        is_valid, error = self._check_blocked_tables(sql)
        if not is_valid:
            return is_valid, error

        return True, None

    def _check_statement_type(self, parsed) -> Tuple[bool, Optional[str]]:
        """Check if SQL is a SELECT statement."""
        for statement in parsed:
            if statement.get_type() and statement.get_type().upper() != "SELECT":
                return False, f"Only SELECT queries are allowed, got {statement.get_type()}"
        return True, None

    def _check_dangerous_keywords(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Check for dangerous SQL keywords."""
        sql_upper = sql.upper()
        for keyword in self.DANGEROUS_KEYWORDS:
            # Use word boundary to avoid false positives
            pattern = r"\b" + keyword + r"\b"
            if re.search(pattern, sql_upper):
                return False, f"Dangerous keyword detected: {keyword}"
        return True, None

    def _check_multiple_statements(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Check for multiple SQL statements (semicolon-separated)."""
        # Remove strings and comments first
        cleaned = re.sub(r"'[^']*'", "", sql)
        cleaned = re.sub(r'"[^"]*"', "", cleaned)
        cleaned = re.sub(r"--.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        # Count semicolons (excluding trailing)
        cleaned = cleaned.strip().rstrip(";")
        if ";" in cleaned:
            return False, "Multiple SQL statements are not allowed"
        return True, None

    def _check_injection_patterns(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Check for common SQL injection patterns."""
        sql_upper = sql.upper()

        # Check for UNION injection (if not allowed)
        if not self.config.allow_union:
            if re.search(r"\bUNION\b", sql_upper):
                return False, "UNION queries are not allowed"

        # Check for comment injection
        if re.search(r"--", sql) or re.search(r"/\*", sql):
            return False, "SQL comments are not allowed"

        # Check for batch operations
        if re.search(r"\b(BULK|BCP)\b", sql_upper):
            return False, "Batch operations are not allowed"

        return True, None

    def _check_blocked_tables(self, sql: str) -> Tuple[bool, Optional[str]]:
        """Check for blocked table access."""
        sql_lower = sql.lower()

        # Check system tables
        for pattern in self.BLOCKED_TABLE_PATTERNS:
            if re.search(pattern, sql_lower):
                return False, f"Access to system tables is blocked: {pattern}"

        # Check explicitly blocked tables
        for table in self.config.blocked_tables:
            if table.lower() in sql_lower:
                return False, f"Access to table '{table}' is blocked"

        # Check allowed tables (whitelist mode)
        if self.config.allowed_tables is not None:
            # Extract table names from SQL (simple regex)
            table_pattern = r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)"
            matches = re.findall(table_pattern, sql, re.IGNORECASE)
            for match in matches:
                table = match[0] or match[1]
                if table.lower() not in [t.lower() for t in self.config.allowed_tables]:
                    return False, f"Table '{table}' is not in allowed tables list"

        return True, None

    def sanitize(self, sql: str) -> str:
        """Sanitize SQL query.

        Args:
            sql: Raw SQL query.

        Returns:
            Sanitized SQL query.
        """
        # Remove extra whitespace
        sql = re.sub(r"\s+", " ", sql).strip()

        # Remove comments
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)

        # Ensure ends with semicolon
        if not sql.endswith(";"):
            sql += ";"

        return sql
