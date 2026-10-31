# Frontend

React 18 + TS + Vite + React Router + TanStack Query + Tailwind + react-hook-form. Dev `npm run dev` (:5173, `/api` proxied to :8000).
Prod: `npm run build` → `dist/` served by Django (D-005).

## Route map (grows per phase)
| Path | Role | Page | Phase |
|---|---|---|---|
| `*` (temporary) | any | Landing (health status) | 0 |
| `/login`, `/signup`, `/forgot-password`, `/reset-password/:uid/:token` | anon | Auth pages | 1 |
| `/staff` | admin | Staff management | 1 |
| `/catalog` → `/catalog/products`, `/catalog/plans`, `/catalog/taxes`, `/catalog/terms` | staff (read-only) + admin | Config-driven CRUD via `CrudPage` + config in `pages/Catalog.tsx` | 2 |
| `/templates`, `/subscriptions`, `/subscriptions/new`, `/subscriptions/:id` | staff+admin | Lists/forms/detail | 3 |
| `/invoices`, `/invoices/:id`, `/invoices/:id/print`, `/billing` | staff+admin | Invoices, print view, Run billing | 4 |
| `/discounts`, `/discounts/:id/redemptions` | admin writes, staff read-only | Discounts (`CrudPage` config) + redemptions audit; the attach control lives on `/subscriptions/:id` | 5 |
| `/payments` | staff+admin | Payments list | 6 |
| `/notifications` | admin | Message log, events and templates, test send, run reminders | 7 |
| `/dashboard` | staff+admin | KPIs, summaries, overdue | 8 |
| `/portal`, `/portal/subscriptions`, `/portal/invoices/:id`, `/portal/settings` | customer | Self-service (read-only) | 8 |
| `/403`, `*` | any | Forbidden / Not found | 9 |

## Folder ownership
`src/features/ops/` (catalog, staff, later subscriptions/invoices/billing/payments) and `src/features/insight/` (home, later dashboard/portal/discounts/notifications)
each export `<name>Routes()` (keyed `<Route>` elements) and `<name>Nav` (`NavItem[]`); `src/routes.tsx` and `components/Layout.tsx` only merge them. See `docs/TEAM.md`.
Paths in the route map below are URLs; the files live in the owning feature folder.

## Shared kit (`src/components/`) — new CRUD screens are config, not components
| Component | Props (summary) |
|---|---|
| `DataTable<T>` | `columns:[{key,header,render?,sortable?}]`, `queryKey`, `endpoint`, `filters?:[{key,label,type,options?}]`, `rowActions?`, `onRowClick?` — server pagination (`?page`), filters → query string |
| `ResourceForm` | `fields:[{name,label,type: text|number|money|date|select|checkbox|textarea|lines,...,validate?}]`, `defaultValues`, `onSubmit`; maps DRF field errors onto inputs (react-hook-form) |
| `StatusBadge` | `status`, `kind: subscription|invoice|sync|notification` → colour map |
| `MoneyText` | `value: string` → `₹1,23,456.00` via `Intl.NumberFormat('en-IN')`, **display only** |
| `ConfirmButton` | `onConfirm`, `label`, `confirmText`, `danger?` — two-step click |
| `RoleGuard` | `allow: Role[]`, `fallback?` — hides/redirects; cosmetic, server enforces |
| `Layout` | role-aware nav, user menu, toast area, `<Outlet/>` |

## API client (`src/api/client.ts`)
`api.get/post/patch/del` → `fetch` with `credentials:'include'`; for non-GET adds `X-CSRFToken` read from the `csrftoken` cookie.
Call `GET /api/auth/csrf/` once on app start so the cookie exists. Non-2xx → throws `ApiError(status, body)`; 401/403 on `me` → logged-out state;
DRF field errors (`{field:[msg]}`) are mapped onto form fields; others → toast. Money stays a string; never `parseFloat` for arithmetic.

## Query keys
`[resource, 'list', params]`, `[resource, 'detail', id]`, `['me']`, `['dashboard', params]`, `['healthz']`.
After a mutation invalidate `[resource]` and any dependent resource (payment → `['invoices']`, `['payments']`, `['dashboard']`).

## Conventions
- Pages are thin: a config object + `DataTable`/`ResourceForm`. A bespoke page needs a reason noted in `TASKS.md`.
- Loading → skeleton/“Loading…”; empty → message + call to action; errors → toast. Print CSS hides `nav` and `.no-print`.
- No frontend unit tests (rule 12): `docs/TEST_PLAN.md` manual checklist instead.
