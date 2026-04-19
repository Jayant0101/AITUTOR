/**
 * AI Integration Hook — High-scale SaaS ready.
 * Supports streaming, observability, and background job queueing.
 */

import { useState } from 'react';
import { trackEvent } from '@/lib/analytics/tracker';
import { logError } from '@/lib/logger';

export function useAI() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Standard AI query with logging and analytics.
   */
  async function askAI(prompt: string) {
    setLoading(true);
    setError(null);

    try {
      await trackEvent('ai_ask_start', { prompt_length: prompt.length });

      const res = await fetch("/api/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
      });

      if (!res.ok) throw new Error("AI Request failed");

      const data = await res.json();
      await trackEvent('ai_ask_success');
      return data;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "AI Request failed";
      logError(err, "USE_AI_HOOK");
      setError(errorMessage);
      await trackEvent('ai_ask_error', { error: errorMessage });
    } finally {
      setLoading(false);
    }
  }

  /**
   * Streaming AI query for real-time responsiveness.
   */
  async function streamAI(prompt: string, onChunk: (text: string) => void) {
    setLoading(true);
    setError(null);

    try {
      await trackEvent('ai_stream_start');

      const response = await fetch("/api/ai/stream", { // Assuming a /stream route
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let fullText = "";

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunk = decoder.decode(value);
        fullText += chunk;
        onChunk(fullText);
      }

      await trackEvent('ai_stream_success', { length: fullText.length });
      return fullText;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Streaming failed";
      logError(err, "USE_AI_STREAM_HOOK");
      setError(errorMessage);
      await trackEvent('ai_stream_error', { error: errorMessage });
    } finally {
      setLoading(false);
    }
  }

  /**
   * Queues an AI task for background processing.
   */
  async function queueAIJob(type: string, payload: Record<string, unknown>) {
    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, payload })
      });
      return await res.json();
    } catch (err) {
      logError(err, "QUEUE_AI_JOB");
    }
  }

  /**
   * AI Tutor Brain query — Context-aware and personalized.
   */
  async function askTutor(prompt: string) {
    setLoading(true);
    setError(null);

    try {
      await trackEvent('ai_tutor_start', { prompt_length: prompt.length });

      const res = await fetch("/api/ai/tutor", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
      });

      if (!res.ok) throw new Error("AI Tutor Request failed");

      const data = await res.json();
      await trackEvent('ai_tutor_success');
      return data;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "AI Tutor Request failed";
      logError(err, "USE_AI_TUTOR_HOOK");
      setError(errorMessage);
      await trackEvent('ai_tutor_error', { error: errorMessage });
    } finally {
      setLoading(false);
    }
  }

  return { askAI, askTutor, streamAI, queueAIJob, loading, error };
}
