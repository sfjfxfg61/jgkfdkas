-- Run once in Supabase SQL Editor.
-- This migration is idempotent and replaces the old single-table sales funnel schema.

create table if not exists public.users (
    user_id bigint primary key,
    username text,
    first_name text not null default 'User',
    lang text not null default 'en' check (lang in ('ru', 'uk', 'en', 'es', 'de', 'fr')),
    ref text not null default 'direct',
    style text not null default 'warm' check (style in ('warm', 'playful', 'calm')),
    market text not null default 'global' check (market in ('ua', 'cis', 'latam', 'eu', 'us', 'global')),
    pricing_variant text not null default 'control',
    onboarding_complete boolean not null default false,
    proactive_enabled boolean not null default false,
    is_paid boolean not null default false,
    is_premium boolean not null default false,
    premium_until timestamptz,
    subscription_tier text not null default 'free' check (subscription_tier in ('free', 'plus', 'pro', 'ultra', 'black')),
    subscription_recurring boolean not null default false,
    subscription_canceled boolean not null default false,
    subscription_charge_id text,
    daily_message_count integer not null default 0,
    daily_message_date date not null default current_date,
    total_messages integer not null default 0,
    xp integer not null default 0,
    blocked boolean not null default false,
    last_active_at timestamptz not null default now(),
    last_proactive_at timestamptz,
    last_reminder_at timestamptz,
    reminder_stage smallint not null default 0 check (reminder_stage between 0 and 3),
    human_takeover_until timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.users add column if not exists style text not null default 'warm';
alter table public.users add column if not exists is_paid boolean not null default false;
alter table public.users add column if not exists is_premium boolean not null default false;
alter table public.users add column if not exists market text not null default 'global';
alter table public.users add column if not exists pricing_variant text not null default 'control';
alter table public.users add column if not exists subscription_tier text not null default 'free';
alter table public.users add column if not exists subscription_recurring boolean not null default false;
alter table public.users add column if not exists subscription_canceled boolean not null default false;
alter table public.users add column if not exists subscription_charge_id text;
alter table public.users add column if not exists onboarding_complete boolean not null default false;
alter table public.users add column if not exists proactive_enabled boolean not null default false;
alter table public.users add column if not exists premium_until timestamptz;
alter table public.users add column if not exists daily_message_count integer not null default 0;
alter table public.users add column if not exists daily_message_date date not null default current_date;
alter table public.users add column if not exists total_messages integer not null default 0;
alter table public.users add column if not exists xp integer not null default 0;
alter table public.users add column if not exists blocked boolean not null default false;
alter table public.users add column if not exists last_active_at timestamptz not null default now();
alter table public.users add column if not exists last_proactive_at timestamptz;
alter table public.users add column if not exists last_reminder_at timestamptz;
alter table public.users add column if not exists reminder_stage smallint not null default 0;
alter table public.users add column if not exists human_takeover_until timestamptz;
alter table public.users add column if not exists updated_at timestamptz not null default now();
alter table public.users add column if not exists created_at timestamptz not null default now();

alter table public.users drop constraint if exists users_lang_check;
alter table public.users add constraint users_lang_check
    check (lang in ('ru', 'uk', 'en', 'es', 'de', 'fr')) not valid;
alter table public.users validate constraint users_lang_check;

alter table public.users drop constraint if exists users_reminder_stage_check;
alter table public.users add constraint users_reminder_stage_check
    check (reminder_stage between 0 and 3) not valid;
alter table public.users validate constraint users_reminder_stage_check;

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public' and table_name = 'users' and column_name = 'is_paid'
    ) then
        execute 'update public.users set '
            || 'is_premium = true, subscription_tier = ''black'', subscription_recurring = false, '
            || 'premium_until = coalesce(premium_until, ''2099-12-31 23:59:59+00''::timestamptz) '
            || 'where is_paid = true';
    end if;
end $$;

create table if not exists public.messages (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.users(user_id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null check (char_length(content) <= 8000),
    created_at timestamptz not null default now()
);

create index if not exists messages_user_created_idx on public.messages(user_id, created_at desc);

create table if not exists public.memories (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.users(user_id) on delete cascade,
    memory_key text not null,
    memory_value text not null,
    confidence real not null default 0.8 check (confidence between 0 and 1),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(user_id, memory_key)
);

create index if not exists memories_user_updated_idx on public.memories(user_id, updated_at desc);

create table if not exists public.payments (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.users(user_id),
    telegram_charge_id text not null unique,
    payload text not null,
    amount integer not null check (amount > 0),
    currency text not null default 'XTR',
    plan text not null default 'plus',
    market text not null default 'global',
    pricing_variant text not null default 'control',
    duration_days integer not null default 30,
    recurring boolean not null default false,
    refunded_at timestamptz,
    created_at timestamptz not null default now()
);

alter table public.payments add column if not exists plan text not null default 'plus';
alter table public.payments add column if not exists market text not null default 'global';
alter table public.payments add column if not exists pricing_variant text not null default 'control';
alter table public.payments add column if not exists duration_days integer not null default 30;
alter table public.payments add column if not exists recurring boolean not null default false;
alter table public.payments add column if not exists refunded_at timestamptz;

create table if not exists public.events (
    id bigint generated always as identity primary key,
    user_id bigint not null references public.users(user_id) on delete cascade,
    event text not null,
    properties jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists events_name_created_idx on public.events(event, created_at desc);
create index if not exists events_user_created_idx on public.events(user_id, created_at desc);
create index if not exists users_reminder_queue_idx
    on public.users(blocked, reminder_stage, last_active_at)
    where onboarding_complete = true and total_messages > 0;

drop function if exists public.consume_message_quota(bigint, integer);

create function public.consume_message_quota(p_user_id bigint, p_daily_limit integer)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    u public.users%rowtype;
    premium_active boolean;
    remaining_count integer;
begin
    select * into u from public.users where user_id = p_user_id for update;
    if not found then
        return jsonb_build_object('allowed', false, 'remaining', 0);
    end if;

    if u.daily_message_date <> current_date then
        u.daily_message_count := 0;
        u.daily_message_date := current_date;
    end if;

    premium_active := u.is_premium and u.premium_until is not null and u.premium_until > now();
    if u.is_premium and not premium_active then
        u.is_premium := false;
        u.is_paid := false;
        u.subscription_tier := 'free';
        u.subscription_recurring := false;
        u.subscription_canceled := false;
        u.subscription_charge_id := null;
    end if;

    if u.daily_message_count >= p_daily_limit then
        update public.users set
            is_premium = u.is_premium,
            is_paid = u.is_paid,
            subscription_tier = u.subscription_tier,
            subscription_recurring = u.subscription_recurring,
            subscription_canceled = u.subscription_canceled,
            subscription_charge_id = u.subscription_charge_id,
            daily_message_date = u.daily_message_date,
            daily_message_count = u.daily_message_count,
            last_active_at = now(),
            last_reminder_at = null,
            reminder_stage = 0,
            updated_at = now()
        where user_id = p_user_id;
        return jsonb_build_object('allowed', false, 'remaining', 0, 'is_premium', false);
    end if;

    u.daily_message_count := u.daily_message_count + 1;
    u.total_messages := u.total_messages + 1;
    u.xp := u.xp + 2;
    remaining_count := greatest(p_daily_limit - u.daily_message_count, 0);

    update public.users set
        is_premium = u.is_premium,
        is_paid = u.is_paid,
        subscription_tier = u.subscription_tier,
        subscription_recurring = u.subscription_recurring,
        subscription_canceled = u.subscription_canceled,
        subscription_charge_id = u.subscription_charge_id,
        daily_message_date = u.daily_message_date,
        daily_message_count = u.daily_message_count,
        total_messages = u.total_messages,
        xp = u.xp,
        last_active_at = now(),
        last_reminder_at = null,
        reminder_stage = 0,
        updated_at = now()
    where user_id = p_user_id;

    return jsonb_build_object(
        'allowed', true,
        'remaining', remaining_count,
        'is_premium', premium_active,
        'tier', u.subscription_tier,
        'total_messages', u.total_messages,
        'xp', u.xp
    );
end;
$$;

drop function if exists public.mark_payment_refunded(text);

create function public.mark_payment_refunded(p_charge_id text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    payment_user_id bigint;
begin
    update public.payments
    set refunded_at = coalesce(refunded_at, now())
    where telegram_charge_id = p_charge_id
    returning user_id into payment_user_id;

    if payment_user_id is null then
        return jsonb_build_object('found', false);
    end if;

    update public.users set
        is_premium = false,
        is_paid = false,
        premium_until = null,
        subscription_tier = 'free',
        subscription_recurring = false,
        subscription_canceled = false,
        subscription_charge_id = null,
        updated_at = now()
    where user_id = payment_user_id
      and subscription_charge_id = p_charge_id;

    return jsonb_build_object('found', true, 'user_id', payment_user_id);
end;
$$;

drop function if exists public.record_payment_and_activate(bigint, text, text, integer, integer);
drop function if exists public.record_payment_and_activate(bigint, text, text, integer, text, text, integer, boolean);
drop function if exists public.record_payment_and_activate(bigint, text, text, integer, text, text, integer, boolean, timestamptz);

create function public.record_payment_and_activate(
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
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    new_until timestamptz;
begin
    insert into public.payments(
        user_id, telegram_charge_id, payload, amount, plan, market,
        pricing_variant, duration_days, recurring
    )
    values (
        p_user_id, p_charge_id, p_payload, p_amount, p_plan, p_market,
        coalesce((select pricing_variant from public.users where user_id = p_user_id), 'control'),
        p_days, p_recurring
    )
    on conflict (telegram_charge_id) do nothing;

    if not found then
        select premium_until into new_until from public.users where user_id = p_user_id;
        return jsonb_build_object('premium_until', new_until, 'duplicate', true);
    end if;

    update public.users set
        is_premium = true,
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
        updated_at = now()
    where user_id = p_user_id
    returning premium_until into new_until;

    return jsonb_build_object('premium_until', new_until, 'duplicate', false);
end;
$$;

create or replace function public.companion_admin_stats()
returns jsonb
language sql
security definer
set search_path = public
as $$
    select jsonb_build_object(
        'overview', jsonb_build_object(
            'users', (select count(*) from public.users),
            'reachable', (select count(*) from public.users where not blocked),
            'new_1d', (select count(*) from public.users where created_at > now() - interval '1 day'),
            'new_7d', (select count(*) from public.users where created_at > now() - interval '7 days'),
            'new_30d', (select count(*) from public.users where created_at > now() - interval '30 days'),
            'active_1d', (select count(*) from public.users where last_active_at > now() - interval '1 day'),
            'active_7d', (select count(*) from public.users where last_active_at > now() - interval '7 days'),
            'active_30d', (select count(*) from public.users where last_active_at > now() - interval '30 days'),
            'messages', (select count(*) from public.messages where role = 'user')
        ),
        'funnel', jsonb_build_object(
            'started', (select count(*) from public.users),
            'chatted', (select count(*) from public.users where total_messages > 0),
            'chatted_pct', (select round(100.0 * count(*) filter (where total_messages > 0) / greatest(count(*), 1), 2) from public.users),
            'engaged_3', (select count(*) from public.users where total_messages >= 3),
            'engaged_3_pct', (select round(100.0 * count(*) filter (where total_messages >= 3) / greatest(count(*), 1), 2) from public.users),
            'engaged_10', (select count(*) from public.users where total_messages >= 10),
            'engaged_10_pct', (select round(100.0 * count(*) filter (where total_messages >= 10) / greatest(count(*), 1), 2) from public.users),
            'paywall_users', (select count(distinct user_id) from public.events where event in ('paywall_view', 'quota_paywall')),
            'premium_nudges', (select count(*) from public.events where event = 'premium_nudge_shown'),
            'channel_nudges', (select count(*) from public.events where event = 'channel_nudge_shown'),
            'checkout_users', (select count(distinct user_id) from public.events where event = 'checkout_created'),
            'payer_users', (select count(distinct user_id) from public.payments where refunded_at is null),
            'premium_active', (select count(*) from public.users where is_premium and premium_until > now()),
            'start_to_paid_pct', (
                select round(100.0 * count(distinct p.user_id) / greatest((select count(*) from public.users), 1), 2)
                from public.payments p where p.refunded_at is null
            ),
            'paywall_to_checkout_pct', (
                select round(100.0 *
                    (select count(distinct user_id) from public.events where event = 'checkout_created') /
                    greatest((select count(distinct user_id) from public.events where event in ('paywall_view', 'quota_paywall')), 1), 2)
            ),
            'checkout_to_paid_pct', (
                select round(100.0 *
                    (select count(distinct user_id) from public.payments where refunded_at is null) /
                    greatest((select count(distinct user_id) from public.events where event = 'checkout_created'), 1), 2)
            )
        ),
        'revenue', jsonb_build_object(
            'stars', (select coalesce(sum(amount), 0) from public.payments where refunded_at is null),
            'payments', (select count(*) from public.payments where refunded_at is null),
            'payers', (select count(distinct user_id) from public.payments where refunded_at is null),
            'arppu_stars', (
                select round(coalesce(sum(amount), 0)::numeric / greatest(count(distinct user_id), 1), 1)
                from public.payments where refunded_at is null
            ),
            'refunds', (select count(*) from public.payments where refunded_at is not null),
            'refund_pct', (
                select round(100.0 * count(*) filter (where refunded_at is not null) / greatest(count(*), 1), 2)
                from public.payments
            ),
            'canceled_subscriptions', (select count(*) from public.users where subscription_canceled),
            'black_purchases', (select count(*) from public.payments where refunded_at is null and plan = 'black'),
            'tiers', (
                select coalesce(jsonb_object_agg(plan, purchases), '{}'::jsonb)
                from (select plan, count(*) purchases from public.payments where refunded_at is null group by plan) s
            ),
            'markets', (
                select coalesce(jsonb_object_agg(market, stars), '{}'::jsonb)
                from (select market, sum(amount) stars from public.payments where refunded_at is null group by market) s
            )
        ),
        'retention', jsonb_build_object(
            'd1_eligible', (select count(*) from public.users where created_at <= now() - interval '1 day'),
            'd1_returned', (
                select count(*) from public.users u where u.created_at <= now() - interval '1 day'
                and exists (select 1 from public.messages m where m.user_id = u.user_id and m.role = 'user' and m.created_at >= u.created_at + interval '1 day')
            ),
            'd1_pct', (
                select round(100.0 * count(*) filter (where exists (
                    select 1 from public.messages m where m.user_id = u.user_id and m.role = 'user' and m.created_at >= u.created_at + interval '1 day'
                )) / greatest(count(*), 1), 2) from public.users u where u.created_at <= now() - interval '1 day'
            ),
            'd3_eligible', (select count(*) from public.users where created_at <= now() - interval '3 days'),
            'd3_returned', (
                select count(*) from public.users u where u.created_at <= now() - interval '3 days'
                and exists (select 1 from public.messages m where m.user_id = u.user_id and m.role = 'user' and m.created_at >= u.created_at + interval '3 days')
            ),
            'd3_pct', (
                select round(100.0 * count(*) filter (where exists (
                    select 1 from public.messages m where m.user_id = u.user_id and m.role = 'user' and m.created_at >= u.created_at + interval '3 days'
                )) / greatest(count(*), 1), 2) from public.users u where u.created_at <= now() - interval '3 days'
            ),
            'd7_eligible', (select count(*) from public.users where created_at <= now() - interval '7 days'),
            'd7_returned', (
                select count(*) from public.users u where u.created_at <= now() - interval '7 days'
                and exists (select 1 from public.messages m where m.user_id = u.user_id and m.role = 'user' and m.created_at >= u.created_at + interval '7 days')
            ),
            'd7_pct', (
                select round(100.0 * count(*) filter (where exists (
                    select 1 from public.messages m where m.user_id = u.user_id and m.role = 'user' and m.created_at >= u.created_at + interval '7 days'
                )) / greatest(count(*), 1), 2) from public.users u where u.created_at <= now() - interval '7 days'
            )
        ),
        'reminders', jsonb_build_object(
            'd1_sent', (select count(*) from public.events where event = 'reminder_sent' and properties->>'stage' = 'd1'),
            'd3_sent', (select count(*) from public.events where event = 'reminder_sent' and properties->>'stage' = 'd3'),
            'd7_sent', (select count(*) from public.events where event = 'reminder_sent' and properties->>'stage' = 'd7'),
            'returned', (select count(*) from public.events where event = 'reminder_returned'),
            'returned_users', (select count(distinct user_id) from public.events where event = 'reminder_returned'),
            'return_pct', (
                select round(100.0 *
                    (select count(*) from public.events where event = 'reminder_returned') /
                    greatest((select count(*) from public.events where event = 'reminder_sent'), 1), 2)
            )
        ),
        'acquisition', jsonb_build_object(
            'refs', (
                select coalesce(jsonb_object_agg(ref, users), '{}'::jsonb)
                from (select ref, count(*) users from public.users group by ref order by count(*) desc limit 15) s
            ),
            'languages', (
                select coalesce(jsonb_object_agg(lang, users), '{}'::jsonb)
                from (select lang, count(*) users from public.users group by lang order by count(*) desc) s
            )
        )
    );
$$;

alter table public.users enable row level security;
alter table public.messages enable row level security;
alter table public.memories enable row level security;
alter table public.payments enable row level security;
alter table public.events enable row level security;

revoke execute on function public.consume_message_quota(bigint, integer) from public, anon, authenticated;
revoke execute on function public.record_payment_and_activate(bigint, text, text, integer, text, text, integer, boolean, timestamptz) from public, anon, authenticated;
revoke execute on function public.mark_payment_refunded(text) from public, anon, authenticated;
revoke execute on function public.companion_admin_stats() from public, anon, authenticated;
grant execute on function public.consume_message_quota(bigint, integer) to service_role;
grant execute on function public.record_payment_and_activate(bigint, text, text, integer, text, text, integer, boolean, timestamptz) to service_role;
grant execute on function public.mark_payment_refunded(text) to service_role;
grant execute on function public.companion_admin_stats() to service_role;

-- The bot must use a server-side service role key. Never expose it in a client or commit it.
