/**
 * Agent365 wrapper server for the n8n Foundry agent.
 *
 * Architecture:
 *   Client -> Agent365 Wrapper (this server, port 8001)
 *          -> n8n webhook (port 5678, /webhook/agent)
 *          -> n8n AI Agent workflow (Azure OpenAI GPT 5.2)
 *          -> Response flows back through wrapper with tracing
 *
 * The n8n workflow contains ALL the agent logic (LLM calls, tool use, memory).
 * This wrapper adds Agent 365 SDK lifecycle management and Foundry tracing
 * around each invocation - it does NOT modify the agent behavior.
 *
 * Endpoints:
 *   POST /invoke  - Send a message to the agent
 *   GET  /health  - Health check
 */

import "dotenv/config";
import express from "express";
import { randomUUID } from "crypto";
import { Agent365Client, Agent365Config } from "./agent365-client.mjs";
import {
  setupTracing,
  startSessionSpan,
  endSessionSpan,
  recordError,
  getTraceId,
} from "./tracing.mjs";

const app = express();
app.use(express.json());

const config = new Agent365Config();
const client = new Agent365Client(config);

const N8N_WEBHOOK_URL =
  process.env.N8N_WEBHOOK_URL ||
  `http://localhost:${process.env.N8N_PORT || 5678}/webhook/agent`;

// --- Startup ---

setupTracing();

const registrationResult = await client.register();
console.log("[server] Agent365 registration:", registrationResult);

// --- Routes ---

app.post("/invoke", async (req, res) => {
  const { message, session_id } = req.body;

  if (!message) {
    return res.status(400).json({ error: "message is required" });
  }

  const sessionId = session_id || randomUUID();
  const span = startSessionSpan(sessionId, message);

  try {
    // Forward to n8n webhook (where the actual agent logic runs)
    const n8nResponse = await fetch(N8N_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        sessionId,
      }),
    });

    if (!n8nResponse.ok) {
      throw new Error(
        `n8n webhook returned ${n8nResponse.status}: ${await n8nResponse.text()}`
      );
    }

    const result = await n8nResponse.json();
    const agentOutput = result.response || result.output || JSON.stringify(result);
    const traceId = getTraceId(span);

    endSessionSpan(span, agentOutput);

    // Report through Agent 365
    await client.reportActivity({
      sessionId,
      traceId,
      userInput: message,
      agentOutput,
    });

    res.json({
      response: agentOutput,
      session_id: sessionId,
      trace_id: traceId,
      agent_id: config.agentId,
      model: config.modelDeployment,
    });
  } catch (err) {
    console.error("[server] Agent invocation error:", err);
    recordError(span, err);

    await client.reportActivity({
      sessionId,
      traceId: "error",
      userInput: message,
      agentOutput: err.message,
      status: "error",
    });

    res.status(500).json({
      error: err.message,
      session_id: sessionId,
      agent_id: config.agentId,
    });
  }
});

app.get("/health", (req, res) => {
  res.json({
    agent_id: config.agentId,
    display_name: config.displayName,
    framework: "n8n",
    model: config.modelDeployment,
    status: "active",
    capabilities: config.capabilities,
    n8n_webhook: N8N_WEBHOOK_URL,
  });
});

// --- Graceful shutdown ---

async function shutdown() {
  console.log("[server] Shutting down...");
  await client.shutdown();
  process.exit(0);
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);

// --- Start ---

const port = parseInt(process.env.WRAPPER_PORT || "8001", 10);
app.listen(port, () => {
  console.log(`[server] Agent365 wrapper listening on port ${port}`);
  console.log(`[server] Proxying to n8n webhook: ${N8N_WEBHOOK_URL}`);
});
