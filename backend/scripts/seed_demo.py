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


if __name__ == "__main__":
    seed_users()
    print(f"done. password for all demo users: {PASSWORD}")
