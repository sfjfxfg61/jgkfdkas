-- Read-only report for the Supabase SQL Editor; amounts are gross Telegram Stars.
-- Refunds are deducted from net Stars, but processing/payout value is not inferred.
SELECT
    p.market,
    p.plan,
    p.duration_days,
    p.recurring,
    COUNT(*) FILTER (WHERE p.refunded_at IS NULL) AS successful_charges,
    COUNT(*) FILTER (WHERE p.refunded_at IS NOT NULL) AS refunded_charges,
    COUNT(DISTINCT p.user_id) FILTER (WHERE p.refunded_at IS NULL) AS paying_users,
    COALESCE(SUM(p.amount) FILTER (WHERE p.refunded_at IS NULL), 0) AS net_stars,
    COALESCE(SUM(p.amount), 0) AS gross_stars
FROM public.payments AS p
GROUP BY p.market, p.plan, p.duration_days, p.recurring
ORDER BY net_stars DESC, p.market, p.plan;

-- Optional daily totals:
SELECT
    (p.created_at AT TIME ZONE 'Europe/Kyiv')::date AS kyiv_day,
    COUNT(*) FILTER (WHERE p.refunded_at IS NULL) AS successful_charges,
    COALESCE(SUM(p.amount) FILTER (WHERE p.refunded_at IS NULL), 0) AS net_stars
FROM public.payments AS p
GROUP BY 1
ORDER BY 1 DESC;
