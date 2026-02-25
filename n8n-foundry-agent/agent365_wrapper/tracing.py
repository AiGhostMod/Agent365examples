"""Azure AI Foundry tracing for the n8n agent.

Sets up OpenTelemetry with Azure Monitor exporter so that n8n agent
invocations appear in Application Insights and the Foundry portal.

The trace attributes follow the OpenTelemetry Semantic Conventions for
Generative AI and the Foundry multi-agent conventions.

References:
    https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/trace-agent-setup
    https://learn.microsoft.com/en-us/azure/ai-foundry/observability/concepts/trace-agent-concept
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, StatusCode

logger = logging.getLogger(__name__)

_current_session: ContextVar[str | None] = ContextVar("current_session", default=None)


def setup_tracing(
    service_name: str = "n8n-foundry-agent",
    service_version: str = "0.1.0",
) -> TracerProvider:
    """Initialize the Foundry tracing pipeline.

    Pipeline:
        OpenTelemetry SDK -> Azure Monitor Exporter -> Application Insights -> Foundry portal
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "ai.foundry.agent_type": "n8n",
            "ai.foundry.model_deployment": os.environ.get(
                "AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"
            ),
        }
    )
    provider = TracerProvider(resource=resource)

    if connection_string:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=connection_string)
            logger.info("Azure Monitor configured; traces will appear in Application Insights")
        except ImportError:
            logger.warning(
                "azure-monitor-opentelemetry not installed; "
                "install it for Application Insights integration"
            )
            try:
                from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

                exporter = AzureMonitorTraceExporter(connection_string=connection_string)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except ImportError:
                pass
    else:
        logger.info(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set; "
            "tracing active locally only (set it to export to Foundry portal)"
        )

    if os.environ.get("FOUNDRY_TRACE_DEBUG"):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.info("Console trace exporter enabled (FOUNDRY_TRACE_DEBUG=1)")

    trace.set_tracer_provider(provider)
    return provider


class FoundryTracer:
    """Emits spans with Azure AI Foundry and gen_ai semantic conventions.

    Attribute conventions:
    - gen_ai.system, gen_ai.request.model, gen_ai.usage.* (OpenTelemetry GenAI semconv)
    - agent.session.id (Foundry/multi-agent semconv)
    """

    def __init__(self, tracer_name: str = "foundry.n8n.agent"):
        self._tracer = trace.get_tracer(tracer_name)

    def start_session_span(self, session_id: str, user_input: str) -> Span:
        """Start a top-level span for an agent session."""
        _current_session.set(session_id)
        span = self._tracer.start_span(
            "agent.session",
            attributes={
                "agent.session.id": session_id,
                "agent.framework": "n8n",
                "gen_ai.system": "azure_ai_foundry",
                "gen_ai.request.model": os.environ.get(
                    "AZURE_OPENAI_DEPLOYMENT", "gpt-5.2"
                ),
                "agent.input.text": user_input[:500],
            },
        )
        return span

    def trace_tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> Span:
        """Record a tool invocation."""
        span = self._tracer.start_span(
            "agent.tool.invoke",
            attributes={
                "tool.name": tool_name,
                "tool.input.keys": str(list(tool_input.keys())),
                "agent.session.id": _current_session.get("unknown"),
            },
        )
        return span

    def record_error(self, span: Span, error: Exception) -> None:
        """Mark a span as errored."""
        span.set_status(StatusCode.ERROR, str(error))
        span.record_exception(error)
        span.end()

    def end_session_span(self, span: Span, output: str) -> None:
        """Close a session span with the agent's output."""
        span.set_attribute("agent.output.text", output[:500])
        span.set_status(StatusCode.OK)
        span.end()
