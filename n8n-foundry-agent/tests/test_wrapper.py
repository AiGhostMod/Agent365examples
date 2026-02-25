"""Tests for the n8n Agent365 wrapper."""

from agent365_wrapper.sdk import Agent365Config, Agent365Client


def test_config_defaults():
    """Agent365Config loads defaults."""
    config = Agent365Config()
    assert config.agent_id
    assert config.display_name
    assert config.capabilities


def test_config_custom():
    """Agent365Config accepts overrides."""
    config = Agent365Config(
        agent_id="test-n8n-agent",
        display_name="Test n8n Agent",
    )
    assert config.agent_id == "test-n8n-agent"
    assert config.display_name == "Test n8n Agent"


def test_client_init():
    """Agent365Client initializes without error."""
    client = Agent365Client()
    assert client.config.agent_id
    assert not client._registered
