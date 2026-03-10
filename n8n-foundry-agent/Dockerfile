FROM python:3.11-slim

WORKDIR /app

# Install n8n (runs as Node.js service; the wrapper is Python)
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g n8n \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY workflows/ workflows/
COPY agent365_server.py .

RUN n8n import:workflow --input=workflows/foundry-agent-flow.json || true

EXPOSE 5678 8001

CMD ["sh", "-c", "n8n start & sleep 5 && python agent365_server.py"]
