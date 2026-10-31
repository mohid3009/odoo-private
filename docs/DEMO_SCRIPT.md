# Demo script (click by click, ~25 min)

**Before judging:** fresh DB → `python manage.py migrate` → `python scripts/seed_demo.py` (logins below, plus catalog "Brightloop Suite"
and one active subscription for `customer@demo`). Password for every demo login: `Demo@12345` — `admin@demo`, `staff@demo`, `customer@demo`.
Rehearse the whole data path first: `python -m pytest -q tests/test_demo_flow.py` runs S1–S7 below through the API in a few seconds.
WhatsApp: `WHATSAPP_PROVIDER=twilio` with the demo phone re-joined to the sandbox, or `console` and show the Notifications log.

**Dates.** The subscription starts three months back so the billing days already happened: with demo day **2026-10-31**, `START` =
**2026-08-01**, and the billing days are 08-01, 09-01, 10-01 and 11-01 (a future billing date is allowed for the demo). On another day,
shift every date by the same number of months. A subscription cannot be activated before its start date, so `START` must not be in the future.

## S1 — Sign-up & roles (3 min)
1. `/signup`: `new@demo.com`, password `weakpass` → rejected (needs 9+ characters, upper, lower, special). `Strong@Pass1` → created as a customer. Tick WhatsApp opt-in with a 10-digit number (stored as `+91…`).
2. Sign up again as `NEW@demo.com` → "already exists" (case-insensitive).
3. **Forgot password** → the reset link appears in the server console → open it → set `Another@Pass2` → log in. Opening the link a second time → "invalid or expired".
4. Log in as `admin@demo` → **Staff** → create `ops@demo.com` (staff). Log in as staff: no Staff menu; typing `/staff` → 403 page.
5. **Expected:** three different menus — admin (Catalog edit, Discounts edit, Notifications, Staff), staff (operations), customer (My subscriptions / invoices / payments / notifications).

## S2 — New plan (3 min, admin)
1. Catalog → Taxes: `GST 18%` (18). Payment terms: `Net 15` (15 days, default).
2. Products → New: `Brightloop CRM`, software, sales 1000.00, cost 400.00, a note; tax GST 18%; variant `Brand` = `Odoo`, extra `560.00` → effective price **1560.00**.
3. Plans → New: `CRM Monthly`, that product, price 1000.00, **monthly**, min qty 1, available 2026-01-01 → 2027-12-31, all four flags on.
4. Log in as staff: Catalog is read-only (no buttons; the API answers 403).

## S3 — Quotation → subscription (4 min, staff)
1. Subscriptions → Quotation templates → `CRM Starter`: plan CRM Monthly, validity 15 days, line CRM × 5, variant Odoo.
2. Subscriptions → New → from template, customer `new@demo.com`, start **`START`** (2026-08-01), expiry 2027-07-31, Net 15 → line 5 × ₹1,560.00 = **₹7,800.00**.
3. Send quotation → Confirm → Activate; the history logs each step with user and time. Only legal buttons are shown; a direct API call for an illegal one → 409.

## S4 — Billing day (4 min, staff)
1. Billing → date 2026-08-01 → **Run billing** → `1 invoice created · 0 skipped · 0 errors`.
2. Invoices → the draft: 7,800.00 + GST 1,404.00 = **₹9,204.00**. **Confirm** → number `INV-000001`; Odoo badge `skipped` (Odoo off) or `synced`.
3. **Run billing again** for 2026-08-01 → `0 created` (nothing is ever billed twice). **Send** → email in the console (+ WhatsApp). **Print** → browser Save as PDF.

## S5 — Discounts (3 min, admin)
1. Discounts → New: `Launch 10%`, percent 10, scope product (Brightloop CRM), min qty 5, start 2026-09-01, **usage limit 2**.
2. Billing for 2026-09-01, then 2026-10-01 → each new invoice has a **−₹780.00** discount line → **₹8,283.60** (the worked example). The rule shows `2 / 2 Exhausted`; click it for the redemptions.
3. Billing for 2026-11-01 → the November invoice has **no** discount (limit reached): ₹9,204.00. (This run may also bill the seeded subscription; that is expected.)
4. Log in as staff: Discounts is read-only, creating one → 403.

## S6 — Payments (3 min, staff)
1. Open the September invoice (₹8,283.60) → Confirm → **Record payment** ₹5,000.00, UPI, note "first part" → still Confirmed, balance **₹3,283.60**.
2. Record ₹4,000.00 → rejected (more than the balance). Record ₹3,283.60 → **Paid**.
3. Invoices → **Overdue** chip: INV-000001 (August, due 2026-08-16, unpaid) with its days overdue in red.
4. Optional: three failed attempts flag the invoice "Needs attention"; only an admin can reset it; an admin can reverse a payment (Paid → Confirmed).

## S7 — Finance view and portal (3 min)
1. Staff → **Dashboard**: active subscriptions, MRR, ARR, revenue collected (₹8,283.60), invoiced, outstanding (₹9,204.00 + any later confirmed), overdue count and amount. Filter by plan, customer, status or dates; click **Overdue** → the overdue invoice list.
2. Log in as `new@demo.com` → My subscriptions → the subscription and its invoices (confirmed only, never drafts) → print one. Typing another customer's id in the URL → "not found" (API 404).
3. Scale: on a DB with `seed_demo.py --big`, reload the dashboard with the Network tab open (summary request ~150 ms) and run `python scripts/perf_check.py` (34 calls, all < 1 s).

## Notifications (2 min, admin)
Notifications page → Log shows WELCOME, QUOTATION_READY, SUBSCRIPTION_ACTIVATED, INVOICE_READY and PAYMENT_RECEIVED rows (`sent`). **Run reminders** twice → the second run adds nothing; re-running billing adds nothing. Test send → a message to the demo phone (Twilio) or the console.
