# TASKS

Tick as acceptance checks pass. Cut-line order: KICKOFF §9.

## Phase 0 — Bootstrap (0:00–0:30)
- [x] All md files in KICKOFF §3 created with real content
- [x] Django + DRF project, 8 app packages, `accounts.User` model + migration (D-026)
- [x] Vite React TS app with Tailwind, Router, TanStack Query; `api/client.ts` with CSRF + `credentials: 'include'`; `/api` proxy
- [x] Multi-stage Dockerfile, compose, Makefile, `.env.example`, `odoo.conf`
- [x] `/api/healthz` reports app DB + Odoo status; React landing page renders it
- [x] Backend health test passes; frontend `npm run build` passes
- [ ] `docker compose up` works — **blocked: Docker Desktop engine did not start on this laptop (D-030); compose file is untested**
- [x] Odoo initialised + smoke test (auth, `search_read`, create+delete partner): passed 2026-10-31 on a native Odoo 18 (db `odoo_brightloop`), see docs/ODOO_INTEGRATION.md "Live verification" and D-045
- [ ] First commit (repo is not yet a git repo)

## Phase 1 — Auth, roles, shell (0:30–1:15) [S1]
- [x] API: csrf, signup, login, logout, me (GET/PATCH), password-reset request/confirm, staff create/list
- [x] Password validator (≥ 9, upper, lower, special) on signup/reset/staff creation
- [x] `IsAdmin`, `IsStaffOrAdmin`, `IsCustomer`; `for_user()` scoped manager (`apps/accounts/scoping.py`)
- [x] React: Login, Signup (+ optional WhatsApp number & opt-in), Forgot/Reset, Profile, AuthProvider, RoleGuard, Layout, Staff page
- [x] Shared kit: DataTable, ResourceForm, StatusBadge, MoneyText, ConfirmButton, RoleGuard, Layout
- [x] Seed `admin@demo`, `staff@demo`, `customer@demo` (`python scripts/seed_demo.py`, pw `Demo@12345`)
- [x] Tests (33 passing): password table incl. exactly 8 chars, duplicate email other case, reset token (valid/garbage/reused), CSRF enforced, staff-creation 403 for staff/customer/anon, role matrix, `for_user` scoping
- [x] Acceptance, checked in the browser against the built SPA: admin/staff/customer log in and see different nav (Staff link only for admin; Home label per role); staff and customer opening `/staff` land on the 403 page; weak/duplicate signup rejected; admin created `ops@demo.com`; reset link printed in server console, worked once, second use rejected

## Phase 2 — Catalog and plans (1:15–1:55) [S2]
- [x] Product (+nested variants), Tax, PaymentTerm, Plan ViewSets; writes admin-only, reads staff+admin (`ReadOnlyOrAdmin`)
- [x] Config-driven CRUD pages: one `CrudPage` + a config object per screen (`pages/Catalog.tsx`); `ResourceForm` gained `lines`, `multiselect`, `money`, options-from-endpoint
- [x] Odoo mirror for Tax/Product after commit (`integrations/odoo/{mappers,sync}.py`); `skipped|pending|synced|error`, `sync_pending()` retry; failure never blocks a save
- [x] Tests (37 new, 70 total passing): variant +560 → 1560.00, plan price + variant, date/min-qty/period/price validation, duplicate variants, variant replace-by-id, single default payment term, 409 on deleting an in-use product, permission matrix on all 4 endpoints, pagination/filter/search, query-count guards, Odoo mocked success / down→`pending` / rejected→`error` / disabled→`skipped` / retry
- [x] Acceptance, in the browser: admin created GST 18%, product "Brightloop CRM" (tax + Brand=Odoo +560.00 → `effective_unit_price` 1560.00) and a monthly plan; an invalid date range showed the server error; staff see the catalog read-only (PATCH → 403); customer gets 403 page / API 403
- [ ] Odoo mirror against a real instance (needs Docker, see Cut) — mappers are unverified

## Phase 3 — Templates and subscriptions (1:55–2:45) [S3]
- [x] QuotationTemplate (+lines); Subscription (+lines); `services.transition()` + StatusLog; `from-template`; `renew`; `activate_due()` (for billing); `/customers/` picker; auto-numbering `SUB-000001` (Counter row lock)
- [x] React (`features/ops`): subscription list with status/plan/search filters, new (from template or scratch with live line totals), detail with server-driven action buttons + status history, Templates screen (`CrudPage`, staff may write)
- [x] Tests (58 new, 128 total passing, 1 skipped): every illegal transition → 409, all guards (no lines, min qty, plan window, expired quotation, start date, plan flags, admin override), pause/resume without back-billing, renew, template prefill, draft-only editing, role matrix, customer sees only own rows (other id → 404), list N+1 guard
- [x] Acceptance, in the browser as staff: template "CRM Starter" → subscription from template (5 × ₹1,560.00 = ₹7,800.00) → Send quotation → Confirm → Activate (history logged, next invoice 2026-10-31); Pause/Resume/Renew work; from-scratch form shows live totals and rejects qty below the plan minimum; customer is refused on every staff screen/endpoint
- [ ] Concurrent numbering test is written but **skipped on sqlite** — run `pytest tests/test_subscriptions.py` against Postgres (needs Docker, see Cut)

## Phase 4 — Billing engine and invoices (2:45–3:50) [S4]
- [x] `apps/core/billing/engine.py` (pure `price_lines` + atomic `bill_subscription` + `run_billing`), `run_billing` command, `POST /billing/run/`, BillingRun list/detail
- [x] Invoice API: list/detail (filters status/customer/subscription/overdue, search, ordering), confirm / cancel / send / print data; `INV-000001` numbering; customers see only their own non-draft invoices
- [x] Odoo (mocked): draft `account.move` after commit, `action_post` on confirm with total comparison, partner/tax push, `sync_odoo` retry — **mappers unverified, no live Odoo yet**
- [x] Notification skeleton (`apps/finance/notifications`): `notify()`, email + WhatsApp-console channels, dedupe key, on_commit dispatch, failure isolation; `INVOICE_READY` wired to confirm and send
- [x] React (`features/ops`): invoices list with Draft/Confirmed/Paid/Overdue/Cancelled chips and days-overdue highlight, detail with Confirm / Send / Cancel / Print and Odoo status, print view (print CSS), Run billing page with result card and history
- [x] Mandatory tests 1–8 plus period maths, discount hook, cursor repair, cap of 12, expiry and auto-close, state/permission matrix, overdue, notification dedupe and retry (215 pass, 2 skipped)
- [x] Acceptance, in the browser: 20 active subscriptions → **20 draft invoices, every total verified to the paisa; rerun → 0 created, 0 errors**; one invoice confirmed → INV-000001 + email; staff Send, print view, customer sees only their own invoice
- [ ] "One confirmed invoice visible in Odoo" — blocked on Docker (see Cut)
- [ ] 2 Postgres-only concurrency tests (`test_concurrent_runs_create_no_duplicates`, concurrent numbering) skipped on sqlite — run against Postgres

## Phase 5 — Discounts (3:50–4:10) [S5]
- [x] Discount CRUD (admin write, staff read), `GET /discounts/{id}/redemptions/`, attach/detach on a subscription (`POST|DELETE /subscriptions/{id}/discount/`, staff + admin); computed `state` (inactive / scheduled / active / expired / exhausted)
- [x] Engine integration through the Phase 4 hook (`apps/finance/discounts/services.py`: `pick_discounts → reserve → record`); one rule per line (largest saving) + one subscription rule; usage counted once per invoice with a single conditional `UPDATE`; rolled back with a failed invoice
- [x] React: Discounts page (`features/insight`, admin writes, staff read-only) with usage `n / limit` linking to a redemptions audit view; attach/detach control on the subscription detail page; discount lines already render on invoice, detail and print view
- [x] Tests (67 new, 282 total passing, 2 skipped): validation table, permission matrix, date window on the billing date, minimums, fixed capped at the line, largest wins / tie → older rule, one use per invoice for several lines, subscription rule stacking + proportional split with different tax rates, **limit 2 across 3 invoices (sequential) and 3 eligible invoices in one run → exactly 2**, last-use race, rollback gives the use back, rerun never double-uses, cancel keeps the use, attach/detach rules
- [x] Acceptance, in the browser: admin created "Launch 10%" (limit 2); December billing of 20 eligible subscriptions → **exactly 2 invoices discounted** (sample = the worked example, total ₹8,283.60); January → 0; the rule shows `2 / 2 Exhausted` and the redemptions page lists both invoices; "Bundle 5%" attached on a subscription applied to that subscription's next invoice only (₹234.00 off ₹4,680.00); staff see the page read-only and get 403 on create
- [ ] Concurrency of `reserve` against real Postgres row locks is covered by a sequential test only; the conditional `UPDATE` is atomic by construction, but run the billing concurrency tests on Postgres too

## Phase 6 — Payments (4:10–4:30) [S6]
- [x] API-first: `docs/API.md` (Phase 6 section) and `docs/DATA_MODEL.md` written before any code; `STATE_MACHINES.md`, `RBAC.md`, `DECISIONS.md` (D-041, D-042) updated after
- [x] `Payment` = one row per attempt, `status` completed / failed / reversed; only `completed` counts toward `amount_paid` (recomputed from the rows under the invoice row lock); failed attempts never touch balances
- [x] Retry: nullable self-FK `retry_of` (DB-unique), `attempt_number = failed_attempts + 1`; configurable `PAYMENT_MAX_ATTEMPTS` (default 3); at the limit the invoice is flagged `payment_needs_attention` and further attempts get 409 `max_attempts_reached` until an admin resets with a reason
- [x] Reversal (admin only, reason required): row kept as `reversed`, balance restored, Paid → Confirmed; append-only `PaymentEvent` audit trail; payments are never edited or deleted (405)
- [x] API: `POST|GET /invoices/{id}/payments/`, `POST /payments/{id}/retry|reverse/`, `POST /invoices/{id}/reset-payment-attempts/`, `GET /payments/`, filters incl. `needs_attention`; customers see own payments with a reduced field set and never the attention flag
- [x] React (`features/ops`): payments section on the invoice (attempts n of max, status badges, failure reasons, retry links, reversal info), record / retry / reverse / reset dialogs (new `Modal`), attention banner + badge + list chip, Payments page with filters
- [x] Tests: `tests/test_payments.py` — 51 tests: partial → full exactly at the sum, one-paisa edges, overpayment (also for failed attempts), draft / cancelled / paid refused, failed attempts, attempt numbering, limit + configurable limit + admin reset, retry chain / once-only / DB constraint, reversal + Paid→Confirmed + overdue again, audit trail order, immutability, authorization matrix (customer / staff / admin / anonymous, service layer too), customer scoping + reduced fields, N+1 guard, discount invoice (8283.60) and Odoo-off / Odoo-failing, invariant check over a long random-ish sequence, receipts
- [x] **Concurrency verified on PostgreSQL 16, not sqlite** (6 threaded tests: only one full payment wins, 12 partials never lose an update, no overpayment race, failed attempts never exceed the limit, one reversal, one retry). **Mutation-checked:** with the invoice lock removed the three lock-dependent tests fail (the limit test recorded 9 failed attempts instead of 3), and the reversal test fails once the payment lock is removed too. The partial-payments test cannot fail by design (the balance is recomputed from rows), and the retry test is additionally backed by `UNIQUE(retry_of)`
- [x] Complete backend suite: **PostgreSQL 335 passed / 0 skipped / 0 failed; sqlite 327 passed / 8 skipped** (the 8 are the PostgreSQL-only concurrency tests). Frontend `npm run build` passes
- [x] Acceptance, in the browser (dev DB): overpayment rejected in the dialog; ₹3,000 partial leaves ₹4,363.20; three failed attempts via Retry (chain 1→2→3) leave the balance untouched, raise the banner / badge and hide Record and Retry for staff; staff 4th attempt → 409 and reset → 403; admin reset needs a reason and restores Record; final ₹4,363.20 → Paid; admin reversal needs a reason, restores the balance and flips back to Confirmed with every row kept; Payments page filters (failed 3, reversed 1); customer sees 5 rows with 9 safe fields and no internal flags
- [ ] Odoo payment mirroring: not implemented (KICKOFF §9 cut). `odoo_sync_status` stays `skipped`; nothing calls Odoo and `ODOO_ENABLED=false` works (also tested with Odoo enabled and failing)

## Phase 7 — Notifications (4:30–5:05)
- [x] Adapters: `console` and `twilio` (stdlib HTTP, sandbox-aware status) in `integrations/whatsapp`; `meta` cut (D-043)
- [x] Events wired: `WELCOME`, `QUOTATION_READY`, `SUBSCRIPTION_ACTIVATED` (plus `INVOICE_READY`, `PAYMENT_RECEIVED` from Phases 4/6); reminders `INVOICE_DUE_SOON`, `INVOICE_OVERDUE` (day 1/7), `SUBSCRIPTION_EXPIRING`
- [x] Commands `run_notifications` (also called at the end of `run_billing`) and `send_notifications` (retry sweep, max 3 attempts, backoff 1/5/30 min)
- [x] API: logs (+retry), events, test-send, run-reminders, provider-status, `/me/notifications/`, `/me/notification-settings/`
- [x] React: admin Notifications page (log + retry, event toggles / templates, test send, run reminders, provider banner), "Send via email / WhatsApp" on invoice detail, notification timeline on invoice and subscription detail
- [x] The 8 mandatory tests from `docs/NOTIFICATIONS.md` §9 plus Twilio request shape / error mapping, API permissions, wiring
- [x] Acceptance, console provider: test send, reminders run and Events tab checked in the browser; confirm + payment rows `sent`; reruns of billing and reminders add no rows (tests)
- [ ] Acceptance with `WHATSAPP_PROVIDER=twilio` on a joined phone: **not run** (no Twilio credentials here); the adapter is verified only against a mocked HTTP layer

## Phase 8 — Portal, dashboard, performance (5:05–5:35) [S1/S7]
- [x] API-first: `docs/API.md` Phase 8 written before code; D-044 logged
- [x] Portal (`features/insight`, read-only): My subscriptions (+ new detail page with lines and that subscription's invoices), My invoices → print view, My payments, My notifications. Print view "← Back" now goes to `/my-invoices` for customers (was the staff page → 403, Phase 4 gap)
- [x] **Fixed a routing bug:** the customer Payments route and the staff `/payments` route shared one path, so React Router matched the customer route first and **staff/admin got the 403 page on Payments** in the merged Phase 7 branches. Customer pages now live under `/my-*` (`/my-payments`)
- [x] `GET /dashboard/summary/` (`apps/finance/dashboard`): KPIs (active, MRR, ARR, revenue collected, invoiced, outstanding, overdue count/amount), by plan, by month (zeros included), paginated overdue list sorted by days overdue; filters from/to, customer, plan, subscription status; 15 queries whatever the data size
- [x] React dashboard (`features/insight/Dashboard.tsx`): filter bar (dates, customer type-ahead, plan, status, reset), KPI cards with drill-down links (`/subscriptions?status=active`, `/invoices?status=overdue`), by-plan / by-month tables with CSS bars (Recharts skipped), overdue table with paging; subscription list now reads `?status=&plan=` from the URL
- [x] `seed_demo.py --big`: 500 customers, 5 000 subscriptions, ~16 400 invoices (~1 360 overdue), ~14 300 payments (completed / partial / failed) in ~20 s via `bulk_create`; idempotent (second run skips)
- [x] `perf_check.py` **green on PostgreSQL 16 with the big seed: 34 calls (every list page 1 + last page, filtered lists, details, dashboard ×3, customer portal), slowest 333 ms (dashboard filtered by status), budget 1 000 ms**. No index or N+1 fix was needed; `/notifications/events/` runs a fixed 29 queries (lazy catalog creation), not per row
- [x] Tests: `tests/test_portal_isolation.py` (11) and `tests/test_dashboard.py` (14). Full suite: **PostgreSQL 396 passed / 0 skipped; sqlite 388 passed / 8 skipped** (the PostgreSQL-only concurrency tests). Frontend `npm run build` passes
- [x] Acceptance, in the browser on the big seed (Postgres): dashboard summary request 92–148 ms, plan and customer filters and overdue paging work, KPI cards drill down to filtered lists; admin `/payments` shows the staff list (14 337 rows); customer `big-0001@big.seed` sees 10 own subscriptions, the detail page, print view with Back → My invoices, 32 own payments; `/dashboard` → 403 page; `/my-subscriptions/2` (someone else's) → "not found", API 404
- [ ] Customer self-service pause/close/renew in the portal: not built (KICKOFF §9 cut item 3)

## Phase 9 — Hardening, demo, deploy (5:35–6:00)
- [ ] README + DEMO_SCRIPT final; TASKS honest
- [ ] Error/empty/loading states, 404/403
- [ ] Single container build; `DEBUG=false`; tunnel tested from phone
- [ ] Fresh-DB rehearsal S1–S7 + WhatsApp; manual QA checklist; tag `v1.0`

## Cut
- **Odoo local bring-up (Phase 0)** — Docker Desktop's engine did not come up on the dev laptop (error dialog on startup; needs someone to look at its window). Running with `ODOO_ENABLED=false`. Files ready: `docker-compose.yml`, `odoo/config/odoo.conf`, `Makefile odoo-init`, `backend/scripts/odoo_smoke.py`. Retry on a Docker-capable machine / in Phase 4.

## Bugs
- **Fixed in Phase 6 (found by running the suite on PostgreSQL; hidden by sqlite since Phase 3):** `services.transition()` locked the subscription with `select_for_update()` while joining the optional `template`, which PostgreSQL rejects (`FOR UPDATE cannot be applied to the nullable side of an outer join`). On the real database **every subscription status change returned HTTP 500** (34 tests failed on Postgres, all green on sqlite). PRs #3 and #4 contain the bug. Fixed by locking only the main row (`of=("self",)`) in the five joined locks (also stops billing's `skip_locked` from skipping subscriptions that merely share a plan). The full suite must be run against PostgreSQL before any release (`docs/TEST_PLAN.md`).
- Phase 6 notes: `docs/PRD.md` only defines FR-PAY-01…06, so the status / retry / reversal / attempt-limit rules are tracked in D-041, not as FR-PAY-07…10; the attempt limit counts failed attempts since the last completed payment or admin reset (so several good part-payments never exhaust it); "pay" is offered only while attempts remain.
- Fixed in Phase 4 (found by driving the UI): Django's stock console email backend raises on a Windows cp1252 console when the body contains `₹`, so every invoice email in dev logged `failed` (the confirm still succeeded, as designed). Replaced by `ConsoleEmailBackend` (D-039); the failed row was retried and went out.
- Phase 4 known gaps: on a customer's print page the "← Back" link goes to the staff-only invoice page (403) until the portal exists in Phase 8; `Payment` side of an invoice (`amount_paid`, Paid status) is Phase 6; Odoo cancel mirror is cut; reminders / `run_notifications` after a run are Phase 7.
- Fixed in Phase 3 (found by driving the UI): after a server error on a `lines` field (e.g. the plan's minimum quantity), react-hook-form kept the manually-set error and silently blocked every resubmit. `ResourceForm` and `SubscriptionForm` now `clearErrors()` before each submit. Same pass: `CrudPage` hardcoded admin-only writes, so staff could not manage templates; it now takes `writeRoles`.
- Fixed in Phase 1: `AuthProvider` used `queryClient.clear()` on login, which detached the `["me"]` query and bounced users back to `/login`. Now drops every cache key except `me`.
- Phase 1 notes: staff and customer navs differ only by the Home label until later-phase pages exist; password-reset email still sent directly, moves behind `notify()` in Phase 4; `WELCOME` notification not wired yet (Phase 7).
- Phase 1 UI checks were done by driving the built SPA in the in-app browser; the pane could not draw screenshots, so clicks went through page JS rather than pixel clicks.
=======
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD



=======
=======
>>>>>>> other-repo/phase-5-discounts
=======
- **Fixed in Phase 6 (found by running the suite on PostgreSQL; hidden by sqlite since Phase 3):** `services.transition()` locked the subscription with `select_for_update()` while joining the optional `template`, which PostgreSQL rejects (`FOR UPDATE cannot be applied to the nullable side of an outer join`). On the real database **every subscription status change returned HTTP 500** (34 tests failed on Postgres, all green on sqlite). PRs #3 and #4 contain the bug. Fixed by locking only the main row (`of=("self",)`) in the five joined locks (also stops billing's `skip_locked` from skipping subscriptions that merely share a plan). The full suite must be run against PostgreSQL before any release (`docs/TEST_PLAN.md`).
- Phase 6 notes: `docs/PRD.md` only defines FR-PAY-01…06, so the status / retry / reversal / attempt-limit rules are tracked in D-041, not as FR-PAY-07…10; the attempt limit counts failed attempts since the last completed payment or admin reset (so several good part-payments never exhaust it); "pay" is offered only while attempts remain.
>>>>>>> 6a6a6ed (phase 6: payments (attempt status, retry, reversal, attempt limit, audit trail) + Postgres lock-scope fix)
=======
- **Fixed in Phase 6 (found by running the suite on PostgreSQL; hidden by sqlite since Phase 3):** `services.transition()` locked the subscription with `select_for_update()` while joining the optional `template`, which PostgreSQL rejects (`FOR UPDATE cannot be applied to the nullable side of an outer join`). On the real database **every subscription status change returned HTTP 500** (34 tests failed on Postgres, all green on sqlite). PRs #3 and #4 contain the bug. Fixed by locking only the main row (`of=("self",)`) in the five joined locks (also stops billing's `skip_locked` from skipping subscriptions that merely share a plan). The full suite must be run against PostgreSQL before any release (`docs/TEST_PLAN.md`).
- Phase 6 notes: `docs/PRD.md` only defines FR-PAY-01…06, so the status / retry / reversal / attempt-limit rules are tracked in D-041, not as FR-PAY-07…10; the attempt limit counts failed attempts since the last completed payment or admin reset (so several good part-payments never exhaust it); "pay" is offered only while attempts remain.
>>>>>>> other-repo/phase-8a
=======
- **Fixed in Phase 6 (found by running the suite on PostgreSQL; hidden by sqlite since Phase 3):** `services.transition()` locked the subscription with `select_for_update()` while joining the optional `template`, which PostgreSQL rejects (`FOR UPDATE cannot be applied to the nullable side of an outer join`). On the real database **every subscription status change returned HTTP 500** (34 tests failed on Postgres, all green on sqlite). PRs #3 and #4 contain the bug. Fixed by locking only the main row (`of=("self",)`) in the five joined locks (also stops billing's `skip_locked` from skipping subscriptions that merely share a plan). The full suite must be run against PostgreSQL before any release (`docs/TEST_PLAN.md`).
- Phase 6 notes: `docs/PRD.md` only defines FR-PAY-01…06, so the status / retry / reversal / attempt-limit rules are tracked in D-041, not as FR-PAY-07…10; the attempt limit counts failed attempts since the last completed payment or admin reset (so several good part-payments never exhaust it); "pay" is offered only while attempts remain.
>>>>>>> other-repo/phase-8b
- Fixed in Phase 4 (found by driving the UI): Django's stock console email backend raises on a Windows cp1252 console when the body contains `₹`, so every invoice email in dev logged `failed` (the confirm still succeeded, as designed). Replaced by `ConsoleEmailBackend` (D-039); the failed row was retried and went out.
- Phase 4 known gaps: on a customer's print page the "← Back" link goes to the staff-only invoice page (403) until the portal exists in Phase 8; `Payment` side of an invoice (`amount_paid`, Paid status) is Phase 6; Odoo cancel mirror is cut; reminders / `run_notifications` after a run are Phase 7.
- Fixed in Phase 3 (found by driving the UI): after a server error on a `lines` field (e.g. the plan's minimum quantity), react-hook-form kept the manually-set error and silently blocked every resubmit. `ResourceForm` and `SubscriptionForm` now `clearErrors()` before each submit. Same pass: `CrudPage` hardcoded admin-only writes, so staff could not manage templates; it now takes `writeRoles`.
- Fixed in Phase 1: `AuthProvider` used `queryClient.clear()` on login, which detached the `["me"]` query and bounced users back to `/login`. Now drops every cache key except `me`.
- Phase 1 notes: staff and customer navs differ only by the Home label until later-phase pages exist; password-reset email still sent directly, moves behind `notify()` in Phase 4; `WELCOME` notification not wired yet (Phase 7).
- Phase 1 UI checks were done by driving the built SPA in the in-app browser; the pane could not draw screenshots, so clicks went through page JS rather than pixel clicks.
<<<<<<< HEAD

=======
>>>>>>> other-repo/phase-5-discounts
>>>>>>> recovery-old-main
