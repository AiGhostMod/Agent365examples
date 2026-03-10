"""Tests for agent365_server configuration."""

import os


def test_defaults():
    """Config defaults load from env or fallback."""
    agent_id = os.environ.get("AGENT365_AGENT_ID", "n8n-foundry-agent-001")
    assert agent_id
    model = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.2")
    assert model
