"""Microsoft Agent 365 SDK integration.

The Microsoft Agent 365 SDK (microsoft-agents-a365) provides enterprise-grade
extensions for agents built on any platform. It does NOT replace the agent logic
itself - instead it layers on:

- Entra-backed Agent Identity (agents get @-mentionable identities in Teams, etc.)
- Observability via OpenTelemetry (audited, traceable interactions)
- Notifications (agents can receive and respond to Teams/Outlook/email events)
- Governed MCP tool access to Microsoft 365 data

This module wraps the Agent 365 Python SDK to register and manage the LangGraph
agent's identity and observability hooks within the Foundry ecosystem.

References:
    https://github.com/microsoft/Agent365-python
    https://learn.microsoft.com/en-us/microsoft-agent-365/developer/
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
        default_factory=lambda: os.environ.get("AGENT365_AGENT_ID", "langgraph-foundry-agent-001")
    )
    display_name: str = field(
        default_factory=lambda: os.environ.get(
            "AGENT365_AGENT_DISPLAY_NAME", "LangGraph Foundry Agent"
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
    description: str = "LangGraph ReAct agent powered by Azure AI Foundry GPT 5.2"
    capabilities: list[str] = field(
        default_factory=lambda: ["chat", "tool_use", "knowledge_search", "task_creation"]
    )
    model_deployment: str = field(
        default_factory=lambda: os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "gpt-5.2")
    )


class Agent365Client:
    """Client wrapping the Microsoft Agent 365 Python SDK.

    This handles the Agent 365 lifecycle:
    1. Configure Entra-backed agent identity
    2. Register the agent's capabilities and metadata
    3. Set up observability hooks (OpenTelemetry integration)
    4. Handle incoming activity (messages, notifications) via the Agent 365 hosting layer
    5. Deregister on shutdown

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

        This attempts to use the actual microsoft-agents-a365 SDK packages.
        If the SDK is not installed (it's in Frontier preview), falls back to
        standalone mode with manual OpenTelemetry setup.
        """
        try:
            # Try to import the actual Agent 365 SDK
            from microsoft.agents.a365.hosting import AgentHost, AgentHostConfig
            from microsoft.agents.a365.observability import (
                ObservabilityConfig,
                enable_agent_observability,
            )

            # Configure the Agent 365 host with Entra identity
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

            # Enable Agent 365 observability (auto-instruments OpenTelemetry)
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
        """Report a completed agent activity to Agent 365.

        When running with the full SDK, this flows through Agent 365's
        observability pipeline. In standalone mode, this is a no-op (tracing
        is handled directly via OpenTelemetry).
        """
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
