"""Performance gate (Phase 8, FR-DASH-04): every list endpoint (page 1 + the last page) and the dashboard, as admin and
as a big-seed customer. Prints ms + query count per call; exits 1 if any call takes longer than BUDGET seconds or fails.

Run from backend/ after `python scripts/seed_demo.py --big`:  python scripts/perf_check.py
In-process (Django test client), so it measures the backend only; the browser budget is 2 s (docs/TEST_PLAN.md).
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from apps.core.accounts.models import User  # noqa: E402
from apps.core.billing.models import Invoice  # noqa: E402
from apps.core.subscriptions.models import Subscription  # noqa: E402

BUDGET_MS = 1000
LISTS = [
    "/api/subscriptions/", "/api/invoices/", "/api/payments/", "/api/billing/runs/", "/api/products/", "/api/plans/",
    "/api/taxes/", "/api/payment-terms/", "/api/quotation-templates/", "/api/discounts/", "/api/customers/", "/api/staff/",
    "/api/notifications/logs/", "/api/notifications/events/",
]
FILTERED = [
    "/api/invoices/?overdue=true", "/api/invoices/?status=paid&ordering=-total", "/api/invoices/?search=INV-0001",
    "/api/subscriptions/?status=active&search=SUB-00", "/api/payments/?status=failed",
    "/api/dashboard/summary/", "/api/dashboard/summary/?status=active&page=5", "/api/dashboard/summary/?from=2026-01-01&to=2026-12-31",
]


def call(client, url):
    with CaptureQueriesContext(connection) as q:
        t = time.perf_counter()
        r = client.get(url)
        ms = (time.perf_counter() - t) * 1000
    return r, ms, len(q)


def run(client, label, urls):
    rows = []
    for url in urls:
        r, ms, n = call(client, url)
        body = r.json() if r.status_code == 200 else None
        count = body.get("count") if isinstance(body, dict) else None
        rows.append((label, url, ms, n, r.status_code, "" if count is None else f"count={count}"))
        if count and count > 25 and "?" not in url:  # the last page too: OFFSET cost grows with depth
            last = f"{url}?page={(count + 24) // 25}"
            r, ms, n = call(client, last)
            rows.append((label, last, ms, n, r.status_code, "last page"))
    return rows


def main():
    admin = User.objects.filter(role="admin").order_by("id").first()
    customer = User.objects.filter(email__endswith="@big.seed").order_by("id").first() or User.objects.filter(role="customer").first()
    sub = Subscription.objects.filter(customer=customer).first()
    inv = Invoice.objects.filter(customer=customer).exclude(status="draft").first()
    if not (admin and sub and inv):
        sys.exit("no data: run scripts/seed_demo.py --big first")
    print(f"data: {Subscription.objects.count()} subscriptions, {Invoice.objects.count()} invoices; customer {customer.email}")

    a, c = Client(HTTP_HOST="localhost"), Client(HTTP_HOST="localhost")
    a.force_login(admin)
    c.force_login(customer)
    call(a, "/api/plans/")  # warm-up: first-request imports are not what we measure

    rows = run(a, "admin", LISTS + FILTERED + [f"/api/subscriptions/{sub.pk}/", f"/api/invoices/{inv.pk}/"])
    rows += run(c, "customer", ["/api/subscriptions/", "/api/invoices/", "/api/payments/", f"/api/invoices/{inv.pk}/print/"])
    bad = 0
    for label, url, ms, n, code, note in rows:
        ok = code == 200 and ms <= BUDGET_MS
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {ms:7.1f} ms {n:3} q  {label:8} {url}  {note if code == 200 else f'HTTP {code}'}")
    print(f"{len(rows)} calls, slowest {max(r[2] for r in rows):.1f} ms, budget {BUDGET_MS} ms, {bad} failing")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
