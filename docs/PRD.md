<<<<<<< HEAD
=======
<<<<<<< HEAD
<<<<<<< HEAD
>>>>>>> recovery-old-main
# PRD — Subscription Management System (Brightloop Software)

Version 1.0 · Hackathon online round · Companion to `KICKOFF.md` (build plan) and `docs/DECISIONS.md` (D-xxx references)

---

## 1. Summary

Brightloop Software sells software on subscription (monthly/yearly plans, add-ons, product variants). Today subscriptions live in a spreadsheet, renewals are remembered by whoever notices, invoices are typed by hand, payments are matched by scrolling bank statements, and revenue reports are built manually each quarter. Result: missed renewals, wrong invoices, and nobody can say how much recurring revenue exists.

**Product:** one platform that runs the whole subscription lifecycle: catalog and plans → quotation → subscription → automatic recurring invoicing → discounts → payments → finance reporting, with a self-service customer portal. Accounting records are mirrored to Odoo.

## 2. Goals and non-goals

**Goals**
1. Replace every manual step in the "How things run today" list with a system action.
2. Guarantee billing correctness: every due period billed exactly once.
3. Give each role exactly the access it needs; customers see only their own data.
4. Give finance one place to answer: active subscriptions, revenue, outstanding, overdue.
5. Stay responsive (< 2 s per page) with thousands of subscriptions.
6. Mirror customers, products, taxes and invoices into Odoo as the accounting ledger.

**Non-goals (v1)**
- Payment gateway / card processing (payments are recorded manually)
- Proration, mid-cycle upgrades/downgrades, usage-based billing
- Multi-currency, multi-company, multi-step dunning sequences (only the single reminders in §5.8)
- Two-way WhatsApp chat, support bot, or broadcast campaigns
- Odoo-hosted authentication, or building a native Odoo module
- Mobile apps (responsive web only)

## 3. Users and roles

| Role | Who | Can do | Cannot do |
|---|---|---|---|
| **Admin** | Brightloop system owner | Everything: catalog, plans, taxes, payment terms, discounts, staff accounts, all operations, billing, dashboard | — |
| **Staff** | Internal team, day-to-day | Create/manage quotations and subscriptions, attach existing discounts, run billing, confirm/cancel/send/print invoices, record payments, view dashboard, view catalog | Create staff, create/edit discount rules, edit taxes/plans/products |
| **Customer** | Small shop to large company | Sign up, log in, reset password, view own subscriptions and invoices, print own invoices | See any other customer's data; any internal screen |

## 4. Scope tiers

**MVP (must ship):** auth + roles, catalog (products, variants, taxes, payment terms, plans), subscriptions with lifecycle, automatic billing with tax, invoice workflow, payments → Paid, discounts with auto-apply and limits, finance dashboard, row-level access, performance on seeded data, Odoo mirroring of partners/products/taxes/invoices (or graceful `skipped`).

**Should:** quotation templates with validity, customer portal, invoice "send" by email and print view, overdue highlighting, WhatsApp + email notifications (§5.8).

**Nice (only if ahead):** customer self-service pause/close/renew, charts, CSV export, Odoo payment mirroring, Odoo PDF.

## 5. Functional requirements

Priority: **M** = MVP, **S** = Should, **N** = Nice. "Phase" refers to `KICKOFF.md`.

### 5.1 Accounts and access (Scene 1) — Phase 1

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-AUTH-01 | Customer self-signup with email + password | M | Creates a `customer` user and profile; cannot choose a role |
| FR-AUTH-02 | One account per email | M | Duplicate email (any letter case) rejected with a clear message |
| FR-AUTH-03 | Password policy | M | Length ≥ 9, ≥ 1 uppercase, ≥ 1 lowercase, ≥ 1 special character; exactly 8 chars rejected; enforced on signup, reset, staff creation |
| FR-AUTH-04 | Login / logout | M | Session login; wrong credentials give a generic error |
| FR-AUTH-05 | Password reset by email | M | Reset link emailed to the registered address; token single-use and expiring; new password must satisfy FR-AUTH-03 |
| FR-AUTH-06 | Three roles with different navigation and API permissions | M | Admin/Staff/Customer see different menus; forbidden API calls return 403 |
| FR-AUTH-07 | Only Admin can add staff | M | Staff and Customer calls to staff-creation return 403; Admin creates staff with a temporary password and role `staff` |
| FR-AUTH-08 | Row-level isolation for customers | M | A customer requesting another customer's subscription/invoice/payment gets 404 (enforced in queryset, not UI) |

### 5.2 Catalog and plans (Scene 2) — Phase 2

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-CAT-01 | Product with name, type, sales price, cost price, notes | M | Admin CRUD; staff read-only |
| FR-CAT-02 | Product variants (attribute/value/extra price) | M | Brand = Odoo adds 560; effective unit price = sales price + extra price |
| FR-CAT-03 | Taxes with rate, attachable to products | M | Admin CRUD; tax applied to invoice lines automatically (FR-BILL-04) |
| FR-CAT-04 | Payment terms (name, days) | M | Used for subscription terms and invoice due dates |
| FR-CAT-05 | Plan: price, billing period (daily/weekly/monthly/yearly), minimum quantity, availability dates | M | Validation: from ≤ to, min qty ≥ 1; a plan cannot be used outside its availability window |
| FR-CAT-06 | Per-plan behaviour flags: auto-close, allow early close, allow pause, allow renew | M | Admin sets per plan; lifecycle actions are refused when the flag is off (FR-SUB-05) |
| FR-CAT-07 | Mirror products and taxes to Odoo | S | Records show sync status; failure never blocks save |

### 5.3 Quotations and subscriptions (Scene 3) — Phase 3

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-SUB-01 | Quotation templates with plan, product lines, validity days | S | Creating a subscription from a template prefills lines and sets quotation valid-until = today + validity days |
| FR-SUB-02 | Subscription record | M | Unique auto number (SUB-000001), customer, plan, start date, expiry date, payment term, lines (product, quantity, unit price, taxes, amount) |
| FR-SUB-03 | Minimum quantity enforced | M | Primary product quantity < plan minimum is rejected |
| FR-SUB-04 | Lifecycle Draft → Quotation → Confirmed → Active → Closed | M | Illegal transitions rejected server-side; every transition logged with user and time; status visible to the whole team |
| FR-SUB-05 | Plan-governed actions | M | Pause, early close and renew only when the plan flag allows; auto-close at expiry only when `auto_close` is on |
| FR-SUB-06 | Subscription list with filters and search | M | Filter by status, customer, plan; search by number; paginated |

### 5.4 Invoicing (Scene 4) — Phase 4

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-BILL-01 | Automatic invoice generation from active subscriptions | M | Run via button or command; invoice carries customer, lines, taxes, totals, period, due date |
| FR-BILL-02 | Exactly-once billing | M | Running billing repeatedly or concurrently never creates a second invoice for the same subscription period (DB uniqueness + row locking) |
| FR-BILL-03 | Catch-up | M | Missed periods are each billed (cap 12 per run); nothing billed beyond expiry; paused/draft/closed skipped |
| FR-BILL-04 | Automatic tax | M | Tax computed from admin-defined rates on post-discount line amounts; example in §8 |
| FR-BILL-05 | Invoice workflow Draft → Confirmed → Paid, with Cancel | M | Confirm assigns invoice number; cancel allowed from Draft/Confirmed; Paid set automatically (FR-PAY-03) |
| FR-BILL-06 | Send and print | S | Send emails the invoice; print view renders cleanly to PDF via browser |
| FR-BILL-07 | Failure isolation | M | One failing subscription is logged in the billing run and does not stop others |
| FR-BILL-08 | Odoo mirror of invoices | S | Draft created in Odoo after local commit; posted on Confirm; Odoo being down leaves a local invoice marked `pending` and retryable |
| FR-BILL-09 | Billing run history | S | Each run shows created / skipped / error counts |

### 5.5 Discounts (Scene 5) — Phase 5

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-DISC-01 | Admin-only discount rules | M | Fixed or percent; minimum purchase amount and/or minimum quantity; start and end dates; usage limit; Staff creating one gets 403 |
| FR-DISC-02 | Scope: specific products or whole subscription | M | Product rules auto-apply to matching lines; subscription rules apply when attached to the subscription |
| FR-DISC-03 | Automatic application | M | Eligible discount appears on the next generated invoice as a separate negative line without manual action |
| FR-DISC-04 | Stops on expiry or exhaustion | M | After end date or when used count reaches limit, it is no longer applied; counter is race-safe |
| FR-DISC-05 | Audit | S | Redemption record per invoice; discount detail shows where it was used |

### 5.6 Payments (Scene 6) — Phase 6

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-PAY-01 | Record payment | M | Method, amount, date, note, against a Confirmed invoice |
| FR-PAY-02 | Validation | M | Amount > 0 and ≤ amount due; payment on Draft/Cancelled invoice rejected |
| FR-PAY-03 | Paid status | M | Invoice becomes Paid exactly when payments sum to the total (partial payments leave a balance) |
| FR-PAY-04 | Paid vs outstanding view | M | Invoice list filter: Paid / Outstanding / Overdue |
| FR-PAY-05 | Overdue identification | M | Confirmed, balance > 0, due date passed; shown with days overdue |
| FR-PAY-06 | Odoo payment mirror | N | Failure marks `error`, local record stays valid |

### 5.7 Finance dashboard and portal (Scene 7) — Phase 8

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-DASH-01 | KPIs | M | Active subscriptions, MRR, ARR, revenue collected (period), outstanding, overdue count and amount |
| FR-DASH-02 | Filters and summary | M | Filter by date range, customer, plan, status; summary by plan and by month |
| FR-DASH-03 | Overdue list | M | Sorted by days overdue, paginated |
| FR-DASH-04 | Performance | M | Every page and API list < 2 s on ~5k subscriptions / ~15k invoices / ~10k payments |
| FR-PORT-01 | Customer portal | S | Customer sees only their subscriptions and invoices, with detail and print |
| FR-PORT-02 | Self-service actions | N | Pause/close/renew where the plan flags allow |

### 5.8 Notifications: WhatsApp + email — Phases 4 and 7

Detail in `docs/NOTIFICATIONS.md`.

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-NOTIF-01 | Central notification service with email and WhatsApp channels | S | Domain events call one `notify()`; every attempt is logged with status, provider and error |
| FR-NOTIF-02 | WhatsApp opt-in and number capture | S | Optional E.164 number and explicit consent at signup/profile; no WhatsApp sent without opt-in and valid number |
| FR-NOTIF-03 | Event notifications | S | Welcome, quotation ready, subscription activated, invoice ready (on confirm), payment received (with balance / fully paid) |
| FR-NOTIF-04 | Reminders | S | Due-soon (3 days before), overdue (day 1 and day 7), expiring (7 days before); command or button driven |
| FR-NOTIF-05 | No duplicates | S | Re-running billing or reminders never re-sends the same notification (unique dedupe key); manual "Send" is an explicit forced send |
| FR-NOTIF-06 | Failure isolation and retry | S | Provider failure never fails the originating action; failed rows retried up to 3 times; admin can retry from the log |
| FR-NOTIF-07 | Pluggable provider | S | `console` (default), `twilio` sandbox for demo, `meta` optional; app fully works on `console` |
| FR-NOTIF-08 | Notification settings and admin console | S | Customer toggles WhatsApp/email and edits number; admin sees log, toggles events, sends a test message |
| FR-NOTIF-09 | Delivery-status webhook and STOP opt-out | N | Provider callbacks update status; inbound "STOP" clears opt-in |


## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | < 2 s per page; list endpoints paginated at 25; aggregate queries for KPIs; indexes on status, due date, customer |
| Correctness | Money as `Decimal(2dp)` server-side; idempotent billing; atomic discount counters; every state transition validated server-side |
| Security | Session auth with CSRF; authorization in queryset and permission classes; passwords hashed; reset tokens expiring; no secrets in repo |
| Reliability | Odoo or WhatsApp outage must not break any user flow; sync and notifications retryable; `ODOO_ENABLED=false` and `WHATSAPP_PROVIDER=console` supported |
| Auditability | Subscription status log; billing run log; discount redemptions; payment records with recorder |
| Usability | Role-aware navigation, empty/loading/error states, readable on laptop and phone |
| Deployability | One container serves API + SPA; `docker compose up`; demo logins documented |

## 7. Odoo integration requirements

| Local entity | Odoo model | Direction | When |
|---|---|---|---|
| Customer | `res.partner` | App → Odoo | On first invoice or on demand |
| Product | `product.product` | App → Odoo | On save |
| Tax | `account.tax` | Match/create | On save |
| Invoice | `account.move` | App → Odoo | Draft on creation; post on Confirm |
| Payment | `account.payment` | App → Odoo | Stretch |

Constraints: Odoo Community 18.0 (self-hosted, free); one wrapper module for all calls; field names verified with `fields_get`; sync states `skipped / pending / synced / error`; local data is authoritative for the dashboard.

## 8. Reference definitions

**Invoice example (acceptance test):** plan 1000/month, quantity 5, variant +560 → unit price 1560, subtotal 7800; 10 % product discount −780 → 7020; 18 % tax = 1263.60; **total 8283.60**.

**Overdue:** status Confirmed, amount due > 0, due date < today. Due date = invoice date + payment term days.

**MRR:** sum of active subscription line totals normalized to monthly (daily ×30, weekly ×52/12, monthly ×1, yearly ÷12). **ARR** = MRR × 12.

**Subscription states:** Draft → Quotation → Confirmed → Active → Closed (Paused as an Active side-state where the plan allows). **Invoice states:** Draft → Confirmed → Paid; Cancelled from Draft/Confirmed.

## 9. Success metrics (for the demo and judging)

| Metric | Target |
|---|---|
| Scenes demonstrable end to end | 7 of 7 |
| Duplicate invoices after repeated billing runs | 0 |
| Duplicate notifications after repeated billing/reminder runs | 0 |
| Cross-customer data leaks in access tests | 0 |
| Slowest page on seeded data | < 2 s |
| Time from signup to first paid invoice in demo | < 5 minutes |
| Mandatory backend tests passing | 100 % |

## 10. Assumptions and open questions

Assumptions are logged as D-001 to D-019 in `docs/DECISIONS.md` (plan price semantics, discount stacking, overdue definition, no overpayments, single currency, and so on). To confirm against the round instructions:

1. Is Odoo integration mandatory or optional for the round? (Plan degrades to `ODOO_ENABLED=false`.)
2. Required submission format: live link, repository, demo video, or all three?
3. Any mandated tech stack or Odoo version?
4. Whether discounts should be allowed to stack more broadly than D-010.
5. Whether "renew" should create a new subscription term or extend the current one (currently extends, D-014).
6. WhatsApp: which provider and credentials the team can get today (Twilio sandbox assumed), and whether the judges can see messages on a registered demo phone.

## 11. Traceability (scene → requirement → phase)

| Scene | Requirements | Phase |
|---|---|---|
| 1 Sign-up | FR-AUTH-01…08 | 1 |
| 2 Plan launch | FR-CAT-01…07 | 2 |
| 3 Quote → subscription | FR-SUB-01…06 | 3 |
| 4 Billing day | FR-BILL-01…09 | 4 |
| 5 Discounts | FR-DISC-01…05 | 5 |
| 6 Payments | FR-PAY-01…06 | 6 |
| 7 Finance + portal | FR-DASH-01…04, FR-PORT-01…02 | 8 |
| Notifications (cross-cutting) | FR-NOTIF-01…09 | 4, 7 |
| Hardening, demo, deploy | NFRs, success metrics | 9 |

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Time (6 h for 7 scenes + Odoo + React) | Incomplete scenes | Cut-line in `KICKOFF.md` §9; protect Phase 4 |
| Odoo setup or API friction | Integration incomplete | `ODOO_ENABLED=false` fallback; wrapper isolation |
| Billing bug creates duplicates or skips | Fails the core requirement | DB uniqueness, row locks, eight mandatory billing tests |
| Dashboard slow at scale | Fails the 2 s requirement | Aggregates, denormalized balances, perf gate on seed data |
| Access control only in UI | Data exposure | Queryset-level scoping, isolation tests |
| WhatsApp sandbox limits (registered numbers, 24 h window) | Notification demo fails live | `console` fallback, test-send before judging, honest pitch note |
<<<<<<< HEAD
=======
=======
# PRD — Brightloop subscription management
=======
# PRD — Subscription Management System (Brightloop Software)
>>>>>>> other-repo/phase-5-discounts

Version 1.0 · Hackathon online round · Companion to `KICKOFF.md` (build plan) and `docs/DECISIONS.md` (D-xxx references)

---

## 1. Summary

Brightloop Software sells software on subscription (monthly/yearly plans, add-ons, product variants). Today subscriptions live in a spreadsheet, renewals are remembered by whoever notices, invoices are typed by hand, payments are matched by scrolling bank statements, and revenue reports are built manually each quarter. Result: missed renewals, wrong invoices, and nobody can say how much recurring revenue exists.

**Product:** one platform that runs the whole subscription lifecycle: catalog and plans → quotation → subscription → automatic recurring invoicing → discounts → payments → finance reporting, with a self-service customer portal. Accounting records are mirrored to Odoo.

## 2. Goals and non-goals

**Goals**
1. Replace every manual step in the "How things run today" list with a system action.
2. Guarantee billing correctness: every due period billed exactly once.
3. Give each role exactly the access it needs; customers see only their own data.
4. Give finance one place to answer: active subscriptions, revenue, outstanding, overdue.
5. Stay responsive (< 2 s per page) with thousands of subscriptions.
6. Mirror customers, products, taxes and invoices into Odoo as the accounting ledger.

**Non-goals (v1)**
- Payment gateway / card processing (payments are recorded manually)
- Proration, mid-cycle upgrades/downgrades, usage-based billing
- Multi-currency, multi-company, multi-step dunning sequences (only the single reminders in §5.8)
- Two-way WhatsApp chat, support bot, or broadcast campaigns
- Odoo-hosted authentication, or building a native Odoo module
- Mobile apps (responsive web only)

## 3. Users and roles

| Role | Who | Can do | Cannot do |
|---|---|---|---|
| **Admin** | Brightloop system owner | Everything: catalog, plans, taxes, payment terms, discounts, staff accounts, all operations, billing, dashboard | — |
| **Staff** | Internal team, day-to-day | Create/manage quotations and subscriptions, attach existing discounts, run billing, confirm/cancel/send/print invoices, record payments, view dashboard, view catalog | Create staff, create/edit discount rules, edit taxes/plans/products |
| **Customer** | Small shop to large company | Sign up, log in, reset password, view own subscriptions and invoices, print own invoices | See any other customer's data; any internal screen |

## 4. Scope tiers

**MVP (must ship):** auth + roles, catalog (products, variants, taxes, payment terms, plans), subscriptions with lifecycle, automatic billing with tax, invoice workflow, payments → Paid, discounts with auto-apply and limits, finance dashboard, row-level access, performance on seeded data, Odoo mirroring of partners/products/taxes/invoices (or graceful `skipped`).

**Should:** quotation templates with validity, customer portal, invoice "send" by email and print view, overdue highlighting, WhatsApp + email notifications (§5.8).

**Nice (only if ahead):** customer self-service pause/close/renew, charts, CSV export, Odoo payment mirroring, Odoo PDF.

## 5. Functional requirements

Priority: **M** = MVP, **S** = Should, **N** = Nice. "Phase" refers to `KICKOFF.md`.

### 5.1 Accounts and access (Scene 1) — Phase 1

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-AUTH-01 | Customer self-signup with email + password | M | Creates a `customer` user and profile; cannot choose a role |
| FR-AUTH-02 | One account per email | M | Duplicate email (any letter case) rejected with a clear message |
| FR-AUTH-03 | Password policy | M | Length ≥ 9, ≥ 1 uppercase, ≥ 1 lowercase, ≥ 1 special character; exactly 8 chars rejected; enforced on signup, reset, staff creation |
| FR-AUTH-04 | Login / logout | M | Session login; wrong credentials give a generic error |
| FR-AUTH-05 | Password reset by email | M | Reset link emailed to the registered address; token single-use and expiring; new password must satisfy FR-AUTH-03 |
| FR-AUTH-06 | Three roles with different navigation and API permissions | M | Admin/Staff/Customer see different menus; forbidden API calls return 403 |
| FR-AUTH-07 | Only Admin can add staff | M | Staff and Customer calls to staff-creation return 403; Admin creates staff with a temporary password and role `staff` |
| FR-AUTH-08 | Row-level isolation for customers | M | A customer requesting another customer's subscription/invoice/payment gets 404 (enforced in queryset, not UI) |

### 5.2 Catalog and plans (Scene 2) — Phase 2

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-CAT-01 | Product with name, type, sales price, cost price, notes | M | Admin CRUD; staff read-only |
| FR-CAT-02 | Product variants (attribute/value/extra price) | M | Brand = Odoo adds 560; effective unit price = sales price + extra price |
| FR-CAT-03 | Taxes with rate, attachable to products | M | Admin CRUD; tax applied to invoice lines automatically (FR-BILL-04) |
| FR-CAT-04 | Payment terms (name, days) | M | Used for subscription terms and invoice due dates |
| FR-CAT-05 | Plan: price, billing period (daily/weekly/monthly/yearly), minimum quantity, availability dates | M | Validation: from ≤ to, min qty ≥ 1; a plan cannot be used outside its availability window |
| FR-CAT-06 | Per-plan behaviour flags: auto-close, allow early close, allow pause, allow renew | M | Admin sets per plan; lifecycle actions are refused when the flag is off (FR-SUB-05) |
| FR-CAT-07 | Mirror products and taxes to Odoo | S | Records show sync status; failure never blocks save |

### 5.3 Quotations and subscriptions (Scene 3) — Phase 3

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-SUB-01 | Quotation templates with plan, product lines, validity days | S | Creating a subscription from a template prefills lines and sets quotation valid-until = today + validity days |
| FR-SUB-02 | Subscription record | M | Unique auto number (SUB-000001), customer, plan, start date, expiry date, payment term, lines (product, quantity, unit price, taxes, amount) |
| FR-SUB-03 | Minimum quantity enforced | M | Primary product quantity < plan minimum is rejected |
| FR-SUB-04 | Lifecycle Draft → Quotation → Confirmed → Active → Closed | M | Illegal transitions rejected server-side; every transition logged with user and time; status visible to the whole team |
| FR-SUB-05 | Plan-governed actions | M | Pause, early close and renew only when the plan flag allows; auto-close at expiry only when `auto_close` is on |
| FR-SUB-06 | Subscription list with filters and search | M | Filter by status, customer, plan; search by number; paginated |

### 5.4 Invoicing (Scene 4) — Phase 4

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-BILL-01 | Automatic invoice generation from active subscriptions | M | Run via button or command; invoice carries customer, lines, taxes, totals, period, due date |
| FR-BILL-02 | Exactly-once billing | M | Running billing repeatedly or concurrently never creates a second invoice for the same subscription period (DB uniqueness + row locking) |
| FR-BILL-03 | Catch-up | M | Missed periods are each billed (cap 12 per run); nothing billed beyond expiry; paused/draft/closed skipped |
| FR-BILL-04 | Automatic tax | M | Tax computed from admin-defined rates on post-discount line amounts; example in §8 |
| FR-BILL-05 | Invoice workflow Draft → Confirmed → Paid, with Cancel | M | Confirm assigns invoice number; cancel allowed from Draft/Confirmed; Paid set automatically (FR-PAY-03) |
| FR-BILL-06 | Send and print | S | Send emails the invoice; print view renders cleanly to PDF via browser |
| FR-BILL-07 | Failure isolation | M | One failing subscription is logged in the billing run and does not stop others |
| FR-BILL-08 | Odoo mirror of invoices | S | Draft created in Odoo after local commit; posted on Confirm; Odoo being down leaves a local invoice marked `pending` and retryable |
| FR-BILL-09 | Billing run history | S | Each run shows created / skipped / error counts |

### 5.5 Discounts (Scene 5) — Phase 5

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-DISC-01 | Admin-only discount rules | M | Fixed or percent; minimum purchase amount and/or minimum quantity; start and end dates; usage limit; Staff creating one gets 403 |
| FR-DISC-02 | Scope: specific products or whole subscription | M | Product rules auto-apply to matching lines; subscription rules apply when attached to the subscription |
| FR-DISC-03 | Automatic application | M | Eligible discount appears on the next generated invoice as a separate negative line without manual action |
| FR-DISC-04 | Stops on expiry or exhaustion | M | After end date or when used count reaches limit, it is no longer applied; counter is race-safe |
| FR-DISC-05 | Audit | S | Redemption record per invoice; discount detail shows where it was used |

### 5.6 Payments (Scene 6) — Phase 6

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-PAY-01 | Record payment | M | Method, amount, date, note, against a Confirmed invoice |
| FR-PAY-02 | Validation | M | Amount > 0 and ≤ amount due; payment on Draft/Cancelled invoice rejected |
| FR-PAY-03 | Paid status | M | Invoice becomes Paid exactly when payments sum to the total (partial payments leave a balance) |
| FR-PAY-04 | Paid vs outstanding view | M | Invoice list filter: Paid / Outstanding / Overdue |
| FR-PAY-05 | Overdue identification | M | Confirmed, balance > 0, due date passed; shown with days overdue |
| FR-PAY-06 | Odoo payment mirror | N | Failure marks `error`, local record stays valid |

### 5.7 Finance dashboard and portal (Scene 7) — Phase 8

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-DASH-01 | KPIs | M | Active subscriptions, MRR, ARR, revenue collected (period), outstanding, overdue count and amount |
| FR-DASH-02 | Filters and summary | M | Filter by date range, customer, plan, status; summary by plan and by month |
| FR-DASH-03 | Overdue list | M | Sorted by days overdue, paginated |
| FR-DASH-04 | Performance | M | Every page and API list < 2 s on ~5k subscriptions / ~15k invoices / ~10k payments |
| FR-PORT-01 | Customer portal | S | Customer sees only their subscriptions and invoices, with detail and print |
| FR-PORT-02 | Self-service actions | N | Pause/close/renew where the plan flags allow |

### 5.8 Notifications: WhatsApp + email — Phases 4 and 7

Detail in `docs/NOTIFICATIONS.md`.

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-NOTIF-01 | Central notification service with email and WhatsApp channels | S | Domain events call one `notify()`; every attempt is logged with status, provider and error |
| FR-NOTIF-02 | WhatsApp opt-in and number capture | S | Optional E.164 number and explicit consent at signup/profile; no WhatsApp sent without opt-in and valid number |
| FR-NOTIF-03 | Event notifications | S | Welcome, quotation ready, subscription activated, invoice ready (on confirm), payment received (with balance / fully paid) |
| FR-NOTIF-04 | Reminders | S | Due-soon (3 days before), overdue (day 1 and day 7), expiring (7 days before); command or button driven |
| FR-NOTIF-05 | No duplicates | S | Re-running billing or reminders never re-sends the same notification (unique dedupe key); manual "Send" is an explicit forced send |
| FR-NOTIF-06 | Failure isolation and retry | S | Provider failure never fails the originating action; failed rows retried up to 3 times; admin can retry from the log |
| FR-NOTIF-07 | Pluggable provider | S | `console` (default), `twilio` sandbox for demo, `meta` optional; app fully works on `console` |
| FR-NOTIF-08 | Notification settings and admin console | S | Customer toggles WhatsApp/email and edits number; admin sees log, toggles events, sends a test message |
| FR-NOTIF-09 | Delivery-status webhook and STOP opt-out | N | Provider callbacks update status; inbound "STOP" clears opt-in |


## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | < 2 s per page; list endpoints paginated at 25; aggregate queries for KPIs; indexes on status, due date, customer |
| Correctness | Money as `Decimal(2dp)` server-side; idempotent billing; atomic discount counters; every state transition validated server-side |
| Security | Session auth with CSRF; authorization in queryset and permission classes; passwords hashed; reset tokens expiring; no secrets in repo |
| Reliability | Odoo or WhatsApp outage must not break any user flow; sync and notifications retryable; `ODOO_ENABLED=false` and `WHATSAPP_PROVIDER=console` supported |
| Auditability | Subscription status log; billing run log; discount redemptions; payment records with recorder |
| Usability | Role-aware navigation, empty/loading/error states, readable on laptop and phone |
| Deployability | One container serves API + SPA; `docker compose up`; demo logins documented |

## 7. Odoo integration requirements

| Local entity | Odoo model | Direction | When |
|---|---|---|---|
| Customer | `res.partner` | App → Odoo | On first invoice or on demand |
| Product | `product.product` | App → Odoo | On save |
| Tax | `account.tax` | Match/create | On save |
| Invoice | `account.move` | App → Odoo | Draft on creation; post on Confirm |
| Payment | `account.payment` | App → Odoo | Stretch |

<<<<<<< HEAD
## Out of scope
Multi-currency, proration, dunning beyond reminders, payment gateways (payments are recorded manually), tax regimes beyond admin-managed rates, SSO.
>>>>>>> origin/main
=======
Constraints: Odoo Community 18.0 (self-hosted, free); one wrapper module for all calls; field names verified with `fields_get`; sync states `skipped / pending / synced / error`; local data is authoritative for the dashboard.

## 8. Reference definitions

**Invoice example (acceptance test):** plan 1000/month, quantity 5, variant +560 → unit price 1560, subtotal 7800; 10 % product discount −780 → 7020; 18 % tax = 1263.60; **total 8283.60**.

**Overdue:** status Confirmed, amount due > 0, due date < today. Due date = invoice date + payment term days.

**MRR:** sum of active subscription line totals normalized to monthly (daily ×30, weekly ×52/12, monthly ×1, yearly ÷12). **ARR** = MRR × 12.

**Subscription states:** Draft → Quotation → Confirmed → Active → Closed (Paused as an Active side-state where the plan allows). **Invoice states:** Draft → Confirmed → Paid; Cancelled from Draft/Confirmed.

## 9. Success metrics (for the demo and judging)

| Metric | Target |
|---|---|
| Scenes demonstrable end to end | 7 of 7 |
| Duplicate invoices after repeated billing runs | 0 |
| Duplicate notifications after repeated billing/reminder runs | 0 |
| Cross-customer data leaks in access tests | 0 |
| Slowest page on seeded data | < 2 s |
| Time from signup to first paid invoice in demo | < 5 minutes |
| Mandatory backend tests passing | 100 % |

## 10. Assumptions and open questions

Assumptions are logged as D-001 to D-019 in `docs/DECISIONS.md` (plan price semantics, discount stacking, overdue definition, no overpayments, single currency, and so on). To confirm against the round instructions:

1. Is Odoo integration mandatory or optional for the round? (Plan degrades to `ODOO_ENABLED=false`.)
2. Required submission format: live link, repository, demo video, or all three?
3. Any mandated tech stack or Odoo version?
4. Whether discounts should be allowed to stack more broadly than D-010.
5. Whether "renew" should create a new subscription term or extend the current one (currently extends, D-014).
6. WhatsApp: which provider and credentials the team can get today (Twilio sandbox assumed), and whether the judges can see messages on a registered demo phone.

## 11. Traceability (scene → requirement → phase)

| Scene | Requirements | Phase |
|---|---|---|
| 1 Sign-up | FR-AUTH-01…08 | 1 |
| 2 Plan launch | FR-CAT-01…07 | 2 |
| 3 Quote → subscription | FR-SUB-01…06 | 3 |
| 4 Billing day | FR-BILL-01…09 | 4 |
| 5 Discounts | FR-DISC-01…05 | 5 |
| 6 Payments | FR-PAY-01…06 | 6 |
| 7 Finance + portal | FR-DASH-01…04, FR-PORT-01…02 | 8 |
| Notifications (cross-cutting) | FR-NOTIF-01…09 | 4, 7 |
| Hardening, demo, deploy | NFRs, success metrics | 9 |

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Time (6 h for 7 scenes + Odoo + React) | Incomplete scenes | Cut-line in `KICKOFF.md` §9; protect Phase 4 |
| Odoo setup or API friction | Integration incomplete | `ODOO_ENABLED=false` fallback; wrapper isolation |
| Billing bug creates duplicates or skips | Fails the core requirement | DB uniqueness, row locks, eight mandatory billing tests |
| Dashboard slow at scale | Fails the 2 s requirement | Aggregates, denormalized balances, perf gate on seed data |
| Access control only in UI | Data exposure | Queryset-level scoping, isolation tests |
| WhatsApp sandbox limits (registered numbers, 24 h window) | Notification demo fails live | `console` fallback, test-send before judging, honest pitch note |
>>>>>>> other-repo/phase-5-discounts
>>>>>>> recovery-old-main
