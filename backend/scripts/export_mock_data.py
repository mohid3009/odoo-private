"""Snapshot the real API into frontend/src/api/mockData.json, the data behind the front end's mock mode (docs/MOCK_MODE.md).

Run from backend/ against a database seeded with scripts/seed_demo.py:
    python scripts/export_mock_data.py
Every response comes from the real views and serializers (as the demo admin), so mock shapes cannot drift from the API.
Re-run it whenever an API response shape changes.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from rest_framework.test import APIClient  # noqa: E402

from apps.core.accounts.models import User  # noqa: E402

OUT = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "api" / "mockData.json"
LISTS = [
    "subscriptions", "invoices", "payments", "discounts", "plans", "products", "taxes", "payment-terms",
    "quotation-templates", "customers", "staff", "notifications/logs", "billing/runs", "me/notifications",
]
DETAILS = ["subscriptions", "invoices"]  # also /{id}/ for each row


def main():
    admin = APIClient(HTTP_HOST="localhost")
    admin.force_login(User.objects.get(email="admin@demo"))

    def get(client, path):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code} {getattr(r, 'data', '')}"
        return r.json()

    data = {"lists": {}, "details": {}, "other": {}, "users": {}}
    for name in LISTS:
        data["lists"][name] = get(admin, f"/api/{name}/?page_size=200")["results"]
    for name in DETAILS:
        for row in data["lists"][name]:
            data["details"][f"{name}/{row['id']}"] = get(admin, f"/api/{name}/{row['id']}/")
    for path in ["notifications/events", "notifications/provider-status"]:
        data["other"][path] = get(admin, f"/api/{path}/")
    data["other"]["healthz"] = {"status": "ok", "app_db": "mock", "odoo": {"status": "disabled"}}
    for u in User.objects.filter(email__endswith="@demo"):  # who the mock login can sign in as
        c = APIClient(HTTP_HOST="localhost")
        c.force_login(u)
        data["users"][u.email] = get(c, "/api/auth/me/")
    data["password"] = "Demo@12345"

    OUT.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    print("wrote", OUT.name + ":", ", ".join(f"{k}={len(v)}" for k, v in data["lists"].items()))


if __name__ == "__main__":
    main()
