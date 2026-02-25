"""Microsoft Agent 365 SDK client for the n8n agent.

Provides the same Agent 365 lifecycle management as the LangGraph agent's
wrapper:

- Register agent with Agent 365 (Entra-backed identity)
- Report activity completions for Foundry evaluation tracking
- Deregister on shutdown

The actual agent logic runs in n8n. This wrapper sits outside and proxies
requests through to the n8n webhook, adding Agent 365 tracing and lifecycle
management around each invocation.

References:
    https://github.com/microsoft/Agent365-python
    https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Agent365Config:
    """Configuration for Agent 365 SDK registration and hosting."""

    agent_id: str = field(
        default_factory=lambda: os.environ.get("AGENT365_AGENT_ID", "n8n-foundry-agent-001")
    )
    display_name: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT365_AGENT_DISPLAY_NAME", "n8n Foundry Agent"
        )
    )
    tenant_id: str = field(
        default_factory=lambda: os.environ.get("AGENT365_TENANT_ID", "")
    )
    client_id: str = field(
        default_factory=lambda: os.environ.get("AGENT365_CLIENT_ID", "")
    )
    client_secret: str = field(
        default_factory=lambda: os.environ.get("AGENT365_CLIENT_SECRET", "")
    )
    description: str = "n8n workflow agent powered by Azure AI Foundry GPT 5.2"
    capabilities: list[str] = field(
        default_factory=lambda: ["chat", "tool_use", "knowledge_search", "task_creation"]
    )
    model_deployment: str = field(
        default_factory=lambda: os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
    )


class Agent365Client:
    """Client wrapping the Microsoft Agent 365 Python SDK.

    Handles Agent 365 lifecycle: registration, activity reporting, shutdown.

    NOTE: The microsoft-agents-a365 packages are in Frontier preview. This
    implementation uses the SDK's public API surface as documented; the actual
    import paths may evolve as the SDK reaches GA.
    """

    def __init__(self, config: Agent365Config | None = None):
        self.config = config or Agent365Config()
        self._registered = False
        self._agent_host = None
        self._observability = None

    async def register(self) -> dict[str, Any]:
        """Register the agent with Agent 365 and configure observability.

        Attempts to use the actual microsoft-agents-a365 SDK packages.
        Falls back to standalone mode if not installed (Frontier preview).
        """
        try:
            from microsoft.agents.a365.hosting import AgentHost, AgentHostConfig
            from microsoft.agents.a365.observability import (
                ObservabilityConfig,
                enable_agent_observability,
            )

            host_config = AgentHostConfig(
                agent_id=self.config.agent_id,
                display_name=self.config.display_name,
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                description=self.config.description,
                capabilities=self.config.capabilities,
            )

            self._agent_host = AgentHost(config=host_config)
            await self._agent_host.start()

            obs_config = ObservabilityConfig(
                enable_tracing=True,
                enable_metrics=True,
                connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
            )
            self._observability = enable_agent_observability(obs_config)

            self._registered = True
            logger.info(
                "Agent registered with Agent 365 SDK: %s (%s)",
                self.config.display_name,
                self.config.agent_id,
            )
            return {
                "agent_id": self.config.agent_id,
                "status": "registered",
                "mode": "agent365_sdk",
            }

        except ImportError:
            logger.warning(
                "microsoft-agents-a365 SDK not installed (Frontier preview). "
                "Running in standalone mode with manual OpenTelemetry. "
                "Install via: pip install microsoft-agents-a365-hosting microsoft-agents-a365-observability"
            )
            self._registered = False
            return {
                "agent_id": self.config.agent_id,
                "status": "standalone",
                "mode": "standalone",
                "note": "Install microsoft-agents-a365-* packages for full Agent 365 integration",
            }

    async def report_activity(
        self,
        session_id: str,
        trace_id: str,
        user_input: str,
        agent_output: str,
        status: str = "completed",
    ) -> None:
        """Report a completed agent activity to Agent 365."""
        if self._agent_host is not None:
            try:
                await self._agent_host.report_activity(
                    session_id=session_id,
                    trace_id=trace_id,
                    input_text=user_input,
                    output_text=agent_output,
                    status=status,
                )
            except Exception as exc:
                logger.debug("Agent 365 activity report failed: %s", exc)

    async def shutdown(self) -> None:
        """Deregister from Agent 365 and clean up."""
        if self._agent_host is not None:
            try:
                await self._agent_host.stop()
                logger.info("Agent deregistered from Agent 365")
            except Exception as exc:
                logger.debug("Agent 365 shutdown error: %s", exc)
        self._registered = False
