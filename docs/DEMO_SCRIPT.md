# Demo script (click by click)

Prereq: fresh DB → `seed`. Logins (password for all: `Demo@12345`): `admin@demo`, `staff@demo`, `customer@demo`.
Use `WHATSAPP_PROVIDER=twilio` with the demo phone joined to the sandbox, or `console` and show the notification log.
_Data below is the intended seed; adjust if `seed_demo.py` differs and update this file._

## S1 — Sign-up & roles (3 min)
1. `/signup`: email `new@demo.com`, password `weakpass` → rejected (needs upper, lower, special, > 8). Use `Strong@Pass1` → created as customer; WhatsApp opt-in ticked.
2. Sign up again with `NEW@demo.com` → "An account with this email already exists." (case-insensitive).
3. Forgot password → open console/email → link → set `Another@Pass2` → log in.
4. Log in as admin → **Staff** page → create `ops@demo.com` (staff). Log in as staff → no Staff menu; `/staff` → 403 page.
5. Customer sees only "My subscriptions / My invoices". **Expected:** different nav per role.

## S2 — New plan (3 min, admin)
1. Catalog → Taxes: `GST 18%` = 18. Payment terms: `Net 15` = 15 days (default).
2. Products → New: `Brightloop CRM`, type software, sales 1000.00, cost 400.00, notes; tax GST 18%; variant `Brand` = `Odoo`, extra price `560.00`.
3. Plans → New: `CRM Monthly`, product above, price 1000.00, **monthly**, min qty 1, available 2026-01-01 → 2027-12-31, flags: auto-close ✔, pause ✔, renew ✔, early close ✔.
4. Log in as staff → Catalog is read-only. **Expected:** unit price with Odoo variant = 1560.00.

## S3 — Quotation → subscription (4 min, staff)
1. Templates → `CRM Starter`: plan `CRM Monthly`, validity 15 days, line CRM × 5 variant Odoo.
2. Subscriptions → New from template, customer `customer@demo`, start 2026-11-01, expiry 2027-10-31, term Net 15. Lines show qty 5 × 1560.00 = 7800.00.
3. Buttons walk Draft → Quotation → Confirmed → Active (timeline logs each). Illegal buttons are absent; try the API → 409.

## S4 — Billing day (4 min)
1. Billing → **Run billing** (as of 2026-11-01): result `created 1, skipped 0, errors 0`.
2. Invoices → open draft: lines, tax 18 %, totals (7800.00 + 1404.00 = 9204.00 with no discount). **Confirm** → number assigned, Odoo badge `synced` (or `skipped`).
3. **Run billing again** → `created 0`. **Send** → email in console. **Print** → print preview → Save as PDF.

## S5 — Discounts (3 min, admin)
1. Discounts → New: `Launch 10%`, percent 10, scope product (CRM), min qty 5, valid 2026-11-01 → 2027-03-31, **usage limit 2**.
2. Run billing as of 2026-12-01 and 2027-01-01 → both invoices show a −780.00 line (total 8283.60). As of 2027-02-01 → no discount line (limit reached).
3. Staff cannot open Discounts (403).

## S6 — Payments (3 min, staff)
1. Open the December invoice (total 8283.60) → **Record payment** 5000.00, UPI, today, note "first part" → status Confirmed, outstanding 3283.60.
2. Try 4000.00 → rejected (exceeds balance). Pay 3283.60 → **Paid**.
3. Invoices → **Overdue** chip: the November invoice (unpaid, past due) shows "N days overdue".

## S7 — Finance view (3 min)
1. Dashboard: active subscriptions, MRR/ARR, revenue collected, outstanding, overdue count/amount; filter by plan and month.
2. Seed-big environment: reload with network tab open → **< 2 s**; run `perf_check` to show timings.

## Notifications (2 min)
Confirm an invoice and record a payment → WhatsApp + email arrive; Notifications page lists them; re-run billing → no duplicates.
