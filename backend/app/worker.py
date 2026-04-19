import os
import time
import logging
import uuid
import json
from datetime import datetime, timezone
from app.learner.learner_tracker import LearnerTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("worker")

class BackgroundWorker:
    def __init__(self):
        self.db_path = os.getenv("LEARNER_DB_PATH", "learner.db")
        self.tracker = LearnerTracker(db_path=self.db_path)
        self.worker_id = f"worker-py-{uuid.uuid4().hex[:6]}"
        self.max_retries = 3
        self.poll_interval = 5  # seconds

    def start(self):
        logger.info(f"Starting Python Background Worker: {self.worker_id}")
        while True:
            try:
                self.process_jobs()
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
            time.sleep(self.poll_interval)

    def process_jobs(self):
        # --- TASK 4: ATOMIC JOB CLAIMING ---
        # We use the 'claim_jobs' RPC function defined in schema.sql
        with self.tracker._connect() as conn:
            if not self.tracker.is_postgres:
                logger.warning("Worker requires PostgreSQL for atomic claiming. Skipping...")
                return

            cur = conn.cursor()
            cur.execute("SELECT id, user_id, type, payload, status, retry_count FROM claim_jobs(%s, %s)", (self.worker_id, 10))
            jobs = cur.fetchall()

            if not jobs:
                return

            logger.info(f"Worker {self.worker_id}: Claimed {len(jobs)} jobs")

            for job in jobs:
                job_id = job['id']
                job_type = job['type']
                try:
                    logger.info(f"Processing job {job_id} ({job_type})")
                    self.handle_job(job)
                    
                    # Mark as completed
                    cur.execute(
                        "UPDATE jobs SET status = 'completed', updated_at = %s WHERE id = %s",
                        (datetime.now(timezone.utc), job_id)
                    )
                    logger.info(f"Job {job_id} completed")
                except Exception as e:
                    logger.error(f"Job {job_id} failed: {e}")
                    self.handle_job_failure(cur, job, str(e))

    def handle_job(self, job):
        # Logic for specific job types
        job_type = job['type']
        payload = job['payload'] or {}
        
        if job_type == 'ai_processing':
            # Example: call AI service or update graph
            time.sleep(2) # Simulate work
        elif job_type == 'generate_embedding':
            # Example: generate vector embedding
            time.sleep(1)
        else:
            logger.warning(f"Unknown job type: {job_type}")

    def handle_job_failure(self, cur, job, error_message):
        job_id = job['id']
        next_retry = (job.get('retry_count') or 0) + 1

        if next_retry >= self.max_retries:
            # --- TASK 4: DEAD LETTER LOGGING ---
            logger.error(f"Job {job_id} exceeded max retries. Moving to dead_jobs.")
            cur.execute(
                "INSERT INTO dead_jobs (id, user_id, type, payload, error_message, failed_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (job_id, job['user_id'], job['type'], json.dumps(job['payload']), error_message, datetime.now(timezone.utc))
            )
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        else:
            # --- TASK 4: RETRY LOGGING ---
            logger.info(f"Scheduling retry {next_retry} for job {job_id}")
            cur.execute(
                "UPDATE jobs SET status = 'pending', retry_count = %s, error_message = %s, last_attempt_at = %s, updated_at = %s WHERE id = %s",
                (next_retry, error_message, datetime.now(timezone.utc), datetime.now(timezone.utc), job_id)
            )

if __name__ == "__main__":
    worker = BackgroundWorker()
    worker.start()
