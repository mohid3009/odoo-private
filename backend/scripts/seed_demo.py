"""Idempotent demo seed. Phase 1: the three demo logins. Later phases extend this file (catalog, subscriptions, --big).

Run from backend/:  python scripts/seed_demo.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.core.accounts.models import CustomerProfile, Role, User  # noqa: E402

PASSWORD = "Mohid@3009"
ADMIN_EMAIL = "mo.test.1.acc@gmail.com"
# customer@demo is created through the ORM, so it skips EmailField validation (D-031).
DEMO_USERS = [
    (ADMIN_EMAIL, "Demo Admin", Role.ADMIN),
    ("mo.test.2.acc@gmail.com", "Demo Staff", Role.STAFF),
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


def seed_data():
    """Demo business data: catalog, customers, subscriptions, discounts, billed + confirmed invoices, payments of every kind.
    Idempotent: does nothing when the demo catalog already exists. Dates are relative to today so the data always looks current."""
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    from apps.core.billing import engine
    from apps.core.billing import services as billing
    from apps.core.billing.models import Invoice
    from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax
    from apps.core.subscriptions.models import Subscription, SubscriptionLine
    from apps.core.subscriptions.services import next_number
    from apps.finance.discounts.models import Discount
    from apps.finance.payments import services as pay

    if Product.objects.filter(name="CRM Suite").exists():
        print("demo data already present; skipping")
        return
    today = timezone.localdate()
    admin = User.objects.get(email=ADMIN_EMAIL)

    gst = Tax.objects.create(name="GST 18%", rate=18)
    term, _ = PaymentTerm.objects.get_or_create(name="Net 15", defaults={"days": 15, "is_default": True})
    products = {}
    for name, kind, price in [("CRM Suite", "software", "1560.00"), ("Helpdesk Pro", "software", "900.00"), ("Analytics Add-on", "addon", "450.00")]:
        p = Product.objects.create(name=name, type=kind, sales_price=Decimal(price))
        p.taxes.add(gst)
        products[name] = p
    plans = {
        "monthly": Plan.objects.create(name="Monthly", product=products["CRM Suite"], price=Decimal("1560.00"), billing_period="monthly", min_quantity=1, allow_pause=True, allow_renew=True),
        "yearly": Plan.objects.create(name="Yearly", product=products["Helpdesk Pro"], price=Decimal("9000.00"), billing_period="yearly", min_quantity=1, allow_renew=True),
        "weekly": Plan.objects.create(name="Weekly", product=products["Analytics Add-on"], price=Decimal("450.00"), billing_period="weekly", min_quantity=1),
    }

    customers = []
    for i, (name, company) in enumerate([("Asha Rao", "Acme Retail"), ("Ben Fernandes", "Bluefin Labs"), ("Chitra Nair", "Cedar Foods"), ("Dev Malhotra", "Delta Logistics")]):
        u = User.objects.create_user(f"{name.split()[0].lower()}@demo", PASSWORD, name=name, role=Role.CUSTOMER)
        CustomerProfile.objects.create(user=u, company_name=company, phone=f"+9198765432{i}0", whatsapp_number=f"+9198765432{i}0", whatsapp_opt_in=i % 2 == 0)
        customers.append(u)

    launch = Discount.objects.create(name="Launch 15%", code="LAUNCH15", type="percent", value=Decimal("15"), scope="product", usage_limit=5, created_by=admin)
    launch.products.add(products["CRM Suite"])
    loyalty = Discount.objects.create(name="Loyalty 10%", code="LOYAL10", type="percent", value=Decimal("10"), scope="subscription", created_by=admin)

    # (customer, plan, product, qty, days ago started, status, discount)
    specs = [
        (0, "monthly", "CRM Suite", 5, 75, "active", loyalty), (1, "monthly", "CRM Suite", 3, 40, "active", None),
        (2, "yearly", "Helpdesk Pro", 1, 20, "active", None), (3, "weekly", "Analytics Add-on", 4, 22, "active", None),
        (0, "weekly", "Analytics Add-on", 2, 10, "paused", None), (1, "monthly", "CRM Suite", 2, -5, "quotation", None),
        (3, "monthly", "CRM Suite", 1, -10, "draft", None),
    ]
    for ci, plan, prod, qty, ago, status, disc in specs:
        start = today - timedelta(days=ago)
        sub = Subscription.objects.create(
            number=next_number(), customer=customers[ci], plan=plans[plan], start_date=start, payment_term=term, status=status,
            next_invoice_date=start if status == "active" else None, discount=disc,
            expiry_date=start + timedelta(days=365) if plan == "yearly" else None,
        )
        unit = products[prod].sales_price
        line = SubscriptionLine.objects.create(subscription=sub, product=products[prod], quantity=qty, unit_price=unit, amount=unit * qty, description=products[prod].name)
        line.taxes.add(gst)

    # billing runs at past dates (the invoice date is the run date) so some invoices are long overdue; the two newest stay draft
    for days_ago in (70, 45, 20, 0):
        engine.run_billing(today - timedelta(days=days_ago))
    invoices = list(Invoice.objects.order_by("id"))
    for inv in invoices[:-2]:
        billing.confirm(inv, admin)
    confirmed = list(Invoice.objects.filter(status="confirmed").order_by("id"))
    for inv, kind in zip(confirmed[1:], ["full", "partial", "fail2then_pay", "fail3", "full"]):  # the oldest stays unpaid and overdue
        inv.refresh_from_db()
        due = inv.amount_due
        if kind == "full":
            pay.record_payment(inv, admin, {"amount": due, "method": "bank_transfer", "status": "completed"})
        elif kind == "partial":
            pay.record_payment(inv, admin, {"amount": (due / 3).quantize(Decimal("0.01")), "method": "upi", "status": "completed"})
        elif kind == "fail2then_pay":
            for _ in range(2):
                pay.record_payment(inv, admin, {"amount": due, "method": "card", "status": "failed", "failure_reason": "card declined"})
            pay.record_payment(inv, admin, {"amount": due, "method": "upi", "status": "completed"})
        elif kind == "fail3":
            for _ in range(3):
                pay.record_payment(inv, admin, {"amount": due, "method": "card", "status": "failed", "failure_reason": "insufficient funds"})
    print(f"data  {len(customers)} customers, {Subscription.objects.count()} subscriptions, {Invoice.objects.count()} invoices")


if __name__ == "__main__":
    seed_users()
    seed_data()
    print(f"done. password for all demo users: {PASSWORD}")
