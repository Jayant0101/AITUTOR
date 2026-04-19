import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';
import { trackEvent } from '@/lib/analytics/tracker';

/**
 * Background Job System API.
 * Queues long-running tasks for asynchronous processing.
 */
export async function POST(req: Request) {
  try {
    const supabase = await createClient();
    const body = await req.json();
    
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return Response.json({ error: "Unauthorized" }, { status: 401 });

    logInfo(`Queueing background job: ${body.type}`, "JOB_SYSTEM");

    const { data, error } = await supabase.from('jobs').insert({
      type: body.type || 'ai_processing',
      payload: body.payload || {},
      status: 'pending',
      user_id: user.id
    }).select().single();

    if (error) throw error;

    await trackEvent('job_queued', { job_id: data.id, type: data.type });

    return Response.json({ status: 'queued', job_id: data.id });
  } catch (error) {
    logError(error, "JOB_API_ROUTE");
    return Response.json({ error: "Failed to queue job" }, { status: 500 });
  }
}
