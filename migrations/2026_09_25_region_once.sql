-- Run once before deploying the region-onboarding code.
-- Existing accounts retain their current market and are not asked again.
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS region_confirmed boolean NOT NULL DEFAULT true;

ALTER TABLE public.users
    ALTER COLUMN region_confirmed SET DEFAULT false;

-- Old accounts have already passed the old /start flow; let them use the open chat.
UPDATE public.users SET onboarding_complete = true
WHERE region_confirmed = true AND onboarding_complete = false;
