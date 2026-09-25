-- Run after 2026_09_25_region_once.sql, before deploying the Python release.
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS channel_member boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS users_channel_expiry_idx
ON public.users(premium_until) WHERE channel_member = true;

CREATE TABLE IF NOT EXISTS public.pending_replies (
    user_id bigint PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pending_replies_due_idx ON public.pending_replies(updated_at);
ALTER TABLE public.pending_replies ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.record_chat_activity(p_user_id bigint)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE previous_stage integer;
BEGIN
    UPDATE public.users SET
        total_messages = total_messages + 1,
        last_active_at = now(), last_reminder_at = NULL,
        reminder_stage = 0, updated_at = now()
    WHERE user_id = p_user_id
    RETURNING reminder_stage INTO previous_stage;
    RETURN coalesce(previous_stage, 0);
END $$;
REVOKE EXECUTE ON FUNCTION public.record_chat_activity(bigint) FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_chat_activity(bigint) TO service_role;

CREATE TABLE IF NOT EXISTS public.call_requests (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(user_id),
    period_end timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'canceled')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS calls_user_period_idx ON public.call_requests(user_id, period_end);
ALTER TABLE public.call_requests ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.request_paid_call(p_user_id bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE u public.users%rowtype; n integer; request_id bigint;
BEGIN
    SELECT * INTO u FROM public.users WHERE user_id = p_user_id FOR UPDATE;
    IF NOT FOUND OR u.subscription_tier <> 'black' OR u.premium_until <= now() THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'inactive');
    END IF;
    SELECT count(*) INTO n FROM public.call_requests
    WHERE user_id = p_user_id AND period_end = u.premium_until AND status <> 'canceled';
    IF n >= 2 THEN RETURN jsonb_build_object('ok', false, 'reason', 'limit'); END IF;
    INSERT INTO public.call_requests(user_id, period_end)
    VALUES (p_user_id, u.premium_until) RETURNING id INTO request_id;
    RETURN jsonb_build_object('ok', true, 'id', request_id, 'remaining', 1 - n);
END $$;
REVOKE EXECUTE ON FUNCTION public.request_paid_call(bigint) FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.request_paid_call(bigint) TO service_role;

CREATE OR REPLACE FUNCTION public.companion_retention_days()
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
WITH cohorts AS (
    SELECT u.user_id,
           (u.created_at AT TIME ZONE 'Europe/Kyiv')::date AS joined,
           (now() AT TIME ZONE 'Europe/Kyiv')::date AS today,
           EXISTS (SELECT 1 FROM public.messages m WHERE m.user_id = u.user_id AND m.role = 'user'
                   AND (m.created_at AT TIME ZONE 'Europe/Kyiv')::date = (u.created_at AT TIME ZONE 'Europe/Kyiv')::date + 1) AS d1,
           EXISTS (SELECT 1 FROM public.messages m WHERE m.user_id = u.user_id AND m.role = 'user'
                   AND (m.created_at AT TIME ZONE 'Europe/Kyiv')::date = (u.created_at AT TIME ZONE 'Europe/Kyiv')::date + 3) AS d3,
           EXISTS (SELECT 1 FROM public.messages m WHERE m.user_id = u.user_id AND m.role = 'user'
                   AND (m.created_at AT TIME ZONE 'Europe/Kyiv')::date = (u.created_at AT TIME ZONE 'Europe/Kyiv')::date + 7) AS d7
    FROM public.users u
), totals AS (
    SELECT count(*) FILTER (WHERE joined <= today - 1) AS e1,
           count(*) FILTER (WHERE joined <= today - 1 AND d1) AS r1,
           count(*) FILTER (WHERE joined <= today - 3) AS e3,
           count(*) FILTER (WHERE joined <= today - 3 AND d3) AS r3,
           count(*) FILTER (WHERE joined <= today - 7) AS e7,
           count(*) FILTER (WHERE joined <= today - 7 AND d7) AS r7
    FROM cohorts
)
SELECT jsonb_build_object(
    'd1_eligible', e1, 'd1_returned', r1, 'd1_pct', round(100.0 * r1 / greatest(e1, 1), 2),
    'd3_eligible', e3, 'd3_returned', r3, 'd3_pct', round(100.0 * r3 / greatest(e3, 1), 2),
    'd7_eligible', e7, 'd7_returned', r7, 'd7_pct', round(100.0 * r7 / greatest(e7, 1), 2)
) FROM totals;
$$;
REVOKE EXECUTE ON FUNCTION public.companion_retention_days() FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.companion_retention_days() TO service_role;

CREATE OR REPLACE FUNCTION public.companion_membership_stats()
RETURNS jsonb LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
SELECT jsonb_build_object(
    'channel_members', (SELECT count(*) FROM public.users WHERE channel_member),
    'joined', (SELECT count(*) FROM public.events WHERE event = 'channel_joined'),
    'access_ended', (SELECT count(*) FROM public.events WHERE event = 'channel_access_ended'),
    'reply_queue', (SELECT count(*) FROM public.pending_replies),
    'delayed_replies', (SELECT count(*) FROM public.events WHERE event = 'delayed_reply_sent'),
    'call_pending', (SELECT count(*) FROM public.call_requests WHERE status = 'pending'),
    'call_completed', (SELECT count(*) FROM public.call_requests WHERE status = 'completed')
);
$$;
REVOKE EXECUTE ON FUNCTION public.companion_membership_stats() FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.companion_membership_stats() TO service_role;
