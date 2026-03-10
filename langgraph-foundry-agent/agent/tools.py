"""Tools available to the LangGraph agent.

Defines the tool set that the agent can invoke. These are standard LangChain
tools that LangGraph will bind to the Azure Foundry GPT 5.2 model via
function calling.
"""

from __future__ import annotations

import datetime
import json

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Get the current date and time in ISO format."""
    return datetime.datetime.now(datetime.UTC).isoformat()


@tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for relevant information.

    Args:
        query: The search query to look up.
    """
    # Placeholder - in production this would hit Azure AI Search or similar
    return json.dumps(
        {
            "results": [
                {
                    "title": f"Result for: {query}",
                    "snippet": "This is a placeholder knowledge base result. "
                    "Connect to Azure AI Search for production use.",
                    "score": 0.95,
                }
            ],
            "source": "azure-ai-search",
        }
    )


@tool
def create_task(title: str, description: str, priority: str = "medium") -> str:
    """Create a new task or work item.

    Args:
        title: The title of the task.
        description: Detailed description of what needs to be done.
        priority: Priority level - low, medium, or high.
    """
    # Placeholder - in production this would create items in Azure DevOps, Planner, etc.
    return json.dumps(
        {
            "status": "created",
            "task_id": "TASK-001",
            "title": title,
            "description": description,
            "priority": priority,
        }
    )


ALL_TOOLS = [get_current_time, search_knowledge_base, create_task]
