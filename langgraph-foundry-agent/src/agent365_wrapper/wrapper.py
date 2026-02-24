"""Agent365-wrapped LangGraph agent.

This is the integration layer that wraps the LangGraph agent (which contains
all the actual agent logic) with the Microsoft Agent 365 SDK. The wrapper:

1. Registers with Agent 365 on startup (Entra-backed identity, observability)
2. Delegates ALL agent invocations to the LangGraph graph
3. Correlates OpenTelemetry traces with Foundry sessions
4. Reports activity completions back through Agent 365
5. Deregisters on shutdown

The LangGraph agent itself (src/agent/) has ZERO knowledge of Agent 365.
This is the clean boundary between "agent logic" and "platform integration."
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ..agent.graph import run_agent
from ..tracing.foundry_tracing import FoundryTracer
from .sdk import Agent365Client, Agent365Config

logger = logging.getLogger(__name__)


class Agent365WrappedAgent:
    """LangGraph agent wrapped with Microsoft Agent 365 SDK.

    Usage:
        agent = Agent365WrappedAgent()
        await agent.startup()
        response = await agent.invoke("What can you do?")
        await agent.shutdown()
    """

    def __init__(self, config: Agent365Config | None = None):
        self.config = config or Agent365Config()
        self._client = Agent365Client(self.config)
        self._tracer = FoundryTracer()
        self._is_running = False

    async def startup(self) -> dict[str, Any]:
        """Register with Agent 365 and mark the agent as active."""
        result = await self._client.register()
        self._is_running = True
        logger.info(
            "Agent365WrappedAgent started: %s (%s) [mode=%s]",
            self.config.display_name,
            self.config.agent_id,
            result.get("mode", "unknown"),
        )
        return result

    async def invoke(self, user_input: str, session_id: str | None = None) -> dict[str, Any]:
        """Invoke the LangGraph agent with Agent365 tracing.

        Flow:
        1. Create a Foundry-correlated tracing span
        2. Delegate to run_agent() (the LangGraph graph - actual agent logic)
        3. Report activity through Agent 365
        4. Return response with tracing metadata
        """
        session_id = session_id or uuid.uuid4().hex
        span = self._tracer.start_session_span(session_id, user_input)

        try:
            # ===== THIS IS WHERE THE LANGGRAPH AGENT RUNS =====
            response = await run_agent(user_input, session_id)
            # ===================================================

            self._tracer.end_session_span(span, response)

            # Extract trace ID for Foundry correlation
            span_context = span.get_span_context()
            trace_id = format(span_context.trace_id, "032x") if span_context else "no-trace"

            # Report through Agent 365 SDK
            await self._client.report_activity(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                agent_output=response,
            )

            return {
                "response": response,
                "session_id": session_id,
                "trace_id": trace_id,
                "agent_id": self.config.agent_id,
                "model": self.config.model_deployment,
            }

        except Exception as exc:
            self._tracer.record_error(span, exc)
            await self._client.report_activity(
                session_id=session_id,
                trace_id="error",
                user_input=user_input,
                agent_output=str(exc),
                status="error",
            )
            raise

    async def health(self) -> dict[str, Any]:
        """Return agent health status."""
        return {
            "agent_id": self.config.agent_id,
            "display_name": self.config.display_name,
            "framework": "langgraph",
            "model": self.config.model_deployment,
            "status": "active" if self._is_running else "inactive",
            "capabilities": self.config.capabilities,
        }

    async def shutdown(self) -> None:
        """Deregister from Agent 365 and clean up."""
        self._is_running = False
        await self._client.shutdown()
        logger.info("Agent365WrappedAgent shut down: %s", self.config.agent_id)
