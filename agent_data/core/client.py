"""
Main client for Agent Data framework.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Union

from agent_data.cache.base import BaseCache
from agent_data.cache.memory import MemoryCache
from agent_data.core.connector import BaseConnector, get_connector, list_connectors
from agent_data.core.errors import format_error
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
from agent_data.core.redact import redact
from agent_data.tracing.base import BaseTracer, TraceSpan
from agent_data.tracing.memory import MemoryTracer

# Planning imports
from agent_data.planning.task import Task, TaskPlan, TaskResult
from agent_data.planning.planner import TaskPlanner, SimpleTaskPlanner
from agent_data.planning.executor import FunctionTaskExecutor, PlanExecutor

# Workflow imports
from agent_data.workflow.step import WorkflowStep
from agent_data.workflow.engine import WorkflowEngine

# Loop imports
from agent_data.loop.agent_loop import AgentLoop, LoopRunner, AgentResult

# Multi-agent imports
from agent_data.multi_agent.orchestrator import AgentOrchestrator


class AgentDataClient:
    """Main client for accessing data sources in Agent applications."""

    def __init__(
        self,
        data_sources: Optional[List[DataSource]] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
        cache_max_size: int = 10000,
        trace_enabled: bool = True,
        cache: Optional[BaseCache] = None,
        tracer: Optional[BaseTracer] = None,
    ):
        """
        Initialize the client.

        Args:
            data_sources: List of data source configurations
            cache_enabled: Whether to enable caching
            cache_ttl: Default cache TTL in seconds
            cache_max_size: Maximum number of cached items
            trace_enabled: Whether to enable tracing
            cache: Custom cache implementation
            tracer: Custom tracer implementation
        """
        self._data_sources: Dict[str, DataSource] = {}
        self._connectors: Dict[str, BaseConnector] = {}
        self._connector_locks: Dict[str, asyncio.Lock] = {}
        # Top-level lock that protects _connector_locks itself; prevents two
        # concurrent first-time accesses from creating duplicate per-source locks.
        self._init_lock = asyncio.Lock()
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl
        self._trace_enabled = trace_enabled

        # Initialize cache
        self._cache = cache or MemoryCache(max_size=cache_max_size)

        # Initialize tracer
        self._tracer = tracer or MemoryTracer()

        # Register data sources
        if data_sources:
            for ds in data_sources:
                self._data_sources[ds.name] = ds

    @property
    def data_sources(self) -> Dict[str, DataSource]:
        """Get all registered data sources."""
        return self._data_sources.copy()

    def add_data_source(self, data_source: DataSource) -> None:
        """Add a data source."""
        self._data_sources[data_source.name] = data_source

    def remove_data_source(self, name: str) -> None:
        """Remove a data source."""
        self._data_sources.pop(name, None)
        self._connectors.pop(name, None)

    async def _get_connector(self, source_name: str) -> BaseConnector:
        """Get or create a connector for a data source.

        Two layers of locking:
        1. A top-level lock ensures only one per-source lock is created.
        2. Each source has its own lock so that concurrent first-time
           accesses for different sources don't serialize, while
           concurrent first-time accesses for the SAME source do — so we
           don't accidentally build two connectors (or two connection
           pools) for the same source.
        """
        if source_name in self._connectors:
            return self._connectors[source_name]

        async with self._init_lock:
            if source_name in self._connectors:
                return self._connectors[source_name]
            if source_name not in self._data_sources:
                raise ValueError(f"Data source '{source_name}' not found")
            if source_name not in self._connector_locks:
                self._connector_locks[source_name] = asyncio.Lock()

        source_lock = self._connector_locks[source_name]
        async with source_lock:
            # Re-check after acquiring the per-source lock.
            if source_name in self._connectors:
                return self._connectors[source_name]

            if source_name not in self._data_sources:
                raise ValueError(f"Data source '{source_name}' not found")

            data_source = self._data_sources[source_name]
            connector_class = get_connector(data_source.type)

            if connector_class is None:
                raise ValueError(
                    f"No connector registered for type '{data_source.type}'. "
                    f"Available: {list_connectors()}"
                )

            connector = connector_class(data_source.config)
            try:
                await connector.connect()
            except Exception:
                # Clean up the half-built connector so callers don't see a
                # `_connected=False` instance pinned in the cache.
                try:
                    await connector.disconnect()
                except Exception:
                    pass
                raise
            self._connectors[source_name] = connector
            return connector

    def _generate_cache_key(self, query: Query, context: Optional[AgentContext] = None) -> str:
        """Generate a cache key for a query.

        For natural-language queries (marked by _parse_natural_language via the
        'natural_language' metadata key), the raw text is excluded from the
        hash — any punctuation / whitespace change would otherwise defeat the
        cache. NL queries are bucketed by (source, query_type) only.
        """
        key_parts: Dict[str, Any] = {
            "source": query.source,
            "query_type": query.query_type,
            "filters": [f.model_dump() for f in query.filters] if query.filters else [],
            "fields": query.fields,
            "limit": query.limit,
            "offset": query.offset,
            "order_by": query.order_by,
        }
        # If the query originated from natural-language input, drop the raw
        # text from the cache key.
        if query.metadata.get("natural_language"):
            key_parts["query"] = None
        else:
            key_parts["query"] = query.query
        if context:
            key_parts["context"] = {
                "agent_id": context.agent_id,
                "session_id": context.session_id,
                "user_id": context.user_id,
            }
        return MemoryCache.generate_query_key(key_parts)

    async def query(
        self,
        query: Union[Query, str],
        context: Optional[AgentContext] = None,
        timeout: Optional[float] = None,
    ) -> QueryResult:
        """
        Execute a query against a data source.

        Args:
            query: Query object or natural language query string
            context: Agent context for context-aware caching
            timeout: Query timeout in seconds

        Returns:
            QueryResult with the query results
        """
        # Start trace span
        span = None
        if self._trace_enabled:
            span = await self._tracer.start_span(
                name="query",
                attributes={
                    "query_type": (
                        query.query_type if isinstance(query, Query) else "natural_language"
                    ),
                    "source": query.source if isinstance(query, Query) else "auto",
                    "has_context": context is not None,
                },
            )

        start_time = time.time()

        try:
            # Convert string query to Query object if needed
            if isinstance(query, str):
                query = await self._parse_natural_language(query, context)

            # Bind the new top-level span's trace id to the contextvar so any
            # nested spans opened by downstream layers inherit it.
            from agent_data.tracing.memory import set_active_trace_id

            trace_token = set_active_trace_id(span.trace_id) if span else None

            # Check cache
            cache_key = None
            if self._cache_enabled:
                cache_key = self._generate_cache_key(query, context)
                cached_result = await self._cache.get(cache_key)
                if cached_result is not None:
                    result = QueryResult(**cached_result)
                    result.cached = True
                    # cache hit 也填 query_time_ms,便于上层观测
                    if result.query_time_ms is None or result.query_time_ms == 0:
                        result.query_time_ms = (time.time() - start_time) * 1000
                    if span:
                        span.set_attribute("cache_hit", True)
                        await self._tracer.finish_span(span)
                    return result

            # Get connector and execute query
            connector = await self._get_connector(query.source)

            # Set timeout if specified
            if timeout:
                result = await asyncio.wait_for(connector.execute(query), timeout=timeout)
            else:
                result = await connector.execute(query)

            # Calculate query time
            query_time_ms = (time.time() - start_time) * 1000
            result.query_time_ms = query_time_ms

            # Cache result
            if self._cache_enabled and cache_key and not result.error:
                await self._cache.set(
                    cache_key,
                    result.model_dump(),
                    ttl=self._cache_ttl,
                )

            # Finish trace span
            if span:
                span.set_attribute("query_time_ms", query_time_ms)
                span.set_attribute("result_count", len(result.data))
                span.set_attribute("cache_hit", False)
                await self._tracer.finish_span(span)

            return result

        except asyncio.TimeoutError:
            error_msg = f"Query timed out after {timeout}s"
            if span:
                span.finish(status="error", error=error_msg)
            return QueryResult(
                source=query.source if isinstance(query, Query) else "unknown",
                error=error_msg,
                query_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            error_msg = redact(format_error(e))
            if span:
                span.finish(status="error", error=error_msg)
            return QueryResult(
                source=query.source if isinstance(query, Query) else "unknown",
                error=error_msg,
                query_time_ms=(time.time() - start_time) * 1000,
            )
        finally:
            # Reset the active trace id so it doesn't leak across queries.
            if trace_token is not None:
                from agent_data.tracing.memory import _active_trace_id

                _active_trace_id.reset(trace_token)

    async def batch_query(
        self,
        queries: List[Union[Query, str]],
        context: Optional[AgentContext] = None,
        parallel: bool = True,
    ) -> List[QueryResult]:
        """
        Execute multiple queries.

        Args:
            queries: List of queries to execute
            context: Agent context
            parallel: Whether to execute queries in parallel

        Returns:
            List of QueryResult objects
        """
        if parallel:
            tasks = [self.query(q, context) for q in queries]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for q in queries:
                result = await self.query(q, context)
                results.append(result)
            return results

    async def _parse_natural_language(
        self, text: str, context: Optional[AgentContext] = None
    ) -> Query:
        """
        Parse natural language into a Query object.

        This is a simple implementation that can be enhanced with LLM.
        """
        # Simple heuristic-based parsing
        # In production, this would use an LLM to generate structured queries

        # Try to find matching data source
        source = None
        for ds_name, ds in self._data_sources.items():
            if any(tag in text.lower() for tag in ds.tags):
                source = ds_name
                break

        # Default to first data source if no match
        if source is None and self._data_sources:
            source = list(self._data_sources.keys())[0]

        return Query(
            source=source or "default",
            query_type=QueryType.SEARCH,
            query=text,
            metadata={"natural_language": text},
        )

    async def get_data_sources(self) -> List[DataSource]:
        """Get all registered data sources."""
        return list(self._data_sources.values())

    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all data sources.

        Returns:
            Dictionary mapping data source names to health status
        """
        results = {}
        for name in self._data_sources:
            try:
                connector = await self._get_connector(name)
                results[name] = await connector.health_check()
            except Exception:
                results[name] = False
        return results

    async def close(self) -> None:
        """Close all connections."""
        for connector in self._connectors.values():
            try:
                await connector.disconnect()
            except Exception:
                pass
        self._connectors.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    # ==================== Planning Methods ====================

    async def execute_task(
        self,
        task: Task,
        executor: Optional[Callable] = None,
        context: Optional[AgentContext] = None,
    ) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task to execute
            executor: Async function to execute the task
            context: Agent context

        Returns:
            TaskResult
        """
        if executor is None:
            raise ValueError("Executor function required")

        # Start trace
        span = None
        if self._trace_enabled:
            span = await self._tracer.start_span(
                name="execute_task",
                attributes={"task_name": task.name, "task_id": task.id},
            )

        try:
            task.start()
            result = await executor(task.input_data)
            task_result = task.complete(output=result)

            if span:
                span.set_attribute("task_status", "completed")
                await self._tracer.finish_span(span)

            return task_result

        except Exception as e:
            task_result = task.fail(redact(format_error(e)))

            if span:
                span.set_attribute("task_status", "failed")
                await self._tracer.finish_span(span)

            return task_result

    async def execute_plan(
        self,
        plan: TaskPlan,
        executor: Callable,
        parallel: bool = True,
        max_concurrent: int = 5,
        context: Optional[AgentContext] = None,
    ) -> Dict[str, TaskResult]:
        """
        Execute a task plan.

        Args:
            plan: Task plan to execute
            executor: Async function to execute tasks
            parallel: Whether to execute tasks in parallel
            max_concurrent: Max parallel tasks (only used when parallel=True)
            context: Agent context

        Returns:
            Dictionary mapping task IDs to results
        """
        task_executor = FunctionTaskExecutor()
        for task in plan.tasks:
            task_executor.register(task.name, executor)

        plan_executor = PlanExecutor(task_executor, max_concurrent=max_concurrent)

        if parallel:
            return await plan_executor.execute(plan)
        else:
            return await plan_executor.execute_sequential(plan)

    # ==================== Workflow Methods ====================

    async def execute_workflow(
        self,
        steps: List[WorkflowStep],
        initial_state: Optional[Dict[str, Any]] = None,
        context: Optional[AgentContext] = None,
    ) -> Dict[str, Any]:
        """
        Execute a workflow.

        Args:
            steps: List of workflow steps
            initial_state: Initial workflow state
            context: Agent context

        Returns:
            Workflow execution results
        """
        # Start trace
        span = None
        if self._trace_enabled:
            span = await self._tracer.start_span(
                name="execute_workflow",
                attributes={"steps_count": len(steps)},
            )

        try:
            engine = WorkflowEngine()
            result = await engine.execute(steps, initial_state)

            if span:
                span.set_attribute("workflow_status", "completed")
                await self._tracer.finish_span(span)

            return result

        except Exception as e:
            if span:
                span.set_attribute("workflow_status", "failed")
                await self._tracer.finish_span(span)
            raise

    # ==================== Loop Methods ====================

    async def agent_loop(
        self,
        loop: AgentLoop,
        initial_state: Optional[Dict[str, Any]] = None,
        max_iterations: int = 100,
        timeout_seconds: Optional[float] = None,
        context: Optional[AgentContext] = None,
    ) -> AgentResult:
        """
        Run an agent loop.

        Args:
            loop: Agent loop to run
            initial_state: Initial state
            max_iterations: Maximum iterations
            timeout_seconds: Timeout in seconds
            context: Agent context

        Returns:
            AgentResult
        """
        # Start trace
        span = None
        if self._trace_enabled:
            span = await self._tracer.start_span(
                name="agent_loop",
                attributes={
                    "max_iterations": max_iterations,
                    "timeout": timeout_seconds,
                },
            )

        try:
            runner = LoopRunner(
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds,
            )
            result = await runner.run(loop, initial_state)

            if span:
                span.set_attribute("loop_status", result.status.value)
                span.set_attribute("iterations", result.iterations)
                await self._tracer.finish_span(span)

            return result

        except Exception as e:
            if span:
                span.set_attribute("loop_status", "failed")
                await self._tracer.finish_span(span)
            raise

    # ==================== Multi-Agent Methods ====================

    def create_orchestrator(self) -> AgentOrchestrator:
        """
        Create a new agent orchestrator.

        Returns:
            AgentOrchestrator instance
        """
        return AgentOrchestrator()
