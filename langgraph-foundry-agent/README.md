# LangGraph Foundry Agent

ReAct-style agent built with [LangGraph](https://github.com/langchain-ai/langgraph),
powered by Azure AI Foundry GPT 5.2, wrapped in the
[Microsoft Agent 365 SDK](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/).

## Quick Start

```bash
# 1. Configure
cp .env.example .env
# Edit .env with your Azure AI Foundry endpoint, deployment, and credentials

# 2. Install
pip install -e .

# 3. Run
python -m src.server
# Server starts on http://localhost:8000

# 4. Test
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it?"}'
```

## Project Structure

```
langgraph-foundry-agent/
├── src/
│   ├── agent/                  # LangGraph agent (ALL agent logic)
│   │   ├── graph.py            #   State graph: agent node ↔ tool node
│   │   └── tools.py            #   Tool definitions (time, search, tasks)
│   ├── agent365_wrapper/       # Agent 365 SDK integration (NO agent logic)
│   │   ├── sdk.py              #   Agent 365 client (registration, lifecycle)
│   │   └── wrapper.py          #   Wraps LangGraph agent with Agent 365
│   ├── tracing/                # Foundry observability pipeline
│   │   └── foundry_tracing.py  #   OpenTelemetry + Azure Monitor + GenAI semconv
│   └── server.py               # FastAPI server
├── deploy/
│   ├── azure-container-app.bicep   # Azure Container Apps deployment
│   └── foundry-agent-manifest.yaml # Foundry Agent Service manifest
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## Deployment

### Azure Container Apps

```bash
# Build and push container
az acr build --registry <acr> --image langgraph-foundry-agent:latest .

# Deploy
az deployment group create \
  --resource-group <rg> \
  --template-file deploy/azure-container-app.bicep \
  --parameters containerImage=<acr>.azurecr.io/langgraph-foundry-agent:latest \
               foundryEndpoint=https://<project>.services.ai.azure.com
```

### Foundry Agent Service (Hosted)

```bash
az ai foundry agent create --manifest deploy/foundry-agent-manifest.yaml
```

## Tools

| Tool | Description |
|------|-------------|
| `get_current_time` | Returns current UTC datetime |
| `search_knowledge_base` | Searches internal knowledge (connect to Azure AI Search for production) |
| `create_task` | Creates a work item (connect to Azure DevOps/Planner for production) |
