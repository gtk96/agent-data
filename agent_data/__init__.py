"""
Agent Data Orchestration Framework

A unified data access layer for AI Agent applications.
"""

from agent_data.core.models import (
    DataSource,
    DataSourceConfig,
    DataSourceType,
    Query,
    QueryType,
    QueryFilter,
    QueryResult,
    AgentContext,
)
from agent_data.core.client import AgentDataClient
from agent_data.core.connector import BaseConnector, register_connector

# Planning
from agent_data.planning.task import Task, TaskStatus, TaskResult, TaskPlan
from agent_data.planning.planner import TaskPlanner, SimpleTaskPlanner
from agent_data.planning.executor import TaskExecutor, PlanExecutor

# Workflow
from agent_data.workflow.step import WorkflowStep, FunctionStep
from agent_data.workflow.state import WorkflowState
from agent_data.workflow.engine import WorkflowEngine

# Loop
from agent_data.loop.agent_loop import AgentLoop, AgentResult, LoopRunner

# Multi-Agent
from agent_data.multi_agent.agent import Agent, AgentRole, WorkerAgent
from agent_data.multi_agent.orchestrator import AgentOrchestrator

# MCP
from agent_data.mcp.server import MCPServer
from agent_data.mcp.tool import MCPTool

# Import connectors to register them
import agent_data.connectors

__version__ = "0.1.0"
__all__ = [
    # Core
    "AgentDataClient",
    "DataSource",
    "DataSourceConfig",
    "DataSourceType",
    "Query",
    "QueryType",
    "QueryFilter",
    "QueryResult",
    "AgentContext",
    "BaseConnector",
    "register_connector",
    # Planning
    "Task",
    "TaskStatus",
    "TaskResult",
    "TaskPlan",
    "TaskPlanner",
    "SimpleTaskPlanner",
    "TaskExecutor",
    "PlanExecutor",
    # Workflow
    "WorkflowStep",
    "FunctionStep",
    "WorkflowState",
    "WorkflowEngine",
    # Loop
    "AgentLoop",
    "AgentResult",
    "LoopRunner",
    # Multi-Agent
    "Agent",
    "AgentRole",
    "AgentOrchestrator",
]