<div align="center">

# Brightloop

**The billing backbone for companies that earn their money every month.**

Plans, subscriptions, invoices, payments and revenue reporting in one system, with Odoo as the accounting ledger.

`React 18` · `Django 5 + DRF` · `PostgreSQL` · `Odoo 18` · `Firebase Auth`

</div>

---

## The problem

Brightloop Software sells everything on subscription. Behind the scenes it looks like this:

| Today | What goes wrong |
|---|---|
| Subscriptions live in a spreadsheet | Nobody knows who is on which plan |
| Renewals are "remembered by whoever notices first" | Renewals get missed |
| Invoices are typed by hand every month | Invoices go out wrong, or twice, or not at all |
| Payments are matched by scrolling bank statements | Overdue money isn't chased until it's lost |
| Revenue reports are built at quarter end | Nobody can say what the recurring revenue actually is |

## The solution

Brightloop runs the whole life of a subscription business in one place:

**Set up** products, variants, plans, taxes and discounts → **Quote** from templates → **Subscribe** customers with a tracked lifecycle → **Bill** automatically, never twice → **Collect** payments against the right invoice → **See** active subscriptions, revenue, outstanding and overdue on one dashboard.

### What it does

| | |
|---|---|
| **Accounts and roles** | Sign up with Google or email. Strong-password rule, one account per email, reset by email. Admin, staff and customer roles; only the admin adds staff. |
| **Catalog** | Products with cost and sales price, variants with price extras (choose the Odoo brand, +560), plans billed daily, weekly, monthly or yearly, with minimum quantity, availability dates, and per-plan rules for auto-close, early close, pause and renew. |
| **Quote to subscription** | Quotation templates with a validity window. Subscriptions carry a number, customer, plan, dates, payment terms and tax-aware lines, moving Draft → Quotation → Confirmed → Active → Closed. |
| **Billing engine** | One click (or one scheduled command) creates every due invoice with customer, lines, tax and totals filled in. A unique constraint on subscription and period plus row locking means **nothing is billed twice or skipped**, including catch-up after downtime. |
| **Invoices** | Draft → Confirmed → Paid. Confirm, cancel, send by email, print. Taxes come from admin-set rules. |
| **Discounts** | Admin-only rules: fixed or percent, minimum purchase or quantity, start and end dates, usage limit, scoped to products or whole subscriptions. They attach to the next invoice on their own and stop when expired or used up. |
| **Payments** | Method, amount, date and note against an invoice. Partial payments, overpayment rejection, failed-attempt limits, retries, reversals, full audit trail. |
| **Dashboard** | Active subscriptions, revenue collected, outstanding, overdue, monthly trend and recent payments. Real data only, scoped per user. |
| **Notifications** | Email and WhatsApp for invoices, receipts and reminders, de-duplicated, and a send failure never blocks the action that triggered it. |
| **Odoo ledger** | Taxes, products, customers and invoices are mirrored to Odoo (`account.tax`, `product.product`, `res.partner`, `account.move`). If Odoo is down, nothing local is lost and the sync retries. |

## Why it's built the way it is

- **Money is exact.** `Decimal` to 2 dp in the backend, strings over the API, formatting only in React. No float maths on money.
- **Authorization lives in the data layer.** Every queryset goes through `Model.objects.for_user(user)`. A customer asking for another customer's invoice gets a `404`, not a hidden button.
- **Idempotent by construction.** Billing is guarded by a database unique constraint and `select_for_update(skip_locked)`, so a double-clicked button or two workers can't double-bill.
- **Odoo is never a hard dependency.** The app runs with `ODOO_ENABLED=false`; an Odoo failure never rolls back a local write. All Odoo calls go through one client module, and field names are checked with `fields_get` against the live instance.
- **Notifications can't break billing.** Everything goes through one `notify()` with a unique dedupe key.
- **Identity is delegated, access is not.** Firebase proves who you are (Google or email, email verified). The server turns that into a normal Django session; roles and row-level access stay in your database.

## Architecture

```
 React 18 + TS + Vite + Tailwind            Firebase Auth (Google / email)
        │  same origin, session cookie + CSRF           │ ID token
        ▼                                               ▼
 ┌────────────────────────── Django 5 + DRF ──────────────────────────┐
 │ accounts · catalog · subscriptions · billing   (core)              │
 │ discounts · payments · notifications · dashboard   (finance)       │
 │ for_user() scoping · DRF role permissions · billing engine         │
 └───────┬────────────────────────────────────┬───────────────────────┘
         │ PostgreSQL (Neon in prod)          │ XML-RPC, one client module
         ▼                                    ▼
   app database                       Odoo 18 Community (accounting ledger)
                                      Email / WhatsApp (Twilio or Meta) for notifications
```

The browser always sees one origin: locally the Vite proxy (or one Docker container), in production a Vercel rewrite to the API.

## Quick start

**Local, no Docker** (SQLite fallback if `DATABASE_URL` is unset; use Postgres for the billing concurrency tests):

```bash
cp .env.example .env                      # set ODOO_ENABLED=false to run without Odoo
cd backend && python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python scripts/seed_demo.py     # demo catalog, customers, invoices, payments
.venv\Scripts\python manage.py runserver
# second terminal
cd frontend && npm install && npm run dev     # http://localhost:5173, proxies /api to :8000
```

**Docker:**

```bash
cp .env.example .env
docker compose up -d --build              # web :8000, odoo :8069, postgres x2
make odoo-init                            # one-time Odoo database + smoke test
```

Local password login stays on in development (`LOCAL_PASSWORD_AUTH=true`) so the seeded demo users work; demo logins are listed in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). To try Google sign-in locally, add the Firebase values from [frontend/.env.example](frontend/.env.example).

## Deploy

Vercel (React app, [`frontend/vercel.json`](frontend/vercel.json)) + Render (Django API, [`render.yaml`](render.yaml)) + Neon (Postgres) + Firebase (auth). Vercel proxies `/api` to Render, so the browser sees one origin. Step by step: **[docs/DEPLOY.md](docs/DEPLOY.md)**.

## Everyday commands

| Task | Command |
|---|---|
| Tests | `cd backend && python -m pytest -q` |
| Run billing | `python manage.py run_billing` |
| Send reminders | `python manage.py run_notifications` |
| Retry Odoo sync | `python manage.py sync_odoo` |
| Big seed + perf gate | `python scripts/seed_demo.py --big` then `python scripts/perf_check.py` |
| Odoo smoke test | `python scripts/odoo_smoke.py` |

## Status, honestly

- **Tested:** 375 backend tests pass (8 Postgres-only concurrency tests skip on SQLite). Frontend type-checks and builds clean.
- **Odoo:** verified against a native Windows Odoo 18 with Odoo on: 10 invoices mirrored, every `amount_total` equal to the local total to 0.01 (see [docs/ODOO_INTEGRATION.md](docs/ODOO_INTEGRATION.md)). Not exercised in the Docker route yet.
- **Not yet verified:** the Firebase / Neon / Render deployment path (written and documented, needs your accounts to run end to end), the WhatsApp provider against a live number, and a `--big` run of the perf gate.
- **Known limits:** single currency (INR), payments are recorded manually (no payment gateway), no proration, no scheduled jobs in `render.yaml` yet (run billing from the UI or add cron jobs).

## Documentation

[PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Data model](docs/DATA_MODEL.md) · [State machines](docs/STATE_MACHINES.md) · [Billing engine](docs/BILLING_ENGINE.md) · [Odoo integration](docs/ODOO_INTEGRATION.md) · [RBAC](docs/RBAC.md) · [API](docs/API.md) · [Frontend](docs/FRONTEND.md) · [Notifications](docs/NOTIFICATIONS.md) · [Test plan](docs/TEST_PLAN.md) · [Demo script](docs/DEMO_SCRIPT.md) · [Demo video script](docs/DEMO_VIDEO_SCRIPT.md) · [Deploy](docs/DEPLOY.md) · [Decisions](docs/DECISIONS.md)

## Built for

The Odoo "Subscription Management System" challenge: one platform covering sign-up and roles, plans, quote-to-subscription, billing day, discounts, payments and the finance lead's month-end view.
