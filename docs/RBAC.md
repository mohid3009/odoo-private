# RBAC

Roles: `admin`, `staff`, `customer` (`User.role`). Public signup → `customer` unless the visitor presents the server's staff/admin signup code (D-044; both codes are empty = disabled by default). An admin can always create staff and other admins from the Staff page.
Enforcement is server-side: **permission classes** (what actions) + **`for_user()` querysets** (which rows). React hiding is cosmetic.

## Capability matrix
| Capability | Admin | Staff | Customer |
|---|:-:|:-:|:-:|
| Create staff users | ✔ | ✘ | ✘ |
| Catalog (products, variants, taxes, payment terms, plans) — read | ✔ | ✔ | ✘ |
| Catalog — write | ✔ | ✘ | ✘ |
| Quotation templates — read / write | ✔ / ✔ | ✔ / ✔ | ✘ |
| Subscriptions — list/create/edit/transition | ✔ all | ✔ all | ✘ |
| Subscriptions — view own | ✔ | ✔ | ✔ read-only |
| Discount rules — create/edit/delete | ✔ | ✘ | ✘ |
| Discount — read / attach to subscription | ✔ / ✔ | ✔ / ✔ | ✘ |
| Run billing | ✔ | ✔ | ✘ |
| Invoices — list/confirm/cancel/send | ✔ all | ✔ all | ✘ |
| Invoices — view / print own | ✔ | ✔ | ✔ |
| Record a payment attempt / retry a failed one | ✔ | ✔ | ✘ |
| Reverse a completed payment, reset the attempt limit | ✔ | ✘ | ✘ |
| Payments — list | ✔ all | ✔ all | own only, customer-safe fields (no notes, reasons, audit trail, recorder) |
| See the "needs attention" flag and attempt counter | ✔ | ✔ | ✘ |
| Dashboard | ✔ | ✔ | ✘ |
| Notifications log / retry / toggles / test-send / run reminders | ✔ | ✘ | ✘ |
| Notification timeline of one invoice / subscription (`?object_type&object_id`) | ✔ | ✔ | ✘ |
| Own notification settings | ✔ | ✔ | ✔ |
| Cancel a confirmed invoice | ✔ | ✘ | ✘ |

## Scoping rules (`Model.objects.for_user(user)`)
| Model | admin / staff | customer |
|---|---|---|
| Subscription | all | `customer=user` |
| Invoice | all | `customer=user` |
| Payment | all | `invoice__customer=user` |
| StatusLog / InvoiceLine / SubscriptionLine | via parent | via parent |
| NotificationLog | all (admin only endpoint) | `recipient_user=user` (own timeline only) |
| CustomerProfile | all | own |
| Catalog, Discount, Template | all | none (403 on the endpoint) |

A customer requesting another customer's id gets **404**, not 403 — the row doesn't exist from their point of view. Unauthenticated → 401/403 (DRF session).
List filters can only narrow the scoped queryset, never widen it (e.g. `?customer=` is ignored for customers).

## Permission classes
`IsAdmin`, `IsStaffOrAdmin`, `IsCustomer`, plus `ReadOnlyOrAdmin` for catalog (SAFE methods → staff+admin, writes → admin).
Views declare `permission_classes` explicitly; the project default is `IsAuthenticated`. Object-level access is by queryset, not per-object permission.

## Protected screens (React `RoleGuard`)
`/staff` admin · `/catalog/*` staff+admin (edit controls admin) · `/discounts` admin · `/dashboard`, `/billing`, `/payments` staff+admin ·
`/notifications` admin · `/my-*` customer (`/invoices/:id/print` every role; the API scopes it). Mismatch → redirect to the role's home or the 403 page.

## Tests (Phase 1 / 8)
Role × endpoint matrix test; staff cannot create staff (403); customer A → customer B's subscription/invoice/payment ids → 404; customer → catalog write → 403.
