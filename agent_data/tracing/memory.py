"""
In-memory tracer implementation for development and testing.
"""

import asyncio
from collections import defaultdict
from typing import Any, Dict, List, Optional

from agent_data.tracing.base import BaseTracer, TraceSpan


class MemoryTracer(BaseTracer):
    """In-memory tracer for development and testing."""

    def __init__(self):
        self._traces: Dict[str, List[TraceSpan]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Start a new trace span."""
        span = TraceSpan(
            name=name,
            parent_id=parent_id,
            attributes=attributes or {},
        )
        async with self._lock:
            self._traces[span.trace_id].append(span)
        return span

    async def finish_span(self, span: TraceSpan) -> None:
        """Finish a trace span."""
        span.finish()

    async def get_trace(self, trace_id: str) -> Optional[List[TraceSpan]]:
        """Get all spans for a trace."""
        async with self._lock:
            return self._traces.get(trace_id)

    async def export(self, spans: List[TraceSpan]) -> None:
        """Export spans (no-op for memory tracer)."""
        pass

    def get_all_traces(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all traces as dictionaries (for debugging)."""
        return {
            trace_id: [span.to_dict() for span in spans]
            for trace_id, spans in self._traces.items()
        }

    def clear(self) -> None:
        """Clear all traces."""
        self._traces.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get tracer statistics."""
        total_spans = sum(len(spans) for spans in self._traces.values())
        total_traces = len(self._traces)
        error_spans = sum(
            1
            for spans in self._traces.values()
            for span in spans
            if span.status == "error"
        )
        return {
            "total_traces": total_traces,
            "total_spans": total_spans,
            "error_spans": error_spans,
        }