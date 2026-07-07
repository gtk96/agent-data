"""
Agent Data Orchestration Framework

A unified data access layer for AI Agent applications.
"""

from agent_data.core.models import (
    AgentContext,
    DataSource,
    DataSourceConfig,
    DataSourceType,
    Query,
    QueryFilter,
    QueryResult,
    QueryType,
)
from agent_data.core.client import AgentDataClient
from agent_data.core.connector import BaseConnector, register_connector

# Planning
from agent_data.planning import (
    CompositeTaskPlanner,
    FunctionTaskExecutor,
    PlanExecutor,
    SimpleTaskPlanner,
    Task,
    TaskExecutor,
    TaskPlan,
    TaskPlanner,
    TaskResult,
    TaskStatus,
)

# Workflow
from agent_data.workflow.engine import WorkflowEngine
from agent_data.workflow.state import WorkflowState
from agent_data.workflow.step import FunctionStep, WorkflowStep

# Loop
from agent_data.loop import (
    AgentLoop,
    AgentResult,
    LoopRunner,
    LoopStatus,
    SimpleAgentLoop,
)

# Multi-Agent
from agent_data.multi_agent import (
    Agent,
    AgentMessage,
    AgentOrchestrator,
    AgentRole,
    WorkerAgent,
)

# MCP
from agent_data.mcp import DataQueryTool, MCPServer, MCPTool

# Import connectors to register them
import agent_data.connectors  # noqa: F401

__version__ = "0.1.0"
__all__ = [
    # Core
    "AgentDataClient",
    "AgentContext",
    "BaseConnector",
    "DataSource",
    "DataSourceConfig",
    "DataSourceType",
    "Query",
    "QueryFilter",
    "QueryResult",
    "QueryType",
    "register_connector",
    # Planning
    "CompositeTaskPlanner",
    "FunctionTaskExecutor",
    "PlanExecutor",
    "SimpleTaskPlanner",
    "Task",
    "TaskExecutor",
    "TaskPlan",
    "TaskPlanner",
    "TaskResult",
    "TaskStatus",
    # Workflow
    "FunctionStep",
    "WorkflowEngine",
    "WorkflowState",
    "WorkflowStep",
    # Loop
    "AgentLoop",
    "AgentResult",
    "LoopRunner",
    "LoopStatus",
    "SimpleAgentLoop",
    # Multi-Agent
    "Agent",
    "AgentMessage",
    "AgentOrchestrator",
    "AgentRole",
    "WorkerAgent",
    # MCP
    "DataQueryTool",
    "MCPServer",
    "MCPTool",
]
