"""n8n Foundry Agent - Agent365 server.

Single-file server that:
1. Sets up OpenTelemetry tracing -> Azure Monitor -> Foundry portal
2. Registers with Microsoft Agent 365 SDK on startup
3. Exposes /invoke and /health endpoints for Foundry to route traffic to
4. Proxies requests to the n8n webhook (where all agent logic runs)

Run:  python agent365_server.py
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import StatusCode
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (all from env)
# ---------------------------------------------------------------------------
AGENT_ID = os.environ.get("AGENT365_AGENT_ID", "n8n-foundry-agent-001")
AGENT_NAME = os.environ.get("AGENT365_AGENT_DISPLAY_NAME", "n8n Foundry Agent")
MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
N8N_WEBHOOK = os.environ.get(
    "N8N_WEBHOOK_URL",
    f"http://localhost:{os.environ.get('N8N_PORT', '5678')}/webhook/agent",
)
PORT = int(os.environ.get("WRAPPER_PORT", "8001"))

# ---------------------------------------------------------------------------
# Tracing  (OTel -> Azure Monitor -> App Insights -> Foundry portal)
# ---------------------------------------------------------------------------
_tracer: trace.Tracer | None = None


def _setup_tracing() -> None:
    global _tracer

    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")

    resource = Resource.create({
        "service.name": "n8n-foundry-agent",
        "service.version": "0.1.0",
        "ai.foundry.agent_type": "n8n",
        "ai.foundry.model_deployment": MODEL,
    })
    provider = TracerProvider(resource=resource)

    # Azure Monitor exporter
    if conn:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(connection_string=conn)
            logger.info("Traces -> Application Insights")
        except ImportError:
            try:
                from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

                provider.add_span_processor(BatchSpanProcessor(
                    AzureMonitorTraceExporter(connection_string=conn)
                ))
            except ImportError:
                logger.warning("No Azure Monitor exporter installed; traces are local only")

    # Console exporter for local debugging
    if os.environ.get("FOUNDRY_TRACE_DEBUG"):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("foundry.n8n.agent")


# ---------------------------------------------------------------------------
# Agent 365 registration  (try SDK, fall back to standalone)
# ---------------------------------------------------------------------------
_agent_host = None


async def _register_agent365() -> dict[str, Any]:
    global _agent_host
    try:
        from microsoft.agents.a365.hosting import AgentHost, AgentHostConfig
        from microsoft.agents.a365.observability import (
            ObservabilityConfig,
            enable_agent_observability,
        )

        cfg = AgentHostConfig(
            agent_id=AGENT_ID,
            display_name=AGENT_NAME,
            tenant_id=os.environ.get("AGENT365_TENANT_ID", ""),
            client_id=os.environ.get("AGENT365_CLIENT_ID", ""),
            client_secret=os.environ.get("AGENT365_CLIENT_SECRET", ""),
            description="n8n workflow agent on Azure AI Foundry GPT 5.2",
            capabilities=["chat", "tool_use", "knowledge_search", "task_creation"],
        )
        _agent_host = AgentHost(config=cfg)
        await _agent_host.start()

        enable_agent_observability(ObservabilityConfig(
            enable_tracing=True,
            enable_metrics=True,
            connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
        ))

        logger.info("Registered with Agent 365: %s", AGENT_ID)
        return {"agent_id": AGENT_ID, "status": "registered", "mode": "agent365_sdk"}

    except ImportError:
        logger.warning(
            "microsoft-agents-a365 not installed (Frontier preview); running standalone"
        )
        return {"agent_id": AGENT_ID, "status": "standalone", "mode": "standalone"}


async def _deregister_agent365() -> None:
    if _agent_host:
        try:
            await _agent_host.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HTTP client for proxying to n8n
# ---------------------------------------------------------------------------
_http: httpx.AsyncClient | None = None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _http
    _setup_tracing()
    _http = httpx.AsyncClient(timeout=60.0)
    reg = await _register_agent365()
    logger.info("Startup complete: %s  (n8n webhook: %s)", reg, N8N_WEBHOOK)
    yield
    await _deregister_agent365()
    if _http:
        await _http.aclose()


app = FastAPI(title="n8n Foundry Agent", version="0.1.0", lifespan=lifespan)


class InvokeRequest(BaseModel):
    message: str
    session_id: str | None = None


class InvokeResponse(BaseModel):
    response: str
    session_id: str
    trace_id: str
    agent_id: str
    model: str


@app.post("/invoke", response_model=InvokeResponse)
async def invoke(req: InvokeRequest):
    session_id = req.session_id or uuid.uuid4().hex

    span = _tracer.start_span("agent.session", attributes={
        "agent.session.id": session_id,
        "agent.framework": "n8n",
        "gen_ai.system": "azure_ai_foundry",
        "gen_ai.request.model": MODEL,
        "agent.input.text": req.message[:500],
    }) if _tracer else None

    try:
        # Forward to n8n webhook (where ALL agent logic runs)
        r = await _http.post(N8N_WEBHOOK, json={"message": req.message, "sessionId": session_id})
        r.raise_for_status()
        result = r.json()
        response = result.get("response") or result.get("output") or json.dumps(result)

        trace_id = "no-trace"
        if span:
            span.set_attribute("agent.output.text", response[:500])
            span.set_status(StatusCode.OK)
            ctx = span.get_span_context()
            trace_id = format(ctx.trace_id, "032x") if ctx else "no-trace"
            span.end()

        if _agent_host:
            try:
                await _agent_host.report_activity(
                    session_id=session_id, trace_id=trace_id,
                    input_text=req.message, output_text=response, status="completed",
                )
            except Exception:
                pass

        return InvokeResponse(
            response=response, session_id=session_id, trace_id=trace_id,
            agent_id=AGENT_ID, model=MODEL,
        )

    except Exception as exc:
        if span:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            span.end()
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
async def health():
    return {
        "agent_id": AGENT_ID,
        "display_name": AGENT_NAME,
        "framework": "n8n",
        "model": MODEL,
        "status": "active",
        "n8n_webhook": N8N_WEBHOOK,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent365_server:app", host="0.0.0.0", port=PORT)
