"""Tracing module for Agent Data framework."""

from agent_data.tracing.base import BaseTracer, TraceSpan
from agent_data.tracing.memory import MemoryTracer

# OpenTelemetry tracer (optional)
try:
    from agent_data.tracing.opentelemetry import OpenTelemetryTracer

    __all__ = ["BaseTracer", "TraceSpan", "MemoryTracer", "OpenTelemetryTracer"]
except ImportError:
    __all__ = ["BaseTracer", "TraceSpan", "MemoryTracer"]
