/**
 * Azure AI Foundry tracing for the n8n agent.
 *
 * Sets up OpenTelemetry with Azure Monitor exporter so that n8n agent
 * invocations appear in Application Insights and the Foundry portal.
 *
 * The trace attributes follow OpenTelemetry Semantic Conventions for GenAI
 * and the Foundry multi-agent conventions.
 */

import { trace, SpanStatusCode } from "@opentelemetry/api";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import {
  BatchSpanProcessor,
  ConsoleSpanExporter,
  SimpleSpanProcessor,
} from "@opentelemetry/sdk-trace-base";
import { Resource } from "@opentelemetry/resources";

let provider = null;
let tracer = null;

/**
 * Initialize the tracing pipeline.
 * OpenTelemetry SDK -> Azure Monitor Exporter -> Application Insights -> Foundry Portal
 */
export function setupTracing() {
  const connectionString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

  const resource = new Resource({
    "service.name": "n8n-foundry-agent",
    "service.version": "0.1.0",
    "ai.foundry.agent_type": "n8n",
    "ai.foundry.model_deployment":
      process.env.AZURE_OPENAI_DEPLOYMENT || "gpt-5.2",
  });

  provider = new NodeTracerProvider({ resource });

  if (connectionString) {
    try {
      // Dynamic import for Azure Monitor exporter
      import("@azure/monitor-opentelemetry-exporter").then(
        ({ AzureMonitorTraceExporter }) => {
          const exporter = new AzureMonitorTraceExporter({ connectionString });
          provider.addSpanProcessor(new BatchSpanProcessor(exporter));
          console.log(
            "[tracing] Azure Monitor exporter configured -> Application Insights"
          );
        }
      ).catch(() => {
        console.warn(
          "[tracing] @azure/monitor-opentelemetry-exporter not installed; traces local only"
        );
      });
    } catch {
      // fallthrough
    }
  } else {
    console.log(
      "[tracing] APPLICATIONINSIGHTS_CONNECTION_STRING not set; traces local only"
    );
  }

  if (process.env.FOUNDRY_TRACE_DEBUG) {
    provider.addSpanProcessor(
      new SimpleSpanProcessor(new ConsoleSpanExporter())
    );
    console.log("[tracing] Console exporter enabled (FOUNDRY_TRACE_DEBUG)");
  }

  provider.register();
  tracer = trace.getTracer("foundry.n8n.agent");

  console.log("[tracing] OpenTelemetry tracing initialized");
  return provider;
}

/**
 * Start a session-level span for an agent invocation.
 */
export function startSessionSpan(sessionId, userInput) {
  if (!tracer) return null;

  const span = tracer.startSpan("agent.session", {
    attributes: {
      "agent.session.id": sessionId,
      "agent.framework": "n8n",
      "gen_ai.system": "azure_ai_foundry",
      "gen_ai.request.model":
        process.env.AZURE_OPENAI_DEPLOYMENT || "gpt-5.2",
      "agent.input.text": (userInput || "").slice(0, 500),
    },
  });
  return span;
}

/**
 * End a session span with the agent's output.
 */
export function endSessionSpan(span, output) {
  if (!span) return;
  span.setAttribute("agent.output.text", (output || "").slice(0, 500));
  span.setStatus({ code: SpanStatusCode.OK });
  span.end();
}

/**
 * Record an error on a span.
 */
export function recordError(span, error) {
  if (!span) return;
  span.setStatus({ code: SpanStatusCode.ERROR, message: String(error) });
  span.recordException(error);
  span.end();
}

/**
 * Get the trace ID from a span for Foundry correlation.
 */
export function getTraceId(span) {
  if (!span) return "no-trace";
  const ctx = span.spanContext();
  return ctx ? ctx.traceId : "no-trace";
}
