# Billing engine

Code: `backend/apps/billing/engine.py` (pure `build_invoice` + transaction wrapper). Entry points: `manage.py run_billing [--as-of YYYY-MM-DD]`,
`POST /api/billing/run/`. Never bills twice, never skips a period.

## Algorithm
```
run_billing(as_of=today, triggered_by):
  run = BillingRun.create(as_of_date=as_of, ...)
  activate_due(as_of)                       # confirmed & start_date <= as_of -> active
  ids = Subscription.filter(status=active, next_invoice_date <= as_of).order_by(next_invoice_date).values_list(id)
  for id in ids:
     try: bill_subscription(id, as_of, run)
     except Exception: run.error_count += 1; run.log += trace; continue     # isolation per subscription
  run.finished_at = now; run.save()
  run_notifications()                       # reminders, deduped

bill_subscription(id, as_of, run):
  repeat up to 12 times:                    # D-015 catch-up cap per run
    with transaction.atomic():
      sub = Subscription.select_for_update(skip_locked=True).filter(id=id).first()
      if sub is None: return                # another worker holds it
      if sub.status != active or sub.next_invoice_date > as_of: return
      if sub.expiry_date and sub.next_invoice_date > sub.expiry_date:
          close_if_auto(sub); return        # nothing left to bill
      start = sub.next_invoice_date
      end   = add_period(start, plan.billing_period) - 1 day
      if Invoice.exists(subscription=sub, period_start=start):
          sub.next_invoice_date = end + 1 day; sub.save(); run.skipped_count += 1; continue
      invoice = build_invoice(sub, start, end)      # inserts invoice + lines + redemptions
      sub.next_invoice_date = end + 1 day; sub.save(); run.created_count += 1
    transaction.on_commit(odoo_sync.create_draft_invoice(invoice))   # failure -> 'pending'
```
`add_period`: daily +1 d, weekly +7 d, monthly `relativedelta(months=1)` (anchored to the original start day to avoid drift: 31 Jan → 28/29 Feb → 31 Mar),
yearly +1 y. The last period is never truncated; billing stops when `next_invoice_date > expiry_date`.

## Idempotency keys (belt and braces)
1. `UNIQUE(subscription, period_start)` on Invoice — last safety net, even across crashes/concurrent runs.
2. `next_invoice_date` cursor advanced in the **same transaction** as the invoice insert.
3. `select_for_update(skip_locked=True)` — concurrent runs skip locked rows instead of waiting/duplicating.
4. Pre-check `Invoice.exists` repairs a cursor that is behind (skip, advance, count as skipped).
5. Notification `dedupe_key` — reruns never re-notify.

## build_invoice order
1. Snapshot each subscription line → `InvoiceLine(kind=product)` (qty, unit_price, tax rate snapshot).
2. Line-level product discounts: eligible active rules (scope=product, dates, min qty, min purchase, `used_count < limit`);
   pick largest saving; percent on line subtotal, fixed capped at line subtotal; emit a negative `discount` line (D-010).
3. Subscription-level discount (attached rule) on the subtotal after step 2.
4. Tax on post-discount amounts; a discount line carries the tax rate of the line it reduces.
5. Totals; `amount_paid=0`, `amount_due=total`; due_date = invoice_date + payment_term.days.
6. Redemption: `UPDATE discounts_discount SET used_count = used_count + 1 WHERE id=%s AND (usage_limit IS NULL OR used_count < usage_limit)`.
   0 rows updated → drop that discount from this invoice and recompute; else insert `DiscountRedemption`.

All money math uses `Decimal`, quantized with `ROUND_HALF_UP` at line level; totals are sums of rounded line values.

## Worked example (use as test 6)
Plan 1000/month, qty 5, variant +560 → unit 1560.00, line subtotal 7800.00.
10 % product discount → −780.00 → 7020.00. 18 % tax on 7020.00 = 1263.60. **Total 8283.60.**

## Catch-up example
Monthly sub, start 2026-01-01, `next_invoice_date` 2026-01-01, run on 2026-04-15 → invoices for Jan, Feb, Mar, Apr (4 periods),
cursor ends at 2026-05-01. Second run the same day → 0 created. Expiry 2026-03-31 → only Jan–Mar; then `auto_close` closes it if the flag is set.

## Odoo
After commit only; never inside the billing transaction. Confirm (separate action) posts it. Details: `ODOO_INTEGRATION.md`.

## As built (Phase 4) — where the code differs from the sketch above
Code: `backend/apps/core/billing/engine.py` (`price_lines` pure math, `build_invoice`, `bill_subscription`, `run_billing`), `services.py` (confirm / cancel / send), `discount_hooks.py`. Decisions: D-037.
- **Which subscriptions:** `status = active` and (`next_invoice_date <= as_of` **or** `expiry_date < as_of`), ordered by cursor, so `auto_close` also fires when nothing is left to bill. Each subscription runs in its own `try/except`; a run keeps counters in a `BillingRun` row (`created / skipped / errors`, plus a `log` of failures).
- **Dates:** `invoice_date = as_of` (the run date), `due_date = invoice_date + payment_term.days`, `period_start/end` = the service period. Monthly/yearly arithmetic is anchored on the subscription's start day: 31 Jan → 28 Feb → 31 Mar.
- **Expiry:** a period that *starts* on or before `expiry_date` is billed in full; once the cursor is past expiry nothing more is billed, and the subscription closes if `plan.auto_close` and the expiry date has passed.
- **Failure isolation:** every catch-up period is its own transaction, so a failure on period 3 keeps periods 1–2 and the cursor stays where it stopped; the next run continues from there. A subscription with no lines raises and shows up in the run's `log`.
- **Cursor repair:** if an invoice for `(subscription, period_start)` already exists (a crash, or a cancelled invoice), the cursor is advanced and the period counted as `skipped`; cancelled periods are never re-billed (D-019).
- **Tax:** `tax_rate` of a line is the sum of its taxes; tax is computed per line on the post-discount amount, rounded half-up; invoice totals are sums of rounded line values. Worked example (tested): 5 × 1560.00 = 7800.00, discount −780.00, tax 1263.60, **total 8283.60** (9204.00 without the discount).
- **Discounts (Phase 5, D-040):** `build_invoice` calls `discount_hooks.pick_discounts(sub, lines, start, end, as_of) → reserve → record` inside the billing transaction; the implementation is `apps/finance/discounts/services.py`. `pick` takes active rules inside their window with uses left: product rules per line (largest saving, ties → older rule), then the attached subscription rule on the post-line-discount subtotal, split across lines by value so each share is taxed at its line's rate. `reserve` is one conditional `UPDATE … WHERE used_count < usage_limit` per distinct rule (a loser is dropped from the invoice); `record` writes one `DiscountRedemption` per rule. Because they run in the billing transaction, a failed invoice also rolls back its use. Engine tests still use a stub with the same three functions; `tests/test_discounts.py` uses the real ones.
- **Mandatory tests** (`tests/test_billing_engine.py`): 1 run twice → nothing new · 2 interrupted/concurrent runs (cursor repair + UNIQUE constraint on sqlite; the threaded version runs on Postgres) · 3 catch-up (4 months; cap of 12 per run) · 4 expiry and `auto_close` only with the flag · 5 draft / quotation / confirmed-future / paused / closed skipped · 6 worked example · 7 one failing subscription (and a failure in a later period) · 8 Odoo down → local invoice `pending`.
