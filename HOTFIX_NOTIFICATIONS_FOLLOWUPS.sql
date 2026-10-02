-- Victoria hotfix: notifications + durable follow-ups
-- Safe to run on the existing database. Does not delete users/payments/jobs.

-- The bot backend must use Supabase service_role (legacy JWT) or a new sb_secret_ key.
-- These objects intentionally stay protected by RLS.
ALTER TABLE public.automation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pending_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.call_requests ENABLE ROW LEVEL SECURITY;

-- Make server-role privileges explicit. service_role bypasses RLS but still needs SQL grants.
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.users,
    public.messages,
    public.events,
    public.payments,
    public.pending_replies,
    public.call_requests,
    public.automation_jobs
TO service_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- Keep the operational RPCs server-only.
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
