import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';
import assert from 'node:assert/strict';
const db = new PGlite();
const sql=fs.readFileSync(new URL('../V11_SETUP.sql', import.meta.url),'utf8');
let checks=0;
function ok(value){assert.ok(value);checks++;}
const rows=async(s,p=[]) => (await db.query(s,p)).rows;
const one=async(s,p=[]) => (await rows(s,p))[0];
await db.exec('CREATE ROLE anon;CREATE ROLE authenticated;CREATE ROLE service_role BYPASSRLS;');
await db.exec(sql);ok((await one('select victoria_v11_preflight() v')).v.ok);
await db.exec(sql);ok((await one('select victoria_v11_preflight() v')).v.ok);
await db.exec("INSERT INTO users(user_id,ref) VALUES(101,'p_testpartner'); INSERT INTO traffic_partners(telegram_user_id,code,display_name) VALUES(900,'testpartner','Test');");
async function pay(charge,{user=101,plan='black',payload='invoice-one',first=false,expiry='2030-01-01T00:00:00Z',amount=2500}={}){
 return (await one('select victoria_v11_activate($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) v',[user,charge,payload,amount,plan,'global',30,true,expiry,first])).v;
}
let r=await pay('charge-one',{first:true});ok(!r.duplicate);
let u=await one('select * from users where user_id=101');ok(u.subscription_tier==='black'&&u.is_premium&&u.subscription_charge_id==='charge-one');
r=await pay('charge-one',{first:true});ok(r.duplicate);
ok(Number((await one('select count(*) n from payments')).n)===1);
ok(Number((await one('select count(*) n from traffic_commissions')).n)===1);
// A third or fourth completed call can be requested in the same paid period.
for(let i=0;i<4;i++){
 const c=(await one('select victoria_v11_request_call(101) v')).v;
 ok(c.ok&&!c.existing);
 const c2=(await one('select victoria_v11_request_call(101) v')).v;
 ok(c2.existing&&c2.id===c.id);
 await db.query("UPDATE call_requests SET status='completed' WHERE id=$1",[c.id]);
}
await pay('renewal-one',{expiry:'2030-02-01T00:00:00Z'});
u=await one('select * from users where user_id=101');ok(u.subscription_charge_id==='charge-one');
await pay('new-subscription',{first:true,payload:'invoice-two',plan:'pro',amount:500,expiry:'2030-03-01T00:00:00Z'});
u=await one('select * from users where user_id=101');ok(u.subscription_charge_id==='new-subscription'&&u.subscription_tier==='pro');
ok((await one("select charge_id from subscription_cancellations where charge_id='charge-one'")).charge_id==='charge-one');
r=await pay('late-old-renewal',{expiry:'2030-04-01T00:00:00Z'});ok(r.ignored_renewal);
u=await one('select * from users where user_id=101');ok(u.subscription_charge_id==='new-subscription'&&u.subscription_tier==='pro');
// Refund a single last purchase without revoking other valid receipts.
await db.query('select victoria_v11_refund($1)',['new-subscription']);
u=await one('select * from users where user_id=101');ok(u.is_premium);
for(const charge of ['charge-one','renewal-one','late-old-renewal'])await db.query('select victoria_v11_refund($1)',[charge]);
u=await one('select * from users where user_id=101');ok(!u.is_premium&&u.subscription_tier==='free');
r=await pay('charge-one');ok(r.refunded&&r.duplicate);
ok(!(await one('select victoria_v11_request_call(101) v')).v.ok);
// Old user/payment preserved on repeated upgrade.
await db.exec("INSERT INTO users(user_id,is_premium,premium_until,subscription_tier,subscription_charge_id) VALUES(102,true,'2031-01-01','black','legacy-charge'); INSERT INTO payments(user_id,telegram_charge_id,payload,amount) VALUES(102,'legacy-charge','legacy-payload',2500);");
await db.exec(sql);
ok((await one('select subscription_payload from users where user_id=102')).subscription_payload==='legacy-payload');
ok((await one("select amount from payments where telegram_charge_id='legacy-charge'")).amount===2500);
// Lease ownership and cancellation are represented in the real SQL state machine.
await db.exec("INSERT INTO automation_jobs(user_id,job_type,scheduled_at,dedupe_key) VALUES(102,'offer_3h',now(),'job-one');");
let jobs=await rows("select * from victoria_v11_claim_jobs(1,'worker-one')");ok(jobs.length===1&&jobs[0].attempts===1);
ok((await rows("select * from victoria_v11_claim_jobs(1,'worker-two')")).length===0);
await db.exec("UPDATE automation_jobs SET locked_at=now()-interval '11 minutes' WHERE dedupe_key='job-one';");
await rows("select * from victoria_v11_claim_jobs(1,'worker-two')");
ok((await one("select status from automation_jobs where dedupe_key='job-one'")).status==='failed');
// Verify ACLs as actual non-service role.
await db.exec('SET ROLE anon');
let denied=false;try{await rows('select victoria_v11_request_call(101)');}catch(e){denied=true;}ok(denied);
denied=false;try{await rows('select * from payments');}catch(e){denied=true;}ok(denied);
await db.exec('RESET ROLE');
console.log(`${checks} PostgreSQL integration assertions passed`);
await db.close();
