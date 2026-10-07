# Victoria v10 test report

- Python source compilation: passed.
- Pytest: 53 passed, 1 skipped.
- Skip reason: the local container does not have aiogram installed for the live Telegram invite integration test.
- Partner attribution helpers tested.
- V10 migration checked to contain no DROP TABLE or DELETE FROM.
- Traffic partner tables, commission trigger, refund-aware dashboard RPC, payout ledger, admin commands and self-service dashboard are covered by static/unit tests.
- Existing payment, regional pricing, follow-up, admin and private-channel regression tests remain green.

A real Telegram Stars purchase and live Supabase execution still need one production test after deployment because those external services cannot be executed inside this offline container.
