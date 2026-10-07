# Victoria v10 — deploy notes

You said v7/v8/v9 were not deployed. This v10 release includes the required v9 business migration changes plus the traffic-partner schema, so run only `V10_MIGRATION_SAFE.sql`.

## Safe order

1. In Supabase SQL Editor run `V10_MIGRATION_SAFE.sql`. It is non-destructive: no DROP TABLE and no DELETE FROM. It does cancel legacy pending sales jobs so old cold_daily messages do not continue firing.
2. Deploy the v10 ZIP to Render.
3. Run `/diag`. Startup now verifies the partner tables/RPC too; if the migration was skipped, the bot should fail fast instead of silently losing attribution.
4. Run `/stats`.
5. Add one test uploader: `/partneradd <telegram_id> testtraffic 30 Test`.
6. Have that uploader open the bot once, then run `/partner`.
7. Open their generated `?start=p_testtraffic` link from a fresh account. The uploader dashboard should increment by one after registration.
8. Test a real Stars payment. The partner commission ledger is created automatically from successful payment rows.

## Important accounting behavior

- Partner commission is calculated on gross successful Stars charged to attributed users.
- Each sale stores the percentage that applied at the moment of payment. Later rate changes do not rewrite history.
- Refunded payments remain in history but are excluded from dashboard earned commission.
- `/partnerpay` only records that you actually paid an uploader; the bot does not send money by itself.
- An uploader cannot see customer identities, messages, or admin data.

## Existing variables

No new Render secret is needed. Keep the existing server-side Supabase key.
