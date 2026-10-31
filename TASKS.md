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
- [ ] Odoo initialised + smoke test (auth, `search_read`, create+delete partner) — see `## Cut`
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
- [ ] Discount CRUD (admin), attach/detach, redemptions list
- [ ] React Discounts page, attach control, discount lines on invoice/print
- [ ] Tests incl. limit 2 with 3 eligible → exactly 2
- [ ] Acceptance: 10 % limit-2 rule hits next two invoices, not the third

## Phase 6 — Payments (4:10–4:30) [S6]
- [ ] `POST /invoices/{id}/payments/`, payments list
- [ ] React record-payment modal, payments page, Paid/Outstanding/Overdue chips
- [ ] Tests: partial→full, overpayment rejected, draft/cancelled rejected, overdue rule
- [ ] Acceptance: partial shows balance; final flips to Paid

## Phase 7 — Notifications (4:30–5:05)
- [ ] `console` + `twilio` adapters; event catalog; `run_notifications`; `send_notifications` retry
- [ ] API + React settings/admin pages
- [ ] 8 mandatory tests from `docs/NOTIFICATIONS.md` §9
- [ ] Acceptance: confirm invoice + record payment each deliver; reruns send no duplicates

## Phase 8 — Portal, dashboard, performance (5:05–5:35) [S1/S7]
- [ ] Portal (my subscriptions / invoices, read-only)
- [ ] `GET /dashboard/summary/` + React dashboard
- [ ] `seed_demo.py --big`, `perf_check.py` green (< 1.0 s per call)
- [ ] Tests: cross-customer 404s; dashboard = hand-computed values

## Phase 9 — Hardening, demo, deploy (5:35–6:00)
- [ ] README + DEMO_SCRIPT final; TASKS honest
- [ ] Error/empty/loading states, 404/403
- [ ] Single container build; `DEBUG=false`; tunnel tested from phone
- [ ] Fresh-DB rehearsal S1–S7 + WhatsApp; manual QA checklist; tag `v1.0`

## Cut
- **Odoo local bring-up (Phase 0)** — Docker Desktop's engine did not come up on the dev laptop (error dialog on startup; needs someone to look at its window). Running with `ODOO_ENABLED=false`. Files ready: `docker-compose.yml`, `odoo/config/odoo.conf`, `Makefile odoo-init`, `backend/scripts/odoo_smoke.py`. Retry on a Docker-capable machine / in Phase 4.

## Bugs
- Fixed in Phase 4 (found by driving the UI): Django's stock console email backend raises on a Windows cp1252 console when the body contains `₹`, so every invoice email in dev logged `failed` (the confirm still succeeded, as designed). Replaced by `ConsoleEmailBackend` (D-039); the failed row was retried and went out.
- Phase 4 known gaps: on a customer's print page the "← Back" link goes to the staff-only invoice page (403) until the portal exists in Phase 8; `Payment` side of an invoice (`amount_paid`, Paid status) is Phase 6; Odoo cancel mirror is cut; reminders / `run_notifications` after a run are Phase 7.
- Fixed in Phase 3 (found by driving the UI): after a server error on a `lines` field (e.g. the plan's minimum quantity), react-hook-form kept the manually-set error and silently blocked every resubmit. `ResourceForm` and `SubscriptionForm` now `clearErrors()` before each submit. Same pass: `CrudPage` hardcoded admin-only writes, so staff could not manage templates; it now takes `writeRoles`.
- Fixed in Phase 1: `AuthProvider` used `queryClient.clear()` on login, which detached the `["me"]` query and bounced users back to `/login`. Now drops every cache key except `me`.
- Phase 1 notes: staff and customer navs differ only by the Home label until later-phase pages exist; password-reset email still sent directly, moves behind `notify()` in Phase 4; `WELCOME` notification not wired yet (Phase 7).
- Phase 1 UI checks were done by driving the built SPA in the in-app browser; the pane could not draw screenshots, so clicks went through page JS rather than pixel clicks.
