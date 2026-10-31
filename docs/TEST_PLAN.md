# Test plan

Backend: `pytest-django` (`cd backend && python -m pytest -q`). Billing concurrency and `skip_locked` tests need **Postgres** (D-029).
Frontend: no unit tests (rule 12) — manual checklist below, run in Phase 9.

## Backend tests by phase
| Phase | Tests |
|---|---|
| 0 | `test_health`: `/api/healthz` with Odoo disabled → `ok` |
| 1 | Password table: valid + 6 invalid (no upper, no lower, no special, 8 chars exactly, empty, too common) · duplicate email in another case · reset token valid/expired/reused · staff creation 403 for staff & customer · role × endpoint matrix |
| 2 | Variant +560 → `effective_unit_price` · plan date validation (`from ≤ to`, `min_quantity ≥ 1`) · write permissions · Odoo mocked: success → `synced`, failure → `pending`, disabled → `skipped` |
| 3 | Legal and illegal transitions · min-quantity · concurrent numbering (unique `SUB-…`) · template prefill |
| 4 | **(1)** run twice → no new invoices · **(2)** concurrent runs → no duplicates · **(3)** catch-up creates each missed period · **(4)** nothing beyond expiry; auto-close only with flag · **(5)** paused/draft/closed skipped · **(6)** worked example = 8283.60 · **(7)** one failing sub doesn't stop the run · **(8)** Odoo down → local invoice `pending` |
| 5 | percent/fixed · min qty / min purchase unmet · before start / after end · limit 2 with 3 eligible → exactly 2 · scope product vs subscription · race-safe counter · staff create 403 |
| 6 | partial then full → Paid exactly at the sum · overpayment rejected · draft/cancelled rejected · overdue rule (D-013) · denormalized totals equal recomputation |
| 7 | The 8 tests in `NOTIFICATIONS.md` §9 (`tests/test_notifications.py`, `tests/test_notifications_phase7.py`) · Twilio request shape and error mapping (HTTP mocked) · retry sweep · log / events / test-send / reminders permissions · timeline scope for staff |
| 8 | Customer A → B's subscription/invoice/payment → 404 · dashboard numbers equal hand-computed fixture |
=======
| 8 | `tests/test_portal_isolation.py`: customer A → B's subscription / invoice / print / invoice payments / payment → 404 (same as a missing id), lists and filters leak nothing, customer actions 403 before any lookup · `tests/test_dashboard.py`: KPIs, by-plan, by-month and overdue order equal a hand-computed fixture; customer / plan / status / date filters; failed, reversed, draft and cancelled rows never count; bad filters 400; customer and anonymous 403; query count independent of row count |

## Run the suite on PostgreSQL (required before a release; D-042)
sqlite silently ignores `FOR UPDATE`, so it can neither verify concurrency nor catch Postgres-only errors (a nullable-join lock bug hid behind it from Phase 3 to Phase 6).
```
cd backend
DATABASE_URL=postgres://<user>@localhost:5432/<anydb> python -m pytest -q      # pytest-django creates and drops test_<anydb>
```
Expected: 0 skipped. With sqlite the PostgreSQL-only tests (billing runs, subscription numbering, payment races) show as **skipped**, never as passed. Phase 6 added a mutation check: temporarily remove `select_for_update` from `payments/services.py::_lock_invoice` and the lock-dependent concurrency tests must fail.
>>>>>>> other-repo/phase-8b

## Run the suite on PostgreSQL (required before a release; D-042)
sqlite silently ignores `FOR UPDATE`, so it can neither verify concurrency nor catch Postgres-only errors (a nullable-join lock bug hid behind it from Phase 3 to Phase 6).
```
cd backend
DATABASE_URL=postgres://<user>@localhost:5432/<anydb> python -m pytest -q      # pytest-django creates and drops test_<anydb>
```
Expected: 0 skipped. With sqlite the PostgreSQL-only tests (billing runs, subscription numbering, payment races) show as **skipped**, never as passed. Phase 6 added a mutation check: temporarily remove `select_for_update` from `payments/services.py::_lock_invoice` and the lock-dependent concurrency tests must fail.

## Run the suite on PostgreSQL (required before a release; D-042)
sqlite silently ignores `FOR UPDATE`, so it can neither verify concurrency nor catch Postgres-only errors (a nullable-join lock bug hid behind it from Phase 3 to Phase 6).
```
cd backend
DATABASE_URL=postgres://<user>@localhost:5432/<anydb> python -m pytest -q      # pytest-django creates and drops test_<anydb>
```
Expected: 0 skipped. With sqlite the PostgreSQL-only tests (billing runs, subscription numbering, payment races) show as **skipped**, never as passed. Phase 6 added a mutation check: temporarily remove `select_for_update` from `payments/services.py::_lock_invoice` and the lock-dependent concurrency tests must fail.

## Performance method (Phase 8)
`python scripts/seed_demo.py --big` → ~5k subs, ~15k invoices, ~10k payments (`bulk_create`).
`python scripts/perf_check.py` logs in as admin, calls every list endpoint (page 1 and a deep page) and `/dashboard/summary/`,
prints `endpoint · ms · query count`, **exits non-zero if any call > 1.0 s**. Fix with indexes, `select_related`, aggregates, denormalized `amount_due`.
Browser check: Network tab, dashboard < 2 s on a cold load.

## Manual QA checklist (Phase 9)
- [ ] Fresh DB → `seed` → three demo logins work; each role sees different navigation
- [ ] Signup rejects weak passwords & duplicate email (any case); reset link appears in console and works once
- [ ] Customer cannot open `/staff`, `/dashboard`, other customers' ids (typed in URL) → 403/404 page
- [ ] Catalog: product with Brand variant (+560), monthly plan; non-admin has no edit controls and API refuses
- [ ] Template → subscription → Quotation → Confirmed → Active; illegal buttons hidden; direct API call returns 409
- [ ] Run billing → invoices; run again → 0 new; confirm → number assigned; print view saves as PDF
- [ ] Discount 10 %, limit 2: appears on next two invoices, not the third; negative line visible
- [ ] Partial payment shows balance; final payment → Paid; overdue chip highlights days overdue
- [ ] Dashboard KPIs match Payments/Invoices pages; filters work; loads < 2 s on big seed
- [ ] Notification log shows sent rows; reruns don't duplicate; WhatsApp on phone (Twilio sandbox, joined)
- [ ] Odoo (if enabled): confirmed invoice visible in Odoo UI with correct lines/tax/total
- [ ] Mobile width: nav usable, tables scroll; tunnel URL works on mobile data
