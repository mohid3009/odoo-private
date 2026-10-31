# Brightloop — Subscription Management

React + Django REST API + Odoo 18 (accounting ledger). Catalog and plans, quotations, subscriptions with a lifecycle, automatic
exactly-once billing with tax, discounts with usage limits, payments, a finance dashboard, a customer portal, and email/WhatsApp
notifications. Built phase by phase from [KICKOFF.md](KICKOFF.md); what is done, cut and known-broken is in [TASKS.md](TASKS.md).

**Status (v1.0 candidate):** all seven scenes (S1–S7) work end to end and are rehearsed automatically (`tests/test_demo_flow.py`).
The full test suite passes on PostgreSQL with nothing skipped, and the performance gate is green on ~5k subscriptions / ~16k invoices.
Not verified on this machine: the Docker image, Odoo, a live Twilio send and a public tunnel (see Known limitations).

## Quick start (local, the verified path — about 5 minutes)
Needs Python 3.10+ and Node 20. PostgreSQL is recommended; without `DATABASE_URL` the backend falls back to sqlite (dev only).
```bash
# 1. backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt          # Linux/macOS: .venv/bin/pip
set DATABASE_URL=postgres://postgres@localhost:5432/brightloop   # optional; createdb brightloop first
.venv\Scripts\python manage.py migrate
.venv\Scripts\python scripts\seed_demo.py               # demo logins + catalog + one active subscription
.venv\Scripts\python manage.py runserver                # http://localhost:8000 (API)

# 2. frontend (second terminal)
cd frontend
npm install
npm run dev                                              # http://localhost:5173, proxies /api to :8000
```
`ODOO_ENABLED=false` (in `.env`) runs without Odoo; `WHATSAPP_PROVIDER=console` (the default) prints WhatsApp messages instead of sending.

### One URL, production mode (what the tunnel serves)
```bash
cd frontend && npm run build                             # Django serves frontend/dist (WhiteNoise + SPA catch-all)
cd backend
set DEBUG=false
set DJANGO_SECRET_KEY=<50+ random chars>                 # DEBUG=false refuses to start with the dev key
set ALLOWED_HOSTS=localhost,<your-tunnel-host>
set CSRF_TRUSTED_ORIGINS=https://<your-tunnel-host>
set SITE_URL=https://<your-tunnel-host>                  # used in password-reset links
.venv\Scripts\python manage.py collectstatic --noinput
.venv\Scripts\python manage.py runserver 8000 --insecure  # or gunicorn config.wsgi on Linux / in the image
cloudflared tunnel --url http://localhost:8000           # or: ngrok http 8000
```
Cookies are `Secure` when `DEBUG=false`; browsers accept them on `http://localhost` and over the tunnel's HTTPS.

## Quick start (Docker — written, not yet run: D-030)
```bash
cp .env.example .env            # set DJANGO_SECRET_KEY; ODOO_ENABLED=false unless you run make odoo-init
docker compose up -d --build    # web :8000 (API + built SPA), odoo :8069, postgres x2
make seed                       # migrations run automatically on container start
make odoo-init                  # optional, one time: Odoo DB + India/INR + smoke test
```

## Demo logins (after `seed_demo.py`) — password `Demo@12345` for all
| Role | Email | Sees |
|---|---|---|
| Admin | `admin@demo` | everything: catalog, discounts, staff, notifications, plus all staff screens |
| Staff | `staff@demo` | dashboard, subscriptions, invoices, payments, billing; catalog and discounts read-only |
| Customer | `customer@demo` | My subscriptions / invoices / payments / notifications only |

After `seed_demo.py --big`: 500 more customers `big-0001@big.seed` … `big-0500@big.seed` (same password).
The click-by-click demo is [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).
**Step-by-step setup for everything (tools, .env, tunnel, Odoo, Twilio, email, Docker, release): [docs/SETUP.md](docs/SETUP.md).**

## URLs
| What | URL |
|---|---|
| App (dev) | http://localhost:5173 |
| App (one-URL / prod mode / Docker) | http://localhost:8000 |
| Health (DB + Odoo) | http://localhost:8000/api/healthz |
| Django admin | http://localhost:8000/admin/ (`admin@demo`) |
| Odoo | http://localhost:8069 (db `odoo_sub`, `admin` / `admin`) |

## Everyday commands (from `backend/`)
| Task | Command |
|---|---|
| Tests (sqlite, quick) | `.venv\Scripts\python -m pytest -q` — PostgreSQL-only concurrency tests show as skipped |
| Tests (release gate) | `set DATABASE_URL=postgres://postgres@localhost:5432/brightloop_test` then the same — **0 skipped expected** |
| Demo rehearsal (S1–S7 via the API) | `.venv\Scripts\python -m pytest -q tests/test_demo_flow.py` |
| Run billing | `python manage.py run_billing [--as-of YYYY-MM-DD]` (or the Billing page) |
| Reminders / retries | `python manage.py run_notifications` · `python manage.py send_notifications` |
| Odoo retry | `python manage.py sync_odoo` |
| Big seed + perf gate | `python scripts/seed_demo.py --big` then `python scripts/perf_check.py` (fails if any call > 1.0 s) |
| Frontend build | `cd frontend && npm run build` |

Docs: [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Data model](docs/DATA_MODEL.md) · [State machines](docs/STATE_MACHINES.md) ·
[Billing engine](docs/BILLING_ENGINE.md) · [Odoo](docs/ODOO_INTEGRATION.md) · [RBAC](docs/RBAC.md) · [API](docs/API.md) ·
[Frontend](docs/FRONTEND.md) · [Notifications](docs/NOTIFICATIONS.md) · [Test plan](docs/TEST_PLAN.md) · [Demo script](docs/DEMO_SCRIPT.md) ·
[Decisions](docs/DECISIONS.md) · [Team split](docs/TEAM.md)

## Known limitations
- **Odoo is unverified.** Docker's engine never started on the dev laptop (D-030), so the XML-RPC mappers were only tested against a mock. With `ODOO_ENABLED=false` everything works and records show `skipped`; Odoo payment and cancel mirroring are cut.
- **Docker image and compose file have not been run** for the same reason. The one-URL production mode above was verified locally with `runserver`.
- **WhatsApp:** the Twilio adapter is tested against a mocked HTTP layer only. Sandbox numbers must have joined the sandbox, and free-form text works only inside the 24 h window; production needs a verified business account and approved templates (D-025).
- **No public tunnel test yet** (no `cloudflared`/`ngrok` on the dev laptop); test from a phone on mobile data before judging.
- Single currency (INR); payments are recorded by hand (no gateway); no proration or mid-cycle plan changes; customers cannot pause/close/renew themselves.
