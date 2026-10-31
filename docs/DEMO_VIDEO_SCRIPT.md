# Brightloop — Demo Video Script (~7 min)

Narrated walkthrough that follows "A Month at Brightloop" from the brief, one scene per section (S1–S7).
Click-by-click data and seed values live in `DEMO_SCRIPT.md`; this file adds voice-over and timing.

**Pre-flight:** fresh DB → `python scripts/seed_demo.py` (use `--big` for the S7 perf shot), `ODOO_ENABLED=true`, three browser profiles (admin / staff / customer), 1080p, zoom 110%.
Logins are in `DEMO_SCRIPT.md`; blur or skip the password field on camera.

---

## 0. Hook (0:00–0:20)
**Screen:** Title card, then the login page.
**Say:** "Brightloop sells everything on subscription, but today it runs on spreadsheets. Renewals get missed, invoices are typed by hand, and nobody knows the real recurring revenue. This is the system that replaces all of that."

## 1. A new customer signs up (0:20–1:20) — S1
| Screen | Say |
|---|---|
| `/signup`. Enter `weakpass`. Inline password errors appear. | "A new customer creates an account. The password needs more than eight characters, with upper case, lower case and a special character. Weak ones are rejected." |
| Retry with `NEW@demo.com` after `new@demo.com` exists. "Account with this email already exists." | "Each email can belong to only one account, regardless of case." |
| Sign up with `Strong@Pass1`. Land in the customer portal. | "A valid signup creates a customer and opens their own portal." |
| Log out. **Forgot password**, show the reset link in the console or email log, set a new password, log in. | "Forgot the password? A reset link goes to the registered email." |
| Customer portal: only "My subscriptions" and "My invoices". Type `/staff` in the URL. Forbidden page. | "Customers see only their own subscriptions and invoices. Internal screens are blocked, and the API enforces it too." |
| Admin profile, **Staff**: create `ops@demo.com`. Switch to staff: no Staff or Notifications menu. | "Only the admin can add staff. Staff get day-to-day tools with limited access." |

## 2. Launching a new plan (1:20–2:20) — S2
| Screen | Say |
|---|---|
| Admin, **Catalog → Taxes**: `GST 18%`. **Terms**: `Net 15`. | "Taxes and payment terms are set once by the admin and reused everywhere." |
| **Products → New**: `Brightloop CRM`, type, sales 1000.00, cost 400.00, notes. | "A product has a name, type, sales price, cost price and notes." |
| Add variant **Brand = Odoo**, extra price **560.00**. Show unit price 1560.00. | "Variants carry an extra price. Choosing the Odoo brand adds 560." |
| **Plans → New**: `CRM Monthly`, price, period dropdown (daily / weekly / monthly / yearly), min qty, available dates. | "A plan sets the price, how often it bills, the minimum quantity and the dates it is on sale." |
| Toggle auto-close, early close, pause, renew. | "The admin decides plan by plan: close on its own, close early, pause or renew." |
| Switch to staff: Catalog is read-only. | "Staff can see the catalog but not change it." |

## 3. Quote to subscription (2:20–3:30) — S3
| Screen | Say |
|---|---|
| **Subscriptions → Templates**: `CRM Starter`, plan, validity 15 days, line CRM × 5. | "A sales rep starts from a quotation template with the right plan and product lines. It stays valid for a set number of days." |
| **New from template**, customer `customer@demo`, start and expiry dates, term Net 15. Lines: 5 × 1560.00 = 7800.00. | "Pick the template and customer. Lines fill in with product, quantity, unit price, taxes and amount." |
| Detail page: subscription number, timeline. Click through **Quotation → Confirmed → Active**. | "Each subscription gets its own number. It moves Draft, Quotation, Confirmed, Active, and finally Closed. The badge and timeline show anyone on the team where it stands." |
| Point out that only legal buttons appear. | "Illegal transitions aren't offered, and the API rejects them too." |

## 4. Billing day (3:30–4:40) — S4
| Screen | Say |
|---|---|
| **Billing → Run billing**. Result: created 1, skipped 0, errors 0. | "It's billing day. Nobody types invoices. One click creates them from the subscriptions that are due." |
| **Run billing again**: created 0. | "Run it twice and nothing is billed twice. Each subscription and period is unique." |
| **Invoices**: open the draft. Customer, lines, tax 18%, totals 7800.00 + 1404.00 = 9204.00. | "Customer details, lines, tax and totals are already filled in. Tax comes from the admin's rules." |
| **Confirm**, then **Send**, then **Print** (preview). Show **Cancel** on a draft. | "The team can confirm, cancel, send or print any invoice. It moves Draft, Confirmed, Paid." |
| Odoo badge `synced`. Briefly show the invoice in Odoo. | "Each invoice is mirrored to Odoo, our accounting ledger. If Odoo is down, nothing local is lost." |

## 5. A better price (4:40–5:25) — S5
| Screen | Say |
|---|---|
| Staff opens **Discounts**: no create option. Try `/discounts` as customer: Forbidden. | "Only the admin can create discount rules." |
| Admin **Discounts → New**: `Launch 10%`, percent 10, scope CRM product, min qty 5, valid dates, **usage limit 2**. | "A rule is a fixed amount or a percentage, with a minimum quantity, start and end dates, and a usage limit. It can target products or whole subscriptions." |
| Run billing for December and January. Both invoices show a −780.00 line (total 8283.60). | "On the next invoice the discount appears on its own." |
| Run billing for February: no discount line. Open **Redemptions**: 2 of 2 used. | "When the limit is reached, or the rule expires, it stops by itself." |

## 6. The money comes in (5:25–6:10) — S6
| Screen | Say |
|---|---|
| Staff, December invoice, **Record payment**: 5000.00, UPI, today, note "first part". | "Payments arrive by different methods on different days. Each is recorded with method, amount, date and a note, against the right invoice." |
| Outstanding shows 3283.60. Try 4000.00: rejected. Pay 3283.60: **Paid**. | "The system won't let you overpay. Settle the balance and the invoice moves to Paid." |
| **Invoices → Overdue** chip: November invoice, "N days overdue". | "At any moment the team sees what's paid and what's outstanding, so overdue invoices are chased before they become lost revenue." |
| **Notifications** (admin): confirmation and payment messages, no duplicates. | "Reminders and receipts go out automatically, and sending never blocks the originating action." |

## 7. Finance lead dashboard (6:10–6:55) — S7
| Screen | Say |
|---|---|
| Admin **Home**: active subscriptions, MRR/ARR, revenue collected, outstanding, overdue count and amount. | "The finance lead asks: how many subscriptions are active, how much came in, how much is owed, and which invoices are overdue. One page answers all four." |
| Filter by plan and month. Charts update. | "Filters and a summary view slice it by plan and period." |
| `--big` data: network tab shows every call under 2 s, or run `perf_check.py` and show timings. | "With thousands of subscriptions, every page still responds in under two seconds." |
| Customer profile: portal shows only their own data. | "And customers only ever see their own records." |

## 8. Close (6:55–7:10)
**Screen:** Fast montage: plan → subscription → invoice → payment → dashboard.
**Say:** "Plans, subscriptions, billing, discounts, payments and reporting in one system, with Odoo as the ledger. No spreadsheets, no missed renewals, no double billing."

---

## Recording tips
- Move the cursor slowly and pause for 1 s after each click.
- Pre-record the risky steps (reset email, Odoo tab, `perf_check`) and cut them in.
- Record against a seeded database (`seed_demo.py`), not production.
