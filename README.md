# Vika — monetized AI conversation bot for Telegram

Production-oriented Telegram product with persistent memory, tiered AI models, language-based pricing, recurring Telegram Stars subscriptions, a high-value annual plan, subscription controls, refunds, funnel analytics, and six interface languages.

Vika is disclosed as AI in the dedicated About screen and when directly asked. The product does not use jealousy, guilt, fake scarcity, or claims of consciousness to drive payment.

## Product architecture

- instant chat without a multi-step onboarding flow;
- Supabase-backed conversation history and structured long-term memory;
- Free, Plus, Pro, Ultra, and Black tiers with server-side entitlements;
- recurring 30-day Stars subscriptions through invoice links;
- one-payment Black annual plan designed to raise average order value through real value;
- prices selected automatically from the user's Telegram language;
- signed payment payloads, amount verification, idempotent activation, cancellation, and refund handling;
- direct Groq API integration with a fallback model and low output-token budget;
- automatic AI replies plus administrator ticket forwarding and timed human takeover;
- automatic D1/D3/D7 re-engagement reminders with return tracking;
- detailed reach, funnel, revenue, retention, reminder, source, and language analytics;
- direct administrator messages to any known Telegram user ID;
- RU, UK, EN, ES, DE, and FR UI and AI replies;
- admin revenue, conversion, ARPPU, tier, and market reporting;
- rate limiting, health endpoint, Docker, and Render configuration.

## Plans and entitlements

| Plan | Messages/day | History | Memories | Model | Billing |
|---|---:|---:|---:|---|---|
| Free | 20 | 12 | 10 | `GROQ_MODEL` | free |
| Plus | 100 | 30 | 30 | `GROQ_MODEL` | every 30 days |
| Pro | 300 | 60 | 100 | `PRO_AI_MODEL` | every 30 days |
| Ultra | 800 | 100 | 250 | `ULTRA_AI_MODEL` | every 30 days |
| Black | 800 | 100 | 250 | `ULTRA_AI_MODEL` | one payment, 365 days |

Prices live in `monetization.py`; the server always recalculates the expected amount from the signed product and market payload. Never trust price data sent from a client.

## Quick start

1. Create a Telegram bot with BotFather.
2. Run the complete `schema.sql` in Supabase SQL Editor. It upgrades the existing minimal `users(user_id, username, first_name, lang, ref, is_paid, created_at)` table in place and preserves its rows.
3. Copy `.env.example` to `.env` and fill in every required value. Use the server-side Supabase service-role key, never the public anon key.
4. Install and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

The health endpoint is `GET /health` on `PORT`. Polling deployment must run as a single bot worker.

## Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `BOT_TOKEN` | yes | Telegram bot token |
| `ADMIN_ID` | recommended | Telegram user ID for admin commands |
| `SUPABASE_URL` | yes | Supabase project URL |
| `SUPABASE_KEY` | yes | server-side service-role key |
| `GROQ_API_KEY` | yes | Groq API access |
| `PAYMENT_SECRET` | no | optional separate HMAC secret; `BOT_TOKEN` is used when omitted |
| `GROQ_MODEL` | no | Free/Plus model; default `openai/gpt-oss-20b` |
| `GROQ_FALLBACK_MODEL` | no | fallback after a retryable Groq error |
| `PRO_AI_MODEL` | no | Pro model ID |
| `ULTRA_AI_MODEL` | no | Ultra/Black model ID |
| `MEMORY_EXTRACTION_INTERVAL` | no | messages between memory extraction passes |
| `HUMAN_TAKEOVER_MINUTES` | no | how long AI pauses after an admin reply |
| `PRIVATE_CHANNEL_URL` | no | paid community URL shown after payment |
| `AI_TIMEOUT_SECONDS` | no | model request timeout |
| `PORT` | no | health server port |

Generate a secret locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Commands

- `/start [ref]` — instant chat start and attribution;
- `/menu` — navigation;
- `/about` — AI disclosure;
- `/stats` — admin product metrics;
- `/funnel` — alias for the complete funnel, revenue, and retention report;
- `/broadcast TEXT` — admin broadcast.
- `/send USER_ID TEXT` or `/msg USER_ID TEXT` — send directly to one user and pause AI temporarily;
- `/pause USER_ID [MINUTES]` — pause automatic AI for one conversation;
- `/ai USER_ID` — resume automatic AI;
- reply directly to a forwarded `TICKET_ID` message — answer the user and pause AI automatically.

## Existing Render service

Keep the current `ADMIN_ID`, `BOT_TOKEN`, `PORT`, `PRIVATE_CHANNEL_URL`, `PUB_LINK_*`, `SUPABASE_KEY`, and `SUPABASE_URL` values. Add:

- `GROQ_API_KEY` — secret from Groq;
- `GROQ_MODEL=openai/gpt-oss-20b`;
- `GROQ_FALLBACK_MODEL=qwen/qwen3.8-27b`;
- `HUMAN_TAKEOVER_MINUTES=30`.

Set the relevant `PUB_LINK_*` variables to show the localized Telegram-channel button.

## Launch checklist

- run `schema.sql` and verify all RPC functions with the service role;
- create separate Telegram test and production bots;
- test every plan, renewal, cancellation, duplicate update, and refund;
- confirm the selected Groq model IDs and account limits;
- publish reviewed Privacy Policy and Terms based on the included drafts;
- add monitoring and database backups;
- start with one polling replica, or migrate to webhooks before horizontal scaling;
- review `MONETIZATION.md`, then change prices only through measured cohorts.

## Safety and privacy

The prompt prohibits exclusivity pressure, secrecy, romantic or sexual roleplay, and attempts to replace real relationships. It can discuss dating, attraction, consent, and relationship boundaries in a non-explicit way. Memory extraction excludes credentials, exact addresses, diagnoses, financial secrets, and sexual details.

## Retention automation

The bot checks inactive users hourly. A user who has sent at least one message can receive one localized reminder after 24 hours, one after 3 days, and one after 7 days. It sends no further reminder until that user returns. Returning resets the cycle and records `reminder_returned` for analytics.

After installing this version, run the complete `schema.sql` once in Supabase SQL Editor before redeploying the bot. The migration is idempotent and preserves existing users, messages, memories, and payments.
