# Deploy: Render + Neon + Firebase

One Docker web service serves the API and the built React app (D-005). Auth is Firebase (D-046), the database is Neon.

## 1. Firebase (identity)
1. console.firebase.google.com → create a project (Analytics not needed).
2. **Build → Authentication → Get started**. Enable **Google** and **Email/Password**.
3. **Authentication → Settings → Authorized domains**: add your Render domain (e.g. `brightloop.onrender.com`). `localhost` is already there. Without this the Google popup fails with `auth/unauthorized-domain`.
4. **Authentication → Settings → Password policy** (optional): require upper, lower, special and 9+ characters to match the app's rule (D-006). The sign-up form hint already says so.
5. **Project settings → Your apps → Web (`</>`)**: register an app and copy `apiKey`, `authDomain`, `projectId`, `appId`.
6. **Email templates** (Authentication → Templates): customise the verification and password-reset emails (sender name, language). Firebase sends these, not Django.

## 2. Neon (database)
1. neon.tech → create a project (pick the region closest to your Render region).
2. Dashboard → **Connect** → turn **Connection pooling off** to get the *direct* host (no `-pooler`). Copy the string; it ends in `?sslmode=require`.
   (Billing uses `select_for_update(skip_locked)` inside transactions; the direct host is the safe default. Keep migrations on the direct host.)
3. That string is `DATABASE_URL`. The container runs `migrate` on every start, so the schema creates itself.

## 3. Render (host)
1. Push the repo to GitHub. Render → **New → Blueprint** → pick the repo; it reads `render.yaml`.
2. Fill the prompted secrets:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon string from step 2 |
| `FIREBASE_PROJECT_ID` | Firebase `projectId` |
| `VITE_FIREBASE_API_KEY` / `_AUTH_DOMAIN` / `_PROJECT_ID` / `_APP_ID` | the web config from Firebase step 5 (public values, baked into the build) |
| `STAFF_SIGNUP_CODE` / `ADMIN_SIGNUP_CODE` | long random strings; empty disables that account type |
| `EMAIL_HOST*`, `DEFAULT_FROM_EMAIL` | optional SMTP for invoices and reminders (otherwise they only log to the console) |

`DJANGO_SECRET_KEY` is generated for you. The service refuses to start with `DEBUG=false` and no secret key. `LOCAL_PASSWORD_AUTH=false` and `ODOO_ENABLED=false` are preset.

3. First deploy builds the image (~3-5 min). Health check: `/api/healthz`.

## 4. First admin
Open the site → **Sign up → Admin** → enter the `ADMIN_SIGNUP_CODE` and sign up with email (verify the link, then log in). Google sign-in does not carry the admin code; staff and admins added later by an admin can use Google because their row already exists (Staff page, no password needed).

## 5. Scheduled jobs (not in `render.yaml` yet)
Billing and reminders are commands, safe to repeat (idempotent): `python manage.py run_billing` daily, `python manage.py run_notifications` hourly, `python manage.py sync_odoo` only if Odoo is on. Add two Render **Cron Jobs** with the same Dockerfile, the same env vars as the web service, and those commands as the Docker command. Until then, use the **Billing → Run billing** button.

## Local development with Firebase
Copy `frontend/.env.example` to `frontend/.env.local`, set `FIREBASE_PROJECT_ID` in the root `.env`, keep `LOCAL_PASSWORD_AUTH=true`. Both login styles then work locally.

## Known limits
- Google sign-in creates **customers**. Staff/admin via Google only works for emails that already exist (admin-added) because the registration code is typed on the email sign-up form.
- The sign-up code for an email account is held in the browser's localStorage between sign-up and first login (cleared after the first attempt).
- Odoo is off in production; invoices show `skipped` sync status.
