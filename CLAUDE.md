# CLAUDE.md — Brightloop (Subscription Management: React + Django API + Odoo)

Hackathon build, 6 h, phased. Plan = `KICKOFF.md` (phases, acceptance checks, cut-line). Specs live in `docs/`.
Scenes judged: S1 sign-up/roles, S2 plans, S3 quote→subscription, S4 billing, S5 discounts, S6 payments, S7 finance dashboard (<2 s).

## Stack
Python 3.12 (Docker; local venv may be 3.10), Django 5 + DRF + django-filter + pytest-django, PostgreSQL 15.
React 18 + TS + Vite + React Router + TanStack Query + Tailwind + react-hook-form.
Odoo Community 18.0 (XML-RPC) as accounting ledger. Session cookie + CSRF, same origin (D-005).

## Folder map
- `backend/config/` settings, urls, `health.py` (`/api/healthz`)
- `backend/apps/core/{accounts,catalog,subscriptions,billing}/` (person A) and `backend/apps/finance/{discounts,payments,notifications,dashboard}/` (person B)
  — import as `apps.core.<app>` / `apps.finance.<app>`; app labels unchanged. Ownership + workflow: `docs/TEAM.md`
- `backend/integrations/odoo/client.py` — the ONLY place that talks to Odoo (+ `mappers.py`, `sync.py` when built)
- `backend/integrations/whatsapp/` — provider adapters (Phase 7)
- `backend/scripts/` `odoo_smoke.py`, `odoo_bootstrap.py`, `seed_demo.py`, `perf_check.py`
- `frontend/src/{api,auth,components,pages}/` shared kit + auth pages; `frontend/src/features/ops/` (person C) and `features/insight/` (person D),
  each with its own `routes.tsx` (routes + nav). Add screens there, not in `src/routes.tsx` (see `docs/FRONTEND.md`, `docs/TEAM.md`)
- `odoo/config/odoo.conf`, `odoo/addons/`; `docs/` all specs; `docs/DECISIONS.md` decision log

## Commands (no `make` on Windows → use the raw command)
| Task | Command |
|---|---|
| Stack up | `docker compose up -d --build` (`make up`) |
| Backend dev | `cd backend && .venv\Scripts\python manage.py runserver` (venv: `python -m venv .venv && pip install -r requirements.txt`) |
| Frontend dev | `cd frontend && npm run dev` (:5173, proxies `/api` → :8000) |
| Migrate | `python manage.py migrate` |
| Tests | `cd backend && .venv\Scripts\python -m pytest -q` |
| Seed / big seed | `python scripts/seed_demo.py [--big]` |
| Billing / reminders | `python manage.py run_billing` / `run_notifications` / `sync_odoo` |
| Perf gate | `python scripts/perf_check.py` (fails if any call > 1.0 s) |
| Odoo init + smoke | `make odoo-init` or `python scripts/odoo_smoke.py` |
| Prod build | `docker compose build web` (node build → python runtime, serves SPA) |

## Conventions
- **Money**: `Decimal` quantized to 2 dp in backend; API sends **strings**; React formats only, never `float` math.
- **Authz in the queryset layer**: `get_queryset` → `Model.objects.for_user(request.user)`; roles in DRF permission classes
  (`IsAdmin`, `IsStaffOrAdmin`, `IsCustomer`). A customer gets **404** for another customer's ids. React hiding is cosmetic.
- **No N+1**: every list is paginated (25), filterable, uses `select_related`/`prefetch_related`.
- **Odoo**: never guess model/field names — `fields_get` on the running instance first. All calls via `client.py`.
  App must run with `ODOO_ENABLED=false` (`odoo_sync_status='skipped'`); Odoo failure never rolls back a local write.
- **Billing**: UNIQUE (subscription, period_start) + `select_for_update(skip_locked)`; catch-up ≤ 12 periods; never past expiry.
- **Notifications**: always through `notify()`; UNIQUE `dedupe_key`; sending never fails the originating request.
- **UI**: config objects feeding `DataTable`, `ResourceForm`, `StatusBadge`, `ConfirmButton`, `RoleGuard`, `MoneyText`. No bespoke pages.
- **Roles**: `admin | staff | customer` on `User.role`. Public signup creates customers only.

## Working rules (condensed from KICKOFF §0)
1. Phase by phase; don't start N+1 until N's acceptance checks pass (run them, show output).
2. API first: write the phase's endpoints into `docs/API.md` before coding.
3. After each phase: tick `TASKS.md`, commit `phase N: <summary>`, print a 5-line status (done / broken / next).
4. Don't ask unless blocked; decide and log in `docs/DECISIONS.md`.
5. Cut honestly: record in `TASKS.md ## Cut`; working end-to-end beats complete-but-broken. Cut order: KICKOFF §9.
6. Tests: pytest for the mandatory tests per phase; frontend verified via `docs/TEST_PLAN.md` manual checklist.

## Logging a decision
Append a row to `docs/DECISIONS.md`: next free `D-0NN`, one-line decision, reason, date. Don't edit past rows; supersede them.

## Never cut
Auth + roles, billing idempotency, invoice+tax, payments → Paid, discount auto-apply with limits, dashboard KPIs, row-level access, perf check.
