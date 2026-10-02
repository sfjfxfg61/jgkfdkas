-- Victoria personal sales bot consolidated upgrade — 2026-09-30
-- Includes the queue used by recurring daily sales follow-ups. Run THIS file only if older draft migrations were not deployed.
-- Run once in Supabase SQL Editor before deploying this release.
-- Safe for the existing data. Nothing is deleted. Legacy xp/memories columns/tables may stay,
-- but this bot no longer reads or writes them.

-- ---------------------------------------------------------------------
-- Users: sales + channel + admin workflow fields
-- ---------------------------------------------------------------------
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS public_channel_member boolean NOT NULL DEFAULT false;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS public_channel_lang text;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS public_channel_checked_at timestamptz;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS sales_stage text NOT NULL DEFAULT 'new';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_offer_at timestamptz;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_checkout_at timestamptz;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_payment_at timestamptz;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS automation_paused boolean NOT NULL DEFAULT false;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS admin_notes text;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS last_admin_reply_at timestamptz;

CREATE INDEX IF NOT EXISTS users_public_channel_idx ON public.users(public_channel_member, blocked);
CREATE INDEX IF NOT EXISTS users_sales_stage_idx ON public.users(sales_stage, blocked);
CREATE INDEX IF NOT EXISTS users_last_active_idx ON public.users(last_active_at DESC);

UPDATE public.users
SET sales_stage = CASE
    WHEN blocked THEN 'blocked'
    WHEN is_premium AND premium_until IS NOT NULL AND premium_until > now() THEN 'paid'
    WHEN total_messages > 0 THEN 'engaged'
    ELSE 'new'
END
WHERE sales_stage IS NULL OR sales_stage = 'new';

-- ---------------------------------------------------------------------
-- Manual inbox and calls (already exist in your DB; IF NOT EXISTS is safe)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pending_replies (
    user_id bigint PRIMARY KEY REFERENCES public.users(user_id) ON DELETE CASCADE,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.call_requests (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    period_end timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'canceled')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS call_requests_user_period_idx ON public.call_requests(user_id, period_end, status);

-- ---------------------------------------------------------------------
-- Sales follow-up queue
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.automation_jobs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(user_id) ON DELETE CASCADE,
    job_type text NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'cancelled', 'failed')),
    scheduled_at timestamptz NOT NULL,
    sent_at timestamptz,
    dedupe_key text NOT NULL UNIQUE,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS automation_jobs_due_idx
    ON public.automation_jobs(status, scheduled_at)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS automation_jobs_user_idx
    ON public.automation_jobs(user_id, created_at DESC);

ALTER TABLE public.automation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pending_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_requests ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------
-- Chat activity: NO XP. Only useful operational counters/timestamps.
-- The old bot used the same signature but returned integer. PostgreSQL
-- cannot change a function return type with CREATE OR REPLACE, so drop
-- that legacy function first and recreate it with the new return type.
-- ---------------------------------------------------------------------
DROP FUNCTION IF EXISTS public.record_chat_activity(bigint);

CREATE OR REPLACE FUNCTION public.record_chat_activity(p_user_id bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE public.users
    SET total_messages = total_messages + 1,
        last_active_at = now(),
        updated_at = now(),
        blocked = false
    WHERE user_id = p_user_id;
END;
$$;

-- ---------------------------------------------------------------------
-- Payments / access
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.record_payment_and_activate(
    p_user_id bigint,
    p_charge_id text,
    p_payload text,
    p_amount integer,
    p_plan text,
    p_market text,
    p_days integer,
    p_recurring boolean,
    p_expires_at timestamptz
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    new_until timestamptz;
BEGIN
    INSERT INTO public.payments(
        user_id, telegram_charge_id, payload, amount, plan, market,
        pricing_variant, duration_days, recurring
    )
    VALUES (
        p_user_id, p_charge_id, p_payload, p_amount, p_plan, p_market,
        coalesce((SELECT pricing_variant FROM public.users WHERE user_id = p_user_id), 'control'),
        p_days, p_recurring
    )
    ON CONFLICT (telegram_charge_id) DO NOTHING;

    IF NOT FOUND THEN
        SELECT premium_until INTO new_until FROM public.users WHERE user_id = p_user_id;
        RETURN jsonb_build_object('premium_until', new_until, 'duplicate', true);
    END IF;

    UPDATE public.users
    SET is_premium = true,
        is_paid = true,
        subscription_tier = p_plan,
        subscription_recurring = p_recurring,
        subscription_canceled = false,
        subscription_charge_id = p_charge_id,
        market = p_market,
        premium_until = coalesce(
            p_expires_at,
            greatest(coalesce(premium_until, now()), now()) + make_interval(days => p_days)
        ),
        sales_stage = 'paid',
        last_payment_at = now(),
        blocked = false,
        updated_at = now()
    WHERE user_id = p_user_id
    RETURNING premium_until INTO new_until;

    RETURN jsonb_build_object('premium_until', new_until, 'duplicate', false);
END;
$$;

CREATE OR REPLACE FUNCTION public.mark_payment_refunded(p_charge_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    payment_user_id bigint;
BEGIN
    UPDATE public.payments
    SET refunded_at = coalesce(refunded_at, now())
    WHERE telegram_charge_id = p_charge_id
    RETURNING user_id INTO payment_user_id;

    IF payment_user_id IS NULL THEN
        RETURN jsonb_build_object('found', false);
    END IF;

    UPDATE public.users
    SET is_premium = false,
        is_paid = false,
        premium_until = null,
        subscription_tier = 'free',
        subscription_recurring = false,
        subscription_canceled = false,
        subscription_charge_id = null,
        sales_stage = 'engaged',
        updated_at = now()
    WHERE user_id = payment_user_id
      AND subscription_charge_id = p_charge_id;

    RETURN jsonb_build_object('found', true, 'user_id', payment_user_id);
END;
$$;

-- ---------------------------------------------------------------------
-- Black plan: max two non-cancelled call requests per paid period.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.request_paid_call(p_user_id bigint)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    u public.users%rowtype;
    used_count integer;
    new_id bigint;
BEGIN
    SELECT * INTO u FROM public.users WHERE user_id = p_user_id FOR UPDATE;
    IF NOT FOUND OR NOT u.is_premium OR u.premium_until IS NULL OR u.premium_until <= now() OR u.subscription_tier <> 'black' THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'plan');
    END IF;

    SELECT count(*) INTO used_count
    FROM public.call_requests
    WHERE user_id = p_user_id
      AND period_end = u.premium_until
      AND status <> 'canceled';

    IF used_count >= 2 THEN
        RETURN jsonb_build_object('ok', false, 'reason', 'limit');
    END IF;

    INSERT INTO public.call_requests(user_id, period_end)
    VALUES (p_user_id, u.premium_until)
    RETURNING id INTO new_id;

    RETURN jsonb_build_object('ok', true, 'id', new_id, 'remaining', 1 - used_count);
END;
$$;

-- ---------------------------------------------------------------------
-- Analytics for /stats
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.victoria_sales_stats()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
WITH
u AS (SELECT * FROM public.users),
p AS (SELECT * FROM public.payments WHERE refunded_at IS NULL),
base AS (
    SELECT
        (SELECT count(*) FROM u) users,
        (SELECT count(*) FROM u WHERE NOT blocked) reachable,
        (SELECT count(*) FROM u WHERE blocked) blocked,
        (SELECT count(*) FROM u WHERE created_at > now() - interval '1 day') new_1d,
        (SELECT count(*) FROM u WHERE created_at > now() - interval '7 days') new_7d,
        (SELECT count(*) FROM u WHERE created_at > now() - interval '30 days') new_30d,
        (SELECT count(*) FROM u WHERE NOT blocked AND last_active_at > now() - interval '1 day') active_1d,
        (SELECT count(*) FROM u WHERE NOT blocked AND last_active_at > now() - interval '7 days') active_7d,
        (SELECT count(*) FROM u WHERE NOT blocked AND last_active_at > now() - interval '30 days') active_30d
),
funnel AS (
    SELECT
        (SELECT count(DISTINCT user_id) FROM public.events WHERE event='public_gate_shown') gate_shown,
        (SELECT count(DISTINCT user_id) FROM public.events WHERE event='public_channel_verified') gate_verified,
        (SELECT count(DISTINCT user_id) FROM public.events WHERE event='public_channel_verify_failed') gate_failed,
        (SELECT count(*) FROM u WHERE public_channel_member AND NOT blocked) public_members_now,
        (SELECT count(DISTINCT user_id) FROM public.events WHERE event='paywall_view') paywall_users,
        (SELECT count(DISTINCT user_id) FROM public.events WHERE event='checkout_created') checkout_users,
        (SELECT count(DISTINCT user_id) FROM p) payer_users,
        (SELECT count(*) FROM u WHERE is_premium AND premium_until > now()) premium_active
),
rev AS (
    SELECT
        coalesce((SELECT sum(amount) FROM p),0) lifetime_stars,
        coalesce((SELECT sum(amount) FROM p WHERE created_at > now() - interval '1 day'),0) stars_1d,
        coalesce((SELECT sum(amount) FROM p WHERE created_at > now() - interval '7 days'),0) stars_7d,
        coalesce((SELECT sum(amount) FROM p WHERE created_at > now() - interval '30 days'),0) stars_30d,
        (SELECT count(*) FROM p) payments,
        (SELECT count(DISTINCT user_id) FROM p) payers,
        (SELECT count(*) FROM public.payments WHERE refunded_at IS NOT NULL) refunds
),
jobs AS (
    SELECT
        (SELECT count(*) FROM public.automation_jobs WHERE status='pending') pending,
        (SELECT count(*) FROM public.events WHERE event='sales_followup_sent') sent,
        (SELECT count(*) FROM public.events WHERE event='followup_conversion') conversions
)
SELECT jsonb_build_object(
    'overview', jsonb_build_object(
        'users', base.users, 'reachable', base.reachable, 'blocked', base.blocked,
        'new_1d', base.new_1d, 'new_7d', base.new_7d, 'new_30d', base.new_30d,
        'active_1d', base.active_1d, 'active_7d', base.active_7d, 'active_30d', base.active_30d
    ),
    'channel', jsonb_build_object(
        'gate_shown', funnel.gate_shown,
        'verified_users', funnel.gate_verified,
        'verify_failed_users', funnel.gate_failed,
        'members_now', funnel.public_members_now,
        'verify_pct', round(100.0 * funnel.gate_verified / greatest(funnel.gate_shown,1),2)
    ),
    'funnel', jsonb_build_object(
        'paywall_users', funnel.paywall_users,
        'checkout_users', funnel.checkout_users,
        'payer_users', funnel.payer_users,
        'premium_active', funnel.premium_active,
        'start_to_paywall_pct', round(100.0 * funnel.paywall_users / greatest(base.users,1),2),
        'paywall_to_checkout_pct', round(100.0 * funnel.checkout_users / greatest(funnel.paywall_users,1),2),
        'checkout_to_paid_pct', round(100.0 * funnel.payer_users / greatest(funnel.checkout_users,1),2),
        'start_to_paid_pct', round(100.0 * funnel.payer_users / greatest(base.users,1),2)
    ),
    'revenue', jsonb_build_object(
        'lifetime_stars', rev.lifetime_stars,
        'stars_1d', rev.stars_1d,
        'stars_7d', rev.stars_7d,
        'stars_30d', rev.stars_30d,
        'payments', rev.payments,
        'payers', rev.payers,
        'arppu_stars', round(rev.lifetime_stars::numeric / greatest(rev.payers,1),1),
        'refunds', rev.refunds,
        'tiers', (
            SELECT coalesce(jsonb_object_agg(plan,n), '{}'::jsonb)
            FROM (SELECT plan, count(*) n FROM p GROUP BY plan ORDER BY count(*) DESC) s
        ),
        'markets', (
            SELECT coalesce(jsonb_object_agg(market,stars), '{}'::jsonb)
            FROM (SELECT market, sum(amount) stars FROM p GROUP BY market ORDER BY sum(amount) DESC) s
        )
    ),
    'followups', jsonb_build_object(
        'pending', jobs.pending,
        'sent', jobs.sent,
        'conversions', jobs.conversions,
        'conversion_pct', round(100.0 * jobs.conversions / greatest(jobs.sent,1),2),
        'by_type', (
            SELECT coalesce(jsonb_object_agg(kind,n), '{}'::jsonb)
            FROM (
                SELECT properties->>'job_type' kind, count(*) n
                FROM public.events
                WHERE event='sales_followup_sent'
                GROUP BY properties->>'job_type'
                ORDER BY count(*) DESC
            ) x
            WHERE kind IS NOT NULL
        )
    ),
    'chat', jsonb_build_object(
        'pending_replies', (SELECT count(*) FROM public.pending_replies),
        'chatters', (SELECT count(DISTINCT user_id) FROM public.messages WHERE role='user'),
        'user_messages', (SELECT count(*) FROM public.messages WHERE role='user'),
        'admin_messages', (SELECT count(*) FROM public.messages WHERE role='assistant')
    ),
    'acquisition', jsonb_build_object(
        'languages', (
            SELECT coalesce(jsonb_object_agg(lang,n), '{}'::jsonb)
            FROM (SELECT coalesce(lang,'unknown') lang, count(*) n FROM u GROUP BY coalesce(lang,'unknown') ORDER BY count(*) DESC) s
        ),
        'markets', (
            SELECT coalesce(jsonb_object_agg(market,n), '{}'::jsonb)
            FROM (SELECT coalesce(market,'unknown') market, count(*) n FROM u GROUP BY coalesce(market,'unknown') ORDER BY count(*) DESC) s
        ),
        'refs', (
            SELECT coalesce(jsonb_object_agg(ref,n), '{}'::jsonb)
            FROM (SELECT coalesce(ref,'direct') ref, count(*) n FROM u GROUP BY coalesce(ref,'direct') ORDER BY count(*) DESC LIMIT 15) s
        )
    )
)
FROM base, funnel, rev, jobs;
$$;

-- RPCs should only be callable with the server-side service role.
REVOKE EXECUTE ON FUNCTION public.record_chat_activity(bigint) FROM public, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.record_payment_and_activate(bigint,text,text,integer,text,text,integer,boolean,timestamptz) FROM public, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.mark_payment_refunded(text) FROM public, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.request_paid_call(bigint) FROM public, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.victoria_sales_stats() FROM public, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.record_chat_activity(bigint) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_payment_and_activate(bigint,text,text,integer,text,text,integer,boolean,timestamptz) TO service_role;
GRANT EXECUTE ON FUNCTION public.mark_payment_refunded(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.request_paid_call(bigint) TO service_role;
GRANT EXECUTE ON FUNCTION public.victoria_sales_stats() TO service_role;
