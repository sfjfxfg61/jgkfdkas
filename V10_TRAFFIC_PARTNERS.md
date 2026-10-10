# Traffic uploader system

Each uploader has: Telegram ID, display name, immutable tracking code, commission percentage, active/paused status, personal deep link and aggregate dashboard.

Example creation:
`/partneradd 123456789 max_de 30 Max Germany`

Generated link:
`https://t.me/<your_bot>?start=p_max_de`

The dashboard shows traffic for 1/7/30 days and lifetime, reachable/blocked users, funnel steps, payers, gross Stars revenue, commission accrued, payouts recorded and balance owed.

Commission attribution is tied to actual successful entries in `payments`; clicks or leads alone do not create commission.


The dashboard distinguishes raw `/start` activations through the tracking link from new first-touch leads actually assigned to the uploader. This makes repeat/existing users visible without letting them hijack attribution.

When an attributed customer completes a successful payment, the uploader receives an aggregate sale notification with gross Stars and their commission amount, but no customer identity.
