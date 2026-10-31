"""Phase 8: dashboard numbers equal hand-computed values on a small fixture (docs/API.md Phase 8)."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.accounts.models import Role
from apps.core.billing.models import Invoice
from apps.core.catalog.models import Plan
from apps.finance.payments.models import Payment
from tests.conftest import api_for, mk_user

URL = "/api/dashboard/summary/"
TODAY = timezone.localdate()


def ago(n):
    return TODAY - timedelta(days=n)


@pytest.fixture
def world(cat, cust, make_sub):
    c1, c2 = cust, mk_user("c2@shop.com", Role.CUSTOMER)
    yearly = Plan.objects.create(name="CRM Yearly", product=cat["crm"], price=12000, billing_period="yearly")
    weekly = Plan.objects.create(name="CRM Weekly", product=cat["crm"], price=120, billing_period="weekly")
    sub_a = make_sub(ago(100))                                    # c1 monthly active, 5 x 1560 = 7800 / month
    sub_b = make_sub(ago(100), qty=1, unit="12000.00", customer=c2)
    sub_b.plan = yearly
    sub_b.save()                                                  # 12000 / year -> 1000 / month
    sub_c = make_sub(ago(100), qty=1, unit="120.00", customer=c2)
    sub_c.plan = weekly
    sub_c.save()                                                  # 120 / week -> 520 / month
    sub_d = make_sub(ago(100), qty=1, unit="5000.00", status="paused")   # not in MRR
    make_sub(ago(100), qty=1, unit="5000.00", status="closed")

    n = iter(range(1, 100))

    def inv(sub, status, total, paid="0", issued=10, due=0):
        total, paid = Decimal(total), Decimal(paid)
        return Invoice.objects.create(
            number=None if status == "draft" else f"INV-{next(n):06d}", subscription=sub, customer=sub.customer, status=status,
            invoice_date=ago(issued), due_date=ago(due), period_start=ago(issued), period_end=ago(issued - 29),
            subtotal=total, discount_total=0, tax_total=0, total=total, amount_paid=paid, amount_due=total - paid,
        )

    def pay(invoice, amount, days, status="completed"):
        Payment.objects.create(invoice=invoice, amount=Decimal(amount), method="upi", payment_date=ago(days), status=status)

    i1 = inv(sub_a, "confirmed", "9204.00", issued=40, due=25)              # overdue 25 days
    i2 = inv(sub_a, "paid", "9204.00", paid="9204.00", issued=70, due=55)
    i3 = inv(sub_b, "confirmed", "14160.00", paid="4160.00", issued=20, due=-10)  # due in 10 days
    inv(sub_c, "draft", "100.00", issued=1, due=-14)                        # drafts never count
    inv(sub_d, "cancelled", "500.00", issued=30, due=15)                    # cancelled never counts
    i6 = inv(sub_b, "confirmed", "590.00", issued=18, due=3)                # overdue 3 days
    pay(i2, "9204.00", 60)
    pay(i3, "4160.00", 5)
    pay(i1, "1000.00", 20, status="failed")     # failed attempts never count
    pay(i6, "590.00", 4, status="reversed")     # reversed payments never count
    return dict(c1=c1, c2=c2, yearly=yearly, i1=i1, i6=i6)


def get(user, **params):
    r = api_for(user).get(URL, params)
    assert r.status_code == 200, r.content
    return r.json()


def test_kpis_equal_hand_computed_values(world, staff):
    assert get(staff)["kpis"] == {
        "active_subscriptions": 3,
        "mrr": "9320.00",                  # 7800 + 12000/12 + 120*52/12
        "arr": "111840.00",
        "revenue_collected": "13364.00",   # 9204 + 4160
        "invoiced": "33158.00",            # 9204 + 9204 + 14160 + 590
        "outstanding": "19794.00",         # 9204 + 10000 + 590
        "overdue_count": 2,
        "overdue_amount": "9794.00",       # 9204 + 590
    }


def test_overdue_list_sorted_by_days_overdue(world, admin):
    o = get(admin)["overdue"]
    assert o["count"] == 2
    assert [(r["id"], r["days_overdue"], r["amount_due"]) for r in o["results"]] == [
        (world["i1"].id, 25, "9204.00"), (world["i6"].id, 3, "590.00")]
    assert o["results"][0]["customer_email"] == "c1@shop.com" and o["results"][0]["plan_name"] == "CRM Monthly"


def test_customer_filter(world, staff):
    k = get(staff, customer=world["c1"].id)["kpis"]
    assert (k["active_subscriptions"], k["mrr"], k["revenue_collected"], k["invoiced"], k["outstanding"], k["overdue_count"]) == (
        1, "7800.00", "9204.00", "18408.00", "9204.00", 1)


def test_plan_filter(world, staff):
    k = get(staff, plan=world["yearly"].id)["kpis"]
    assert (k["active_subscriptions"], k["mrr"], k["invoiced"], k["revenue_collected"], k["overdue_amount"]) == (
        1, "1000.00", "14750.00", "4160.00", "590.00")


def test_status_filter(world, staff):
    k = get(staff, status="paused")["kpis"]
    assert (k["active_subscriptions"], k["mrr"], k["invoiced"], k["outstanding"]) == (0, "0.00", "0.00", "0.00")


def test_date_range_limits_flows_not_balances(world, staff):
    d = get(staff, **{"from": ago(50).isoformat(), "to": TODAY.isoformat()})
    k = d["kpis"]
    assert k["invoiced"] == "23954.00"            # i2 (70 days ago) is outside
    assert k["revenue_collected"] == "4160.00"    # the 9204 payment (60 days ago) is outside
    assert k["outstanding"] == "19794.00" and k["overdue_count"] == 2   # balances are as of today
    assert d["filters"]["from"] == ago(50).isoformat()


def test_by_plan_and_by_month_add_up(world, staff):
    d = get(staff)
    by_plan = {r["plan_name"]: r for r in d["by_plan"]}
    assert by_plan["CRM Monthly"] == {
        "plan_id": by_plan["CRM Monthly"]["plan_id"], "plan_name": "CRM Monthly", "billing_period": "monthly",
        "active_subscriptions": 1, "mrr": "7800.00", "invoiced": "18408.00", "collected": "9204.00"}
    assert by_plan["CRM Weekly"]["mrr"] == "520.00" and by_plan["CRM Weekly"]["invoiced"] == "0.00"
    assert sum(Decimal(r["mrr"]) for r in d["by_plan"]) == Decimal("9320.00")
    assert len(d["by_month"]) == 12   # default range: this month and the 11 before, zeros included
    assert sum(Decimal(m["invoiced"]) for m in d["by_month"]) == Decimal("33158.00")
    assert sum(Decimal(m["collected"]) for m in d["by_month"]) == Decimal("13364.00")


def test_empty_database_gives_zeros(staff):
    d = get(staff)
    assert d["kpis"]["mrr"] == "0.00" and d["kpis"]["overdue_count"] == 0 and d["by_plan"] == [] and d["overdue"]["count"] == 0


@pytest.mark.parametrize("params", [{"from": "2026-05-01", "to": "2026-04-01"}, {"from": "not-a-date"}, {"status": "nope"}, {"plan": "x"}])
def test_bad_filters_are_400(staff, params):
    assert api_for(staff).get(URL, params).status_code == 400


def test_customers_and_anonymous_are_refused(world):
    assert api_for(world["c1"]).get(URL).status_code == 403
    assert api_for().get(URL).status_code == 403


def test_query_count_does_not_grow_with_rows(world, staff, make_sub):
    client = api_for(staff)
    client.get(URL)
    with CaptureQueriesContext(connection) as small:
        client.get(URL)
    for _ in range(5):
        make_sub(ago(10))
    with CaptureQueriesContext(connection) as big:
        client.get(URL)
    assert len(big) == len(small) <= 15
