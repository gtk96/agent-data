"""敏感字段脱敏工具,用于在 QueryResult.error / tracing attributes /
MCP 响应里屏蔽连接串、密钥、内部路径等。

设计原则:
- 简单、可预测;不要尝试"理解"输入语义,只做模式匹配。
- 默认 limit 不让单条 error 字符串无限长(>1KB 截断)。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable

# 用于 keys 匹配的脱敏字段名集合(大小写不敏感)
REDACT_KEYS = frozenset(
    {
        "password",
        "passwd",
        "api_key",
        "apikey",
        "token",
        "authorization",
        "secret",
        "private_key",
    }
)

# 单条 error 字符串上限
_MAX_ERROR_LEN = 1024

# 替换字符
_MASK = "***"

# 匹配 URL 中 user:pass@ 的捕获段
_URL_CRED_RE = re.compile(r"://([^@\s]+)@")
# 匹配 key=value 或 "key":"value" 形式的常见敏感字段
_KV_RE = re.compile(
    r'(["\']?(?:'
    + "|".join(re.escape(k) for k in REDACT_KEYS)
    + r')["\']?\s*[:=]\s*)([^\s,;"\'\]}]+)',
    re.IGNORECASE,
)


def redact(text: str) -> str:
    """对字符串进行脱敏与长度截断。

    - 屏蔽 `scheme://user:pass@host` 里的 user:pass
    - 屏蔽 query/path/header 片段里的 `key=value` / `"key":"value"`
    - 截断到 1KB
    """
    if not isinstance(text, str):
        text = str(text)
    text = _URL_CRED_RE.sub(f"://{_MASK}@", text)
    text = _KV_RE.sub(lambda m: m.group(1) + _MASK, text)
    if len(text) > _MAX_ERROR_LEN:
        text = text[: _MAX_ERROR_LEN - 3] + "..."
    return text


def redact_attributes(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """对 tracing attributes dict 脱敏 — 键名在 REDACT_KEYS 中则整体屏蔽值。"""
    out: Dict[str, Any] = {}
    for k, v in attrs.items():
        if isinstance(k, str) and k.lower() in REDACT_KEYS:
            out[k] = _MASK
        elif isinstance(v, str):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


def scrub_mapping(
    mapping: Dict[str, Any], forbidden: Iterable[str] = REDACT_KEYS
) -> Dict[str, Any]:
    """从 dict 里直接删除 forbidden 字段名(主要用于参数 / headers 等)。"""
    forbidden_lower = {f.lower() for f in forbidden}
    return {
        k: v
        for k, v in mapping.items()
        if not (isinstance(k, str) and k.lower() in forbidden_lower)
    }
