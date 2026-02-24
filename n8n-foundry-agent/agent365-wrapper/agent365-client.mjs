/**
 * Microsoft Agent 365 SDK client for the n8n agent.
 *
 * Provides the same Agent 365 lifecycle management as the LangGraph agent's
 * Python wrapper, but in JavaScript for the n8n ecosystem:
 *
 * - Register agent with Agent 365 (Entra-backed identity)
 * - Report activity completions for Foundry evaluation tracking
 * - Deregister on shutdown
 *
 * The actual agent logic runs in n8n - this wrapper sits outside and
 * proxies requests through to the n8n webhook, adding Agent 365 tracing
 * and lifecycle management around each invocation.
 *
 * References:
 *   https://github.com/microsoft/Agent365-Samples
 *   https://learn.microsoft.com/en-us/microsoft-agent-365/developer/
 */

import { DefaultAzureCredential } from "@azure/identity";

export class Agent365Config {
  constructor(overrides = {}) {
    this.agentId =
      overrides.agentId ||
      process.env.AGENT365_AGENT_ID ||
      "n8n-foundry-agent-001";
    this.displayName =
      overrides.displayName ||
      process.env.AGENT365_AGENT_DISPLAY_NAME ||
      "n8n Foundry Agent";
    this.tenantId =
      overrides.tenantId || process.env.AGENT365_TENANT_ID || "";
    this.clientId =
      overrides.clientId || process.env.AGENT365_CLIENT_ID || "";
    this.clientSecret =
      overrides.clientSecret || process.env.AGENT365_CLIENT_SECRET || "";
    this.description =
      "n8n agent workflow powered by Azure AI Foundry GPT 5.2";
    this.capabilities = [
      "chat",
      "tool_use",
      "knowledge_search",
      "task_creation",
    ];
    this.modelDeployment =
      process.env.AZURE_OPENAI_DEPLOYMENT || "gpt-5.2";
  }
}

export class Agent365Client {
  constructor(config) {
    this.config = config || new Agent365Config();
    this._registered = false;
    this._agentHost = null;
  }

  /**
   * Register with Agent 365 SDK.
   *
   * Attempts to use the actual @microsoft/agents-a365 npm packages.
   * Falls back to standalone mode if the SDK is not installed (Frontier preview).
   */
  async register() {
    try {
      // Attempt to use the actual Agent 365 Node.js SDK
      const { AgentHost, AgentHostConfig } = await import(
        "@microsoft/agents-a365-hosting"
      );
      const { enableAgentObservability } = await import(
        "@microsoft/agents-a365-observability"
      );

      const hostConfig = new AgentHostConfig({
        agentId: this.config.agentId,
        displayName: this.config.displayName,
        tenantId: this.config.tenantId,
        clientId: this.config.clientId,
        clientSecret: this.config.clientSecret,
        description: this.config.description,
        capabilities: this.config.capabilities,
      });

      this._agentHost = new AgentHost(hostConfig);
      await this._agentHost.start();

      enableAgentObservability({
        enableTracing: true,
        enableMetrics: true,
        connectionString:
          process.env.APPLICATIONINSIGHTS_CONNECTION_STRING || "",
      });

      this._registered = true;
      console.log(
        `[agent365] Registered with Agent 365 SDK: ${this.config.displayName} (${this.config.agentId})`
      );

      return {
        agentId: this.config.agentId,
        status: "registered",
        mode: "agent365_sdk",
      };
    } catch (err) {
      console.warn(
        `[agent365] Agent 365 SDK not available (Frontier preview): ${err.message}`
      );
      console.warn(
        "[agent365] Running in standalone mode with manual OpenTelemetry."
      );
      this._registered = false;

      return {
        agentId: this.config.agentId,
        status: "standalone",
        mode: "standalone",
        note: "Install @microsoft/agents-a365-* packages for full Agent 365 integration",
      };
    }
  }

  /**
   * Report a completed activity to Agent 365.
   */
  async reportActivity({ sessionId, traceId, userInput, agentOutput, status = "completed" }) {
    if (this._agentHost) {
      try {
        await this._agentHost.reportActivity({
          sessionId,
          traceId,
          inputText: userInput,
          outputText: agentOutput,
          status,
        });
      } catch (err) {
        console.debug(`[agent365] Activity report failed: ${err.message}`);
      }
    }
  }

  /**
   * Deregister from Agent 365.
   */
  async shutdown() {
    if (this._agentHost) {
      try {
        await this._agentHost.stop();
        console.log("[agent365] Deregistered from Agent 365");
      } catch (err) {
        console.debug(`[agent365] Shutdown error: ${err.message}`);
      }
    }
    this._registered = false;
  }
}
