# Victoria v10 — business-ready Telegram sales bot

This release is intended to be deployed directly over the currently running pre-v7 Victoria version.
Do not deploy v7, v8 or v9 first.

## Main business features

- Telegram Stars subscriptions with regional pricing.
- Manual chat/admin inbox; automated conversational replies are disabled.
- Private paid channel access and expiry handling.
- Event-driven sales follow-ups, including checkout help after 10 minutes.
- Admin sales/funnel analytics.
- Traffic uploader/partner profiles with unique Telegram deep links.
- First-touch traffic attribution: `/start p_CODE`.
- Partner dashboards: leads, funnel, paid users, generated Stars revenue, commission earned, paid out and outstanding balance.
- Revenue-share percentage is frozen for each payment at the rate active when that payment was recorded.
- Refunded payments do not count toward partner earnings.

## Deploy order

1. Run `V10_MIGRATION_SAFE.sql` in Supabase SQL Editor.
2. Deploy this code to Render.
3. Keep existing environment variables. `FOLLOWUPS_ENABLED=true` and `MARKETING_MODE=limited` are recommended.
4. Run `/diag`, then `/stats`.
5. Create a traffic partner with `/partneradd TELEGRAM_ID CODE PERCENT NAME`.
6. Test the generated partner link from a fresh Telegram account.
7. Test one real Stars checkout before sending large traffic.

## Traffic partner commands

Admin:
- `/partners` — list all uploaders and headline metrics.
- `/partneradd ID CODE PERCENT NAME` — create a profile.
- `/partnerinfo CODE` — detailed profile.
- `/partnerrate CODE PERCENT` — change future commission rate.
- `/partnerpause CODE` / `/partnerresume CODE` — stop/resume new attribution.
- `/partnerpay CODE STARS note` — mark a payout already made outside the bot.

Uploader:
- `/partner` — their own aggregate dashboard and personal traffic link.

Uploaders never receive customer IDs or message content through the dashboard.

## Attribution rules

The first stored referral wins. Existing users do not get reassigned by opening another uploader's link later. Pausing an uploader stops attribution of new registrations, while already attributed customers remain associated with that uploader for future commission calculations.
