"""LangGraph agent graph using Azure AI Foundry GPT 5.2.

This is the actual agent logic - a ReAct-style agent built with LangGraph that
uses Azure AI Foundry's GPT 5.2 deployment for reasoning. agent365_server.py
imports run_agent() from here - this module has zero knowledge of Agent365.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a helpful AI assistant powered by Azure AI Foundry. You can search a \
knowledge base, create tasks, and answer general questions. Be concise and \
accurate. When you need information you don't have, use the available tools."""


class AgentState(TypedDict):
    """State flowing through the LangGraph agent graph."""

    messages: Annotated[list[BaseMessage], add_messages]


def _build_llm() -> AzureChatOpenAI:
    """Construct the AzureChatOpenAI LLM pointed at the Foundry GPT 5.2 deployment."""
    return AzureChatOpenAI(
        azure_deployment=os.environ.get("AZURE_AI_FOUNDRY_DEPLOYMENT", "gpt-5.2"),
        azure_endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
        api_version=os.environ.get("AZURE_AI_FOUNDRY_API_VERSION", "2025-04-01-preview"),
        # Uses DefaultAzureCredential via azure-identity when no API key is set
        openai_api_type="azure_ad",
        temperature=0,
    )


def _call_model(state: AgentState) -> dict[str, Any]:
    """Invoke the LLM with the current message history."""
    llm = _build_llm().bind_tools(ALL_TOOLS)
    messages = state["messages"]

    # Prepend system prompt if not already present
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    response = llm.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: AgentState) -> str:
    """Determine whether the agent should call tools or finish."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_agent_graph() -> StateGraph:
    """Build the LangGraph agent as a compiled graph.

    Graph structure:
        [start] -> agent -> (has tool calls?) -> tools -> agent -> ...
                                              -> [end]
    """
    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("agent", _call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


async def run_agent(user_input: str, session_id: str | None = None) -> str:
    """Run the agent graph end-to-end and return the final text response.

    This is the primary entry point used by the Agent365 wrapper and the
    REST API server.
    """
    graph = build_agent_graph()
    initial_state: AgentState = {"messages": [HumanMessage(content=user_input)]}

    final_state = await graph.ainvoke(initial_state)

    # Extract the last AI message as the response
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content

    return "I was unable to generate a response."
