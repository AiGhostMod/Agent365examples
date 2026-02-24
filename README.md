# Agent365 Examples: Azure AI Foundry Agents

Two agent implementations using Azure AI Foundry GPT 5.2, each wrapped in the
[Microsoft Agent 365 SDK](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/)
for enterprise identity, observability, and governance. Both are structured for
onboarding to [Microsoft Foundry](https://azure.microsoft.com/en-us/products/ai-foundry/)
(the post-Ignite 2025 rebranding of Azure AI Foundry).

## Projects

| Folder | Agent Framework | Description |
|--------|----------------|-------------|
| [`langgraph-foundry-agent/`](./langgraph-foundry-agent/) | LangGraph (Python) | ReAct agent with LangGraph state graph, AzureChatOpenAI, and FastAPI server |
| [`n8n-foundry-agent/`](./n8n-foundry-agent/) | n8n (Node.js) | Visual workflow agent with n8n AI Agent node, Express wrapper server |

## Architecture

Both agents follow the same pattern:

```
Client Request
    │
    ▼
┌──────────────────────────────┐
│  Agent 365 SDK Wrapper       │  ← Entra identity, observability, lifecycle
│  (tracing, registration)     │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Agent Logic                 │  ← LangGraph graph / n8n workflow
│  (LLM calls, tool use,      │     ALL agent logic lives here
│   memory, reasoning)         │     Zero knowledge of Agent 365
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Azure AI Foundry GPT 5.2   │  ← Model deployment
└──────────────────────────────┘
```

The Agent 365 SDK wraps the agent - it does not implement the agent logic.
The actual reasoning, tool calling, and memory management are handled entirely
by LangGraph or n8n respectively.

## Tracing / Observability

Both agents export traces to Azure Application Insights using:

- **OpenTelemetry** with GenAI semantic conventions (`gen_ai.*` attributes)
- **Azure Monitor exporter** for Application Insights integration
- **azure-ai-projects telemetry** (Python agent) for Foundry SDK-level instrumentation
- **Foundry portal** reads traces from App Insights for agent monitoring dashboards

## Foundry Onboarding

Each project includes a `deploy/foundry-agent-manifest.yaml` for registering
with the Foundry Agent Service. The LangGraph agent supports Foundry's hosted
agents feature (no containers needed); the n8n agent deploys as a container.

## Prerequisites

- Azure subscription with Azure AI Foundry project
- GPT 5.2 model deployment in the Foundry project
- Application Insights resource (for tracing)
- [Agent 365 Frontier preview access](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/) (optional, runs standalone without it)
- Entra ID app registration with Microsoft Graph delegated permissions (for Agent 365)
