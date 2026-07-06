"""
OpenTelemetry tracer implementation.
"""

from typing import Any, Dict, List, Optional

from agent_data.tracing.base import BaseTracer, TraceSpan

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import StatusCode, Status

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False


class OpenTelemetryTracer(BaseTracer):
    """OpenTelemetry tracer implementation for production observability."""

    def __init__(
        self,
        service_name: str = "agent-data",
        endpoint: Optional[str] = None,
        sample_rate: float = 1.0,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize OpenTelemetry tracer.

        Args:
            service_name: Name of the service
            endpoint: OTLP endpoint for exporting traces (e.g., "http://localhost:4317")
            sample_rate: Sampling rate (0.0 to 1.0)
            attributes: Additional resource attributes
        """
        if not OPENTELEMETRY_AVAILABLE:
            raise ImportError(
                "opentelemetry is required for OpenTelemetry tracer. "
                "Install it with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )

        # Create resource
        resource_attributes = {
            "service.name": service_name,
            "service.version": "0.1.0",
        }
        if attributes:
            resource_attributes.update(attributes)

        resource = Resource.create(resource_attributes)

        # Create tracer provider
        self._provider = TracerProvider(resource=resource, sampler=trace.sampling.TraceIdRatioBased(sample_rate))

        # Add exporter if endpoint is provided
        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                exporter = OTLPSpanExporter(endpoint=endpoint)
                self._provider.add_span_processor(BatchSpanProcessor(exporter))
            except ImportError:
                # Fallback to console exporter
                console_exporter = ConsoleSpanExporter()
                self._provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(self._provider)

        # Get tracer
        self._tracer = trace.get_tracer(service_name)

    async def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TraceSpan:
        """Start a new trace span using OpenTelemetry."""
        # Create OpenTelemetry span
        otel_attributes = attributes or {}
        otel_span = self._tracer.start_span(name=name, attributes=otel_attributes)

        # Create our TraceSpan
        span = TraceSpan(
            name=name,
            attributes=attributes or {},
        )

        # Store OTel span reference
        span._otel_span = otel_span

        return span

    async def finish_span(self, span: TraceSpan) -> None:
        """Finish a trace span."""
        span.finish()

        # Finish OpenTelemetry span
        otel_span = getattr(span, "_otel_span", None)
        if otel_span:
            if span.status == "error":
                otel_span.set_status(Status(StatusCode.ERROR, span.error or "Unknown error"))
                if span.error:
                    otel_span.record_exception(Exception(span.error))
            else:
                otel_span.set_status(Status(StatusCode.OK))

            # Add events
            for event in span.events:
                otel_span.add_event(event["name"], event.get("attributes", {}))

            otel_span.end()

    async def get_trace(self, trace_id: str) -> Optional[List[TraceSpan]]:
        """Get trace spans (not implemented for OpenTelemetry - use external tools)."""
        # OpenTelemetry traces are exported to external systems
        # Use Jaeger, Zipkin, or other backends to query traces
        return None

    async def export(self, spans: List[TraceSpan]) -> None:
        """Export spans (handled automatically by OpenTelemetry processor)."""
        pass

    def shutdown(self) -> None:
        """Shutdown the tracer provider."""
        if self._provider:
            self._provider.shutdown()