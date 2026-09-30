# Victoria personal Telegram bot

This release is built around the actual product flow: Victoria's personal bot, manual inbox, paid private access, Telegram Stars, mandatory public-channel subscription, sales follow-ups and analytics.

There is **no XP system, no relationship levels and no long-term AI memory**. Legacy `xp`, `style` and `memories` data can remain in the old Supabase project; this code does not use it.

## Production mode

Recommended Render values:

```text
AUTO_REPLY_AI=false
FOLLOWUPS_ENABLED=true
```

With `AUTO_REPLY_AI=false`, every user message is delivered to the admin as a `TICKET_ID`. Victoria replies manually by replying to that ticket or with `/send USER_ID text`.

If `AUTO_REPLY_AI=true` is enabled later, Groq is used only as a delayed reply writer from recent chat messages. It does not use memory, XP or relationship levels.

## Before deploy

1. Open **Supabase → SQL Editor**.
2. Run `MIGRATION_RUN_FIRST.sql` once.
3. Keep the existing Render environment variables:
   - `ADMIN_ID`
   - `BOT_TOKEN`
   - `COMPANION_NAME`
   - `PORT`
   - `PRIVATE_CHANNEL_URL`
   - `PUB_LINK_UK`, `PUB_LINK_RU`, `PUB_LINK_EN`, `PUB_LINK_ES`, `PUB_LINK_DE`, `PUB_LINK_FR`
   - `SUPABASE_URL`, `SUPABASE_KEY`
   - `FOLLOWUPS_ENABLED=true`
   - `AUTO_REPLY_AI=false`
   - Groq variables may stay; they are only used if auto replies are enabled.
4. `SUPABASE_KEY` must be the server-side service-role key because the tables use RLS.
5. Add the bot as admin to every public channel used in `PUB_LINK_*`. The links should be ordinary public links such as `https://t.me/channelname`; the bot extracts `@channelname` and checks membership with `getChatMember`.

## Private paid channel

`PRIVATE_CHANNEL_URL` works directly when it contains:

- a numeric Telegram channel id such as `-1001234567890`, or
- a public channel username/link.

If it currently contains a private invite link like `https://t.me/+...`, Telegram does not allow the bot to derive the channel id from that URL. Post `/channel_id` once **inside the paid channel** while the bot is an admin. The bot will send the `-100...` id to `ADMIN_ID`; place that number in `PRIVATE_CHANNEL_URL` and redeploy.

The bot needs admin rights in the paid channel to create one-day join-request links and remove expired members.

## User funnel

`/start → region → mandatory public channel → personal bot → Private → checkout → Stars payment → private-channel access`

Users can change region and language later in Settings.

## Manual chat

Every incoming text/media message creates an admin ticket. The admin can:

- reply directly to the ticket with text;
- reply with photo/video/voice/audio/document/animation/sticker;
- use `/send USER_ID text`;
- use quick buttons: Private, Content, Expensive, Plans, How to buy, Later;
- close a ticket without replying.

Quick-reply copy is in `sales_copy.py` and follows the short, casual Victoria style.

## Follow-ups

When `FOLLOWUPS_ENABLED=true`:

- public-channel gate: +6h;
- paywall without checkout: +12h, +48h, then once every 24h;
- checkout without payment: +30m, +6h, +23h, then once every 24h starting on day 2;
- new checkout links are signed for 24 hours. The +23h reminder is therefore real: after the deadline the old link is rejected at pre-checkout, while the next daily reminder opens a fresh checkout.

Daily reminders keep running until the user pays, writes to Victoria, receives a manual reply, blocks the bot, or has automation disabled with `/followups ID off`. Only one future daily job is queued at a time, so the queue does not grow forever.

All automatic copy is localized from `users.lang` (`uk`, `ru`, `en`, `de`, `fr`, `es`). Region/market controls pricing; language controls the text and public-channel link.

No fake link deletion or fake countdown is used.

## Admin commands

```text
/admin
/stats
/queue
/user ID
/history ID
/send ID TEXT
/note ID TEXT
/setregion ID ua|cis|latam|eu|us|global
/setlang ID uk|ru|en|de|fr|es
/followups ID on|off
/broadcast [segment] TEXT
/calls
/call_done REQUEST_ID
/call_cancel REQUEST_ID
```

## Analytics

`/stats` shows:

- total/reachable/blocked users;
- new and active users for 1/7/30 days;
- mandatory-channel verification conversion;
- paywall → checkout → payment funnel;
- Stars revenue for today/7d/30d/lifetime;
- plan and region revenue breakdown;
- follow-up sends and attributed conversions;
- manual-reply queue, chatters, languages, markets and traffic refs.

## Prices

Edit only `PRICE_MATRIX` in `monetization.py` to change regional prices.
