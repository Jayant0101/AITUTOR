import { createClient as createServerClient } from '@/lib/supabase/server';
import { createClient as createBrowserClient } from '@/lib/supabase/client';

export type UserTier = 'free' | 'pro' | 'enterprise';

export interface TierConfig {
  maxTodos: number;
  aiRequestsPerMonth: number;
  canUseStreaming: boolean;
  canUseBackgroundJobs: boolean;
  canUseVectorSearch: boolean;
  maxStorageMB: number;
}

export const TIER_CONFIGS: Record<UserTier, TierConfig> = {
  free: {
    maxTodos: 10,
    aiRequestsPerMonth: 50,
    canUseStreaming: false,
    canUseBackgroundJobs: false,
    canUseVectorSearch: false,
    maxStorageMB: 100,
  },
  pro: {
    maxTodos: 100,
    aiRequestsPerMonth: 1000,
    canUseStreaming: true,
    canUseBackgroundJobs: true,
    canUseVectorSearch: true,
    maxStorageMB: 1000,
  },
  enterprise: {
    maxTodos: 10000,
    aiRequestsPerMonth: 1000000,
    canUseStreaming: true,
    canUseBackgroundJobs: true,
    canUseVectorSearch: true,
    maxStorageMB: 100000,
  },
};

/**
 * Fetch the current user's subscription tier.
 * This function is isomorphic and works in both Server and Client components.
 */
export async function getUserTier(): Promise<UserTier> {
  const isServer = typeof window === 'undefined';
  const supabase = isServer ? await createServerClient() : createBrowserClient();
  
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) return 'free';

  const { data: profile } = await supabase
    .from('profiles')
    .select('subscription_tier')
    .eq('id', user.id)
    .single();

  return (profile?.subscription_tier as UserTier) || 'free';
}

/**
 * Utility to check if a user has access to a specific feature.
 */
export async function hasFeatureAccess(feature: keyof TierConfig): Promise<boolean | number> {
  const tier = await getUserTier();
  return TIER_CONFIGS[tier][feature];
}
