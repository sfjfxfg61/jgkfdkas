# Mira — monetized AI Companion for Telegram

Production-oriented Telegram product with persistent memory, tiered AI models, regional pricing, recurring Telegram Stars subscriptions, a high-value annual plan, subscription controls, refunds, funnel analytics, and six interface languages.

Mira is disclosed as AI. The product is intentionally nonsexual and does not use jealousy, guilt, fake scarcity, or claims of consciousness to drive payment.

## Product architecture

- onboarding with warm, playful, and calm conversation styles;
- Supabase-backed conversation history and structured long-term memory;
- Free, Plus, Pro, Ultra, and Black tiers with server-side entitlements;
- recurring 30-day Stars subscriptions through invoice links;
- one-payment Black annual plan designed to raise average order value through real value;
- regional prices for Ukraine, Eastern Europe, LATAM, EU/UK, USA/Canada, and Global;
- manual pricing-region selector plus campaign-ref overrides such as `/start us_campaign1`;
- signed payment payloads, amount verification, idempotent activation, cancellation, and refund handling;
- direct Groq API integration with a fallback model and low output-token budget;
- automatic AI replies plus administrator ticket forwarding and timed human takeover;
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
| `COMPANION_NAME` | no | displayed character name |
| `MEMORY_EXTRACTION_INTERVAL` | no | messages between memory extraction passes |
| `PROACTIVE_INTERVAL_HOURS` | no | minimum proactive-message interval |
| `HUMAN_TAKEOVER_MINUTES` | no | how long AI pauses after an admin reply |
| `PRIVATE_CHANNEL_URL` | no | paid community URL shown after payment |
| `AI_TIMEOUT_SECONDS` | no | model request timeout |
| `PORT` | no | health server port |

Generate a secret locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Commands

- `/start [ref]` — onboarding and attribution;
- `/menu` — navigation;
- `/about` — AI disclosure;
- `/stats` — admin product metrics;
- `/broadcast TEXT` — admin broadcast.
- `/pause USER_ID [MINUTES]` — pause automatic AI for one conversation;
- `/ai USER_ID` — resume automatic AI;
- reply directly to a forwarded `TICKET_ID` message — answer the user and pause AI automatically.

## Existing Render service

Keep the current `ADMIN_ID`, `BOT_TOKEN`, `PORT`, `PRIVATE_CHANNEL_URL`, `PUB_LINK_*`, `SUPABASE_KEY`, and `SUPABASE_URL` values. Add:

- `GROQ_API_KEY` — secret from Groq;
- `GROQ_MODEL=openai/gpt-oss-20b`;
- `GROQ_FALLBACK_MODEL=qwen/qwen3.8-27b`;
- `COMPANION_NAME=Mira`;
- `HUMAN_TAKEOVER_MINUTES=30`.

The current `PUB_LINK_*` variables may remain even though this bot version does not require them for chat generation.

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

The prompt prohibits exclusivity pressure, secrecy, romantic or sexual roleplay, and attempts to replace real relationships. Memory extraction excludes credentials, exact addresses, diagnoses, financial secrets, and sexual details. Users can inspect and delete stored memory and conversation history.
