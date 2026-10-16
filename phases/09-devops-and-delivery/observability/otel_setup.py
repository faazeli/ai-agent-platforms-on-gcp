"""Lab 9.7 — one trace from the agent to BigQuery.

Call ``configure_tracing("cost-api", app)`` at startup in each Python service.
Spans go to Cloud Trace; W3C trace context propagates through httpx calls, so a
single question shows up as one trace: agents → gateway → mcp-finops → cost-api.

    pip install opentelemetry-sdk opentelemetry-exporter-gcp-trace \
        opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx

On GKE the exporter authenticates with Workload Identity (the workload's GSA
needs roles/cloudtrace.agent; Phase 9's IAM module grants it to agents, add it
to the others too). Locally it uses your ADC.
"""

from __future__ import annotations

import os
from typing import Any


def configure_tracing(service_name: str, fastapi_app: Any | None = None, sample_ratio: float = 0.2) -> None:
    from opentelemetry import trace
    from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    resource = Resource.create({
        "service.name": service_name,
        "service.version": os.environ.get("SERVICE_VERSION", "dev"),
        "deployment.environment": os.environ.get("ENVIRONMENT", "dev"),
    })
    # Sample 20% of new traces, but always follow the caller's decision, so a trace
    # is either complete across services or absent; never half there.
    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(sample_ratio)))
    provider.add_span_processor(BatchSpanProcessor(CloudTraceSpanExporter()))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
    if fastapi_app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(fastapi_app, excluded_urls="healthz")


def trace_id_for_logs() -> str | None:
    """Put this in audit entries and Problem Details so logs, traces and errors join up."""
    from opentelemetry import trace

    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else None
