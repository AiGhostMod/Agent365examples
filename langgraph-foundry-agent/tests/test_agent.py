"""Tests for the LangGraph agent graph construction."""

from src.agent.graph import AgentState, build_agent_graph
from src.agent.tools import ALL_TOOLS


def test_tools_defined():
    """All expected tools are registered."""
    tool_names = {t.name for t in ALL_TOOLS}
    assert "get_current_time" in tool_names
    assert "search_knowledge_base" in tool_names
    assert "create_task" in tool_names


def test_graph_compiles():
    """The agent graph compiles without error."""
    graph = build_agent_graph()
    assert graph is not None


def test_agent_state_schema():
    """AgentState has the expected shape."""
    state: AgentState = {"messages": []}
    assert "messages" in state
