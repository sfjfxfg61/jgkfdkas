-- Run once in Supabase SQL Editor BEFORE deploying v4. Safe to rerun.
-- Existing customer / financial records are retained. Back up the database first.
begin;
select pg_advisory_xact_lock(hashtext('victoria-v4-migration'));

-- Language check name can differ between databases.
do $$ declare r record; begin
 for r in select conname from pg_constraint where conrelid='public.users'::regclass
   and contype='c' and pg_get_constraintdef(oid) ~ '\mlang\M' loop
   execute format('alter table public.users drop constraint %I',r.conname);
 end loop;
end $$;
alter table public.users add constraint users_lang_v4_check check (lang in ('uk','ru','en','de','fr','es','pt','it'));
alter table public.users add column if not exists acquisition_lang text;
alter table public.users add column if not exists language_selected boolean not null default false;
alter table public.users add column if not exists experiment_variant text;
alter table public.users add column if not exists first_bot_start_at timestamptz;
alter table public.users add column if not exists next_reminder_at timestamptz;
alter table public.users add column if not exists assistant_messages bigint not null default 0;
alter table public.messages add column if not exists telegram_message_id bigint;
create unique index if not exists messages_telegram_dedupe on public.messages(user_id,telegram_message_id) where telegram_message_id is not null;
create index if not exists messages_recent_v4 on public.messages(user_id,created_at desc,id desc);
create index if not exists events_user_recent_v4 on public.events(user_id,created_at desc);
create index if not exists payments_user_recent_v4 on public.payments(user_id,created_at desc);
create index if not exists users_reminder_due_v4 on public.users(next_reminder_at,user_id) where blocked=false;
create index if not exists users_expiry_due_v4 on public.users(premium_until,user_id) where is_premium=true;
create index if not exists jobs_due_v4 on public.automation_jobs(scheduled_at,id) where status in ('pending','processing');
create index if not exists jobs_current_due_v4 on public.automation_jobs(scheduled_at,id) where status in ('pending','processing') and job_type like 'v4\_%' escape '\';
create index if not exists jobs_cleanup_v4 on public.automation_jobs(created_at,id) where status in ('sent','cancelled','failed');

create table if not exists public.v4_state (key text primary key,value jsonb not null);
create table if not exists public.access_grants (
 source text primary key,
 user_id bigint not null references public.users(user_id),
 payment_id bigint references public.payments(id),
 tier text not null,
 starts_at timestamptz not null default now(),
 ends_at timestamptz not null,
 revoked_at timestamptz,
 expired_processed_at timestamptz,
 created_at timestamptz not null default now()
);
alter table public.access_grants add column if not exists expired_processed_at timestamptz;
create index if not exists grants_expiry_v4 on public.access_grants(ends_at,user_id) where expired_processed_at is null and revoked_at is null;
create index if not exists grants_user_v4 on public.access_grants(user_id,ends_at) where revoked_at is null;
create table if not exists public.funnel_progress (
 user_id bigint not null references public.users(user_id),
 event text not null,
 first_at timestamptz not null,
 last_at timestamptz not null,
 hits bigint not null default 1,
 primary key(user_id,event)
);
create table if not exists public.telegram_updates (
 update_id bigint primary key,
 body jsonb not null,
 status text not null default 'pending' check(status in ('pending','processing','done','failed')),
 attempts int not null default 0,
 available_at timestamptz not null default now(),
 locked_at timestamptz,
 locked_by text,
 last_error text,
 created_at timestamptz not null default now()
);
create index if not exists updates_due_v4 on public.telegram_updates(available_at,update_id) where status in ('pending','processing');
create table if not exists public.manual_offer_drafts (
 admin_id bigint primary key,
 user_id bigint not null references public.users(user_id),
 plan text,
 amount int check(amount between 1 and 10000),
 body text,
 expires_at timestamptz not null default now()+interval '1 hour'
);
-- Archives are excluded from live reports, retained for support and audit.
create table if not exists public.messages_archive (like public.messages including defaults);
create unique index if not exists messages_archive_id_v4 on public.messages_archive(id);
create index if not exists messages_archive_user_v4 on public.messages_archive(user_id,created_at desc,id desc);
create table if not exists public.events_archive (like public.events including defaults);
create unique index if not exists events_archive_id_v4 on public.events_archive(id);
create table if not exists public.call_requests_archive (like public.call_requests including defaults);
create unique index if not exists calls_archive_id_v4 on public.call_requests_archive(id);

create table if not exists public.automation_errors_archive (
 id bigint primary key,user_id bigint not null,job_type text not null,
 attempts int not null,last_error text,created_at timestamptz not null,archived_at timestamptz not null default now()
);

-- One-time data initialization. A rerun cannot recreate a refunded grant.
do $$ begin
 if not exists(select from public.v4_state where key='initialized') then
  update public.users set acquisition_lang=lang,
    experiment_variant='legacy',
    next_reminder_at=now()+interval '1 day';
  update public.users u set total_messages=(select count(*) from public.messages m where m.user_id=u.user_id and role='user'),
    assistant_messages=(select count(*) from public.messages m where m.user_id=u.user_id and role='assistant');
  insert into public.access_grants(source,user_id,payment_id,tier,starts_at,ends_at)
   select 'receipt:'||id,user_id,id,plan,created_at,entitlement_until from public.payments
    where refunded_at is null and entitlement_until is not null on conflict do nothing;
  insert into public.access_grants(source,user_id,payment_id,tier,starts_at,ends_at)
   select 'legacy:'||u.user_id,u.user_id,p.id,u.subscription_tier,u.created_at,
    coalesce(u.premium_until,'2099-12-31 23:59:59+00'::timestamptz)
   from public.users u left join public.payments p on p.telegram_charge_id=u.subscription_charge_id and p.refunded_at is null
   where (u.is_paid or u.is_premium) on conflict do nothing;
  insert into public.funnel_progress(user_id,event,first_at,last_at,hits)
   select user_id,event,min(created_at),max(created_at),count(*) from public.events
   where event in ('simple_start','simple_offer_seen','simple_checkout','simple_payment_success','simple_reminder_sent',
    'simple_reminder_failed','simple_join_approved','simple_support_message')
   group by user_id,event on conflict do nothing;
  insert into public.v4_state values('initialized','true');
 end if;
end $$;

create or replace function public.v4_capture_event() returns trigger language plpgsql set search_path=public as $$
begin
 -- A fixed vocabulary prevents unbounded per-user counter growth.
 if new.event in ('simple_start','simple_offer_seen','simple_checkout','simple_payment_success','simple_reminder_sent',
  'simple_reminder_failed','simple_join_approved','simple_support_message','v4_blog_request','v4_gate_continue',
  'v4_followup_sent','v4_vip_offer_sent','v4_payment_click','v4_subscription_notice','v4_expired','v4_manual_offer') then
  insert into public.funnel_progress(user_id,event,first_at,last_at,hits) values(new.user_id,new.event,new.created_at,new.created_at,1)
   on conflict(user_id,event) do update set last_at=greatest(funnel_progress.last_at,excluded.last_at),hits=funnel_progress.hits+1;
 end if;
 return new;
end $$;
drop trigger if exists v4_events_counter on public.events;
create trigger v4_events_counter after insert on public.events for each row execute function public.v4_capture_event();
create or replace function public.v4_capture_message() returns trigger language plpgsql set search_path=public as $$
begin
 update public.users set total_messages=total_messages+case when new.role='user' then 1 else 0 end,
  assistant_messages=assistant_messages+case when new.role='assistant' then 1 else 0 end where user_id=new.user_id;
 return new;
end $$;
drop trigger if exists v4_messages_counter on public.messages;
create trigger v4_messages_counter after insert on public.messages for each row execute function public.v4_capture_message();

create or replace function public.v4_register(p_uid bigint,p_name text,p_username text,p_lang text,p_ref text,p_tz text default 'Europe/Kyiv',p_clock text default '20:00')
returns jsonb language plpgsql set search_path=public as $$
declare u public.users; begin
 insert into public.users(user_id,first_name,username,lang,acquisition_lang,ref,market,experiment_variant,next_reminder_at)
 values(p_uid,left(p_name,100),p_username,coalesce(p_lang,'en'),p_lang,left(p_ref,80),
  case p_lang when 'uk' then 'ua' when 'ru' then 'cis' when 'de' then 'eu' when 'fr' then 'eu' when 'it' then 'eu'
   when 'es' then 'latam' when 'pt' then 'latam' else 'global' end,
  case when mod(abs(hashtextextended(p_uid::text,17)::numeric),2)=0 then 'A' else 'B' end,((((now() at time zone p_tz)::date+1)+p_clock::time) at time zone p_tz))
 on conflict(user_id) do update set first_name=excluded.first_name,username=excluded.username,
  last_active_at=now(),updated_at=now(),blocked=false,
  experiment_variant=coalesce(users.experiment_variant,excluded.experiment_variant)
 returning * into u;
 return to_jsonb(u);
end $$;

create or replace function public.v4_start(p_uid bigint) returns void language plpgsql set search_path=public as $$
begin
 perform 1 from public.users where user_id=p_uid for update;
 update public.users set first_bot_start_at=coalesce(first_bot_start_at,now()) where user_id=p_uid;
 insert into public.automation_jobs(user_id,job_type,scheduled_at,dedupe_key)
 select p_uid,'v4_followup',first_bot_start_at+interval '1 hour','v4:hello:'||p_uid from public.users where user_id=p_uid
 on conflict(dedupe_key) do nothing;
end $$;

create or replace function public.v4_rank(p_tier text) returns int language sql immutable as $$
 select case when p_tier in ('daddy','vip','black') then 3 when p_tier='mistress' then 2 else 1 end
$$;
create or replace function public.v4_sync_access(p_uid bigint) returns jsonb language plpgsql set search_path=public as $$
declare u public.users; best text; ends timestamptz; personal_until timestamptz; calls_until timestamptz;
begin
 perform 1 from public.users where user_id=p_uid for update;
 select tier into best from public.access_grants where user_id=p_uid and revoked_at is null and ends_at>now()
  order by public.v4_rank(tier) desc,ends_at desc limit 1;
 select max(ends_at),max(ends_at) filter(where public.v4_rank(tier)>=2),max(ends_at) filter(where public.v4_rank(tier)>=3)
 into ends,personal_until,calls_until from public.access_grants where user_id=p_uid and revoked_at is null and ends_at>now();
 update public.users set is_paid=(best is not null),is_premium=(best is not null),
  subscription_tier=coalesce(best,'free'),premium_until=ends,updated_at=now() where user_id=p_uid returning * into u;
 return to_jsonb(u)||jsonb_build_object('personal_until',personal_until,'calls_until',calls_until);
end $$;

create or replace function public.v4_apply_payment(p_uid bigint,p_charge text,p_payload text,p_amount int,p_plan text,p_days int,p_market text)
returns jsonb language plpgsql set search_path=public as $$
declare u public.users; receipt public.payments; ends timestamptz; partner public.traffic_partners; duplicate boolean:=false;
begin
 select * into u from public.users where user_id=p_uid for update;
 if not found then raise exception 'Unknown user'; end if;
 select * into receipt from public.payments where telegram_charge_id=p_charge;
 if found then
  if receipt.user_id<>p_uid or receipt.amount<>p_amount or receipt.payload<>p_payload then raise exception 'Charge mismatch'; end if;
  duplicate:=true;
 else
  if p_amount<=0 or p_days<1 or p_days>36500 then raise exception 'Invalid payment'; end if;
  if p_plan='forever' then ends:='2099-12-31 23:59:59+00';
  else
   select greatest(now(),coalesce(max(ends_at),now()))+make_interval(days=>p_days) into ends
    from public.access_grants where user_id=p_uid and tier=p_plan and revoked_at is null and ends_at<'2099-01-01';
  end if;
  insert into public.payments(user_id,telegram_charge_id,payload,amount,currency,plan,market,pricing_variant,duration_days,recurring,entitlement_until)
   values(p_uid,p_charge,p_payload,p_amount,'XTR',p_plan,p_market,coalesce(u.experiment_variant,'legacy'),p_days,false,ends)
   returning * into receipt;
  insert into public.access_grants(source,user_id,payment_id,tier,ends_at)
   values('receipt:'||receipt.id,p_uid,receipt.id,p_plan,ends) on conflict do nothing;
  update public.users set subscription_charge_id=p_charge,subscription_payload=p_payload,subscription_recurring=false,
   last_payment_at=now(),sales_stage='paid' where user_id=p_uid;
  select * into partner from public.traffic_partners where code=u.ref and active and telegram_user_id<>p_uid;
  if found then
   insert into public.traffic_commissions(partner_id,payment_id,user_id,gross_stars,commission_pct,commission_stars)
    values(partner.id,receipt.id,p_uid,p_amount,partner.commission_pct,round(p_amount*partner.commission_pct/100)) on conflict(payment_id) do nothing;
  end if;
  insert into public.events(user_id,event,properties) values(p_uid,'simple_payment_success',jsonb_build_object('charge',p_charge,'plan',p_plan,'stars',p_amount));
 end if;
 return jsonb_build_object('receipt',to_jsonb(receipt),'duplicate',duplicate,'user',public.v4_sync_access(p_uid));
end $$;

create or replace function public.v4_refund(p_uid bigint,p_charge text) returns jsonb language plpgsql set search_path=public as $$
declare r public.payments; begin
 perform 1 from public.users where user_id=p_uid for update;
 select * into r from public.payments where user_id=p_uid and telegram_charge_id=p_charge for update;
 if not found then raise exception 'Refund receipt missing: review payment ledger'; end if;
 update public.payments set refunded_at=coalesce(refunded_at,now()) where id=r.id;
 update public.access_grants set revoked_at=coalesce(revoked_at,now()) where payment_id=r.id;
 return public.v4_sync_access(p_uid);
end $$;

create or replace function public.v4_request_call(p_uid bigint) returns jsonb language plpgsql set search_path=public as $$
declare u jsonb; r public.call_requests; begin
 u:=public.v4_sync_access(p_uid);
 if u->>'calls_until' is null then return jsonb_build_object('allowed',false); end if;
 select * into r from public.call_requests where user_id=p_uid and status='pending' order by id limit 1;
 if found then return jsonb_build_object('allowed',true,'created',false,'id',r.id); end if;
 insert into public.call_requests(user_id,period_end) values(p_uid,(u->>'calls_until')::timestamptz) returning * into r;
 return jsonb_build_object('allowed',true,'created',true,'id',r.id);
end $$;

-- Atomic worker claims, bounded batches, leases recover after a worker restart.
create or replace function public.v4_claim_jobs(p_worker text,p_limit int default 10,p_notifications boolean default true) returns setof public.automation_jobs
language sql set search_path=public as $$
 with due as (
  select id from public.automation_jobs where job_type like 'v4\_%' escape '\'
   and ((status='pending' and scheduled_at<=now()) or (status='processing' and locked_at<now()-interval '5 minutes'))
   and (p_notifications or job_type='v4_revoke') and attempts<8 order by scheduled_at,id for update skip locked limit least(greatest(p_limit,1),50)
 ) update public.automation_jobs j set status='processing',locked_at=now(),locked_by=p_worker,attempts=attempts+1
 from due where j.id=due.id returning j.*
$$;
create or replace function public.v4_claim_updates(p_worker text,p_limit int default 4) returns setof public.telegram_updates
language sql set search_path=public as $$
 with due as (
  select update_id from public.telegram_updates where
   ((status='pending' and available_at<=now()) or (status='processing' and locked_at<now()-interval '5 minutes')) and attempts<8
  order by case when body->'message' ? 'successful_payment' then 0 else 1 end,update_id
  for update skip locked limit least(greatest(p_limit,1),20)
 ) update public.telegram_updates j set status='processing',locked_at=now(),locked_by=p_worker,attempts=attempts+1
 from due where j.update_id=due.update_id returning j.*
$$;
create or replace function public.v4_schedule(p_tz text,p_clock text,p_admin bigint) returns int
language plpgsql set search_path=public as $$
declare r record; n int:=0; day date:=(now() at time zone p_tz)::date; due timestamptz;
begin
 for r in select user_id,next_reminder_at from public.users where not blocked and not automation_paused and user_id<>p_admin
  and next_reminder_at<=now() order by next_reminder_at,user_id for update skip locked limit 200 loop
  due:=((day+p_clock::time) at time zone p_tz);
  if due>now() then
   update public.users set next_reminder_at=due where user_id=r.user_id;
  else
   insert into public.automation_jobs(user_id,job_type,scheduled_at,dedupe_key)
    values(r.user_id,'v4_daily',now(),'v4:daily:'||r.user_id||':'||day) on conflict(dedupe_key) do nothing;
   update public.users set next_reminder_at=((day+1+p_clock::time) at time zone p_tz) where user_id=r.user_id;
   n:=n+1;
  end if;
 end loop;
 -- One expiry notice per actual grant endpoint, no full scan of message history.
 insert into public.automation_jobs(user_id,job_type,scheduled_at,dedupe_key,payload)
 select user_id,'v4_expiry_notice',now(),'v4:expiry:'||source,jsonb_build_object('source',source,'ends_at',ends_at,'tier',tier)
 from public.access_grants where revoked_at is null and ends_at between now() and now()+interval '1 day'
 on conflict(dedupe_key) do nothing;
 -- Flag exhausted leases so failures are visible and can be retried by admin.
 update public.automation_jobs set status='failed',last_error=coalesce(last_error,'Attempts exhausted') where attempts>=8 and status in ('pending','processing') and (locked_at is null or locked_at<now()-interval '5 minutes');
 update public.telegram_updates set status='failed',last_error=coalesce(last_error,'Attempts exhausted') where attempts>=8 and status in ('pending','processing') and (locked_at is null or locked_at<now()-interval '5 minutes');
 return n;
end $$;

create or replace function public.v4_analytics(p_admin bigint) returns jsonb language sql stable set search_path=public as $$
 with people as (select * from public.users where user_id<>p_admin),
 f as (select user_id,bool_or(event='simple_offer_seen') offered,bool_or(event='v4_payment_click') clicked,
  bool_or(event='simple_checkout') checkout from public.funnel_progress group by user_id),
 money as (select user_id,count(*) filter(where refunded_at is null) purchases,
  sum(amount) filter(where refunded_at is null) stars,sum(amount) filter(where refunded_at is not null) refunded
  from public.payments where currency='XTR' group by user_id),
 combined as (select u.*,coalesce(f.offered,false) offered,coalesce(f.clicked,false) clicked,coalesce(f.checkout,false) checkout,
  coalesce(m.purchases,0) purchases,coalesce(m.stars,0) stars,coalesce(m.refunded,0) refunded
  from people u left join f using(user_id) left join money m using(user_id)),
 segments as (select 'language' kind,coalesce(acquisition_lang,'unknown') label,count(*) users,
  count(*) filter(where offered) offers,count(*) filter(where clicked or checkout) clicks,count(*) filter(where checkout) checkouts,
  count(*) filter(where purchases>0) buyers,sum(purchases) purchases,sum(stars) stars from combined group by acquisition_lang
 union all select 'ab',coalesce(experiment_variant,'legacy'),count(*),count(*) filter(where offered),count(*) filter(where clicked or checkout),
  count(*) filter(where checkout),count(*) filter(where purchases>0),sum(purchases),sum(stars) from combined group by experiment_variant
 union all select 'source',coalesce(ref,'direct'),count(*),count(*) filter(where offered),count(*) filter(where clicked or checkout),
  count(*) filter(where checkout),count(*) filter(where purchases>0),sum(purchases),sum(stars) from combined group by ref
 union all select 'market',coalesce(market,'global'),count(*),count(*) filter(where offered),count(*) filter(where clicked or checkout),
  count(*) filter(where checkout),count(*) filter(where purchases>0),sum(purchases),sum(stars) from combined group by market)
 select jsonb_build_object('users',(select count(*) from combined),'blocked',(select count(*) from combined where blocked),
  'new7',(select count(*) from combined where created_at>=now()-interval '7 days'),
  'offers',(select count(*) from combined where offered),'clicks',(select count(*) from combined where clicked or checkout),
  'checkouts',(select count(*) from combined where checkout),'buyers',(select count(*) from combined where purchases>0),
  'purchases',(select coalesce(sum(purchases),0) from combined),'stars',(select coalesce(sum(stars),0) from combined),
  'refunds',(select coalesce(sum(refunded),0) from combined),
  'messages',(select coalesce(sum(total_messages),0) from combined),'replies',(select coalesce(sum(assistant_messages),0) from combined),
  'pending',(select count(*) from public.pending_replies where user_id<>p_admin),
  'segments',(select coalesce(jsonb_agg(to_jsonb(segments)),'[]') from segments),
  'reminders',(select coalesce(sum(hits),0) from public.funnel_progress where user_id<>p_admin and event='simple_reminder_sent'))
$$;

create or replace function public.v4_metrics() returns jsonb language sql stable set search_path=public as $$
 select jsonb_build_object('version',4,
  'jobs_pending',(select count(*) from public.automation_jobs where job_type like 'v4_%' and status='pending'),
  'jobs_failed',(select count(*) from public.automation_jobs where job_type like 'v4_%' and status='failed'),
  'updates_failed',(select count(*) from public.telegram_updates where status='failed'),
  'oldest_job_seconds',(select coalesce(greatest(0,extract(epoch from now()-min(scheduled_at))),0) from public.automation_jobs where job_type like 'v4_%' and status='pending'),
  'active_connections',(select count(*) from pg_stat_activity where datname=current_database()),
  'tables',(select jsonb_agg(jsonb_build_object('name',relname,'bytes',pg_total_relation_size(relid),'estimated_rows',n_live_tup))
   from pg_stat_user_tables where schemaname='public' and relname in ('users','payments','messages','events','automation_jobs','telegram_updates','access_grants')))
$$;

create or replace function public.v4_partners() returns jsonb language sql stable set search_path=public as $$
 with registrations as (select ref,count(*) users from public.users group by ref),
 earnings as (select c.partner_id,count(*) filter(where p.refunded_at is null) purchases,
  coalesce(sum(c.commission_stars) filter(where p.refunded_at is null),0) earned
  from public.traffic_commissions c join public.payments p on p.id=c.payment_id group by c.partner_id),
 payouts as (select partner_id,sum(amount_stars) paid from public.partner_payouts group by partner_id)
 select coalesce(jsonb_agg(to_jsonb(p)||jsonb_build_object('users',coalesce(r.users,0),
  'purchases',coalesce(e.purchases,0),'earned',coalesce(e.earned,0),'paid',coalesce(o.paid,0))),'[]')
 from public.traffic_partners p left join registrations r on r.ref=p.code
 left join earnings e on e.partner_id=p.id left join payouts o on o.partner_id=p.id
$$;

-- Technical cleanup is batched. Archived content remains available in *_archive.
create or replace function public.v4_cleanup() returns jsonb language plpgsql set search_path=public as $$
declare ms int; ev int; jobs int; upds int; begin
 if exists(select from public.v4_state where key='cleanup' and (value->>'at')::timestamptz>now()-interval '1 hour') then return '{}'::jsonb; end if;
 with picked as (select id from public.messages where created_at<now()-interval '180 days' order by id limit 2000),
 saved as (insert into public.messages_archive select m.* from public.messages m join picked using(id) on conflict(id) do nothing returning id)
 delete from public.messages where id in (select id from picked);
 get diagnostics ms=row_count;
 with picked as (select id from public.events where created_at<now()-interval '90 days' order by id limit 3000),
 saved as (insert into public.events_archive select e.* from public.events e join picked using(id) on conflict(id) do nothing returning id)
 delete from public.events where id in (select id from picked);
 get diagnostics ev=row_count;
 with picked as (select id from public.call_requests where status<>'pending' and created_at<now()-interval '180 days' order by id limit 1000),
 saved as (insert into public.call_requests_archive select c.* from public.call_requests c join picked using(id) on conflict(id) do nothing returning id)
 delete from public.call_requests where id in (select id from picked);
 delete from public.automation_jobs where id in (select id from public.automation_jobs where job_type in ('v4_daily','v4_expiry_notice') and status in ('sent','cancelled') and created_at<now()-interval '30 days' order by id limit 3000);
 get diagnostics jobs=row_count;
 -- Keep failed updates and unresolved financial payloads for support; do not silently delete them.
 delete from public.telegram_updates where update_id in (select update_id from public.telegram_updates where status='done' and created_at<now()-interval '7 days' order by update_id limit 3000);
 get diagnostics upds=row_count;
 with picked as (select id from public.automation_jobs where job_type in ('v4_daily','v4_expiry_notice')
   and status='failed' and created_at<now()-interval '90 days' order by id limit 1000),
 saved as (insert into public.automation_errors_archive(id,user_id,job_type,attempts,last_error,created_at)
   select j.id,j.user_id,j.job_type,j.attempts,j.last_error,j.created_at from public.automation_jobs j join picked using(id)
   on conflict(id) do nothing returning id)
 delete from public.automation_jobs where id in(select id from picked);
 delete from public.automation_errors_archive where id in(select id from public.automation_errors_archive
   where created_at<now()-interval '365 days' order by id limit 1000);
 delete from public.manual_offer_drafts where expires_at<now();
 insert into public.v4_state values('cleanup',jsonb_build_object('at',now())) on conflict(key) do update set value=excluded.value;
 return jsonb_build_object('archived_messages',ms,'archived_events',ev,'jobs',jobs,'updates',upds);
end $$;

-- New tables and every v4 RPC are backend-only; no anonymous client access.
do $$ declare r record; begin
 for r in select unnest(array['v4_state','access_grants','funnel_progress','telegram_updates','manual_offer_drafts','messages_archive','events_archive','call_requests_archive','automation_errors_archive']) name loop
  execute format('alter table public.%I enable row level security',r.name);
  execute format('revoke all on public.%I from public,anon,authenticated',r.name);
  execute format('grant all on public.%I to service_role',r.name);
 end loop;
 for r in select oid::regprocedure fn from pg_proc where pronamespace='public'::regnamespace and proname like 'v4\_%' escape '\' loop
  execute format('revoke all on function %s from public,anon,authenticated',r.fn);
  execute format('grant execute on function %s to service_role',r.fn);
 end loop;
end $$;
insert into public.v4_state values('schema_version','4') on conflict(key) do update set value=excluded.value;
notify pgrst,'reload schema';
commit;
