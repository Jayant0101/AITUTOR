// @ts-ignore
import { z } from 'zod';

/**
 * Enterprise-Grade Validation Schemas using Zod.
 * Ensures all API inputs are sanitized and typed.
 */

export const AIQuerySchema = z.object({
  prompt: z.string().min(1).max(5000),
  context: z.string().optional(),
  stream: z.boolean().optional().default(false),
});

export const SearchQuerySchema = z.object({
  query: z.string().min(1).max(1000),
  limit: z.number().int().min(1).max(50).optional().default(5),
});

export const JobCreateSchema = z.object({
  type: z.enum(['ai_processing', 'generate_embedding', 'data_export']),
  payload: z.record(z.unknown()),
});

/**
 * Sanitizes input to prevent common injection attacks.
 * Upgraded with basic prompt injection prevention.
 */
export function sanitizeInput(input: string): string {
  if (!input) return '';

  const sanitized = input
    .replace(/<script.*?>.*?<\/script>/gi, '')
    .replace(/[<>]/g, '')
    .trim();

  // Basic Prompt Injection Mitigation
  const injectionPatterns = [
    /ignore previous instructions/gi,
    /you are now a/gi,
    /system prompt/gi,
    /override/gi,
  ];

  let safetyChecked = sanitized;
  for (const pattern of injectionPatterns) {
    safetyChecked = safetyChecked.replace(pattern, '[REDACTED]');
  }

  return safetyChecked;
}
