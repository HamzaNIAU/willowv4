"""
OpenTelemetry instrumentation for Veo3 MCP service.

This module provides tracing, metrics, and logging capabilities
for monitoring and observability of the Veo3 service.
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager, asynccontextmanager
from functools import wraps

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)


class TelemetryManager:
    """Manages OpenTelemetry instrumentation for the service."""
    
    def __init__(
        self,
        service_name: str = "veo3-mcp",
        service_version: str = "1.0.0",
        exporter_endpoint: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize telemetry manager.
        
        Args:
            service_name: Name of the service
            service_version: Version of the service
            exporter_endpoint: OTLP exporter endpoint
            enabled: Whether telemetry is enabled
        """
        self.service_name = service_name
        self.service_version = service_version
        self.exporter_endpoint = exporter_endpoint or os.getenv(
            "OTEL_EXPORTER_ENDPOINT", "http://localhost:4317"
        )
        self.enabled = enabled and os.getenv("OTEL_ENABLED", "true").lower() == "true"
        
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
        self._initialized = False
        
        # Metrics
        self.video_generation_counter = None
        self.video_generation_duration = None
        self.operation_status_counter = None
        self.active_operations_gauge = None
        
        if self.enabled:
            self.initialize()
    
    def initialize(self):
        """Initialize OpenTelemetry providers and exporters."""
        if self._initialized:
            return
        
        try:
            # Create resource
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": self.service_version,
                "service.namespace": "veo3",
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            })
            
            # Initialize tracing
            self._init_tracing(resource)
            
            # Initialize metrics
            self._init_metrics(resource)
            
            # Initialize instrumentation
            self._init_instrumentation()
            
            self._initialized = True
            logger.info(f"OpenTelemetry initialized for {self.service_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            self.enabled = False
    
    def _init_tracing(self, resource: Resource):
        """Initialize tracing provider and exporter."""
        # Create OTLP span exporter
        span_exporter = OTLPSpanExporter(
            endpoint=self.exporter_endpoint,
            insecure=True  # For local development
        )
        
        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)
        
        # Add span processor
        span_processor = BatchSpanProcessor(span_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(
            self.service_name,
            self.service_version
        )
    
    def _init_metrics(self, resource: Resource):
        """Initialize metrics provider and exporter."""
        # Create OTLP metric exporter
        metric_exporter = OTLPMetricExporter(
            endpoint=self.exporter_endpoint,
            insecure=True  # For local development
        )
        
        # Create metric reader
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=60000  # Export every minute
        )
        
        # Create meter provider
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        )
        
        # Set global meter provider
        metrics.set_meter_provider(meter_provider)
        
        # Get meter
        self.meter = metrics.get_meter(
            self.service_name,
            self.service_version
        )
        
        # Create metrics
        self._create_metrics()
    
    def _create_metrics(self):
        """Create application-specific metrics."""
        if not self.meter:
            return
        
        # Counter for video generations
        self.video_generation_counter = self.meter.create_counter(
            name="veo3.video.generations",
            description="Number of video generation requests",
            unit="1"
        )
        
        # Histogram for generation duration
        self.video_generation_duration = self.meter.create_histogram(
            name="veo3.video.generation.duration",
            description="Duration of video generation operations",
            unit="s"
        )
        
        # Counter for operation status
        self.operation_status_counter = self.meter.create_counter(
            name="veo3.operation.status",
            description="Count of operations by status",
            unit="1"
        )
        
        # Gauge for active operations
        self.active_operations_gauge = self.meter.create_up_down_counter(
            name="veo3.operations.active",
            description="Number of active operations",
            unit="1"
        )
    
    def _init_instrumentation(self):
        """Initialize automatic instrumentation for libraries."""
        # FastAPI instrumentation
        FastAPIInstrumentor.instrument(
            tracer_provider=trace.get_tracer_provider(),
            meter_provider=metrics.get_meter_provider()
        )
        
        # HTTPX client instrumentation
        HTTPXClientInstrumentor.instrument(
            tracer_provider=trace.get_tracer_provider()
        )
        
        # Logging instrumentation
        LoggingInstrumentor().instrument(set_logging_format=True)
    
    @contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL
    ):
        """
        Create a traced span context manager.
        
        Args:
            name: Span name
            attributes: Span attributes
            kind: Span kind
        
        Yields:
            Span object
        """
        if not self.enabled or not self.tracer:
            yield None
            return
        
        with self.tracer.start_as_current_span(
            name,
            kind=kind,
            attributes=attributes or {}
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    @asynccontextmanager
    async def async_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL
    ):
        """
        Create an async traced span context manager.
        
        Args:
            name: Span name
            attributes: Span attributes
            kind: Span kind
        
        Yields:
            Span object
        """
        if not self.enabled or not self.tracer:
            yield None
            return
        
        with self.tracer.start_as_current_span(
            name,
            kind=kind,
            attributes=attributes or {}
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
    
    def trace_method(self, name: Optional[str] = None):
        """
        Decorator to trace a method.
        
        Args:
            name: Optional span name (defaults to function name)
        
        Returns:
            Decorated function
        """
        def decorator(func):
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    async with self.async_span(span_name):
                        return await func(*args, **kwargs)
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.span(span_name):
                        return func(*args, **kwargs)
                return sync_wrapper
        
        return decorator
    
    def record_video_generation(
        self,
        model: str,
        mode: str,
        duration: float,
        status: str,
        num_videos: int = 1
    ):
        """
        Record video generation metrics.
        
        Args:
            model: Model name used
            mode: Generation mode (text_to_video, image_to_video)
            duration: Duration of generation in seconds
            status: Operation status
            num_videos: Number of videos generated
        """
        if not self.enabled:
            return
        
        attributes = {
            "model": model,
            "mode": mode,
            "status": status,
            "num_videos": num_videos
        }
        
        # Increment generation counter
        if self.video_generation_counter:
            self.video_generation_counter.add(num_videos, attributes)
        
        # Record duration
        if self.video_generation_duration:
            self.video_generation_duration.record(duration, attributes)
        
        # Record operation status
        if self.operation_status_counter:
            self.operation_status_counter.add(1, {"status": status})
    
    def update_active_operations(self, delta: int):
        """
        Update active operations gauge.
        
        Args:
            delta: Change in active operations (+1 for new, -1 for completed)
        """
        if not self.enabled or not self.active_operations_gauge:
            return
        
        self.active_operations_gauge.add(delta)
    
    def shutdown(self):
        """Shutdown OpenTelemetry providers."""
        if not self._initialized:
            return
        
        try:
            # Shutdown tracer provider
            tracer_provider = trace.get_tracer_provider()
            if hasattr(tracer_provider, 'shutdown'):
                tracer_provider.shutdown()
            
            # Shutdown meter provider
            meter_provider = metrics.get_meter_provider()
            if hasattr(meter_provider, 'shutdown'):
                meter_provider.shutdown()
            
            logger.info("OpenTelemetry shutdown complete")
        except Exception as e:
            logger.error(f"Error during OpenTelemetry shutdown: {e}")


# Global telemetry manager instance
_telemetry_manager: Optional[TelemetryManager] = None


def init_telemetry(
    service_name: str = "veo3-mcp",
    service_version: str = "1.0.0",
    enabled: bool = True
) -> TelemetryManager:
    """
    Initialize global telemetry manager.
    
    Args:
        service_name: Service name
        service_version: Service version
        enabled: Whether telemetry is enabled
    
    Returns:
        Telemetry manager instance
    """
    global _telemetry_manager
    
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager(
            service_name=service_name,
            service_version=service_version,
            enabled=enabled
        )
    
    return _telemetry_manager


def get_telemetry() -> Optional[TelemetryManager]:
    """Get global telemetry manager instance."""
    return _telemetry_manager


def shutdown_telemetry():
    """Shutdown global telemetry manager."""
    global _telemetry_manager
    
    if _telemetry_manager:
        _telemetry_manager.shutdown()
        _telemetry_manager = None


# Convenience decorators
def trace_span(name: Optional[str] = None):
    """
    Decorator to trace a function with a span.
    
    Args:
        name: Optional span name
    
    Returns:
        Decorated function
    """
    def decorator(func):
        telemetry = get_telemetry()
        if telemetry:
            return telemetry.trace_method(name)(func)
        return func
    
    return decorator


# Import asyncio only if needed for async detection
import asyncio