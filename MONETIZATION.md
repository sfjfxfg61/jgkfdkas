# Monetization and operations

Four 30-day recurring plans: Plus gives private channel access; Pro adds personal chat; Ultra adds priority handling in the administrator queue; Black adds two scheduled 20-minute calls per paid period. No plan sells a message quota. Prices remain the original matrix in monetization.py and must be reviewed before launch, particularly Black, which was previously priced as a one-year purchase.

Language suggests a region on the first /start. The user may choose another once; the stored users.market sets the displayed and invoiced price. Payment callbacks verify the signed product, user, market, amount and currency.

The bot checks channel admin permissions before accepting payment. It reads the existing PRIVATE_CHANNEL_URL setting as a numeric channel ID or resolvable public channel handle. Private invite links cannot be used for access control; use the numeric ID. It creates a join-request invite after a successful charge. The join handler verifies active access; a worker removes expired members. /access reissues a one-day invite. Revoke older reusable private links before launch.

Chat messages appear in the admin ticket feed and /queue immediately. A database-backed worker may answer after 30 minutes if no human reply has arrived. /send and replies to a ticket clear the pending answer. Ultra and Black are marked priority in tickets and /queue; the human operator must actually honor that priority. Black customers request calls with /call; /calls and /call_done track up to two per paid period.

/stats and /funnel report acquisition sources, engagement, checkout, paid conversion, refunds and revenue in Stars. The retention report counts exact D1/D3/D7 days in the Kyiv timezone and excludes incomplete days. These reports measure correlations and conversion, not causal attribution.

Do not use invented time limits, false popularity claims or emotional pressure. Published product terms must accurately explain any automated chat assistance and how personal conversations are handled.
