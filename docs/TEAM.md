# Team split — 4 people, 2 backend folders, 2 frontend folders

One Django project, one Vite app, one container. The split is by folder ownership, so four people can work in parallel with few merge conflicts.
(Why not two separate services? They would need their own DB access, auth and deploy; the whole app must run as a single container — D-005.)

| Person | Side | Owns | Phases |
|---|---|---|---|
| **A** | backend | `backend/apps/core/` — `accounts` ✔, `catalog` ✔, `subscriptions`, `billing` (engine, invoices); invoice side of `integrations/odoo/` | 3, 4 |
| **B** | backend | `backend/apps/finance/` — `discounts`, `payments`, `dashboard`, `notifications`; `scripts/seed_demo.py --big`, `scripts/perf_check.py` | 5, 6, 8, 7 |
| **C** | frontend | `frontend/src/features/ops/` — catalog ✔, staff ✔, subscriptions, invoices, print view, Run billing, record payment | 3, 4, 6 |
| **D** | frontend | `frontend/src/features/insight/` — home ✔, dashboard, customer portal, discounts, notification screens | 5, 7, 8 |

Pairs: A↔C, B↔D. A is the critical path (billing engine); B and D depend on A's models, so A lands the `Subscription`, `Invoice`, `InvoiceLine` and `Payment`
models + migrations as one small PR in the first hour.

## Layout
```
backend/apps/core/      accounts catalog subscriptions billing        (A)
backend/apps/finance/   discounts payments notifications dashboard    (B)
frontend/src/features/ops/       *.tsx + routes.tsx                   (C)
frontend/src/features/insight/   *.tsx + routes.tsx                   (D)
frontend/src/{api,auth,components,pages}/   shared kit + auth pages   (everyone, small careful changes)
```
Django app **labels** are unchanged (`accounts`, `catalog`, …), so migrations, table names and `AUTH_USER_MODEL = "accounts.User"` are unaffected by the folders.
Import with the full path: `from apps.core.catalog.models import Plan`, `from apps.finance.payments.models import Payment`.

## How a feature plugs into the frontend
Each feature folder exports two things, so nobody edits `routes.tsx` or `Layout.tsx`:
- `opsRoutes()` / `insightRoutes()` — a function returning keyed `<Route>` elements, spread into `<Routes>` in `src/routes.tsx`.
- `opsNav` / `insightNav` — `NavItem[]` merged by `components/Layout.tsx` (a role only sees items listing its role).

To add a screen: create the page in your folder, add one `<Route>` to your `routes.tsx` and one entry to your nav list. Use the shared kit
(`CrudPage`, `DataTable`, `ResourceForm`, `StatusBadge`, `MoneyText`, `ConfirmButton`, `RoleGuard`) — config objects, not bespoke pages.

## Shared files — edit rarely, keep it to a line or two, rebase often
`backend/config/settings.py` (INSTALLED_APPS is already complete), `backend/config/urls.py` (add one `include(...)` per app),
`frontend/src/components/*`, `frontend/src/api/*`, `docs/API.md`, `docs/DECISIONS.md`, `TASKS.md`.
Put your phase's endpoints in your own section of `docs/API.md` **before** coding (project rule 2). Next free decision id: check the bottom of `docs/DECISIONS.md` and pull first.

## Workflow
1. Branch from `main`: `a/billing`, `b/payments`, `c/subscriptions-ui`, `d/dashboard-ui`.
2. Before a PR: `cd backend && python -m pytest -q` and `cd frontend && npm run build` must pass.
3. PR into `main`, one approval, squash or rebase. Small PRs; touch another person's folder only by agreement.
4. API contract first, then UI against it — C and D can build with the contract while A and B are still implementing.

## Known blocker
Docker Desktop's engine did not start on the first dev laptop (D-030), so Odoo is unverified. Whoever has working Docker owns `make odoo-init` and
verifying `integrations/odoo/mappers.py` against `fields_get`.
