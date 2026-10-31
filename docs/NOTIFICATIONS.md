# Notifications

> Authored in Phase 0 from D-020…D-025 and KICKOFF §8 Phase 7 (the original file was not in the repo — D-027). Keep in sync as you build.

## 1. Architecture
One entry point: `notifications.services.notify(event_code, user, obj, *, channels=None, force=False, context=None)`.
It renders the event template, then for each enabled channel (email, whatsapp) creates a `NotificationLog` row (status `queued`) and
dispatches in `transaction.on_commit`. **Sending never raises into the caller**: any failure becomes `failed`/`skipped` on the log row.
```
business code ── notify() ──► NotificationLog(queued, dedupe_key) ──on_commit──► channel.send()
                                                        email: Django EmailBackend (console by default / SMTP)
                                                        whatsapp: provider.send(to_e164, body) → console | twilio | meta
```
Retry: `manage.py send_notifications` picks `failed`/`queued` rows with `attempts < 3` and `next_attempt_at <= now` (backoff 1 min, 5 min, 30 min).
Reminders: `manage.py run_notifications` (called at the end of `run_billing`, by an admin button, or cron).

## 2. Provider decision (D-021, D-025)
| Provider | Use | Notes |
|---|---|---|
| `console` | default, tests, offline demo | writes the message to the log/stdout, marks `sent` |
| `twilio` | judged demo | WhatsApp **sandbox**: each phone must send the join code first; reaches only joined numbers; free-form text only inside the 24 h session window |
| `meta` | **cut** (D-043) | WhatsApp Cloud API; production needs a verified business + approved templates (`meta_template_name`). Selecting it skips WhatsApp rows as `provider_disabled` |
Selected by `WHATSAPP_PROVIDER`. The app is fully functional with `console`. Say in the pitch: production = verified business account + approved templates.

## 3. Eligibility rules
- Email: `CustomerProfile.email_notifications` true (default) and event `enabled_email`.
- WhatsApp: event `enabled_whatsapp` **and** `whatsapp_opt_in` true **and** valid E.164 number (10-digit input → `+91`); otherwise log `skipped` with `skip_reason` (`no_opt_in`, `invalid_number`, `provider_disabled`).
- Password-reset links are email-only (D-022). Staff/admin recipients only get events explicitly addressed to them.

## 4. De-duplication (D-023)
`dedupe_key = "{event}:{object_type}:{object_id}:{channel}:{variant}"`, UNIQUE. Insert-or-skip makes billing/reminder reruns idempotent.
`variant` carries the reminder stage (`d3`, `d1`, `d7`, `exp7`). Manual "Send" passes `force=True` → key gets a timestamp suffix.

## 5. Event catalog
| Code | Trigger | Recipient | Channels | Variant |
|---|---|---|---|---|
| `WELCOME` | signup | customer | email, WA | — |
| `QUOTATION_READY` | subscription → quotation | customer | email, WA | — |
| `SUBSCRIPTION_ACTIVATED` | subscription → active | customer | email, WA | — |
| `INVOICE_READY` | invoice confirm / manual send | customer | email, WA | — |
| `PAYMENT_RECEIVED` | payment recorded | customer | email, WA | payment id |
| `INVOICE_DUE_SOON` | `due_date − today == NOTIFY_DUE_SOON_DAYS` | customer | email, WA | `d3` |
| `INVOICE_OVERDUE` | days overdue ∈ `NOTIFY_OVERDUE_DAYS` (1, 7) | customer | email, WA | `d1`, `d7` |
| `SUBSCRIPTION_EXPIRING` | `expiry_date − today == NOTIFY_EXPIRING_DAYS` | customer | email, WA | `exp7` |
| `PASSWORD_RESET` | reset request | user | email only | — |
| `BILLING_RUN_SUMMARY` *(cut-line 1)* | end of run | admin | email | run id |

## 6. API (Phase 7, built — exact contract in `docs/API.md`)
| Method | Path | Role |
|---|---|---|
| GET | `/notifications/logs/` (filters: event, channel, status, user, object_type, object_id, created_after/before) | admin; staff only when `object_type` + `object_id` are given (timeline); customers: own via `/me/notifications/` |
| POST | `/notifications/logs/{id}/retry/` | admin |
| GET/PATCH | `/notifications/events/` (enable per channel, template body) | admin |
| POST | `/notifications/test-send/ {channel, to, body}` | admin |
| GET/PATCH | `/me/notification-settings/` | any logged-in |
| POST | `/notifications/run-reminders/` | admin |
| POST | `/invoices/{id}/send/ {channels:[email,whatsapp]}` | staff, admin |
Also `GET /notifications/provider-status/` → `{provider, configured, sandbox}` for the admin banner.

## 7. Settings
`WHATSAPP_PROVIDER`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` (`whatsapp:+14155238886` sandbox),
`META_WA_PHONE_NUMBER_ID`, `META_WA_ACCESS_TOKEN`, `META_WA_API_VERSION`, `NOTIFY_DUE_SOON_DAYS=3`, `NOTIFY_OVERDUE_DAYS=1,7`, `NOTIFY_EXPIRING_DAYS=7`.

## 8. Message templates
Plain text with `{customer_name}`, `{invoice_number}`, `{amount}` (string, `₹` prefixed at render), `{due_date}`, `{link}` (`SITE_URL/portal/invoices/<id>`).
Example `INVOICE_READY`: `Hi {customer_name}, invoice {invoice_number} for ₹{amount} is ready. Due {due_date}. View: {link}`.

## 9. Mandatory tests (8)
1. `notify()` writes a log row and sends via `console` provider → status `sent`.
2. Same event+object+channel twice → one row (dedupe); `force=True` → second row.
3. WhatsApp without opt-in → `skipped` / `no_opt_in`; with opt-in + number → sent.
4. Invalid / 10-digit numbers normalised to E.164 (`+91…`) or `skipped` / `invalid_number`.
5. Rerunning `run_billing` and `run_notifications` creates no new log rows.
6. Provider raising → log `failed`, `attempts=1`, originating request still succeeds (invoice confirm returns 200).
7. Retry command: `failed` row with `attempts<3` is re-sent; at 3 attempts it stays `failed`.
8. Reminder windows: due-soon at exactly 3 days, overdue at day 1 and 7, expiring at 7; not on other days.

## 10. Demo checklist
- [ ] `WHATSAPP_PROVIDER=twilio`, demo phone joined to the sandbox just before judging
- [ ] Admin → Notifications → Test send reaches the phone
- [ ] Confirm an invoice → WhatsApp + email; record a payment → WhatsApp + email
- [ ] Re-run billing and reminders → log shows no duplicates
- [ ] Fallback: `WHATSAPP_PROVIDER=console` and show the log screen
