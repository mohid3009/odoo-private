# API contract

Base `/api`. JSON. Session cookie auth; unsafe methods need `X-CSRFToken` (cookie `csrftoken`, set by `GET /api/auth/csrf/`).
Money = **string** with 2 dp (`"8283.60"`). Dates ISO-8601 (`2026-10-31`). Lists are paginated:
`{"count": n, "next": url|null, "previous": url|null, "results": [...]}` (25/page, `?page=`). Errors: `{"detail": "..."}` or `{"field": ["msg"]}`.
Status codes: 400 validation · 401/403 not allowed · 404 not found / not yours · 409 illegal state transition.

Each phase appends its endpoints here **before** implementation (rule 2).

## Phase 0 — implemented
### `GET /api/healthz`  · public
Response `200` (or `503` when the app DB is down):
```json
{"status": "ok", "app_db": "ok", "odoo": {"status": "ok", "version": "18.0", "uid": 2}}
```
`odoo.status` ∈ `ok | disabled | down` (`down` adds `error`). `status` is `degraded` when anything is down.

## Phase 1 — Auth, roles (implemented)
Anonymous POSTs are CSRF-checked too: call `GET /auth/csrf/` first and send `X-CSRFToken`. Anonymous access to authenticated endpoints → **403**.
User JSON: `{id, email, name, role, profile}`; `profile` is `null` for staff/admin, else
`{company_name, phone, address, whatsapp_number, whatsapp_opt_in, email_notifications, whatsapp_opted_in_at, odoo_sync_status}`.

| Method | Path | Role | Request → Response |
|---|---|---|---|
| GET | `/auth/csrf/` | any | sets `csrftoken` cookie → `{"detail":"ok"}` |
| POST | `/auth/signup/` | anon | `{email, password, name?, whatsapp_number?, whatsapp_opt_in?}` → 201 user (`role` is always `customer`; any `role` sent is ignored). 400 `{email:[…]}` duplicate in any case, `{password:[…]}` policy, `{whatsapp_number:[…]}` invalid / missing when opting in. Does **not** log in |
| POST | `/auth/login/` | anon | `{email, password}` (email case-insensitive) → 200 user · 400 `{"detail":"Invalid email or password."}` (identical for unknown email and wrong password) |
| POST | `/auth/logout/` | auth | → 204 |
| GET | `/auth/me/` | auth | → user |
| PATCH | `/auth/me/` | auth | `{name?, profile?:{company_name?, phone?, address?, whatsapp_number?, whatsapp_opt_in?, email_notifications?}}` → user. `profile` ignored for staff/admin. Number normalised to E.164 (10 digits → `+91`); `whatsapp_opted_in_at` set/cleared when opt-in flips |
| POST | `/auth/password-reset/request/` | anon | `{email}` → 200 `{"detail":"If that email is registered…"}` whether or not the account exists; emails `SITE_URL/reset-password/<uid>/<token>` (valid 24 h) |
| POST | `/auth/password-reset/confirm/` | anon | `{uid, token, new_password}` → 200 · 400 `{"detail":"This reset link is invalid or has expired."}` or `{new_password:[…]}`. Token is single-use (password hash changes) |
| GET | `/staff/` | admin | paginated list of users with role `staff`/`admin`; `?search=` on email/name |
| POST | `/staff/` | admin | `{email, name?, password, role?: "staff"(default)|"admin"}` → 201 `{id,email,name,role,is_active,created_at}` (password never returned). Staff/customer/anon → 403 |

Password policy error text: `"Password needs at least 9 characters, an uppercase letter, a lowercase letter, a special character."` (lists only what is missing).

## Phase 2 — Catalog (implemented)
ModelViewSets at `/products/`, `/taxes/`, `/payment-terms/`, `/plans/`: `GET` list (paginated) + detail, `POST`, `PATCH|PUT /{id}/`, `DELETE /{id}/`.
**Read: staff + admin. Write: admin only.** Customers and anonymous → 403. All lists accept `?search=`, `?ordering=`, and `?page_size=` (max 200, for dropdowns; default 25).
`DELETE` of a row that is referenced elsewhere (e.g. a product used by a plan) → 409 `{"detail": "… is in use and cannot be deleted. Deactivate it instead."}`.
Money fields are strings with 2 dp. `odoo_sync_status` ∈ `skipped|pending|synced|error` (read-only); Odoo failures never block a save.

| Resource | Fields (writable unless noted) | Filters |
|---|---|---|
| **Tax** `/taxes/` | `id, name, rate (0–100), is_active`; ro: `odoo_tax_id, odoo_sync_status, odoo_error` | `is_active` |
| **PaymentTerm** `/payment-terms/` | `id, name, days (≥0), is_default`. Setting `is_default` clears it on the others; the first term created becomes the default | — |
| **Product** `/products/` | `id, name, type (service\|software\|addon\|physical), sales_price, cost_price, notes, is_active, taxes:[tax ids], variants:[{id?, attribute, value, extra_price}]`; ro: `odoo_product_id, odoo_sync_status, odoo_error`; variant ro: `effective_unit_price` (= product `sales_price` + `extra_price`) | `type, is_active` |
| **Plan** `/plans/` | `id, name, product, price, billing_period (daily\|weekly\|monthly\|yearly), min_quantity (≥1), available_from, available_to, auto_close, allow_early_close, allow_pause, allow_renew, is_active`; ro: `product_name` | `billing_period, is_active, product` |

Product `variants` is a full replacement list on write: items with `id` are updated, items without are created, existing variants missing from the list are deleted.
Errors: 400 `{variants:["Duplicate variant: Brand = Odoo."]}`, 400 `{available_to:["Available-to date must be on or after available-from."]}`, 400 `{min_quantity:["Ensure this value is greater than or equal to 1."]}`.
Plan price semantics (D-001): the first subscription line costs `plan.price + variant.extra_price`; add-ons cost `product.sales_price + variant.extra_price`.

## Phase 3 — Subscriptions (planned)
`/quotation-templates/`, `/subscriptions/` (filters `status, customer, plan, search=number`),
`POST /subscriptions/{id}/transition/ {to}` → subscription · 409 if illegal, `POST /subscriptions/from-template/ {template, customer, start_date}` → prefilled draft.

## Phase 4 — Billing (planned)
`POST /billing/run/ {as_of?}` → `{run_id, created, skipped, errors}` · `GET /billing/runs/` ·
`GET /invoices/` (filters `status, customer, overdue=true, subscription`), `GET /invoices/{id}/`,
`POST /invoices/{id}/confirm|cancel|send/`, `GET /invoices/{id}/print/`.

## Phase 5 — Discounts · Phase 6 — Payments (planned)
`/discounts/` (admin write), `POST|DELETE /subscriptions/{id}/discount/`, `GET /discounts/{id}/redemptions/`.
`POST /invoices/{id}/payments/ {amount, method, payment_date, note?}` → payment (400 overpay / bad invoice state), `GET /payments/` (filters `invoice, method, date range`).

## Phase 7 — Notifications · Phase 8 — Portal/Dashboard (planned)
`GET /notifications/logs/`, `POST /notifications/logs/{id}/retry/`, `GET|PATCH /notifications/events/`, `POST /notifications/test-send/`,
`GET|PATCH /me/notification-settings/`, `POST /notifications/run-reminders/`.
`GET /dashboard/summary/?from&to&customer&plan&status` → `{kpis, by_plan, by_month, overdue:{count,results}}`.
Portal reuses `/subscriptions/` and `/invoices/` (scoped by role); no separate endpoints.
