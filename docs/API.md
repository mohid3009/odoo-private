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
| POST | `/auth/signup/` | anon | `{email, password, name?, whatsapp_number?, whatsapp_opt_in?, account_type?: customer|staff|admin, signup_code?}` → 201 user. `account_type` defaults to `customer`; `staff` / `admin` need `signup_code` equal to `STAFF_SIGNUP_CODE` / `ADMIN_SIGNUP_CODE` (D-044). A wrong or missing code is 400 `{signup_code:[…]}`; if that code is not configured on the server the type is disabled (also 400). Staff/admin get no customer profile and ignore the WhatsApp fields. A `role` field is still ignored. 400 `{email:[…]}` duplicate in any case, `{password:[…]}` policy, `{whatsapp_number:[…]}` invalid / missing when opting in. Does **not** log in |
| POST | `/auth/login/` | anon | `{email, password}` (email case-insensitive) → 200 user · 400 `{"detail":"Invalid email or password."}` (identical for unknown email and wrong password) |
| POST | `/auth/firebase/` | anon | `{id_token, account_type?, signup_code?, name?, whatsapp_number?, whatsapp_opt_in?}` → 200 user (session cookie set) · 401 bad/expired token · 403 email not verified or account disabled · 400 sign-up fields invalid (staff/admin need the code). Unknown email creates an account (customer unless a valid code); existing users keep their role and the sign-up fields are ignored. Local `/auth/login|signup|password-reset/*` exist only when `LOCAL_PASSWORD_AUTH=true`. |
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

## Phase 3 — Quotation templates & subscriptions (implemented)
Status machine in `docs/STATE_MACHINES.md`. Every change of `status` goes through `services.transition()`; it is never writable via PATCH.

### `GET /customers/` · staff, admin
Picker list of customer users: paginated `{id, email, name}`, `?search=` on email/name.

### Quotation templates `/quotation-templates/` · staff + admin (read and write); customers 403
`GET list|detail`, `POST`, `PATCH|PUT /{id}/`, `DELETE /{id}/`. Filters `plan, is_active`, `?search=` on name.
Body/JSON: `{id, name, plan, plan_name, validity_days (≥1, default 30), is_active, lines:[{id?, product, product_name, variant|null, quantity (≥1)}]}`.
`lines` is a full replacement list on write (same rule as product variants). A variant must belong to its line's product (400).

### Subscriptions `/subscriptions/` · read: any role (customers see **only their own**, other ids → 404); write: staff + admin
`GET` list (light rows, no lines) and detail; `POST` create; `PATCH|PUT /{id}/` **only while `status = draft`** (else 409 `code: not_editable`). No DELETE (close it instead).
Filters `status, customer, plan`; `?search=` matches `number` (and customer email); `?ordering=` on `number, start_date, created_at, next_invoice_date`.

Fields: `id, number (SUB-000001, ro), customer (user id, role must be customer), customer_email (ro), plan, plan_name (ro), template (ro), status (ro), start_date, expiry_date|null, payment_term (default term if omitted), payment_term_name (ro), next_invoice_date (ro), quotation_valid_until (ro), notes, created_by (ro), created_at (ro), lines_total (ro, pre-tax), actions (ro)`.
Detail adds `lines` and `status_log:[{from_status, to_status, by_user_email, at}]`.
`actions` = what the **current user** may attempt now, e.g. `["quotation","closed"]`; targets are statuses, plus `"renew"` as an action. It reflects role and plan flags only — guards (quantity, dates) are still checked by the server when the button is used.

Line: `{id?, product, product_name, variant|null, variant_label, description, quantity (≥1), unit_price, amount (ro), taxes:[tax ids]}`.
`unit_price` omitted → server computes it (D-001): the line for the plan's primary product costs `plan.price + variant.extra_price`, any other product `product.sales_price + variant.extra_price`. `taxes` omitted → the product's taxes. `amount = quantity × unit_price`, 2 dp. `lines` is a full replacement list on write.
If `lines` is omitted on **create**, one first line is added for the plan's primary product with `quantity = plan.min_quantity`.

Create/update validation (400): customer must be a customer · plan must be active and available on `start_date` · `expiry_date ≥ start_date` · variant belongs to product · the primary-product line quantity ≥ `plan.min_quantity` (`lines` error).

### `POST /subscriptions/{id}/transition/` `{ "to": "<status>" }` · staff, admin → subscription detail
| to | From | Guards (409 `code: guard_failed` when not met) |
|---|---|---|
| `quotation` | draft | ≥ 1 line; primary-line qty ≥ plan minimum; plan available on `start_date`. Sets `quotation_valid_until = today + template.validity_days` (30 if no template) |
| `draft` | quotation | — (clears `quotation_valid_until`) |
| `confirmed` | quotation | `quotation_valid_until` not in the past. Sets `next_invoice_date = start_date` |
| `active` | confirmed, paused | confirmed: `start_date ≤ today`. paused: `next_invoice_date = max(existing, today)` (no back-billing, D-014) |
| `paused` | active | `plan.allow_pause` |
| `closed` | draft, quotation, confirmed; active, paused | pre-active: always. active/paused: `plan.allow_early_close`, or the caller is admin (override) |
Anything else → 409 `{"detail": "...", "code": "illegal_transition"}`. Every success writes a `status_log` row.

### `POST /subscriptions/{id}/renew/` · staff, admin → subscription detail
Only `active` with an `expiry_date`, and `plan.allow_renew` (409 `code: guard_failed` otherwise). Extends `expiry_date` by (expiry − start) (D-014).

### `POST /subscriptions/from-template/` `{ template, customer, start_date, expiry_date?, payment_term?, notes? }` · staff, admin → 201 subscription detail (draft)
Plan = the template's plan; lines copied from the template with prices computed as above; `template` is recorded and `quotation_valid_until = today + validity_days` is pre-set (FR-SUB-01; it is recomputed when moved to `quotation`). Inactive template → 400.

## Phase 4 — Billing engine & invoices (implemented)
Engine rules and worked example: `docs/BILLING_ENGINE.md`. Money = strings (2 dp). Errors on state changes are 409 `{"detail","code"}` with `code` = `illegal_transition` | `guard_failed`.

### `POST /billing/run/` `{ "as_of"?: "YYYY-MM-DD" }` · staff, admin → 200
Runs the engine (default `as_of` = today; a future/past date is allowed so the demo can show later billing days).
Response: `{ run_id, as_of_date, created, skipped, errors, started_at, finished_at }`. One failing subscription is counted in `errors` and logged; it never stops the run. Running twice for the same date creates 0 new invoices.
### `GET /billing/runs/` · `GET /billing/runs/{id}/` · staff, admin
Paginated, newest first: `{ id, started_at, finished_at, as_of_date, triggered_by_email, created_count, skipped_count, error_count }`; detail adds `log` (per-subscription errors).

### Invoices `/invoices/` · read: any role; actions: staff + admin
Customers see **only their own, and never drafts** (other ids → 404). `GET` list (paginated) and detail; no create/update/delete over the API (the engine creates invoices).
Filters: `status`, `customer`, `subscription`, `overdue=true` (D-013: confirmed, `amount_due > 0`, `due_date < today`); `?search=` on number, subscription number, customer email; `?ordering=` on `invoice_date, due_date, total, number, id` (default newest first).
List/detail fields: `id, number (null until confirmed; INV-000001…), subscription, subscription_number, customer, customer_email, status (draft|confirmed|paid|cancelled), invoice_date, due_date, period_start, period_end, subtotal, discount_total (positive), tax_total, total, amount_paid, amount_due, days_overdue, is_overdue, odoo_sync_status`.
Detail adds: `lines:[{id, kind: product|discount, description, quantity, unit_price, tax_rate (sum of the line's taxes, %), line_subtotal, line_tax, line_total}]` (discount lines are negative), `odoo_move_id, odoo_error, sent_at, created_at, actions`. `actions` = what the current user may attempt (`confirm`, `cancel`, `send`).
`invoice_date` is the billing-run date; `due_date = invoice_date + payment-term days`; `period_start/period_end` is the service period billed.

| Action | Who | Rules |
|---|---|---|
| `POST /invoices/{id}/confirm/` | staff, admin | draft only, ≥ 1 product line. Assigns `number`, posts to Odoo after commit, sends `INVOICE_READY` (email/WhatsApp via `notify()`, never blocks). A zero-total invoice becomes `paid` immediately |
| `POST /invoices/{id}/cancel/` | draft: staff, admin · confirmed: **admin only**, and only if nothing was paid | The period stays used: the engine never re-bills a cancelled period (D-019). Paid/cancelled → 409 |
| `POST /invoices/{id}/send/` `{channels?: ["email","whatsapp"]}` | staff, admin | confirmed or paid only. Forced send (manual): resends even if sent before; sets `sent_at`. Channels default to all enabled for the customer |
| `GET /invoices/{id}/print/` | any role (scoped) | Detail plus `seller:{name}` and `customer_details:{name,email,company_name,phone,address}` for the print view |
Each action returns the invoice detail.

### Notifications
See **Phase 7 — Notifications** below. `notify(event_code, user, obj, …)` writes a `NotificationLog` row per channel (UNIQUE `dedupe_key`) and sends after commit; failures land on the row and never reach the caller. Spec: `docs/NOTIFICATIONS.md`.

### Commands
`python manage.py run_billing [--as-of YYYY-MM-DD]` · `python manage.py sync_odoo` (retries `pending`/`error` Odoo mirrors).

## Phase 5 — Discounts (implemented)
Rules and engine behaviour: `docs/BILLING_ENGINE.md` (as built, Phase 5) and D-040.

### Discounts `/discounts/` · read: staff + admin · write: **admin only** · customers 403
`GET` list (paginated; filters `scope, type, is_active`; `?search=` name/code; `?ordering=` `name, id, end_date, used_count`) and detail; `POST`; `PATCH|PUT /{id}/`; `DELETE /{id}/` (409 if it was ever redeemed: deactivate it instead).
Fields: `id, name, code|null (unique when set), type (fixed|percent), value, scope (product|subscription), products:[product ids], min_purchase_amount|null, min_quantity|null, start_date|null, end_date|null, usage_limit|null, is_active, used_count (ro), state (ro), created_by (ro), created_at (ro)`.
`state` ∈ `inactive | scheduled | active | expired | exhausted` (computed from today's date and the usage count).
Validation (400): percent `0 < value ≤ 100` · fixed `value > 0` · `start_date ≤ end_date` · `usage_limit ≥ 1` · `min_quantity ≥ 1` · `min_purchase_amount ≥ 0` · scope `product` needs ≥ 1 product · scope `subscription` must have no products.

### `GET /discounts/{id}/redemptions/` · staff, admin
Paginated, newest first: `{ id, invoice, invoice_number, subscription_number, customer_email, amount, created_at }` — one row per invoice the rule was applied to.

### `POST /subscriptions/{id}/discount/` `{ "discount": <id> }` · staff + admin → subscription detail
Attaches a **subscription-scope** rule (replacing any attached one). 400 if the rule is product-scope or inactive; 409 `guard_failed` if the subscription is closed. It applies from the next invoice. `DELETE /subscriptions/{id}/discount/` detaches (→ subscription detail; 409 if closed). Subscription JSON gains `discount` (id|null) and `discount_name`.

### How a rule reaches an invoice (no endpoint; the billing run does it)
- The billing date (`as_of`) must fall inside `start_date…end_date`, the rule must be active and `used_count < usage_limit`.
- **product** rules apply by themselves to every line whose product is listed, when that line meets `min_quantity` and `min_purchase_amount` (the line's amount). At most one rule per line: the largest saving wins. **subscription** rules apply only when attached, on the subtotal after line discounts, with `min_quantity` = total quantity and `min_purchase_amount` = that subtotal; at most one per invoice.
- percent = `value%` of the base; fixed = `value`, capped at the base. A rule is counted **once per invoice** (`used_count + 1`, one `DiscountRedemption`), even if it discounts several lines.
- The discount shows on the invoice as its own negative line (`kind: "discount"`); `discount_total` is the positive amount saved.

## Phase 6 — Payments (implemented)
Payments are recorded by hand against a **confirmed** invoice (no gateway). A payment row is an **attempt** with a `status`; rows are never edited or deleted over the API (PATCH/PUT/DELETE → 405), a mistake is undone by a **reversal**, so the history stays complete. Money = strings (2 dp). Rules and state machine: `docs/STATE_MACHINES.md`, data: `docs/DATA_MODEL.md`, decisions: D-041.

**Core rules**
- `status` ∈ `completed | failed | reversed`. **Only `completed` payments count** toward `invoice.amount_paid`; `amount_paid = Σ completed`, `amount_due = total − amount_paid`, recomputed under a row lock on every change. A `failed` attempt never touches the balance.
- The invoice becomes `paid` exactly when `amount_due` reaches 0, and goes back to `confirmed` when a reversal makes the balance positive again.
- **Attempts:** `invoice.failed_attempts` counts failed attempts since the last completed payment (or the last admin reset). A new attempt gets `attempt_number = failed_attempts + 1`. The limit is `PAYMENT_MAX_ATTEMPTS` (setting/env, default **3**). When the limit is reached the invoice is flagged `payment_needs_attention = true` and further attempts are refused (409 `max_attempts_reached`) until an admin resets it. A completed payment resets the counter.
- Overpayment is rejected (D-019): an attempted amount may not exceed the current balance, whatever its status.

### `POST /invoices/{id}/payments/` · staff, admin → 201
Body: `{ amount, method, status?: "completed"|"failed" (default completed), failure_reason? (required when failed), payment_date?, note? }` — `method` ∈ `cash | bank_transfer | upi | card | cheque | other`; `payment_date` defaults to today and may not be in the future.
Response: the payment (see fields below) plus `invoice_state: { status, amount_paid, amount_due, failed_attempts, payment_needs_attention }`. After commit a completed payment sends `PAYMENT_RECEIVED` (never blocks or fails the request).
Errors: 400 `{amount}` (≤ 0, > 2 decimals, or more than the balance) · 400 `{failure_reason}` missing for a failed attempt · 400 `{payment_date}` future / `{method}` / `{status}` unknown (`reversed` cannot be recorded, only produced by a reversal) · 409 `illegal_transition` when the invoice is draft, cancelled or already paid · 409 `max_attempts_reached` · 403 customers/anonymous.

### `POST /payments/{id}/retry/` · staff, admin → 201
Retries a **failed** attempt: same body as above. Creates a new row with `retry_of = {id}` and the next `attempt_number`. Allowed only if the payment is `failed`, has not been retried before, and the limit is not reached. 409 `illegal_transition` (not failed / invoice no longer payable), 409 `guard_failed` (already retried), 409 `max_attempts_reached`.

### `POST /payments/{id}/reverse/` `{ "reason": "…" }` · **admin only** → 200
Reverses a **completed** payment: `status → reversed`, stores `reversed_at`, `reversed_by`, `reversal_reason` (required, non-blank; 400 otherwise). Recomputes the invoice: the balance is restored and a `paid` invoice goes back to `confirmed` (so it is overdue again if its due date has passed). The row is kept. 409 `illegal_transition` for failed/reversed payments or a cancelled invoice. Staff → 403.

### `POST /invoices/{id}/reset-payment-attempts/` `{ "reason": "…" }` · **admin only** → 200 invoice detail
Clears `failed_attempts` and `payment_needs_attention` so payments can be attempted again; the failed rows stay. Reason required. 409 `guard_failed` if the invoice is not flagged / not confirmed.

### `GET /invoices/{id}/payments/` · any role (scoped) · `GET /payments/` · `GET /payments/{id}/`
Paginated, newest first. Staff/admin see everything; **a customer sees only payments on their own invoices** (other ids → 404) and only the customer-safe fields.
Filters on `/payments/`: `invoice`, `status`, `method`, `customer`, `payment_date_after`, `payment_date_before` (inclusive), `needs_attention=true` (payments of flagged invoices); `?search=` on invoice number, customer email, note; `?ordering=` on `payment_date, amount, id, attempt_number`.
Payment fields (staff/admin): `id, invoice, invoice_number, customer_email, amount, method, payment_date, note, status, attempt_number, retry_of, retried_by (id of the retrying row|null), failure_reason, recorded_by_email, created_at, reversed_at, reversed_by_email, reversal_reason, odoo_sync_status`; the detail adds `events:[{kind, by_user_email, at, detail}]` (the audit trail: `recorded | failed | retried | reversed | attention_flagged | attention_reset`). Customers get `id, invoice, invoice_number, amount, method, payment_date, status, attempt_number, created_at` only.

### Invoice changes
List/detail gain `payment_needs_attention` and `failed_attempts` (staff/admin only; removed for customers). Detail also has `max_payment_attempts` (the configured limit, staff/admin only), `payments` and the actions `"pay"` (confirmed, balance > 0, attempts left, staff/admin) and `"reset_attempts"` (flagged, admin). `GET /invoices/?needs_attention=true` lists flagged invoices. Overdue is unchanged (D-013): a partial payment leaves an invoice overdue; the payment that clears the balance makes it `paid`; a reversal can make it overdue again.

### Odoo
Payment mirroring to Odoo is optional and **not implemented** (KICKOFF §9 cut): `odoo_sync_status` stays `skipped`, nothing in the payment flow calls Odoo, and everything works with `ODOO_ENABLED=false` (and with it `true`: a test proves no Odoo call is made).

## Phase 7 — Notifications (D-043)
Events wired: `WELCOME` (signup), `QUOTATION_READY` (→ quotation), `SUBSCRIPTION_ACTIVATED` (→ active), `INVOICE_READY` (confirm / send), `PAYMENT_RECEIVED` (completed payment) and the reminders `INVOICE_DUE_SOON`, `INVOICE_OVERDUE`, `SUBSCRIPTION_EXPIRING`. Password reset stays email-only and outside `notify()` (D-022).
Log row: `{id, event, event_label, channel, provider, recipient_user, recipient_email, recipient_address, object_type, object_id, body, status, skip_reason, error, attempts, next_attempt_at, created_at, sent_at}`.

| Method · path | Role | Notes |
|---|---|---|
| `GET /notifications/logs/` | admin · staff (only with both `object_type` and `object_id`, for the timeline on invoice / subscription detail; else 403) | Paginated, newest first. Filters: `event` (code), `channel`, `status`, `user`, `object_type`, `object_id`, `created_after`, `created_before` |
| `POST /notifications/logs/{id}/retry/` | admin | `failed` rows only (else 409). Resets `attempts` to 0 and sends now; returns the row |
| `GET /notifications/events/` | admin | One row per event in the catalog (created on first read): `{code, label, enabled_email, enabled_whatsapp, template_body}` |
| `PATCH /notifications/events/{code}/` | admin | `enabled_email`, `enabled_whatsapp`, `template_body` (must be non-empty) |
| `POST /notifications/test-send/` `{channel, to, body}` | admin | Sends directly, writes no log row. `to` is an email or a number (normalised to E.164). → `{ok, provider, detail}`; a provider failure is 200 `ok:false` with the reason |
| `POST /notifications/run-reminders/` `{as_of?}` | admin | Runs the reminder scan → `{as_of, due_soon, overdue, expiring}` (counts of new messages; reruns give 0) |
| `GET /notifications/provider-status/` | admin | `{provider, configured, sandbox}` for the banner |
| `GET /me/notifications/` | any logged-in | Own timeline only: `{id, event_label, channel, status, body, created_at, sent_at}` |
| `GET\|PATCH /me/notification-settings/` | customer (others 404) | `{email_notifications, whatsapp_number, whatsapp_opt_in}`; same validation as `PATCH /auth/me/` profile |
| `POST /invoices/{id}/send/` | staff, admin | unchanged from Phase 4 (`channels` selects email and/or WhatsApp) |

Skip reasons on a `skipped` row: `event_disabled`, `email_opt_out`, `no_opt_in`, `invalid_number`, `provider_disabled` (WhatsApp provider selected but not configured).
Delivery: `sent` after the provider accepts; `failed` rows retry at +1 min, +5 min, +30 min (3 attempts) via `manage.py send_notifications`.

## Phase 8 — Portal/Dashboard (planned)
`GET /dashboard/summary/?from&to&customer&plan&status` → `{kpis, by_plan, by_month, overdue:{count,results}}`.
Portal reuses `/subscriptions/` and `/invoices/` (scoped by role); no separate endpoints.


### Dashboard (as built)
`GET /dashboard/summary/` (any role, scoped by `for_user`) → `{kpis:{active_subscriptions, revenue_collected, outstanding, overdue_count, overdue_amount}, subscriptions:{status:count}, invoices:{draft,confirmed,paid}, by_month:[{month, invoiced, collected}] (last 6), recent_payments:[{id,status,method,amount,invoice,at}]}`; money as strings.
