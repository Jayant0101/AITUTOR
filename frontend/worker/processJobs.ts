import { createClient } from '@supabase/supabase-js';
import { optimizeSystem } from './optimizeSystem';

/**
 * Enterprise-Grade Background Worker.
 * Handles job polling, retry logic with exponential backoff, and failure logging.
 */

interface Job {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  retry_count: number;
  user_id: string;
}

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!; // Required for worker

const supabase = createClient(supabaseUrl, supabaseServiceKey);

const MAX_RETRIES = 3;
const POLL_INTERVAL = 5000; // 5 seconds
const WORKER_ID = `worker-${Math.random().toString(36).substring(2, 9)}`;

async function processJobs() {
  console.log(`Worker ${WORKER_ID}: Polling for pending jobs...`);

  // Atomic claim to prevent race conditions
  const { data, error } = await supabase.rpc('claim_jobs', { 
    worker_id: WORKER_ID, 
    batch_size: 10 
  });

  if (error) {
    console.error('Worker: Error claiming jobs', error);
    return;
  }

  const jobs = data as Job[] | null;

  if (!jobs || jobs.length === 0) return;

  for (const job of jobs) {
    try {
      console.log(`Worker: Processing job ${job.id} (${job.type})`);

      // 2. Perform Job Logic
      await handleJob(job);

      // 3. Mark as completed
      await supabase
        .from('jobs')
        .update({ status: 'completed', updated_at: new Date().toISOString() })
        .eq('id', job.id);

      console.log(`Worker: Job ${job.id} completed successfully`);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      console.error(`Worker: Job ${job.id} failed`, err);
      await handleJobFailure(job, errorMessage);
    }
  }
}

async function handleJob(job: Job) {
  if (job.type === 'ai_processing') {
    // Simulated AI work
    await new Promise(resolve => setTimeout(resolve, 2000));
  } else if (job.type === 'generate_embedding') {
    // Simulated embedding generation
    await new Promise(resolve => setTimeout(resolve, 1000));
  } else if (job.type === 'optimize_system') {
    await optimizeSystem();
  } else {
    console.warn(`Worker: Unknown job type ${job.type}`);
  }
}

async function handleJobFailure(job: Job, errorMessage: string) {
  const nextRetryCount = (job.retry_count || 0) + 1;

  if (nextRetryCount >= MAX_RETRIES) {
    // Move to dead letter table
    console.log(`Worker: Job ${job.id} exceeded max retries. Moving to dead_jobs.`);
    
    await supabase.from('dead_jobs').insert({
      id: job.id,
      user_id: job.user_id,
      type: job.type,
      payload: job.payload,
      error_message: errorMessage
    });

    await supabase.from('jobs').delete().eq('id', job.id);
  } else {
    // Calculate exponential backoff (e.g., 2^retry * 1000ms)
    const backoffMs = Math.pow(2, nextRetryCount) * 1000;
    
    await supabase
      .from('jobs')
      .update({
        status: 'pending', // Reset to pending for retry
        retry_count: nextRetryCount,
        error_message: errorMessage,
        last_attempt_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .eq('id', job.id);
      
    console.log(`Worker: Job ${job.id} scheduled for retry ${nextRetryCount} in ${backoffMs}ms`);
  }
}

// Start the worker loop
function startWorker() {
  setInterval(processJobs, POLL_INTERVAL);
  console.log('Worker: Background job system started.');
}

// In a real production environment (like Vercel), this might be a cron job 
// or a long-running process on a VPS/Container.
if (require.main === module) {
  startWorker();
}

export { processJobs, startWorker };
