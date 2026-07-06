"""
Base tracer interface for observability.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class TraceSpan:
    """A single trace span representing an operation."""

    span_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: Optional[str] = None
    name: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ok"  # ok, error, cancelled
    error: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000

    def finish(self, status: str = "ok", error: Optional[str] = None) -> None:
        """Finish the span."""
        self.end_time = datetime.now()
        self.status = status
        self.error = error

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append(
            {
                "name": name,
                "timestamp": datetime.now().isoformat(),
                "attributes": attributes or {},
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error": self.error,
        }


class BaseTracer(ABC):
    """Base class for all tracer implementations."""

    @abstractmethod
    async def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Start a new trace span."""
        pass

    @abstractmethod
    async def finish_span(self, span: TraceSpan) -> None:
        """Finish a trace span."""
        pass

    @abstractmethod
    async def get_trace(self, trace_id: str) -> Optional[List[TraceSpan]]:
        """Get all spans for a trace."""
        pass

    @abstractmethod
    async def export(self, spans: List[TraceSpan]) -> None:
        """Export spans to external system."""
        pass