FROM python:3.11-slim

WORKDIR /app

# Install n8n (still runs as a Node.js service; the wrapper is Python)
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && npm install -g n8n \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy workflow and wrapper code
COPY workflows/ workflows/
COPY agent365_wrapper/ agent365_wrapper/

# Import the workflow into n8n
RUN n8n import:workflow --input=workflows/foundry-agent-flow.json || true

# Expose both n8n (5678) and wrapper (8001) ports
EXPOSE 5678 8001

# Start both n8n and the Python Agent365 wrapper
CMD ["sh", "-c", "n8n start & sleep 5 && python -m agent365_wrapper.server"]
