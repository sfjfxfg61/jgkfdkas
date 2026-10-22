import {readFileSync} from 'node:fs';
import {performance} from 'node:perf_hooks';
const {PGlite}=await import(process.env.PGLITE_MODULE_PATH || '@electric-sql/pglite');
const db=new PGlite(); await db.waitReady;
await db.exec("SET TIME ZONE 'UTC'; CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role;");
await db.exec(readFileSync(new URL('./schema_before.sql',import.meta.url),'utf8'));
await db.exec(readFileSync(new URL('../migrations/001_victoria_v4.sql',import.meta.url),'utf8'));
await db.exec(`insert into users(user_id,first_name,lang,acquisition_lang,experiment_variant,ref) select x,'Synthetic',
 (array['uk','ru','en','de','fr','es','pt','it'])[1+x%8],(array['uk','ru','en','de','fr','es','pt','it'])[1+x%8],
 case when x%2=0 then 'A' else 'B' end,'synthetic' from generate_series(1,10000) x;
 insert into events(user_id,event) select 1+(x%10000),case when x%2=0 then 'simple_offer_seen' else 'v4_payment_click' end from generate_series(1,100000) x;
 insert into payments(user_id,telegram_charge_id,payload,amount,plan) select x*10,'synthetic-'||x,'synthetic',100,'secret' from generate_series(1,1000) x;
 analyze;`);
const times=[];let report;
for(let i=0;i<10;i++) {const t=performance.now();report=(await db.query('select v4_analytics(999999) report')).rows[0].report;times.push(performance.now()-t);}
console.log(JSON.stringify({runtime:'PGlite/PostgreSQL in WASM; synthetic local test, not Supabase production',users:10000,raw_events:100000,payments:1000,repeats:10,min_ms:Math.min(...times),median_ms:[...times].sort((a,b)=>a-b)[5],max_ms:Math.max(...times),reported_stars:report.stars,reported_users:report.users}));
await db.close();
