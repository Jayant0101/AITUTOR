import { logError, logInfo } from '@/lib/logger';
import { trackEvent } from '@/lib/analytics/tracker';

/**
 * AI Streaming Route — Supports high-scale real-time AI responses.
 * Proxies the stream from the FastAPI backend to the Next.js client.
 */
export async function POST(req: Request) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout for streaming

  try {
    const body = await req.json();
    logInfo(`AI Stream started: ${body.prompt?.substring(0, 50)}...`, "AI_STREAM");
    await trackEvent('ai_stream_proxy_start', { prompt_length: body.prompt?.length });

    const response = await fetch(`${process.env.AI_BACKEND_URL || "http://localhost:8000"}/ai/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`AI Backend responded with ${response.status}`);
    }

    // Proxy the stream with error handling for client disconnect
    const stream = new ReadableStream({
      async start(streamController) {
        const reader = response.body?.getReader();
        if (!reader) {
          streamController.close();
          return;
        }

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            streamController.enqueue(value);
          }
        } catch (err) {
          logError(err, "STREAM_READ_ERROR");
          streamController.error(err);
        } finally {
          streamController.close();
        }
      },
      cancel() {
        controller.abort(); // Abort the backend request if client disconnects
      }
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });

  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      logError("AI Stream Timed Out", "AI_STREAM_ROUTE");
      return Response.json({ error: "AI Stream timed out" }, { status: 504 });
    }
    logError(error, "AI_STREAM_ROUTE");
    return Response.json({ error: "AI Streaming failed" }, { status: 500 });
  }
}
