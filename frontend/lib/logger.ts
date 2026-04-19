import { createClient } from '@supabase/supabase-js';
import * as Sentry from "@sentry/nextjs";

/**
 * Enterprise-Grade Observability System.
 * Integrates Sentry for error tracking and Supabase for persistent app logs.
 */

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! // Use service role for logging to bypass RLS
);

export function logError(error: unknown, context: string = "APP") {
  const timestamp = new Date().toISOString();
  const message = error instanceof Error ? error.message : String(error);
  
  console.error(`[${timestamp}] [${context} ERROR]:`, error);
  
  // 1. Sentry Capture
  Sentry.captureException(error, { tags: { context } });

  // 2. Database Persistent Log (Async)
  saveLogToDb('ERROR', context, message, { 
    stack: error instanceof Error ? error.stack : undefined 
  });
}

export function logInfo(message: string, context: string = "APP") {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${context} INFO]:`, message);
  
  // Database Persistent Log (Async)
  saveLogToDb('INFO', context, message);
}

export function logEvent(event: string, metadata: Record<string, unknown> = {}, context: string = "EVENT") {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${context}]: ${event}`, metadata);
  
  saveLogToDb('INFO', context, `Event: ${event}`, metadata);
}

async function saveLogToDb(level: string, context: string, message: string, metadata: Record<string, unknown> = {}) {
  try {
    await supabase.from('app_logs').insert({
      level,
      context,
      message,
      metadata
    });
  } catch (err) {
    // Fail silently to avoid infinite loops if DB logging fails
    console.error("Failed to save log to DB", err);
  }
}
