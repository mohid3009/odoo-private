"""Idempotent demo seed: the three demo logins, a small catalog, one active subscription.

Run from backend/:  python scripts/seed_demo.py [--big]
--big adds ~5k subscriptions, ~15k invoices, ~10k payments (bulk_create) for the performance gate (scripts/perf_check.py).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from datetime import date, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from apps.core.accounts.models import CustomerProfile, Role, User  # noqa: E402
from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax  # noqa: E402
from apps.core.subscriptions import services  # noqa: E402
from apps.core.subscriptions.models import Subscription, SubscriptionLine  # noqa: E402

PASSWORD = "Demo@12345"
# Created through the ORM, so emails like admin@demo skip EmailField validation (D-031).
DEMO_USERS = [
    ("admin@demo", "Demo Admin", Role.ADMIN),
    ("staff@demo", "Demo Staff", Role.STAFF),
    ("customer@demo", "Demo Customer", Role.CUSTOMER),
]


def seed_users():
    for email, name, role in DEMO_USERS:
        user, _ = User.objects.get_or_create(email=email, defaults={"name": name, "role": role})
        user.name, user.role, user.is_active = name, role, True
        user.is_superuser = role == Role.ADMIN
        user.set_password(PASSWORD)
        user.save()
        if role == Role.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=user, defaults={"company_name": "Demo Traders"})
        print(f"user  {email:<16} {role}")


def seed_catalog():
    gst, _ = Tax.objects.get_or_create(name="GST 18%", defaults={"rate": Decimal("18.00")})
    for name, days in [("Immediate", 0), ("Net 15", 15), ("Net 30", 30)]:
        PaymentTerm.objects.get_or_create(name=name, defaults={"days": days})
    product, _ = Product.objects.get_or_create(
        name="Brightloop Suite", defaults={"type": Product.Type.SOFTWARE, "sales_price": Decimal("999.00")}
    )
    product.taxes.add(gst)
    for name, price, period in [
        ("Suite Monthly", "999.00", Plan.Period.MONTHLY),
        ("Suite Yearly", "9990.00", Plan.Period.YEARLY),
    ]:
        Plan.objects.get_or_create(name=name, defaults={"product": product, "price": Decimal(price), "billing_period": period})
    print("catalog  1 tax, 3 terms, 1 product, 2 plans")


def seed_subscription():
    """One active subscription for the demo customer, walked through the real state machine."""
    admin, customer = User.objects.get(email="admin@demo"), User.objects.get(email="customer@demo")
    plan = Plan.objects.get(name="Suite Monthly")
    if Subscription.objects.filter(customer=customer, plan=plan).exists():
        return
    sub = Subscription.objects.create(
        number=services.next_number(), customer=customer, plan=plan, start_date=date.today(),
        payment_term=PaymentTerm.objects.get(is_default=True), created_by=admin,
    )
    price = services.line_price(plan, plan.product)
    line = SubscriptionLine.objects.create(
        subscription=sub, product=plan.product, description=plan.name, quantity=1, unit_price=price, amount=price
    )
    line.taxes.set(plan.product.taxes.all())
    for to in ("quotation", "confirmed", "active"):
        services.transition(sub, to, admin)
    print(f"subscription  {sub.number} active for customer@demo")


BIG_DOMAIN = "big.seed"


def _big_status(i):
    r = i % 100
    return "active" if r < 82 else "paused" if r < 90 else "closed" if r < 96 else "confirmed" if r < 98 else "quotation" if r < 99 else "draft"


def seed_big(n_customers=500, n_subs=5000):
    """Bulk data with a realistic status / overdue mix. Rows are written directly (not through the engine) for speed,
    but every invoice and payment keeps the engine's invariants: total = subtotal + 18 % tax, amount_due = total minus
    completed payments, paid <=> amount_due = 0, one invoice per (subscription, period_start).
    ponytail: no StatusLog / PaymentEvent history rows for bulk data; add them if a screen ever needs history at scale."""
    import random

    from django.contrib.auth.hashers import make_password
    from django.db import transaction

    from apps.core.billing.engine import next_period_start
    from apps.core.billing.models import Invoice, InvoiceLine
    from apps.core.subscriptions.models import Counter
    from apps.finance.payments.models import Payment

    if User.objects.filter(email__endswith="@" + BIG_DOMAIN).exists():
        print("big  already seeded, skipping")
        return
    rnd, today, cent = random.Random(8), date.today(), Decimal("0.01")
    gst = Tax.objects.get(name="GST 18%")
    product = Product.objects.get(name="Brightloop Suite")
    team, _ = Plan.objects.get_or_create(
        name="Team Monthly", defaults={"product": product, "price": Decimal("2499.00"), "billing_period": Plan.Period.MONTHLY})
    weekly, _ = Plan.objects.get_or_create(
        name="Suite Weekly", defaults={"product": product, "price": Decimal("249.00"), "billing_period": Plan.Period.WEEKLY})
    monthly, yearly = Plan.objects.get(name="Suite Monthly"), Plan.objects.get(name="Suite Yearly")
    term, admin = PaymentTerm.objects.get(name="Net 15"), User.objects.get(email="admin@demo")

    with transaction.atomic():
        pw = make_password(PASSWORD)  # hash once: 500 PBKDF2 hashes would take minutes
        users = User.objects.bulk_create([
            User(email=f"big-{i:04d}@{BIG_DOMAIN}", name=f"Big Customer {i}", role=Role.CUSTOMER, password=pw)
            for i in range(1, n_customers + 1)
        ])
        CustomerProfile.objects.bulk_create([CustomerProfile(user=u, company_name=f"{u.name} Pvt Ltd") for u in users])

        counter, _ = Counter.objects.select_for_update().get_or_create(name="subscription")
        subs, qty = [], []
        for i in range(n_subs):
            status = _big_status(i)
            plan = yearly if i % 10 == 0 else weekly if i % 10 == 1 else (monthly, team)[i % 2]
            back = {"yearly": 400, "weekly": 21, "monthly": 75}[plan.billing_period] + rnd.randint(0, 25)
            started = status in ("active", "paused", "closed")
            subs.append(Subscription(
                number=f"SUB-{counter.value + i + 1:06d}", customer=rnd.choice(users), plan=plan, status=status,
                start_date=today - timedelta(days=back) if started else today + timedelta(days=7), payment_term=term,
                expiry_date=today + timedelta(days=rnd.choice([3, 6, 40, 200, 365])) if i % 7 == 0 else None, created_by=admin,
            ))
            qty.append(1 + i % 5)
        counter.value += n_subs
        counter.save(update_fields=["value"])
        subs = Subscription.objects.bulk_create(subs, batch_size=1000)
        sub_lines = SubscriptionLine.objects.bulk_create([
            SubscriptionLine(subscription=s, product=product, description=s.plan.name, quantity=qty[i],
                             unit_price=s.plan.price, amount=s.plan.price * qty[i]) for i, s in enumerate(subs)
        ], batch_size=1000)
        SubscriptionLine.taxes.through.objects.bulk_create(
            [SubscriptionLine.taxes.through(subscriptionline_id=ln.id, tax_id=gst.id) for ln in sub_lines], batch_size=2000)

        counter, _ = Counter.objects.select_for_update().get_or_create(name="invoice")
        invoices, attempts = [], []  # attempts[k]: (amount, date, status) payment rows for invoices[k]
        for i, s in enumerate(subs):
            if s.status not in ("active", "paused", "closed"):
                continue
            subtotal = s.plan.price * qty[i]
            tax = (subtotal * gst.rate / 100).quantize(cent)
            total, start, periods = subtotal + tax, s.start_date, []
            while start <= today and len(periods) < 12:
                nxt = next_period_start(start, s.plan.billing_period, s.start_date)
                periods.append((start, nxt))
                start = nxt
            if s.status == "active":
                s.next_invoice_date = start
            for k, (p_start, nxt) in enumerate(periods):
                last, roll = k == len(periods) - 1, (i + k) % 20
                if last and s.status == "active" and roll < 2:
                    status = "draft"
                elif roll == 2:
                    status = "cancelled"
                elif (last and roll < 9) or (not last and roll == 3):
                    status = "confirmed"  # the older ones end up overdue
                else:
                    status = "paid"
                due, pays = p_start + timedelta(days=term.days), []
                if status in ("confirmed", "paid") and (i + k) % 25 == 0:
                    pays.append((total, min(today, p_start + timedelta(days=1)), "failed"))
                if status == "paid":
                    pays.append((total, min(today, due - timedelta(days=rnd.randint(0, 10))), "completed"))
                elif status == "confirmed" and (i + k) % 3 == 0:
                    pays.append(((total * Decimal("0.4")).quantize(cent), min(today, p_start + timedelta(days=3)), "completed"))
                paid = sum((a for a, _, st in pays if st == "completed"), Decimal("0.00"))
                if status != "draft":
                    counter.value += 1
                invoices.append(Invoice(
                    number=None if status == "draft" else f"INV-{counter.value:06d}", subscription=s, customer=s.customer,
                    status=status, invoice_date=p_start, due_date=due, period_start=p_start, period_end=nxt - timedelta(days=1),
                    subtotal=subtotal, discount_total=Decimal("0.00"), tax_total=tax, total=total, amount_paid=paid,
                    amount_due=total - paid, failed_attempts=sum(st == "failed" for _, _, st in pays) if status == "confirmed" else 0,
                ))
                attempts.append(pays)
        counter.save(update_fields=["value"])
        Subscription.objects.bulk_update([s for s in subs if s.status == "active"], ["next_invoice_date"], batch_size=1000)
        invoices = Invoice.objects.bulk_create(invoices, batch_size=1000)
        inv_lines = InvoiceLine.objects.bulk_create([
            InvoiceLine(invoice=inv, product=product, description=inv.subscription.plan.name, quantity=1, unit_price=inv.subtotal,
                        tax_rate_snapshot=gst.rate, line_subtotal=inv.subtotal, line_tax=inv.tax_total, line_total=inv.total)
            for inv in invoices
        ], batch_size=1000)
        InvoiceLine.taxes.through.objects.bulk_create(
            [InvoiceLine.taxes.through(invoiceline_id=ln.id, tax_id=gst.id) for ln in inv_lines], batch_size=2000)
        payments = Payment.objects.bulk_create([
            Payment(invoice=inv, amount=amount, method=rnd.choice(Payment.Method.values), payment_date=day, status=st,
                    attempt_number=n + 1, recorded_by=admin, failure_reason="Card declined" if st == "failed" else "")
            for inv, pays in zip(invoices, attempts) for n, (amount, day, st) in enumerate(pays)
        ], batch_size=1000)
    overdue = sum(inv.status == "confirmed" and inv.amount_due > 0 and inv.due_date < today for inv in invoices)
    print(f"big  {len(users)} customers, {len(subs)} subscriptions, {len(invoices)} invoices ({overdue} overdue), {len(payments)} payments")
    print(f"big  customer logins: big-0001@{BIG_DOMAIN} .. big-{n_customers:04d}@{BIG_DOMAIN} (same password)")


if __name__ == "__main__":
    seed_users()
    seed_catalog()
    seed_subscription()
    if "--big" in sys.argv:
        seed_big()
    print(f"done. password for all demo users: {PASSWORD}")
