"""异常层级与重导出。

所有自定义异常的根是 AgentDataError,各模块在此基础上派生专用类型。
约定:
- 业务层(connectors / planner / workflow / loop / MCP)真正失败时 raise
  对应子类的具体异常;调用方 AgentDataClient 会捕获并转写到
  QueryResult.error / TaskResult.error / MCP 响应里,不再暴露原始 str(e)
  以避免泄漏 SQL/路径/密钥等内部信息。
- QueryResult.error 仅用于"业务可恢复错误"(如缺数据、参数不合法),
  不携带敏感片段。
"""

from __future__ import annotations

from typing import Optional


class AgentDataError(Exception):
    """所有 agent-data 异常的基类。"""


# ---------- Connectors ----------


class ConnectorError(AgentDataError):
    """数据源连接/操作错误的基类。"""


class ConnectionError_(ConnectorError):
    """连接建立/维持失败。"""


class AuthError(ConnectorError):
    """鉴权失败(token 无效、密码错等)。"""


class NotFoundError(ConnectorError):
    """目标资源不存在(表/记录/endpoint)。"""


class ValidationError_(ConnectorError):
    """入参校验失败。"""


class TimeoutError_(ConnectorError):
    """操作超时。"""


class RateLimitError(ConnectorError):
    """触发上游限流。"""


class SSRFError(ConnectorError):
    """检测到 SSRF 风险(endpoint 越权跳转)。"""


class ResponseTooLargeError(ConnectorError):
    """响应体过大。"""


# ---------- 其他模块 ----------


class PlannerError(AgentDataError):
    """规划阶段失败。"""


class WorkflowError(AgentDataError):
    """工作流执行失败。"""


class LoopError(AgentDataError):
    """Agent loop 执行失败。"""


class MCPAuthError(AgentDataError):
    """MCP 请求鉴权失败。"""


class MCPMethodError(AgentDataError):
    """MCP 协议层未知方法 / 参数错误。"""


def format_error(exc: BaseException, fallback: Optional[str] = None) -> str:
    """把异常格式化成对外安全的字符串。

    返回 `<ClassName>: <message>`,不带 traceback/路径/连接串。
    """
    cls = type(exc).__name__
    msg = str(exc).strip() or (fallback or "error")
    return f"{cls}: {msg}"
