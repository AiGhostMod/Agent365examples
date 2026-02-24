"""Azure AI Foundry tracing integration.

Sets up the full observability pipeline for the LangGraph agent:

1. azure-ai-projects enable_telemetry() - instruments the Foundry SDK calls
2. OpenTelemetry SDK - collects spans with gen_ai semantic conventions
3. Azure Monitor exporter - sends traces to Application Insights
4. Foundry portal reads traces from App Insights for its agent monitoring UI

The trace attributes follow the OpenTelemetry Semantic Conventions for
Generative AI, plus the multi-agent conventions co-developed by Microsoft
and Cisco/Outshift.

References:
    https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/trace-agent-setup
    https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/trace-agents-sdk
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
    service_name: str = "langgraph-foundry-agent",
    service_version: str = "0.1.0",
) -> TracerProvider:
    """Initialize the full Foundry tracing pipeline.

    Pipeline:
        azure-ai-projects telemetry -> OpenTelemetry SDK -> Azure Monitor -> App Insights -> Foundry portal
    """
    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    # Step 1: Enable azure-ai-projects built-in telemetry
    try:
        from azure.ai.projects import enable_telemetry

        content_recording = os.environ.get(
            "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false"
        ).lower() == "true"
        enable_telemetry(enable_content_recording=content_recording)
        logger.info("azure-ai-projects telemetry enabled (content_recording=%s)", content_recording)
    except ImportError:
        logger.debug("azure-ai-projects not available; skipping SDK-level telemetry")

    # Step 2: Enable azure-core OpenTelemetry tracing
    try:
        from azure.core.settings import settings as azure_settings

        azure_settings.tracing_implementation = "opentelemetry"
    except ImportError:
        pass

    # Step 3: Configure OpenTelemetry TracerProvider
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "ai.foundry.agent_type": "langgraph",
            "ai.foundry.model_deployment": os.environ.get(
                "AZURE_AI_FOUNDRY_DEPLOYMENT", "gpt-5.2"
            ),
        }
    )
    provider = TracerProvider(resource=resource)

    # Step 4: Azure Monitor exporter -> Application Insights
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
            # Fallback: set up the provider manually with the exporter
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

    # Step 5: Optional console exporter for local debugging
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
    - agent.session.id, agent.graph.node.name (Foundry/multi-agent semconv)
    """

    def __init__(self, tracer_name: str = "foundry.langgraph.agent"):
        self._tracer = trace.get_tracer(tracer_name)

    def start_session_span(self, session_id: str, user_input: str) -> Span:
        """Start a top-level span for an agent session."""
        _current_session.set(session_id)
        span = self._tracer.start_span(
            "agent.session",
            attributes={
                "agent.session.id": session_id,
                "agent.framework": "langgraph",
                "gen_ai.system": "azure_ai_foundry",
                "gen_ai.request.model": os.environ.get(
                    "AZURE_AI_FOUNDRY_DEPLOYMENT", "gpt-5.2"
                ),
                "agent.input.text": user_input[:500],
            },
        )
        return span

    def trace_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        messages_count: int,
    ) -> Span:
        """Record an LLM inference call with gen_ai semantic conventions."""
        span = self._tracer.start_span(
            "gen_ai.chat.completions",
            attributes={
                "gen_ai.system": "azure_ai_foundry",
                "gen_ai.request.model": model,
                "gen_ai.response.model": model,
                "gen_ai.usage.prompt_tokens": prompt_tokens,
                "gen_ai.usage.completion_tokens": completion_tokens,
                "gen_ai.request.messages_count": messages_count,
            },
        )
        span.end()
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

    def trace_graph_node(self, node_name: str) -> Span:
        """Record execution of a LangGraph node."""
        span = self._tracer.start_span(
            "agent.graph.node",
            attributes={
                "agent.graph.node.name": node_name,
                "agent.framework": "langgraph",
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
