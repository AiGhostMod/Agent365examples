# Agent365 Examples: Azure AI Foundry Agents

Two agent implementations using Azure AI Foundry GPT 5.2, each wrapped in the
[Microsoft Agent 365 SDK](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk)
for enterprise identity, observability, and governance. Both are structured for
onboarding to [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-azure-ai-foundry?view=foundry-classic)
(the post-Ignite 2025 rebranding of Azure AI Foundry).

## Projects

| Folder | Agent Framework | Description |
|--------|----------------|-------------|
| [`langgraph-foundry-agent/`](./langgraph-foundry-agent/) | LangGraph (Python) | ReAct agent with LangGraph state graph, AzureChatOpenAI, and FastAPI server |
| [`n8n-foundry-agent/`](./n8n-foundry-agent/) | n8n + Python wrapper | Visual workflow agent with n8n AI Agent node, Python FastAPI wrapper server |

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
- **azure-ai-projects telemetry** (LangGraph agent) for Foundry SDK-level instrumentation
- **Foundry portal** reads traces from App Insights for agent monitoring dashboards

## Foundry Onboarding

Each project includes a `deploy/foundry-agent-manifest.yaml` for registering
with the Foundry Agent Service. The LangGraph agent supports Foundry's hosted
agents feature (no containers needed); the n8n agent deploys as a container.

## Prerequisites

- Python 3.11+
- Azure subscription with Azure AI Foundry project
- GPT 5.2 model deployment in the Foundry project
- Application Insights resource (for tracing)
- [Agent 365 Frontier preview access](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk) (optional, runs standalone without it)
- Entra ID app registration with Microsoft Graph delegated permissions (for Agent 365)
- Node.js 20+ and n8n (for the n8n agent only; the wrapper itself is Python)

---

## Microsoft Documentation Reference

Curated links to current Microsoft and OpenTelemetry documentation relevant to
building, tracing, and onboarding agents to Foundry.

### Azure AI Foundry - General

- [What is Microsoft Foundry?](https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-azure-ai-foundry?view=foundry-classic) - Top-level overview of Microsoft Foundry (formerly Azure AI Foundry), the unified Azure PaaS for enterprise AI operations
- [Microsoft Foundry Documentation Hub](https://learn.microsoft.com/en-us/azure/ai-foundry/?view=foundry-classic) - Main docs hub covering models, agents, deployment, fine-tuning, observability, and SDKs
- [Microsoft Foundry Quickstart (Code-First)](https://learn.microsoft.com/en-us/azure/ai-foundry/quickstarts/get-started-code?view=foundry-classic) - SDK installation, authentication, and sample code in Python, Java, TypeScript, and C#
- [Get Started with Microsoft Foundry (Training Module)](https://learn.microsoft.com/en-us/training/modules/get-started-ai-in-foundry/) - Microsoft Learn training module introducing Foundry capabilities

### Azure AI Foundry - Agent Development

- [What is Foundry Agent Service?](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview?view=foundry-classic) - Overview of Foundry Agent Service, the runtime that manages conversations, tool orchestration, content safety, and identity
- [Quickstart: Create a Foundry Agent](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/quickstart?view=foundry-classic) - Quickstart for creating an AI agent using the Foundry SDK in Python, .NET, Java, or TypeScript
- [Foundry SDKs and Endpoints Overview](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/sdk-overview?view=foundry-classic) - Overview of all Foundry SDKs, when to use each, and how they relate to Agent Framework and Foundry Tools
- [Foundry Agent Service REST API Reference](https://learn.microsoft.com/en-us/rest/api/aifoundry/aiagents/) - REST API reference for creating, configuring, and running AI agents

### Azure AI Foundry - Tracing and Monitoring

- [Set Up Tracing for AI Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/trace-agent-setup?view=foundry) - Connect Application Insights to a Foundry project, instrument agents with OpenTelemetry, view and analyze traces
- [Agent Tracing Concepts](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/concepts/trace-agent-concept?view=foundry) - How Foundry uses OpenTelemetry semantic conventions and Application Insights to store and display agent traces
- [Configure Tracing for Agent Frameworks](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/trace-agent-framework?view=foundry) - Step-by-step tracing setup for Microsoft Agent Framework, Semantic Kernel, LangChain, LangGraph, and OpenAI Agents SDK
- [Monitor AI Agents with Application Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/app/agents-view) - The Agent details view in Application Insights for unified monitoring of agents from Foundry, Copilot Studio, and third parties

### Microsoft Agent 365 SDK and Agent Framework

- [Microsoft Agent 365 SDK Overview](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk) - Enterprise SDK extending agents (from any framework) with Entra-backed identity, M365 notifications, OpenTelemetry observability, governed MCP tool servers, and compliance policies
- [Microsoft Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/) - The successor to Semantic Kernel + AutoGen, providing agents, graph-based workflows, middleware, and multi-model support (.NET and Python)
- [Microsoft 365 Agents SDK Overview](https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/agents-sdk-overview) - Framework for building enterprise agents deployable to Microsoft 365 Copilot, Teams, and custom apps
- [Microsoft 365 Agents SDK Documentation Hub](https://learn.microsoft.com/en-us/microsoft-365/agents-sdk/) - Getting started guides, samples, Semantic Kernel integration, and channel deployment

### OpenTelemetry GenAI Semantic Conventions

- [Semantic Conventions for Generative AI Systems](https://opentelemetry.io/docs/specs/semconv/gen-ai/) - Top-level spec defining the `gen_ai.*` attribute namespace for traces, metrics, and events
- [GenAI Span Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) - Detailed span conventions: `gen_ai.operation.name`, `gen_ai.request.model`, `gen_ai.system`, tool execution spans, content capture rules
- [GenAI Metrics Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/) - Metrics for token usage, operation duration, request latency, and time-to-first-token
- [GenAI Spans Source (GitHub)](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md) - Canonical source document with full attribute tables and examples

### Azure Monitor OpenTelemetry Integration

- [OpenTelemetry on Azure](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry) - Azure's OpenTelemetry offerings including the Azure Monitor Distro, Azure SDK instrumentation, and pipeline-at-edge
- [Enable OpenTelemetry in Application Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable) - Step-by-step guide for .NET, Java, Node.js, and Python applications
- [Configuring OpenTelemetry for Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-configuration) - Configuration reference for sampling, exporters, connection strings, and custom settings
- [Application Insights OpenTelemetry Data Collection](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-overview) - Autoinstrumentation vs. manual instrumentation approaches for Application Insights
