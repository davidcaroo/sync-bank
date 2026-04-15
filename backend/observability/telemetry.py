from __future__ import annotations

import logging

from config import settings

logger = logging.getLogger("telemetry")


def init_telemetry() -> None:
    if not settings.OTEL_ENABLED:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("otel_disabled_missing_dependencies")
        return

    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    if not endpoint:
        logger.warning("otel_disabled_missing_endpoint")
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.namespace": "syncbank",
            }
        )
    )
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    logger.info("otel_enabled", extra={"endpoint": endpoint})


def get_tracer(name: str):
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return None
