import { logError, logInfo } from '@/lib/logger';
import { trackEvent } from '@/lib/analytics/tracker';
import { AIQuerySchema, sanitizeInput } from '@/lib/validation';

/**
 * AI Integration Route — Enterprise-Grade Proxy.
 * Implements validation, timeouts, and AbortController.
 */
export async function POST(req: Request) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    const rawBody = await req.json();
    
    // 1. Zod Validation
    const validation = AIQuerySchema.safeParse(rawBody);
    if (!validation.success) {
      return Response.json({ error: "Invalid input", details: validation.error.format() }, { status: 400 });
    }

    const { prompt } = validation.data;
    const sanitizedPrompt = sanitizeInput(prompt);

    logInfo(`AI Request: ${sanitizedPrompt.substring(0, 50)}...`, "AI_API");
    await trackEvent('ai_query_proxy_start', { prompt_length: sanitizedPrompt.length });

    const response = await fetch(`${process.env.AI_BACKEND_URL || "http://localhost:8000"}/ai`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: sanitizedPrompt }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`AI Backend responded with ${response.status}`);
    }

    const data = await response.json();
    await trackEvent('ai_query_proxy_success');
    return Response.json(data);

  } catch (error: any) {
    clearTimeout(timeoutId);
    
    if (error.name === 'AbortError') {
      logError("AI Request Timed Out", "AI_API_ROUTE");
      return Response.json({ error: "AI Processing timed out", fallback: "I'm sorry, the AI is taking too long. Please try again later." }, { status: 504 });
    }

    logError(error, "AI_API_ROUTE");
    await trackEvent('ai_query_proxy_error', { error: error.message });
    return Response.json({ error: "AI Processing failed", details: error.message }, { status: 500 });
  }
}
