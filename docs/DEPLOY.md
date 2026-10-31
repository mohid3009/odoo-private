# Deploy: Vercel (frontend) + Render (backend) + Neon + Firebase

Frontend on Vercel, Django API on Render, Postgres on Neon, auth on Firebase (D-046, D-047). Single-container hosting (the root `Dockerfile`, used by docker-compose) still works if you prefer one service.

## 1. Firebase (identity)
1. console.firebase.google.com → create a project (Analytics not needed).
2. **Build → Authentication → Get started**. Enable **Google** and **Email/Password**.
3. **Authentication → Settings → Authorized domains**: add your **Vercel** domain (e.g. `brightloop.vercel.app`) once you have it. `localhost` is already there. Without this the Google popup fails with `auth/unauthorized-domain`.
4. **Authentication → Settings → Password policy** (optional): require upper, lower, special and 9+ characters to match the app's rule (D-006). The sign-up form hint already says so.
5. **Project settings → Your apps → Web (`</>`)**: register an app and copy `apiKey`, `authDomain`, `projectId`, `appId`.
6. **Email templates** (Authentication → Templates): customise the verification and password-reset emails (sender name, language). Firebase sends these, not Django.

## 2. Neon (database)
1. neon.tech → create a project (pick the region closest to your Render region).
2. Dashboard → **Connect** → turn **Connection pooling off** to get the *direct* host (no `-pooler`). Copy the string; it ends in `?sslmode=require`.
   (Billing uses `select_for_update(skip_locked)` inside transactions; the direct host is the safe default. Keep migrations on the direct host.)
3. That string is `DATABASE_URL`. The container runs `migrate` on every start, so the schema creates itself.

## 3. Render (backend)
1. Push the repo to GitHub. Render → **New → Blueprint** → pick the repo; it reads `render.yaml` and builds `backend/Dockerfile` (API only).
2. Keep the service name `brightloop` (its URL is then `https://odoo-private.onrender.com`, which `frontend/vercel.json` points at). If Render gives you a different URL, edit the three `destination`s in `frontend/vercel.json`.
3. Fill the prompted secrets:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon string from step 2 |
| `FIREBASE_PROJECT_ID` | Firebase `projectId` |
| `SITE_URL` | your Vercel URL, e.g. `https://brightloop.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | the same Vercel URL (add custom domains comma-separated). **Required**: without it every POST fails CSRF. |
| `STAFF_SIGNUP_CODE` / `ADMIN_SIGNUP_CODE` | long random strings; empty disables that account type |
| `EMAIL_HOST*`, `DEFAULT_FROM_EMAIL` | optional SMTP for invoices and reminders (otherwise they only log to the console) |

`DJANGO_SECRET_KEY` is generated for you. The service refuses to start with `DEBUG=false` and no secret key. `LOCAL_PASSWORD_AUTH=false` and `ODOO_ENABLED=false` are preset. Health check: `/api/healthz`. The container runs `migrate` on every start.

## 3b. Vercel (frontend)
1. Vercel → **Add New → Project** → import the repo → set **Root Directory** to `frontend`. Framework preset: Vite (build `npm run build`, output `dist`).
2. Environment variables (public Firebase web config from step 1.5): `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`.
3. Deploy, then add the Vercel domain to Firebase **Authorized domains** (step 1.3) and to Render's `SITE_URL` / `CSRF_TRUSTED_ORIGINS`.

**How the two talk:** `frontend/vercel.json` rewrites `/api/*` (and `/admin`, `/static`) to Render, so the browser only ever sees the Vercel origin. Session cookie, CSRF and Firebase popup all stay first-party: no CORS, no cross-site cookies, no code changes. Trade-off: API calls take one extra hop through Vercel's proxy.

## 4. First admin
Open your Vercel URL → **Sign up → Admin** → enter the `ADMIN_SIGNUP_CODE` and sign up with email (verify the link, then log in). You can also use **Sign up with Google** here: enter the admin code first, and it applies to both the email form and the Google button.

## 5. Scheduled jobs (not in `render.yaml` yet)
Billing and reminders are commands, safe to repeat (idempotent): `python manage.py run_billing` daily, `python manage.py run_notifications` hourly, `python manage.py sync_odoo` only if Odoo is on. Add two Render **Cron Jobs** with `backend/Dockerfile`, the same env vars as the web service, and those commands as the Docker command. Until then, use the **Billing → Run billing** button.

## Local development with Firebase
Copy `frontend/.env.example` to `frontend/.env.local`, set `FIREBASE_PROJECT_ID` in the root `.env`, keep `LOCAL_PASSWORD_AUTH=true`. Both login styles then work locally.

## Known limits
- Google sign-up supports every role: pick the role, enter the registration code (staff/admin), then use the email form or the Google button. A *Log in* with Google for an unknown email creates a customer.
- The sign-up code for an email account is held in the browser's localStorage between sign-up and first login (cleared after the first attempt).
- Odoo is off in production; invoices show `skipped` sync status.
