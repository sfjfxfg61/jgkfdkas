# Victoria v5 — personal sales bot

This version keeps the existing Victoria sales flow, tariffs, Telegram Stars payments,
manual admin replies, analytics and follow-ups, and fixes private Telegram channel invites.

## Private mandatory channels

You may keep the existing Render variables exactly as numeric private-channel IDs:

- `PUB_LINK_UK=-100...`
- `PUB_LINK_RU=-100...`
- `PUB_LINK_EN=-100...`
- `PUB_LINK_DE=-100...`
- `PUB_LINK_FR=-100...`
- `PUB_LINK_ES=-100...`

The bot uses those values as `chat_id` for `getChatMember`. When it needs a clickable
"join" button, it creates a fresh 24-hour invite link through Telegram and puts the
resulting `https://t.me/+...` URL into the button. A numeric `-100...` value is never
inserted into an inline URL button.

The bot must be an administrator in every mandatory channel with **Invite Users** permission.

## Paid private channel

`PRIVATE_CHANNEL_URL` may also remain a numeric `-100...` channel id. After a successful
Stars payment, the buyer gets a fresh one-user 24-hour invite automatically. The same
happens when an active subscriber opens Access again.

For automatic removal after access expires, grant the bot **Ban/Restrict Users** permission
in the paid channel as well.

## Follow-ups

v5 keeps the v4 schedule:

- New/free user before opening tariffs: 6h -> 24h -> 48h -> every 24h.
- Old reachable free users are seeded into daily reactivation after deploy.
- Offer opened without checkout: 12h -> 48h -> every 24h.
- Checkout created without payment: 5m -> 30m -> 3h -> 12h -> 23h -> daily.
- Payment/block/manual disable stops the relevant automation.
- Messages are localized by `users.lang`: uk/ru/en/de/fr/es.

## Render variables

Keep the variables already used by the project. Important values:

- `AUTO_REPLY_AI=false`
- `FOLLOWUPS_ENABLED=true`
- `SUPABASE_KEY` must be a server-side `sb_secret_...` or legacy service-role key.

No new environment-variable names are required for the private-channel fix.

## Supabase

No new database columns are required by v5.

If `HOTFIX_QUEUE_V4.sql` has never been run, run the included copy once. It is designed to
be safe to run again. If retries/processing jobs already work, there is no new SQL required.

## Admin verification

After deploy run `/diag`.

For each mandatory language you should see `✅ invite`. For the paid channel you should see
`✅ invite`; `✅ restrict` is additionally needed for automatic removal after expiry.
