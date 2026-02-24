FROM node:20-slim

WORKDIR /app

# Install n8n globally
RUN npm install -g n8n

# Install wrapper dependencies
COPY package.json .
RUN npm install --omit=dev

# Copy workflow and wrapper code
COPY workflows/ workflows/
COPY agent365-wrapper/ agent365-wrapper/

# Import the workflow into n8n
RUN n8n import:workflow --input=workflows/foundry-agent-flow.json || true

# Expose both n8n (5678) and wrapper (8001) ports
EXPOSE 5678 8001

# Start both n8n and the Agent365 wrapper
CMD ["sh", "-c", "n8n start & sleep 5 && node agent365-wrapper/server.mjs"]
