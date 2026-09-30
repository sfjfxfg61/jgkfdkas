# Privacy notes

The bot stores Telegram user id, username/name, language/region, public/private channel state, subscription/payment metadata, messages sent to the bot, sales events, follow-up jobs and admin notes in Supabase.

With the recommended `AUTO_REPLY_AI=false`, user messages are delivered to the administrator and are not sent to Groq.

If `AUTO_REPLY_AI=true` is enabled, only recent conversation messages are sent to the configured Groq model to draft/send a delayed reply. This release has no long-term AI memory system.

Telegram Stars handles payment processing; the bot does not receive card details.
