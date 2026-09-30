# Vika Telegram bot

Membership bot with an open chat, a private channel, four paid plans, a human admin inbox and an automated reply after 30 minutes without a human answer. It uses Supabase and Telegram Stars and supports Ukrainian, Russian, English, Spanish, German and French.

## Plans

| Internal code | Included for 30 days |
|---|---|
| plus | Private channel |
| pro | Channel and personal chat |
| ultra | Pro plus priority admin handling |
| black | Ultra plus two scheduled 20-minute calls |

All plans currently renew every 30 days. Prices in monetization.py were carried forward from a different package and must be reviewed before enabling checkout. No paid plan promises a message quota.

## Update an existing installation

1. Back up the database. Run migrations/2026_09_25_region_once.sql, then migrations/2026_09_25_channel_access.sql in the Supabase SQL Editor. Do not run the entire schema.sql over a live installation.
2. Add the bot as an administrator of the private channel with invite and restrict-member rights. Keep the existing Render variable PRIVATE_CHANNEL_URL: set its value to the numeric channel ID (`-100…`). To find it, post `/channel_id` in the channel after adding the bot; it sends the ID privately to ADMIN_ID. A public channel username or public `t.me/name` link also works. A private `t.me/+…` or `t.me/joinchat/…` invite link cannot identify the channel to Telegram's bot API; with such a value checkout is disabled until you replace it with the ID. Revoke older reusable invitation links.
3. Replace the changed Python files, install requirements.txt and deploy a single polling worker. The existing BOT_TOKEN, ADMIN_ID, COMPANION_NAME, GROQ_API_KEY, GROQ_MODEL, GROQ_FALLBACK_MODEL, HUMAN_TAKEOVER_MINUTES, PORT, PRIVATE_CHANNEL_URL, PUB_LINK_*, SUPABASE_KEY and SUPABASE_URL keys are recognized. PAYMENT_SECRET and separate PRO_AI_MODEL / ULTRA_AI_MODEL are optional; absent model overrides inherit GROQ_MODEL.
4. On a test account check region choice, invoice, paid join request, /access, refund, renewal/cancellation, expiry removal, human reply and 30-minute fallback. Test /call twice within a Black period and verify a third request is denied.
5. Review prices, terms, privacy text and actual admin availability before selling access.

GET /health runs on PORT. The service uses polling and a database-backed queue; run only one worker or add distributed locks. The generated invitation expires after a day, but /access creates another while the plan is active.

## Commands

- User: /start, /menu, /about, /access, /call, /paysupport.
- Admin: /stats, /funnel, /queue, /calls, /call_done ID, /call_cancel ID, /send ID TEXT, /broadcast TEXT, /pause ID [MINUTES], /ai ID. Post /channel_id in the managed channel to receive its ID privately.
- The admin can also reply to a forwarded TICKET_ID message to answer that user.

The pricing region is selected only at onboarding; existing users retain their old region. The private-channel link is not a static URL in payment confirmation. Messages and payment metadata are stored in Supabase; publish accurate Privacy and Terms documents before launch.
