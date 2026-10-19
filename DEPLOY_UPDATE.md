# Victoria update: deployment checklist

1. Back up the current GitHub commit and Supabase database before deployment.
2. In Supabase SQL Editor, execute `migration_vip_offers.sql` once. It only adds a nullable timestamp column to `users`.
3. Upload the repository files to the existing GitHub repository; keep current Render environment variables, including `BOT_TOKEN`, `SUPABASE_KEY`, `SUPABASE_URL`, `ADMIN_ID`, `PRIVATE_CHANNEL_URL`, and `PUB_LINK_*`. Do not paste secrets into GitHub.
4. Keep `FOLLOWUPS_ENABLED=true`; optional `REMINDER_WINDOW_START=18:00`, `REMINDER_WINDOW_END=21:00`, `REMINDER_TIMEZONE=Europe/Kyiv`.
5. Smoke-test start, plan prices, invoice creation, pre-checkout, successful payment, channel access, partner attribution, opt-out, and 2-hour expiry with test accounts before enabling production broadcasts.

## Behavior
- Trial 7 days: 100 Stars in UA/CIS/LATAM/ASIA, 250 elsewhere.
- Forever: 250 Stars in UA/CIS/LATAM/ASIA, 500 elsewhere.
- VIP: 500 Stars in UA/CIS/LATAM/ASIA, 1000 elsewhere.
- Daily reminder to eligible non-paying users at a stable per-user time in the configured evening window. For EU/US/GLOBAL it creates a 2-hour VIP offer at 500 Stars. For lower-price regions, no fictitious discount is claimed.
- Expiry is based on UTC timestamps and independent of user timezone. The evening sending window is based on the configured timezone.
- Existing simple1/simple2 signed invoices remain compatible; new discounted invoices use simple3 signatures.
- Partner management uses the existing `traffic_partners`, `traffic_commissions`, and `partner_payouts` tables.

## Limitations
- Telegram may show different Star top-up packs depending on platform; the bot cannot guarantee a single-step top-up.
- This release does not change the existing 10-minute/2-hour/6-hour automation-job schedule. Test its behavior separately before enabling heavy traffic.
- The inbox reply gap cannot be proven fixed from the database schema alone; inspect runtime logs and admin message handling.
- Real Supabase/Telegram integration has not been tested here.
