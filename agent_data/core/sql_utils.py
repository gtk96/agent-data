"""SQL identifier validation and LIKE pattern escaping.

共用工具,被 SQLite (connectors/sql.py) 与 PostgreSQL (connectors/postgresql.py) 复用。
- validate_identifier: 防止 SQL 注入(标识符部分)
- escape_like: 转义 LIKE/ILIKE 通配符,防止逻辑型信息泄露
"""

import re

# 标识符白名单:字母/下划线开头,后续字母/数字/下划线
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# LIKE 通配符转义表:对用户传入的字符串里的 \ % _ 加反斜杠
_LIKE_ESCAPE = "\\"


def validate_identifier(name: str) -> str:
    """校验 SQL 标识符(表名/列名),只允许 ASCII 字母、数字、下划线。

    Raises:
        ValueError: 标识符非法。
    """
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def escape_like(value: str, escape: str = _LIKE_ESCAPE) -> str:
    """转义 LIKE/ILIKE 通配符,防止用户输入 _ % \\ 改变匹配语义。

    返回的字符串应配合 `f"LIKE ? ESCAPE '{escape}'"`(SQLite)或
    `f"ILIKE $N ESCAPE '{escape}'"`(PostgreSQL)使用。
    """
    if not isinstance(value, str):
        value = str(value)
    # 顺序很重要:必须先转义反斜杠本身
    return value.replace(escape, escape * 2).replace("%", escape + "%").replace("_", escape + "_")


def quote_identifier_pg(name: str) -> str:
    """PostgreSQL 标识符加双引号并转义内部双引号。

    不能保证完全免疫所有边角(例如含有换行或 NULL 字节),所以仍应先经过
    validate_identifier 做白名单校验。
    """
    validate_identifier(name)
    return '"' + name.replace('"', '""') + '"'
