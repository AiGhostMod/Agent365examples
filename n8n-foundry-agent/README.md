# n8n Foundry Agent

Visual workflow agent built with [n8n](https://n8n.io/), powered by Azure AI
Foundry GPT 5.2, wrapped in the
[Microsoft Agent 365 SDK](https://learn.microsoft.com/en-us/microsoft-agent-365/developer/agent-365-sdk)
via a Python FastAPI server.

## Quick Start

```bash
# 1. Configure
cp .env.example .env
# Edit .env with your Azure OpenAI endpoint, key, and credentials

# 2. Install Python wrapper dependencies
pip install -e .

# 3. Install n8n (requires Node.js 20+)
npm install -g n8n

# 4. Import workflow into n8n
n8n import:workflow --input=workflows/foundry-agent-flow.json

# 5. Start n8n (in one terminal)
n8n start
# n8n UI at http://localhost:5678
# Configure Azure OpenAI credentials in the n8n UI

# 6. Start Agent365 Python wrapper (in another terminal)
python -m agent365_wrapper.server
# Wrapper at http://localhost:8001

# 7. Test
curl -X POST http://localhost:8001/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it?"}'
```

## Architecture

```
Client (port 8001)
    |
    v
Agent365 Wrapper Server (Python / FastAPI)
    |  - OpenTelemetry tracing
    |  - Agent 365 registration/lifecycle
    |  - Session correlation
    |
    v
n8n Webhook (port 5678, /webhook/agent)
    |
    v
n8n AI Agent Workflow
    |-- Azure OpenAI Chat Model (GPT 5.2)
    |-- Window Buffer Memory
    |-- Tool: Get Current Time
    |-- Tool: Search Knowledge Base
    +-- Tool: Create Task
```

## Project Structure

```
n8n-foundry-agent/
|-- workflows/
|   +-- foundry-agent-flow.json     # n8n workflow (ALL agent logic)
|-- agent365_wrapper/               # Agent 365 SDK integration (Python)
|   |-- __init__.py
|   |-- server.py                   #   FastAPI server (proxies to n8n)
|   |-- sdk.py                      #   Agent 365 client (registration, lifecycle)
|   |-- wrapper.py                  #   Wraps n8n agent with Agent 365
|   +-- tracing.py                  #   OpenTelemetry + Azure Monitor
|-- tests/
|   +-- test_wrapper.py
|-- deploy/
|   |-- azure-container-app.bicep   # Azure Container Apps deployment
|   +-- foundry-agent-manifest.yaml # Foundry Agent Service manifest
|-- Dockerfile
|-- pyproject.toml
+-- .env.example
```

## Deployment

### Azure Container Apps

```bash
# Build and push
az acr build --registry <acr> --image n8n-foundry-agent:latest .

# Deploy
az deployment group create \
  --resource-group <rg> \
  --template-file deploy/azure-container-app.bicep \
  --parameters containerImage=<acr>.azurecr.io/n8n-foundry-agent:latest \
               azureOpenAiEndpoint=https://<project>.services.ai.azure.com \
               azureOpenAiKey=<key> \
               n8nEncryptionKey=<random-key>
```

## n8n Workflow

The workflow is defined in `workflows/foundry-agent-flow.json` and can be
edited visually in the n8n UI. It uses:

- **Azure OpenAI Chat Model** node pointed at the GPT 5.2 deployment
- **AI Agent** node with ReAct-style tool calling
- **Window Buffer Memory** for conversation context
- **Code Tool** nodes for time, search, and task creation
- **Webhook** trigger + response for HTTP API access
