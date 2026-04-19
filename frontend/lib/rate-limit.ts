import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

/**
 * Distributed Rate Limiting using Upstash Redis.
 * Ensures high-scale protection across multiple server instances.
 */

// Initialize Redis client only if env vars are present
const redis = (process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN) 
  ? new Redis({
      url: process.env.UPSTASH_REDIS_REST_URL,
      token: process.env.UPSTASH_REDIS_REST_TOKEN,
    })
  : null;

// Create a new ratelimiter that allows 20 requests per 60 seconds
export const globalRateLimit = redis ? new Ratelimit({
  redis: redis,
  limiter: Ratelimit.slidingWindow(20, "60 s"),
  analytics: true,
  prefix: "@upstash/ratelimit",
}) : null;

/**
 * Check rate limit for a given identifier (IP or User ID).
 * @returns {Promise<boolean>} - True if allowed, False if limited.
 */
export async function checkRateLimit(identifier: string): Promise<{ success: boolean; limit: number; remaining: number; reset: number }> {
  if (!globalRateLimit) {
    return { success: true, limit: 20, remaining: 20, reset: Date.now() };
  }
  try {
    const result = await globalRateLimit.limit(identifier);
    return {
      success: result.success,
      limit: result.limit,
      remaining: result.remaining,
      reset: result.reset,
    };
  } catch (error) {
    console.error("Rate Limit Error:", error);
    // Fail open if Redis is down, but log the error
    return { success: true, limit: 20, remaining: 20, reset: Date.now() };
  }
}
