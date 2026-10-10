-- Victoria v11: fresh install OR upgrade of the schema supplied in chat.
-- Stop the old bot first; run this ONE file in Supabase SQL editor.
BEGIN;
CREATE TABLE IF NOT EXISTS public.users (user_id bigint PRIMARY KEY, username text, first_name text,
lang varchar DEFAULT 'en' CHECK(lang IN ('ru','uk','en','es','de','fr')),
ref text DEFAULT 'direct', is_paid boolean DEFAULT false, created_at timestamptz DEFAULT now(),
style text NOT NULL DEFAULT 'warm', is_premium boolean NOT NULL DEFAULT false,
market text NOT NULL DEFAULT 'global', pricing_variant text NOT NULL DEFAULT 'control',
subscription_tier text NOT NULL DEFAULT 'free', subscription_recurring boolean NOT NULL DEFAULT false,
subscription_canceled boolean NOT NULL DEFAULT false, subscription_charge_id text,
onboarding_complete boolean NOT NULL DEFAULT false, proactive_enabled boolean NOT NULL DEFAULT false,
premium_until timestamptz, daily_message_count int NOT NULL DEFAULT 0, daily_message_date date NOT NULL DEFAULT CURRENT_DATE,
total_messages int NOT NULL DEFAULT 0, xp int NOT NULL DEFAULT 0, blocked boolean NOT NULL DEFAULT false,
last_active_at timestamptz NOT NULL DEFAULT now(), last_proactive_at timestamptz, human_takeover_until timestamptz,
updated_at timestamptz NOT NULL DEFAULT now(), last_reminder_at timestamptz, reminder_stage smallint NOT NULL DEFAULT 0 CHECK(reminder_stage BETWEEN 0 AND 3),
channel_member boolean NOT NULL DEFAULT false, region_confirmed boolean NOT NULL DEFAULT false,
public_channel_member boolean NOT NULL DEFAULT false, public_channel_lang text, public_channel_checked_at timestamptz,
sales_stage text NOT NULL DEFAULT 'new', last_offer_at timestamptz, last_checkout_at timestamptz, last_payment_at timestamptz,
automation_paused boolean NOT NULL DEFAULT false, admin_notes text, last_admin_reply_at timestamptz);
CREATE TABLE IF NOT EXISTS public.messages (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), role text NOT NULL CHECK(role IN ('user','assistant')), content text NOT NULL CHECK(char_length(content)<=8000), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.memories (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), memory_key text NOT NULL, memory_value text NOT NULL, confidence real NOT NULL DEFAULT 0.8 CHECK(confidence BETWEEN 0 AND 1), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.payments (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), telegram_charge_id text NOT NULL UNIQUE, payload text NOT NULL, amount int NOT NULL CHECK(amount>0), currency text NOT NULL DEFAULT 'XTR', plan text NOT NULL DEFAULT 'plus', market text NOT NULL DEFAULT 'global', pricing_variant text NOT NULL DEFAULT 'control', duration_days int NOT NULL DEFAULT 30, recurring boolean NOT NULL DEFAULT false, refunded_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.events (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), event text NOT NULL, properties jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.pending_replies (user_id bigint PRIMARY KEY REFERENCES public.users(user_id), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.call_requests (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), period_end timestamptz NOT NULL, status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','completed','canceled')), created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.automation_jobs (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), job_type text NOT NULL, status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','sent','cancelled','failed')), scheduled_at timestamptz NOT NULL, sent_at timestamptz, dedupe_key text NOT NULL UNIQUE, payload jsonb NOT NULL DEFAULT '{}', last_error text, created_at timestamptz NOT NULL DEFAULT now(), attempts int NOT NULL DEFAULT 0, locked_at timestamptz, locked_by text);
CREATE TABLE IF NOT EXISTS public.subscription_cancellations (charge_id text PRIMARY KEY, user_id bigint NOT NULL REFERENCES public.users(user_id), completed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS entitlement_until timestamptz;
ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS subscription_root text;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS subscription_payload text;
UPDATE public.users u SET subscription_payload=p.payload FROM public.payments p
WHERE u.subscription_charge_id=p.telegram_charge_id AND u.subscription_payload IS NULL;

-- Victoria v10 safe migration
-- Non-destructive migration: preserves tables, rows, columns, and historical data.
-- Safe to run on the existing schema shared in chat.


-- 1) Stop legacy sales jobs so an old deployment's daily chase does not fire
-- after v10 is deployed. Historical rows remain for analytics.
UPDATE public.automation_jobs
SET status = 'cancelled',
    locked_at = NULL,
    locked_by = NULL,
    last_error = CASE
      WHEN coalesce(last_error, '') = '' THEN 'cancelled by Victoria v10 migration'
      ELSE left(last_error || ' | cancelled by Victoria v10 migration', 500)
    END
WHERE status IN ('pending', 'processing')
  AND job_type IN (
    'cold_6h','cold_24h','cold_daily',
    'offer_12h','offer_48h','offer_daily',
    'checkout_5m','checkout_30m','checkout_3h','checkout_12h','checkout_23h','checkout_daily'
  );

-- 2) Performance indexes. CREATE IF NOT EXISTS is idempotent and non-destructive.
CREATE INDEX IF NOT EXISTS idx_victoria_events_event_created_user
  ON public.events (event, created_at DESC, user_id);
CREATE INDEX IF NOT EXISTS idx_victoria_jobs_status_scheduled
  ON public.automation_jobs (status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_victoria_users_created
  ON public.users (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_victoria_users_last_active
  ON public.users (last_active_at DESC);
CREATE INDEX IF NOT EXISTS idx_victoria_payments_user_created
  ON public.payments (user_id, created_at DESC)
  WHERE refunded_at IS NULL;

-- 3) Better business analytics: lifetime + a clean 7-day new-user cohort.
CREATE OR REPLACE FUNCTION public.victoria_sales_stats()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
WITH
u AS (SELECT * FROM public.users),
p AS (SELECT * FROM public.payments WHERE refunded_at IS NULL),
cohort7 AS (
    SELECT user_id FROM u WHERE created_at > now() - interval '7 days'
),
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
        (SELECT count(*) FROM u WHERE is_premium AND premium_until > now()) premium_active,
        (SELECT count(*) FROM u
          WHERE NOT is_premium
            AND sales_stage IN ('checkout_started','checkout_abandoned')
            AND last_checkout_at > now() - interval '24 hours') hot_checkout_24h
),
funnel7 AS (
    SELECT
        (SELECT count(*) FROM cohort7) users,
        (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN cohort7 c USING(user_id) WHERE e.event='public_gate_shown') gate_shown,
        (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN cohort7 c USING(user_id) WHERE e.event='public_channel_verified') gate_verified,
        (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN cohort7 c USING(user_id) WHERE e.event='paywall_view') paywall_users,
        (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN cohort7 c USING(user_id) WHERE e.event='checkout_created') checkout_users,
        (SELECT count(DISTINCT p.user_id) FROM p JOIN cohort7 c USING(user_id)) payer_users
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
        (SELECT count(*) FROM public.events WHERE event='followup_conversion') conversions,
        (SELECT count(*) FROM public.events WHERE event='sales_followup_sent' AND created_at > now() - interval '7 days') sent_7d,
        (SELECT count(*) FROM public.events WHERE event='followup_conversion' AND created_at > now() - interval '7 days') conversions_7d
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
        'hot_checkout_24h', funnel.hot_checkout_24h,
        'start_to_paywall_pct', round(100.0 * funnel.paywall_users / greatest(base.users,1),2),
        'paywall_to_checkout_pct', round(100.0 * funnel.checkout_users / greatest(funnel.paywall_users,1),2),
        'checkout_to_paid_pct', round(100.0 * funnel.payer_users / greatest(funnel.checkout_users,1),2),
        'start_to_paid_pct', round(100.0 * funnel.payer_users / greatest(base.users,1),2)
    ),
    'funnel_7d', jsonb_build_object(
        'users', funnel7.users,
        'gate_shown', funnel7.gate_shown,
        'gate_verified', funnel7.gate_verified,
        'paywall_users', funnel7.paywall_users,
        'checkout_users', funnel7.checkout_users,
        'payer_users', funnel7.payer_users,
        'gate_verify_pct', round(100.0 * funnel7.gate_verified / greatest(funnel7.gate_shown,1),2),
        'start_to_paywall_pct', round(100.0 * funnel7.paywall_users / greatest(funnel7.users,1),2),
        'paywall_to_checkout_pct', round(100.0 * funnel7.checkout_users / greatest(funnel7.paywall_users,1),2),
        'checkout_to_paid_pct', round(100.0 * funnel7.payer_users / greatest(funnel7.checkout_users,1),2)
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
        'sent_7d', jobs.sent_7d,
        'conversions_7d', jobs.conversions_7d,
        'by_type', (
            SELECT coalesce(jsonb_object_agg(kind,n), '{}'::jsonb)
            FROM (
                SELECT properties->>'job_type' kind, count(*) n
                FROM public.events
                WHERE event='sales_followup_sent'
                GROUP BY properties->>'job_type'
                ORDER BY count(*) DESC
            ) x WHERE kind IS NOT NULL
        ),
        'by_type_7d', (
            SELECT coalesce(jsonb_object_agg(kind,n), '{}'::jsonb)
            FROM (
                SELECT properties->>'job_type' kind, count(*) n
                FROM public.events
                WHERE event='sales_followup_sent'
                  AND created_at > now() - interval '7 days'
                GROUP BY properties->>'job_type'
                ORDER BY count(*) DESC
            ) x WHERE kind IS NOT NULL
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
        ),
        'refs_7d', (
            SELECT coalesce(jsonb_object_agg(ref,n), '{}'::jsonb)
            FROM (
                SELECT coalesce(u.ref,'direct') ref, count(*) n
                FROM u JOIN cohort7 c USING(user_id)
                GROUP BY coalesce(u.ref,'direct')
                ORDER BY count(*) DESC LIMIT 15
            ) s
        ),
        'markets_7d', (
            SELECT coalesce(jsonb_object_agg(market,n), '{}'::jsonb)
            FROM (
                SELECT coalesce(u.market,'unknown') market, count(*) n
                FROM u JOIN cohort7 c USING(user_id)
                GROUP BY coalesce(u.market,'unknown')
                ORDER BY count(*) DESC
            ) s
        )
    )
)
FROM base, funnel, funnel7, rev, jobs;
$$;

REVOKE EXECUTE ON FUNCTION public.victoria_sales_stats() FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.victoria_sales_stats() TO service_role;

-- 4) Traffic partner / uploader profiles.
-- A customer is attributed on first registration through /start p_<code>.
CREATE TABLE IF NOT EXISTS public.traffic_partners (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  telegram_user_id bigint NOT NULL UNIQUE,
  code text NOT NULL UNIQUE CHECK (code ~ '^[a-z0-9_]{3,32}$'),
  display_name text NOT NULL,
  commission_pct numeric(5,2) NOT NULL DEFAULT 30.00 CHECK (commission_pct >= 0 AND commission_pct <= 100),
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.traffic_commissions (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  partner_id bigint NOT NULL REFERENCES public.traffic_partners(id) ON DELETE RESTRICT,
  payment_id bigint NOT NULL UNIQUE REFERENCES public.payments(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES public.users(user_id) ON DELETE RESTRICT,
  gross_stars integer NOT NULL CHECK (gross_stars > 0),
  commission_pct numeric(5,2) NOT NULL CHECK (commission_pct >= 0 AND commission_pct <= 100),
  commission_stars integer NOT NULL CHECK (commission_stars >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.partner_payouts (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  partner_id bigint NOT NULL REFERENCES public.traffic_partners(id) ON DELETE RESTRICT,
  amount_stars integer NOT NULL CHECK (amount_stars > 0),
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_victoria_users_ref ON public.users(ref);
CREATE INDEX IF NOT EXISTS idx_victoria_partners_active ON public.traffic_partners(active, created_at);
CREATE INDEX IF NOT EXISTS idx_victoria_commissions_partner_created ON public.traffic_commissions(partner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_victoria_payouts_partner_created ON public.partner_payouts(partner_id, created_at DESC);

-- Commission is frozen at the rate that was active when the successful payment
-- was recorded. Changing a partner rate therefore affects future sales only.
CREATE OR REPLACE FUNCTION public.victoria_record_partner_commission()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_partner public.traffic_partners%ROWTYPE;
BEGIN
  SELECT tp.*
  INTO v_partner
  FROM public.traffic_partners tp
  JOIN public.users u ON u.user_id = NEW.user_id
  WHERE u.ref = ('p_' || tp.code)
    AND u.user_id <> tp.telegram_user_id
  LIMIT 1;

  IF FOUND THEN
    INSERT INTO public.traffic_commissions (
      partner_id, payment_id, user_id, gross_stars, commission_pct, commission_stars, created_at
    ) VALUES (
      v_partner.id,
      NEW.id,
      NEW.user_id,
      NEW.amount,
      v_partner.commission_pct,
      floor((NEW.amount::numeric * v_partner.commission_pct) / 100.0)::integer,
      NEW.created_at
    )
    ON CONFLICT (payment_id) DO NOTHING;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_victoria_partner_commission ON public.payments;
CREATE TRIGGER trg_victoria_partner_commission
AFTER INSERT ON public.payments
FOR EACH ROW EXECUTE FUNCTION public.victoria_record_partner_commission();

-- Backfill is idempotent. It matters if partners are created before importing
-- historical payments or if this migration is re-run later.
INSERT INTO public.traffic_commissions (
  partner_id, payment_id, user_id, gross_stars, commission_pct, commission_stars, created_at
)
SELECT
  tp.id,
  p.id,
  p.user_id,
  p.amount,
  tp.commission_pct,
  floor((p.amount::numeric * tp.commission_pct) / 100.0)::integer,
  p.created_at
FROM public.payments p
JOIN public.users u ON u.user_id = p.user_id
JOIN public.traffic_partners tp ON u.ref = ('p_' || tp.code)
WHERE u.user_id <> tp.telegram_user_id
ON CONFLICT (payment_id) DO NOTHING;

-- Aggregate dashboard used both by the admin and by the uploader's own /partner profile.
-- It intentionally exposes only aggregate customer data to uploaders.
CREATE OR REPLACE FUNCTION public.victoria_partner_stats(p_code text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_partner public.traffic_partners%ROWTYPE;
  v_ref text;
  v_result jsonb;
BEGIN
  SELECT * INTO v_partner
  FROM public.traffic_partners
  WHERE code = lower(trim(p_code))
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN '{}'::jsonb;
  END IF;

  v_ref := 'p_' || v_partner.code;

  WITH lead_users AS (
      SELECT * FROM public.users
      WHERE ref = v_ref AND user_id <> v_partner.telegram_user_id
  ),
  lead_ids AS (
      SELECT user_id FROM lead_users
  ),
  valid_payments AS (
      SELECT p.*
      FROM public.payments p
      JOIN lead_ids l USING (user_id)
      WHERE p.refunded_at IS NULL
  ),
  valid_commissions AS (
      SELECT tc.*
      FROM public.traffic_commissions tc
      JOIN public.payments p ON p.id = tc.payment_id
      WHERE tc.partner_id = v_partner.id AND p.refunded_at IS NULL
  ),
  paid_out AS (
      SELECT coalesce(sum(amount_stars), 0)::bigint amount
      FROM public.partner_payouts
      WHERE partner_id = v_partner.id
  )
  SELECT jsonb_build_object(
      'partner', jsonb_build_object(
          'id', v_partner.id,
          'telegram_user_id', v_partner.telegram_user_id,
          'code', v_partner.code,
          'display_name', v_partner.display_name,
          'commission_pct', v_partner.commission_pct,
          'active', v_partner.active,
          'created_at', v_partner.created_at
      ),
      'traffic', jsonb_build_object(
          'link_starts', (SELECT count(*) FROM public.events WHERE event='start' AND properties->>'incoming_ref' = v_ref),
          'unique_link_starters', (SELECT count(DISTINCT user_id) FROM public.events WHERE event='start' AND properties->>'incoming_ref' = v_ref),
          'link_starts_7d', (SELECT count(*) FROM public.events WHERE event='start' AND properties->>'incoming_ref' = v_ref AND created_at > now() - interval '7 days'),
          'leads', (SELECT count(*) FROM lead_users),
          'reachable', (SELECT count(*) FROM lead_users WHERE NOT blocked),
          'blocked', (SELECT count(*) FROM lead_users WHERE blocked),
          'leads_1d', (SELECT count(*) FROM lead_users WHERE created_at > now() - interval '1 day'),
          'leads_7d', (SELECT count(*) FROM lead_users WHERE created_at > now() - interval '7 days'),
          'leads_30d', (SELECT count(*) FROM lead_users WHERE created_at > now() - interval '30 days'),
          'active_7d', (SELECT count(*) FROM lead_users WHERE NOT blocked AND last_active_at > now() - interval '7 days')
      ),
      'funnel', jsonb_build_object(
          'gate_verified', (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='public_channel_verified'),
          'paywall_users', (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='paywall_view'),
          'checkout_users', (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='checkout_created'),
          'payer_users', (SELECT count(DISTINCT user_id) FROM valid_payments),
          'paywall_to_checkout_pct', round(100.0 * (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='checkout_created') / greatest((SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='paywall_view'),1), 2),
          'lead_to_paid_pct', round(100.0 * (SELECT count(DISTINCT user_id) FROM valid_payments) / greatest((SELECT count(*) FROM lead_users),1), 2)
      ),
      'revenue', jsonb_build_object(
          'gross_stars', coalesce((SELECT sum(amount) FROM valid_payments),0),
          'gross_stars_7d', coalesce((SELECT sum(amount) FROM valid_payments WHERE created_at > now() - interval '7 days'),0),
          'payments', (SELECT count(*) FROM valid_payments),
          'payers', (SELECT count(DISTINCT user_id) FROM valid_payments),
          'commission_earned_stars', coalesce((SELECT sum(commission_stars) FROM valid_commissions),0),
          'commission_earned_7d_stars', coalesce((SELECT sum(commission_stars) FROM valid_commissions WHERE created_at > now() - interval '7 days'),0),
          'paid_out_stars', (SELECT amount FROM paid_out),
          'balance_stars', coalesce((SELECT sum(commission_stars) FROM valid_commissions),0) - (SELECT amount FROM paid_out)
      ),
      'recent', jsonb_build_object(
          'paywall_7d', (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='paywall_view' AND e.created_at > now() - interval '7 days'),
          'checkout_7d', (SELECT count(DISTINCT e.user_id) FROM public.events e JOIN lead_ids l USING(user_id) WHERE e.event='checkout_created' AND e.created_at > now() - interval '7 days'),
          'payers_7d', (SELECT count(DISTINCT user_id) FROM valid_payments WHERE created_at > now() - interval '7 days')
      )
  ) INTO v_result;

  RETURN v_result;
END;
$$;

REVOKE ALL ON TABLE public.traffic_partners FROM anon, authenticated;
REVOKE ALL ON TABLE public.traffic_commissions FROM anon, authenticated;
REVOKE ALL ON TABLE public.partner_payouts FROM anon, authenticated;
GRANT ALL ON TABLE public.traffic_partners TO service_role;
GRANT ALL ON TABLE public.traffic_commissions TO service_role;
GRANT ALL ON TABLE public.partner_payouts TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

REVOKE EXECUTE ON FUNCTION public.victoria_partner_stats(text) FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.victoria_partner_stats(text) TO service_role;
REVOKE EXECUTE ON FUNCTION public.victoria_record_partner_commission() FROM public, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.victoria_record_partner_commission() TO service_role;



-- All new RPCs have versioned names: no incompatible CREATE OR REPLACE of old functions.
CREATE OR REPLACE FUNCTION public.victoria_v11_activate(
 p_user_id bigint, p_charge_id text, p_payload text, p_amount integer,
 p_plan text, p_market text, p_days integer, p_recurring boolean,
 p_expires_at timestamptz DEFAULT NULL, p_first_recurring boolean DEFAULT false
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE u public.users%ROWTYPE; old_payment public.payments%ROWTYPE; until_at timestamptz; root_charge text;
BEGIN
 IF p_amount<=0 OR p_days<=0 OR p_plan NOT IN ('plus','pro','ultra','black') THEN
  RAISE EXCEPTION 'Invalid payment';
 END IF;
 INSERT INTO users(user_id) VALUES(p_user_id) ON CONFLICT DO NOTHING;
 SELECT * INTO u FROM users WHERE user_id=p_user_id FOR UPDATE;
 SELECT * INTO old_payment FROM payments WHERE telegram_charge_id=p_charge_id;
 IF FOUND THEN
  IF old_payment.user_id<>p_user_id THEN RAISE EXCEPTION 'Charge owner mismatch'; END IF;
  RETURN jsonb_build_object('duplicate',true,'premium_until',u.premium_until,'refunded',old_payment.refunded_at IS NOT NULL);
 END IF;
 until_at := CASE WHEN p_expires_at IS NOT NULL THEN p_expires_at
                  ELSE greatest(now(),coalesce(u.premium_until,now()))+make_interval(days=>p_days) END;
 IF NOT p_first_recurring AND u.subscription_payload IS NOT NULL AND u.subscription_payload<>p_payload THEN
  SELECT coalesce(subscription_root,telegram_charge_id) INTO root_charge FROM payments
  WHERE user_id=p_user_id AND payload=p_payload ORDER BY created_at,id LIMIT 1;
  INSERT INTO payments(user_id,telegram_charge_id,payload,amount,plan,market,duration_days,recurring,entitlement_until,subscription_root)
  VALUES(p_user_id,p_charge_id,p_payload,p_amount,p_plan,p_market,p_days,p_recurring,until_at,root_charge);
  IF root_charge IS NOT NULL THEN
   INSERT INTO subscription_cancellations(charge_id,user_id) VALUES(root_charge,p_user_id) ON CONFLICT DO NOTHING;
  END IF;
  RETURN jsonb_build_object('duplicate',false,'ignored_renewal',true,'premium_until',u.premium_until);
 END IF;
 -- Never shorten a still-valid entitlement on tier replacement.
 until_at := greatest(until_at,coalesce(u.premium_until,until_at));
 INSERT INTO payments(user_id,telegram_charge_id,payload,amount,plan,market,duration_days,recurring,entitlement_until,subscription_root)
 VALUES(p_user_id,p_charge_id,p_payload,p_amount,p_plan,p_market,p_days,p_recurring,until_at,
 CASE WHEN p_first_recurring THEN p_charge_id ELSE coalesce(u.subscription_charge_id,p_charge_id) END);
 IF p_first_recurring AND u.subscription_recurring AND u.subscription_charge_id IS NOT NULL
    AND u.subscription_charge_id<>p_charge_id THEN
  INSERT INTO subscription_cancellations(charge_id,user_id) VALUES(u.subscription_charge_id,p_user_id)
  ON CONFLICT DO NOTHING;
 END IF;
 UPDATE users SET is_paid=true,is_premium=true,premium_until=until_at,subscription_tier=p_plan,
 subscription_recurring=p_recurring,
 subscription_canceled=CASE WHEN p_first_recurring THEN false ELSE subscription_canceled END,
 subscription_charge_id=CASE WHEN p_first_recurring OR subscription_charge_id IS NULL THEN p_charge_id ELSE subscription_charge_id END,
 subscription_payload=p_payload,market=p_market,sales_stage='paid',last_payment_at=now(),updated_at=now()
 WHERE user_id=p_user_id;
 UPDATE automation_jobs SET status='cancelled',locked_at=NULL,locked_by=NULL
 WHERE user_id=p_user_id AND status IN ('pending','processing') AND job_type<>'buyer_checkin_10m';
 RETURN jsonb_build_object('duplicate',false,'premium_until',until_at);
END; $$;

CREATE OR REPLACE FUNCTION public.victoria_v11_request_call(p_user_id bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE u public.users%ROWTYPE; request_id bigint;
BEGIN
 SELECT * INTO u FROM users WHERE user_id=p_user_id FOR UPDATE;
 IF NOT FOUND OR NOT u.is_premium OR u.premium_until<=now() OR u.premium_until IS NULL OR u.subscription_tier<>'black' THEN
  RETURN jsonb_build_object('ok',false,'reason','plan');
 END IF;
 SELECT id INTO request_id FROM call_requests WHERE user_id=p_user_id AND status='pending' ORDER BY id DESC LIMIT 1;
 IF FOUND THEN RETURN jsonb_build_object('ok',true,'id',request_id,'existing',true); END IF;
 INSERT INTO call_requests(user_id,period_end) VALUES(p_user_id,u.premium_until) RETURNING id INTO request_id;
 RETURN jsonb_build_object('ok',true,'id',request_id,'existing',false);
END; $$;

CREATE OR REPLACE FUNCTION public.victoria_v11_chat_activity(p_user_id bigint)
RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path=public AS $$
 UPDATE users SET total_messages=total_messages+1,
 daily_message_count=CASE WHEN daily_message_date=CURRENT_DATE THEN daily_message_count+1 ELSE 1 END,
 daily_message_date=CURRENT_DATE,last_active_at=now(),updated_at=now() WHERE user_id=p_user_id;
$$;

CREATE OR REPLACE FUNCTION public.victoria_v11_refund(p_charge_id text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE pay public.payments%ROWTYPE; latest public.payments%ROWTYPE; expiry timestamptz; active boolean;
BEGIN
 SELECT * INTO pay FROM payments WHERE telegram_charge_id=p_charge_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Unknown charge; reconcile refund manually'; END IF;
 PERFORM 1 FROM users WHERE user_id=pay.user_id FOR UPDATE;
 IF pay.recurring THEN
  INSERT INTO subscription_cancellations(charge_id,user_id)
  VALUES(coalesce(pay.subscription_root,pay.telegram_charge_id),pay.user_id) ON CONFLICT DO NOTHING;
 END IF;
 UPDATE payments SET refunded_at=coalesce(refunded_at,now()) WHERE telegram_charge_id=p_charge_id;
 SELECT max(entitlement_until) INTO expiry FROM payments WHERE user_id=pay.user_id AND refunded_at IS NULL;
 -- Legacy payments do not have entitlement history. Conservative revoke + operator review.
 active := coalesce(expiry>now(),false);
 SELECT * INTO latest FROM payments WHERE user_id=pay.user_id AND refunded_at IS NULL AND entitlement_until>now() ORDER BY created_at DESC,id DESC LIMIT 1;
 UPDATE users SET premium_until=expiry,is_paid=active,is_premium=active,
 subscription_tier=CASE WHEN active THEN latest.plan ELSE 'free' END,
 subscription_recurring=CASE WHEN active THEN latest.recurring ELSE false END,
 subscription_charge_id=CASE WHEN active THEN coalesce(latest.subscription_root,latest.telegram_charge_id) ELSE NULL END,
 subscription_payload=CASE WHEN active THEN latest.payload ELSE NULL END,updated_at=now()
 WHERE user_id=pay.user_id;
 RETURN jsonb_build_object('found',true,'user_id',pay.user_id,'is_premium',active,'premium_until',expiry,'needs_legacy_review',
 EXISTS(SELECT 1 FROM payments WHERE user_id=pay.user_id AND refunded_at IS NULL AND entitlement_until IS NULL));
END; $$;

CREATE OR REPLACE FUNCTION public.victoria_v11_claim_jobs(p_limit integer,p_worker text)
RETURNS SETOF public.automation_jobs LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
BEGIN
 -- After a crash we cannot know if Telegram accepted a send. Quarantine, never blindly resend.
 UPDATE automation_jobs SET status='failed',last_error='uncertain delivery after worker crash; inspect before retry',locked_at=NULL,locked_by=NULL
 WHERE status='processing' AND locked_at<now()-interval '10 minutes';
 RETURN QUERY WITH selected AS (
  SELECT id FROM automation_jobs WHERE status='pending' AND scheduled_at<=now() AND attempts<5
  ORDER BY scheduled_at,id FOR UPDATE SKIP LOCKED LIMIT greatest(1,least(p_limit,500))
 ) UPDATE automation_jobs j SET status='processing',locked_at=clock_timestamp(),locked_by=p_worker,attempts=j.attempts+1
 FROM selected WHERE j.id=selected.id RETURNING j.*;
END; $$;

CREATE OR REPLACE FUNCTION public.victoria_v11_preflight()
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
BEGIN
 PERFORM entitlement_until FROM payments LIMIT 1;
 PERFORM charge_id FROM subscription_cancellations LIMIT 1;
 IF to_regprocedure('public.victoria_v11_activate(bigint,text,text,integer,text,text,integer,boolean,timestamp with time zone,boolean)') IS NULL
 OR to_regprocedure('public.victoria_v11_request_call(bigint)') IS NULL
 OR to_regprocedure('public.victoria_v11_claim_jobs(integer,text)') IS NULL THEN
  RAISE EXCEPTION 'Apply V11_SETUP.sql before starting this bot';
 END IF;
 RETURN jsonb_build_object('ok',true,'version',11);
END; $$;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.users FROM anon, authenticated;
GRANT ALL ON public.users TO service_role;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.messages FROM anon, authenticated;
GRANT ALL ON public.messages TO service_role;
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.memories FROM anon, authenticated;
GRANT ALL ON public.memories TO service_role;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.payments FROM anon, authenticated;
GRANT ALL ON public.payments TO service_role;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.events FROM anon, authenticated;
GRANT ALL ON public.events TO service_role;
ALTER TABLE public.pending_replies ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pending_replies FROM anon, authenticated;
GRANT ALL ON public.pending_replies TO service_role;
ALTER TABLE public.call_requests ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.call_requests FROM anon, authenticated;
GRANT ALL ON public.call_requests TO service_role;
ALTER TABLE public.automation_jobs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.automation_jobs FROM anon, authenticated;
GRANT ALL ON public.automation_jobs TO service_role;
ALTER TABLE public.subscription_cancellations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.subscription_cancellations FROM anon, authenticated;
GRANT ALL ON public.subscription_cancellations TO service_role;
ALTER TABLE public.traffic_partners ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.traffic_partners FROM anon, authenticated;
GRANT ALL ON public.traffic_partners TO service_role;
ALTER TABLE public.traffic_commissions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.traffic_commissions FROM anon, authenticated;
GRANT ALL ON public.traffic_commissions TO service_role;
ALTER TABLE public.partner_payouts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.partner_payouts FROM anon, authenticated;
GRANT ALL ON public.partner_payouts TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
DO $$ DECLARE f record; BEGIN
 FOR f IN SELECT oid::regprocedure sig FROM pg_proc WHERE pronamespace='public'::regnamespace AND (proname LIKE 'victoria_v11_%' OR proname IN ('record_payment_and_activate','request_paid_call','mark_payment_refunded','record_chat_activity','claim_due_automation_jobs')) LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated', f.sig);
  EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', f.sig);
 END LOOP;
END $$;
NOTIFY pgrst, 'reload schema';
COMMIT;
