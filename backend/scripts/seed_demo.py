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

from decimal import Decimal  # noqa: E402

from apps.core.accounts.models import CustomerProfile, Role, User  # noqa: E402
from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax  # noqa: E402

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


if __name__ == "__main__":
    seed_users()
    seed_catalog()
    print(f"done. password for all demo users: {PASSWORD}")
