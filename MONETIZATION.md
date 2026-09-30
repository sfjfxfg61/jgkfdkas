# Monetization flow

The bot sells paid access while preserving the feel of a personal Telegram account.

Plans use the existing internal codes for payment/database compatibility:

- `plus` — private channel
- `pro` — private channel + personal chat
- `ultra` — channel + personal chat + priority replies
- `black` — personal format + up to two scheduled 20-minute calls per paid period

All current products are 30-day Telegram Stars subscriptions with renewal that can be disabled by the user.

Prepared sales copy and follow-ups live in `sales_copy.py`. They are intentionally short and conversational instead of support-style text.
