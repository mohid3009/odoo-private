"""Phase 8 (FR-AUTH-08, FR-PORT-01): customer A reaches none of customer B's data by any URL — 404, never 403."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.accounts.models import Role
from apps.core.billing.models import Invoice
from apps.finance.payments.models import Payment
from tests.conftest import api_for, mk_user

TODAY = timezone.localdate()


@pytest.fixture
def two(cust, make_sub):
    """Customer A and B, each with an active subscription, a confirmed invoice and a payment."""
    b = mk_user("b@shop.com", Role.CUSTOMER)
    rows = {}
    for who, user in (("a", cust), ("b", b)):
        sub = make_sub(TODAY - timedelta(days=40), customer=user)
        inv = Invoice.objects.create(
            number=f"INV-{who}", subscription=sub, customer=user, status="confirmed", invoice_date=TODAY, due_date=TODAY,
            period_start=TODAY, period_end=TODAY + timedelta(days=29), subtotal=Decimal("100"), discount_total=0,
            tax_total=0, total=Decimal("100"), amount_paid=Decimal("40"), amount_due=Decimal("60"),
        )
        pay = Payment.objects.create(invoice=inv, amount=Decimal("40"), method="upi", payment_date=TODAY)
        rows[who] = dict(user=user, sub=sub, inv=inv, pay=pay)
    return rows


def ids(r):
    return dict(sub=r["sub"].pk, inv=r["inv"].pk, pay=r["pay"].pk)


@pytest.mark.parametrize("url", [
    "/api/subscriptions/{sub}/",
    "/api/invoices/{inv}/",
    "/api/invoices/{inv}/print/",
    "/api/invoices/{inv}/payments/",
    "/api/payments/{pay}/",
])
def test_other_customers_ids_are_404(two, url):
    c = api_for(two["a"]["user"])
    assert c.get(url.format(**ids(two["a"]))).status_code == 200    # own row: visible
    assert c.get(url.format(**ids(two["b"]))).status_code == 404    # theirs: does not exist for A
    assert c.get(url.format(sub=999999, inv=999999, pay=999999)).status_code == 404  # same answer as a missing id


def test_lists_only_contain_own_rows(two):
    a = two["a"]
    c = api_for(a["user"])
    assert [r["id"] for r in c.get("/api/subscriptions/").json()["results"]] == [a["sub"].pk]
    assert [r["id"] for r in c.get("/api/invoices/").json()["results"]] == [a["inv"].pk]
    assert [r["id"] for r in c.get("/api/payments/").json()["results"]] == [a["pay"].pk]


def test_filtering_by_another_customer_leaks_nothing(two):
    c, b = api_for(two["a"]["user"]), two["b"]
    assert c.get("/api/invoices/", {"customer": b["user"].pk}).json()["count"] == 0
    assert c.get("/api/invoices/", {"subscription": b["sub"].pk}).json()["count"] == 0
    assert c.get("/api/invoices/", {"search": "INV-b"}).json()["count"] == 0


@pytest.mark.parametrize("method,url", [
    ("post", "/api/invoices/{inv}/confirm/"),
    ("post", "/api/invoices/{inv}/payments/"),
    ("post", "/api/subscriptions/{sub}/transition/"),
])
def test_customer_actions_are_refused_without_revealing_ids(two, method, url):
    """Actions are role-gated before any lookup: the same 403 for an existing and a missing id."""
    c = api_for(two["a"]["user"])
    for target in (ids(two["b"]), dict(sub=999999, inv=999999, pay=999999)):
        assert getattr(c, method)(url.format(**target), {}, format="json").status_code == 403


def test_staff_see_both(two, staff):
    c = api_for(staff)
    for who in ("a", "b"):
        assert c.get(f"/api/invoices/{two[who]['inv'].pk}/").status_code == 200
