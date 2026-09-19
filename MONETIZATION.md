# Monetization operating plan

## Objective

Increase revenue and average order value through clear, valuable upgrades: more messages, deeper memory, better models, measured D1/D3/D7 retention, and a one-payment annual option. Do not use fake countdowns, invented scarcity, guilt, jealousy, or emotional dependency.

## Regional price matrix (Telegram Stars)

| Market | Plus / 30d | Pro / 30d | Ultra / 30d | Black / 365d |
|---|---:|---:|---:|---:|
| Ukraine | 249 | 549 | 1,299 | 4,999 |
| Eastern Europe | 299 | 699 | 1,499 | 5,499 |
| Latin America | 349 | 799 | 1,799 | 5,999 |
| EU / UK | 599 | 1,399 | 3,299 | 8,499 |
| USA / Canada | 899 | 2,199 | 4,999 | 9,999 |
| Global | 499 | 1,099 | 2,499 | 6,999 |

Prices are selected automatically from Telegram language: Ukrainian → Ukraine, Russian → Eastern Europe, Spanish → LATAM, German/French → EU/UK, English → USA/Canada, and unsupported languages → Global. There is no region selector in the user interface.

## Funnel events already implemented

`start` → `onboarding_completed` → `message_milestone` → `paywall_view` or `quota_paywall` → `checkout_created` → `payment_success` → optional `subscription_canceled` or `payment_refunded`.

Retention events: `reminder_sent` with stage `d1`, `d3`, or `d7` → `reminder_returned`. Contextual monetization events: `premium_nudge_shown` and `channel_nudge_shown`.

Core weekly metrics:

- activation: users reaching 3 and 10 messages;
- payer conversion by market and acquisition ref;
- checkout-to-payment conversion;
- revenue and ARPPU in Stars;
- plan mix and Black share;
- cancellation and refund rates;
- 7-day active payer retention;
- model cost per active user and per paid tier.

## Experiment rules

1. Change one pricing or packaging variable per cohort.
2. Keep an unchanged control cohort.
3. Evaluate conversion, revenue per new user, refunds, and retention together.
4. Do not optimize only for the first payment; a higher refund or churn rate can erase short-term gains.
5. Use only Telegram interface language for the automatic price group; do not infer it from sensitive data.

The database includes a stable `pricing_variant` field for cohort assignment; the initial release records `control` and `anchor` but does not yet change prices between them.
