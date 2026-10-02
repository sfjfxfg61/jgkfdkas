-- Victoria follow-up queue v3: crash-safe claiming + retries.
-- Safe to run on the existing database. No user/payment data is deleted.

BEGIN;

ALTER TABLE public.automation_jobs
  ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS locked_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS locked_by text;

-- Allow a worker to atomically claim a job before sending it.
ALTER TABLE public.automation_jobs
  DROP CONSTRAINT IF EXISTS automation_jobs_status_check;

ALTER TABLE public.automation_jobs
  ADD CONSTRAINT automation_jobs_status_check
  CHECK (status = ANY (ARRAY['pending'::text, 'processing'::text, 'sent'::text, 'cancelled'::text, 'failed'::text]));

CREATE INDEX IF NOT EXISTS automation_jobs_due_idx
  ON public.automation_jobs (status, scheduled_at);

CREATE INDEX IF NOT EXISTS automation_jobs_lock_idx
  ON public.automation_jobs (status, locked_at);

DROP FUNCTION IF EXISTS public.claim_due_automation_jobs(integer, text);

CREATE FUNCTION public.claim_due_automation_jobs(
  p_limit integer DEFAULT 100,
  p_worker text DEFAULT 'victoria-worker'
)
RETURNS SETOF public.automation_jobs
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- If Render died after claiming a row, release the stale lock after 10 minutes.
  UPDATE public.automation_jobs
  SET status = 'pending',
      locked_at = NULL,
      locked_by = NULL,
      last_error = LEFT(
        CASE
          WHEN COALESCE(last_error, '') = '' THEN 'Recovered stale processing lock'
          ELSE last_error || ' | Recovered stale processing lock'
        END,
        500
      )
  WHERE status = 'processing'
    AND locked_at IS NOT NULL
    AND locked_at < now() - interval '10 minutes';

  RETURN QUERY
  WITH picked AS (
    SELECT id
    FROM public.automation_jobs
    WHERE status = 'pending'
      AND scheduled_at <= now()
    ORDER BY scheduled_at ASC, id ASC
    FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(1, LEAST(COALESCE(p_limit, 100), 500))
  )
  UPDATE public.automation_jobs AS j
  SET status = 'processing',
      locked_at = now(),
      locked_by = LEFT(COALESCE(NULLIF(p_worker, ''), 'victoria-worker'), 120),
      attempts = COALESCE(j.attempts, 0) + 1
  FROM picked
  WHERE j.id = picked.id
  RETURNING j.*;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.claim_due_automation_jobs(integer, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_due_automation_jobs(integer, text)
  TO service_role;

COMMIT;
