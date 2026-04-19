import { createClient } from '@/lib/supabase/server';
import { logError, logEvent } from '@/lib/logger';

/**
 * SaaS Analytics System — Tracks user activity and platform usage in Supabase.
 * Reliable for server-side event tracking.
 */
export async function trackEvent(action: string, metadata: any = {}) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) return;

  const event = {
    user_id: user.id,
    action,
    metadata,
  };

  logEvent(action, metadata, "ANALYTICS");

  try {
    const { error } = await supabase.from('user_activity').insert([event]);
    if (error) throw error;
  } catch (err) {
    logError(err, 'ANALYTICS_TRACKING');
  }
}

