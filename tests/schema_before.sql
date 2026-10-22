-- Disposable local fixture matching the columns supplied by the owner.
create table users(
 user_id bigint primary key,username text,first_name text,lang varchar default 'en' check(lang in ('uk','ru','en','de','fr','es')),
 ref text default 'direct',is_paid boolean default false,created_at timestamptz default now(),
 style text not null default 'warm',is_premium boolean not null default false,market text not null default 'global',
 pricing_variant text not null default 'control',subscription_tier text not null default 'free',
 subscription_recurring boolean not null default false,subscription_canceled boolean not null default false,
 subscription_charge_id text,onboarding_complete boolean not null default false,proactive_enabled boolean not null default false,
 premium_until timestamptz,daily_message_count int not null default 0,daily_message_date date default current_date,
 total_messages int not null default 0,xp int not null default 0,blocked boolean not null default false,
 last_active_at timestamptz not null default now(),last_proactive_at timestamptz,human_takeover_until timestamptz,
 updated_at timestamptz not null default now(),last_reminder_at timestamptz,reminder_stage smallint default 0,
 channel_member boolean not null default false,region_confirmed boolean not null default false,
 public_channel_member boolean not null default false,public_channel_lang text,public_channel_checked_at timestamptz,
 sales_stage text not null default 'new',last_offer_at timestamptz,last_checkout_at timestamptz,last_payment_at timestamptz,
 automation_paused boolean not null default false,admin_notes text,last_admin_reply_at timestamptz,
 subscription_payload text,vip_offer_expires_at timestamptz);
create table messages(id bigint generated always as identity primary key,user_id bigint not null references users,
 role text not null check(role in ('user','assistant')),content text not null check(char_length(content)<=8000),created_at timestamptz not null default now());
create table memories(id bigint generated always as identity primary key,user_id bigint references users,memory_key text,memory_value text,confidence real default .8,created_at timestamptz default now(),updated_at timestamptz default now());
create table payments(id bigint generated always as identity primary key,user_id bigint not null references users,
 telegram_charge_id text not null unique,payload text not null,amount int not null check(amount>0),currency text not null default 'XTR',
 plan text not null default 'plus',market text not null default 'global',pricing_variant text not null default 'control',
 duration_days int not null default 30,recurring boolean not null default false,refunded_at timestamptz,
 created_at timestamptz not null default now(),entitlement_until timestamptz,subscription_root text);
create table events(id bigint generated always as identity primary key,user_id bigint not null references users,event text not null,
 properties jsonb not null default '{}',created_at timestamptz not null default now());
create table pending_replies(user_id bigint primary key references users,updated_at timestamptz not null default now());
create table call_requests(id bigint generated always as identity primary key,user_id bigint not null references users,period_end timestamptz not null,
 status text not null default 'pending' check(status in ('pending','completed','canceled')),created_at timestamptz not null default now());
create table automation_jobs(id bigint generated always as identity primary key,user_id bigint not null references users,job_type text not null,
 status text not null default 'pending' check(status in ('pending','processing','sent','cancelled','failed')),scheduled_at timestamptz not null,
 sent_at timestamptz,dedupe_key text not null unique,payload jsonb not null default '{}',last_error text,created_at timestamptz not null default now(),
 attempts int not null default 0,locked_at timestamptz,locked_by text);
create table traffic_partners(id bigint generated always as identity primary key,telegram_user_id bigint not null unique,code text not null unique,
 display_name text not null,commission_pct numeric not null default 30,active boolean not null default true,created_at timestamptz not null default now(),updated_at timestamptz not null default now());
create table traffic_commissions(id bigint generated always as identity primary key,partner_id bigint not null references traffic_partners,
 payment_id bigint not null unique references payments,user_id bigint not null references users,gross_stars int not null,commission_pct numeric not null,commission_stars int not null,created_at timestamptz not null default now());
create table partner_payouts(id bigint generated always as identity primary key,partner_id bigint not null references traffic_partners,amount_stars int not null,note text,created_at timestamptz not null default now());
create table subscription_cancellations(charge_id text primary key,user_id bigint not null references users,completed_at timestamptz,created_at timestamptz not null default now());
