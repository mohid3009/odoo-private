# Setup guide (Windows, step by step)

Everything the code needs but cannot install for itself. Do the parts in order; parts 4–6 are optional (the app runs without them).
Commands are **PowerShell**. Paths assume the repo is at `C:\Users\<you>\Desktop\projects\odoo-kochi`.

| Part | What | Needed for | Time |
|---|---|---|---|
| 1 | Python, Node, PostgreSQL, the app itself | everything | 20 min |
| 2 | `.env` file | everything | 5 min |
| 3 | Production mode + public tunnel + phone test | judging (live link) | 15 min |
| 4 | Odoo 18 (accounting mirror) | "invoice visible in Odoo" | 30–60 min |
| 5 | WhatsApp via Twilio sandbox | the WhatsApp part of the demo | 15 min |
| 6 | Real email (SMTP) | reset links / invoices in a real inbox | 10 min |
| 7 | Docker (alternative to parts 1 + 4) | one-command stack | 30 min + reboot |
| 8 | Git: merge, tag `v1.0` | submission | 10 min |
| 9 | Demo-day checklist | judging | 15 min |

---

## Part 1 — Tools and the app (local, no Docker)

### 1.1 Install the tools
```powershell
winget install --id Python.Python.3.12        # 3.10+ works
winget install --id OpenJS.NodeJS.LTS         # Node 20+
winget install --id PostgreSQL.PostgreSQL.16  # remember the password you set for user "postgres"
```
Close and reopen PowerShell, then check: `python --version`, `node --version`, `psql --version`
(if `psql` is not found, add `C:\Program Files\PostgreSQL\16\bin` to PATH).

### 1.2 Create the app database
```powershell
createdb -U postgres -h localhost brightloop
```
(It asks for the postgres password unless your Postgres trusts local connections.)

### 1.3 Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```
Create the `.env` file now (Part 2), then:
```powershell
.venv\Scripts\python manage.py migrate
.venv\Scripts\python scripts\seed_demo.py          # admin@demo / staff@demo / customer@demo, password Demo@12345
.venv\Scripts\python manage.py runserver           # API on http://localhost:8000 — leave this window open
```

### 1.4 Frontend (second PowerShell window)
```powershell
cd frontend
npm install
npm run dev                                        # open http://localhost:5173 and log in as admin@demo
```

### 1.5 Check it
- http://localhost:8000/api/healthz → `"app_db": "ok"` (Odoo shows `disabled` until Part 4).
- `cd backend; .venv\Scripts\python -m pytest -q tests\test_demo_flow.py` → `1 passed` (the whole demo S1–S7 through the API).

---

## Part 2 — The `.env` file
Copy the template at the **repo root** (Django reads `<repo>\.env`):
```powershell
copy .env.example .env
notepad .env
```
Set these for local development:
```
DJANGO_SECRET_KEY=<paste the output of: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=true
DATABASE_URL=postgres://postgres:<your-postgres-password>@localhost:5432/brightloop
SITE_URL=http://localhost:5173
ODOO_ENABLED=false            # true only after Part 4
WHATSAPP_PROVIDER=console     # twilio only after Part 5
```
Never commit `.env` (it is in `.gitignore`). Restart `runserver` after every change to `.env`.

---

## Part 3 — Production mode, public link, phone test
The judges get **one HTTPS URL**: Django serves the built React app and the API together, and a tunnel makes it public.

### 3.1 Install a tunnel
```powershell
winget install --id Cloudflare.cloudflared         # no account needed for a quick tunnel
```

### 3.2 Build the frontend once
```powershell
cd frontend
npm run build                                       # creates frontend\dist, which Django serves
```

### 3.3 Start the tunnel first (to learn the URL)
```powershell
cloudflared tunnel --url http://localhost:8000
```
It prints a URL like `https://random-words.trycloudflare.com`. Keep this window open. The URL changes every time you restart a quick
tunnel; for a fixed name use a free Cloudflare account with a named tunnel, or `ngrok http 8000` with an ngrok account.

### 3.4 Switch `.env` to production values
```
DEBUG=false
DJANGO_SECRET_KEY=<a long random value — the server refuses to start with the dev key>
ALLOWED_HOSTS=localhost,127.0.0.1,random-words.trycloudflare.com
CSRF_TRUSTED_ORIGINS=https://random-words.trycloudflare.com
SITE_URL=https://random-words.trycloudflare.com
```

### 3.5 Run the server
```powershell
cd backend
.venv\Scripts\python manage.py collectstatic --noinput
.venv\Scripts\python manage.py runserver 8000 --insecure
```
(`--insecure` lets runserver serve static files with `DEBUG=false`. In Docker / Linux, gunicorn + WhiteNoise do this instead.)

### 3.6 Test
1. On the laptop: open the tunnel URL → log in as `staff@demo` → Dashboard loads.
2. **On a phone, Wi-Fi off (mobile data)**: open the same URL → log in → My invoices / Dashboard.
3. Forgot password → the link in the server window must start with the tunnel URL (that is `SITE_URL`).
If login fails with "CSRF verification failed", the tunnel host is missing from `CSRF_TRUSTED_ORIGINS` (it must include `https://`).

**Keep the laptop awake:** Settings → System → Power → Screen and sleep → "Never" while plugged in.

---

## Part 4 — Odoo 18 (accounting mirror)
What it gives you: taxes, products, customers and invoices appear in Odoo; confirming an invoice posts it there. The app works without it
(`ODOO_ENABLED=false`, records show `skipped`). **Never verified against a live Odoo yet** — expect to fix a field name or two (step 4.6).

### 4.1 Install Odoo 18 Community (pick one)
- **Without Docker (recommended on this laptop):** download the Odoo **18.0 Community Windows installer** from
  https://nightly.odoo.com/ → `18.0` → `nightly` → `windows`. Run it, choose "Odoo Server" and let it install its own PostgreSQL
  (separate user, no clash with yours). It runs as a Windows service on **http://localhost:8069**.
- **With Docker:** see Part 7, then `docker compose up -d odoo db_odoo`.

### 4.2 Create the Odoo database
Open http://localhost:8069 → the database manager appears:
- Master password: note it down · Database name: **`odoo_sub`** · Email: **`admin`** · Password: **`admin`**
- Language English · **Country: India** · Demo data: **unchecked** → Create.

### 4.3 Install the apps
In Odoo: Apps → install **Invoicing** (or Accounting) and **Contacts**. With country India, Odoo installs the Indian chart of accounts
(`l10n_in`) together with the accounting app; the bootstrap script below installs it if it did not. Odoo cannot post invoices without it.

### 4.4 Point the app at Odoo (`.env`)
```
ODOO_ENABLED=true
ODOO_URL=http://localhost:8069
ODOO_DB=odoo_sub
ODOO_USER=admin
ODOO_PASSWORD=admin
```
Better: in Odoo, your avatar → My Profile → Account Security → New API Key, then set `ODOO_API_KEY=<key>` and remove `ODOO_PASSWORD`.
Restart `runserver`.

### 4.5 Bootstrap and smoke test
```powershell
cd backend
.venv\Scripts\python scripts\odoo_bootstrap.py     # company → India/INR, l10n_in installed, sales journal present
.venv\Scripts\python scripts\odoo_smoke.py         # login, read a partner, create + delete a test partner
```
Then http://localhost:8000/api/healthz should show `"odoo": {"status": "ok", ...}`.

### 4.6 Verify the field names (project rule: never guess them)
```powershell
.venv\Scripts\python manage.py shell -c "from integrations.odoo.client import get_client as g; c=g(); [print(m, sorted(c.fields_get(m))) for m in ('account.move','account.move.line','account.tax','product.product','res.partner')]"
```
Compare with `backend/integrations/odoo/mappers.py`. If a save shows Odoo status `error`, the message on the record names the bad field;
fix the mapper (or ask Claude: "Odoo is up on 8069, verify the mappers").

### 4.7 End-to-end check
1. Admin: Catalog → edit and save the tax and the product → their Odoo badge turns `synced`.
2. Billing → Run billing → open the draft → Odoo `synced` (a draft exists in Odoo: Invoicing → Customers → Invoices).
3. Confirm → the Odoo invoice becomes **Posted** with the same lines, GST and total.
4. Anything made while Odoo was off: `.venv\Scripts\python manage.py sync_odoo`.
Not mirrored by design (cut): payments and cancellations.

---

## Part 5 — WhatsApp via the Twilio sandbox
1. Sign up at https://www.twilio.com/try-twilio (free trial).
2. Console home → copy **Account SID** and **Auth Token**.
3. Console → Messaging → Try it out → **Send a WhatsApp message**. It shows a code like `join happy-tiger`.
   From **each demo phone**, send that exact text on WhatsApp to **+1 415 523 8886**; you get a "joined" reply.
4. `.env`:
   ```
   WHATSAPP_PROVIDER=twilio
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```
   Restart `runserver`. Admin → Notifications: the banner shows Twilio, configured, sandbox.
5. Admin → Notifications → **Test send** → channel WhatsApp → your number → a message arrives.
6. The customer needs a number **and** the opt-in: log in as the customer → Profile → WhatsApp number (10 digits become `+91…`) and tick
   the WhatsApp opt-in. Then confirming an invoice or recording a payment sends a WhatsApp message.
7. Failed sends retry when you run `.venv\Scripts\python manage.py send_notifications` (or press Retry in the log).

Limits (say so in the pitch): the sandbox reaches only phones that joined, and joins expire after a few days — **re-join right before
judging**; production needs a verified WhatsApp Business sender and approved templates.

---

## Part 6 — Real email (optional)
Without this, emails (reset links, invoices) print in the `runserver` window, which is fine for the demo. For Gmail:
1. Google account → Security → 2-Step Verification on → **App passwords** → create one ("Brightloop").
2. `.env`:
   ```
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=you@gmail.com
   EMAIL_HOST_PASSWORD=<the 16-character app password>
   DEFAULT_FROM_EMAIL=Brightloop <you@gmail.com>
   ```
3. Restart; Admin → Notifications → Test send → channel email → your address.

---

## Part 7 — Docker (alternative to Parts 1 + 4; it failed on the first laptop, D-030)
Docker Desktop needs WSL 2 and CPU virtualization.
1. **Admin** PowerShell: `wsl --install` → reboot.
2. If WSL complains about virtualization: reboot into BIOS/UEFI → enable Intel VT-x / AMD-V (SVM) → save.
3. Start Docker Desktop → wait for "Engine running" → `docker info` prints server details.
4. In the repo: `copy .env.example .env`, set `DJANGO_SECRET_KEY`, keep `ODOO_ENABLED=false` for the first start.
5. `docker compose up -d --build` → web on http://localhost:8000 (migrations run on start), Odoo on :8069.
6. `docker compose exec web python scripts/seed_demo.py`
7. Odoo, one time (there is no `make` on Windows; these are the lines of `make odoo-init`):
   ```powershell
   docker compose run --rm odoo odoo -d odoo_sub -i base,contacts,account,sale_management --without-demo=all --stop-after-init
   docker compose up -d odoo
   docker compose exec web python scripts/odoo_bootstrap.py
   docker compose exec web python scripts/odoo_smoke.py
   ```
   Then set `ODOO_ENABLED=true` in `.env` (compose already sets `ODOO_URL=http://odoo:8069`) and run `docker compose up -d web`.

---

## Part 8 — Git: merge the phase branches and tag v1.0
Each phase is four branches (`phase-Na … phase-Nd`) stacked on the previous phase; `main` still holds only the early phases.
The last phase's branches contain everything before them, so merging those four is enough:
```powershell
git checkout main
git pull
git merge --no-ff phase-9a phase-9b phase-9c phase-9d -m "v1.0: phases 1-9"
cd backend; .venv\Scripts\python -m pytest -q; cd ..\frontend; npm run build; cd ..
git push origin main
git tag -a v1.0 -m "Hackathon submission"
git push origin v1.0
```
(Or open one PR per branch on GitHub and merge them in order.) After the tag, no more pushes to `main` ("freeze").

---

## Part 9 — Demo-day checklist (30 min before)
1. Laptop plugged in, sleep off, notifications off.
2. Fresh database: `dropdb -U postgres brightloop; createdb -U postgres brightloop` → `migrate` → `scripts\seed_demo.py`.
3. `.venv\Scripts\python -m pytest -q tests\test_demo_flow.py` → passes.
4. Start runserver (production mode) + tunnel; open the URL on a phone over mobile data.
5. Re-join the Twilio sandbox on each demo phone; send one Test send.
6. If Odoo is part of the demo: healthz shows Odoo `ok`; keep Odoo open in a second tab.
7. Optional scale proof: a second database with `scripts\seed_demo.py --big` and `scripts\perf_check.py` output ready.
8. Follow `docs/DEMO_SCRIPT.md`. Keep a screen recording of a clean run as a backup.
