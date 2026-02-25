"""Agent365 wrapper around the n8n agent workflow.

Architecture:
    Client -> Agent365 Wrapper (FastAPI, port 8001)
           -> n8n webhook (port 5678, /webhook/agent)
           -> n8n AI Agent workflow (Azure OpenAI GPT 5.2)
           -> Response flows back through wrapper with tracing

The n8n workflow contains ALL the agent logic (LLM calls, tool use, memory).
This wrapper adds Agent 365 SDK lifecycle management and Foundry tracing
around each invocation - it does NOT modify the agent behavior.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import httpx

from .sdk import Agent365Client, Agent365Config
from .tracing import FoundryTracer

logger = logging.getLogger(__name__)


class Agent365WrappedN8nAgent:
    """An n8n agent wrapped with Microsoft Agent 365 SDK.

    Usage:
        agent = Agent365WrappedN8nAgent()
        await agent.startup()
        response = await agent.invoke("Hello, what can you do?")
        await agent.shutdown()
    """

    def __init__(self, config: Agent365Config | None = None):
        self.config = config or Agent365Config()
        self._client = Agent365Client(self.config)
        self._tracer = FoundryTracer()
        self._http = httpx.AsyncClient(timeout=60.0)
        self._is_running = False
        self._n8n_webhook_url = os.environ.get(
            "N8N_WEBHOOK_URL",
            f"http://localhost:{os.environ.get('N8N_PORT', '5678')}/webhook/agent",
        )

    async def startup(self) -> dict[str, Any]:
        """Register with Agent 365 and mark the agent as active."""
        result = await self._client.register()
        self._is_running = True
        logger.info(
            "Agent365WrappedN8nAgent started: %s (%s) [mode=%s]",
            self.config.display_name,
            self.config.agent_id,
            result.get("mode", "unknown"),
        )
        return result

    async def invoke(self, user_input: str, session_id: str | None = None) -> dict[str, Any]:
        """Invoke the n8n agent workflow with Agent365 tracing.

        Flow:
        1. Create a Foundry-correlated tracing span
        2. Forward the request to the n8n webhook (actual agent logic)
        3. Report activity through Agent 365
        4. Return response with tracing metadata
        """
        session_id = session_id or uuid.uuid4().hex
        span = self._tracer.start_session_span(session_id, user_input)

        try:
            # ===== FORWARD TO N8N (WHERE THE AGENT LOGIC RUNS) =====
            n8n_response = await self._http.post(
                self._n8n_webhook_url,
                json={"message": user_input, "sessionId": session_id},
            )
            n8n_response.raise_for_status()
            result = n8n_response.json()
            # ========================================================

            agent_output = result.get("response") or result.get("output") or json.dumps(result)

            self._tracer.end_session_span(span, agent_output)

            span_context = span.get_span_context()
            trace_id = format(span_context.trace_id, "032x") if span_context else "no-trace"

            await self._client.report_activity(
                session_id=session_id,
                trace_id=trace_id,
                user_input=user_input,
                agent_output=agent_output,
            )

            return {
                "response": agent_output,
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
            "framework": "n8n",
            "model": self.config.model_deployment,
            "status": "active" if self._is_running else "inactive",
            "capabilities": self.config.capabilities,
            "n8n_webhook": self._n8n_webhook_url,
        }

    async def shutdown(self) -> None:
        """Deregister from Agent 365 and clean up."""
        self._is_running = False
        await self._client.shutdown()
        await self._http.aclose()
        logger.info("Agent365WrappedN8nAgent shut down: %s", self.config.agent_id)
