"""FastAPI server exposing the Agent365-wrapped n8n agent.

Endpoints:
    POST /invoke     - Send a message to the agent (proxied to n8n)
    GET  /health     - Agent health check

This server is the deployment target for Azure Container Apps.
It proxies requests to the n8n webhook and wraps each invocation
with Agent 365 lifecycle management and Foundry tracing.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .wrapper import Agent365WrappedN8nAgent
from .tracing import setup_tracing

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_agent: Agent365WrappedN8nAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init tracing + register with Agent 365. Shutdown: deregister."""
    global _agent

    setup_tracing()

    _agent = Agent365WrappedN8nAgent()
    registration = await _agent.startup()
    logger.info("Agent startup complete: %s", registration)

    yield

    if _agent:
        await _agent.shutdown()


app = FastAPI(
    title="n8n Foundry Agent",
    description="n8n workflow agent on Azure AI Foundry GPT 5.2, wrapped in Microsoft Agent 365 SDK",
    version="0.1.0",
    lifespan=lifespan,
)


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
async def invoke(request: InvokeRequest):
    """Send a message to the agent and get a response."""
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    result = await _agent.invoke(
        user_input=request.message,
        session_id=request.session_id,
    )
    return InvokeResponse(**result)


@app.get("/health")
async def health():
    """Agent health check endpoint."""
    if _agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    return await _agent.health()


def main():
    """Run the server directly."""
    import uvicorn

    uvicorn.run(
        "agent365_wrapper.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("WRAPPER_PORT", "8001")),
        reload=False,
    )


if __name__ == "__main__":
    main()
