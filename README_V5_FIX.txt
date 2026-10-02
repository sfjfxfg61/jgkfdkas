Victoria v5 fixes private Telegram channel IDs in invite buttons.

Why the old error happened:
Telegram accepts -100... as a chat_id for API methods such as getChatMember, but an inline keyboard
URL must be a real http/https URL. v4 reused PUB_LINK_* for both purposes.

v5 behavior:
- If PUB_LINK_* is a numeric -100... id, it stays the membership-check chat_id.
- When a join button is needed, the bot creates a fresh 24-hour, one-user invite link with
  createChatInviteLink and places that https://t.me/+... URL in the button.
- If PUB_LINK_* is already a normal Telegram URL, it remains supported.
- PRIVATE_CHANNEL_URL can also be a numeric -100... id. Paid users receive a fresh one-user
  24-hour invite after successful payment and when requesting access again.
- No prices, products, recurring subscriptions, sales funnel timing, follow-up schedule,
  manual tickets, broadcasts, admin panel, or payment payloads were changed by this fix.
