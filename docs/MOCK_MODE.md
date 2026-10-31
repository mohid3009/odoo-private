# Mock mode and moving to the real database

## What mock mode is
With `VITE_USE_MOCK=true` (the default in `frontend/.env.development`) the React app does **not** call Django. `src/api/client.ts` hands every `/api/*` request to `src/api/mock.ts`, which answers from `src/api/mockData.json`.
That file is a snapshot of the **real API**, recorded by `backend/scripts/export_mock_data.py` from a seeded database, so every field has the real shape (money as strings, `actions`, nested `lines`/`payments`, and so on).

- Works: login/logout/signup, every list with paging, `status` / `overdue` / `needs_attention` / `search` and exact-field filters, invoice and subscription detail, the dashboard counts, the notification screens.
- Does **not** work: saving. Creates, edits, confirm/cancel/pay, billing runs and the like are accepted and answered, but nothing changes (the browser console shows `[mock] … was accepted but not saved`).
- Sign in with `admin@demo`, `staff@demo`, `customer@demo` (or `asha@demo`, `ben@demo`, `chitra@demo`, `dev@demo`); password `Demo@12345`. In mock signup, staff/admin accounts use the code `demo`.
- Run it: `cd frontend && npm run dev`. No backend is needed.

## Switching to the real database (checklist)
1. **Database.** Use PostgreSQL for anything beyond a laptop demo. Set `DATABASE_URL=postgres://user:pass@localhost:5432/brightloop` in `backend/.env` (sqlite is only the zero-setup fallback). Create an empty database first.
2. **Create the tables.** `cd backend && .venv\Scripts\python manage.py migrate`
3. **Load data.** Either the demo data: `python scripts\seed_demo.py` (users, catalog, subscriptions, discounts, invoices, payments; safe to re-run), or your own: `python manage.py createsuperuser`, then add the catalog and customers through the app.
4. **Start Django.** `python manage.py runserver` (port 8000). Check `http://localhost:8000/api/healthz` says `"app_db": "ok"`.
5. **Turn mock mode off.** In `frontend/.env.development` set `VITE_USE_MOCK=false` (or delete the file) and restart `npm run dev` (Vite reads env files only at start). Requests now go through the proxy in `vite.config.ts` to `localhost:8000`.
6. **Sign in** with a real account and click through the same screens. Anything that now errors is a real API problem, not a mock one.
7. **Production.** `npm run build` ignores `.env.development`, so a production bundle always uses the real API. Set `DEBUG=false`, `SITE_URL`, `CSRF_TRUSTED_ORIGINS` and the signup codes as described in `.env.example`.

Optional integrations stay off until you want them: `ODOO_ENABLED=false` works fully; WhatsApp uses `WHATSAPP_PROVIDER=console` until Twilio credentials are set.

## Keeping the mock honest
When an API response changes shape, refresh the snapshot (needs a seeded database):
```
cd backend
python scripts\seed_demo.py
python scripts\export_mock_data.py
```
Commit the regenerated `frontend/src/api/mockData.json`. Because it comes from the real serializers, a mismatch between the mock and the backend means the snapshot is stale, not that the API is wrong.

## Adding a new screen
Write it against the real endpoint as usual. If it is a list or detail not in the snapshot yet, add its path to `LISTS` / `DETAILS` in `export_mock_data.py` and re-export; until then the mock returns an empty page for it.
