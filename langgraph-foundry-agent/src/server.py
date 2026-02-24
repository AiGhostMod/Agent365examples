"""FastAPI server exposing the Agent365-wrapped LangGraph agent.

Endpoints:
    POST /invoke     - Send a message to the agent
    GET  /health     - Agent health check
    POST /shutdown   - Graceful shutdown (deregister from Agent 365)

This server is the deployment target for Azure Container Apps, Azure App Service,
or Foundry Agent Service's hosted agents feature.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent365_wrapper import Agent365WrappedAgent
from .tracing import setup_tracing

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level agent instance
_agent: Agent365WrappedAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init tracing + register with Agent 365. Shutdown: deregister."""
    global _agent

    # Initialize the full tracing pipeline
    setup_tracing()

    # Create and start the Agent365-wrapped LangGraph agent
    _agent = Agent365WrappedAgent()
    registration = await _agent.startup()
    logger.info("Agent startup complete: %s", registration)

    yield

    # Shutdown
    if _agent:
        await _agent.shutdown()


app = FastAPI(
    title="LangGraph Foundry Agent",
    description="LangGraph ReAct agent on Azure AI Foundry GPT 5.2, wrapped in Microsoft Agent 365 SDK",
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
        "src.server:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
