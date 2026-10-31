import threading
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import connection

from apps.core.billing import engine
from apps.core.billing.models import BillingRun, Invoice
from apps.core.subscriptions.models import Subscription
from conftest import api_for, mk_user

pytestmark = pytest.mark.django_db
D = Decimal


def invoices(sub):
    return list(Invoice.objects.filter(subscription=sub).order_by("period_start"))


def run(as_of, user=None):
    return engine.run_billing(as_of, user)


# --- pure money math: the worked example from KICKOFF/PRD §8 ------------------------------------

def line(qty=5, unit="1560.00", rate="18", taxes=()):
    return {"description": "CRM", "quantity": qty, "unit_price": D(unit), "tax_rate": D(rate), "taxes": list(taxes), "product": None}


def test_worked_example_total_is_8283_60():
    # plan 1000 + Odoo variant 560 = 1560 x 5 = 7800; 10% product discount -780 = 7020; 18% tax = 1263.60
    priced = engine.price_lines([line()], [engine.DiscountLine("10% launch", D("780.00"), D("18"))])
    assert priced["subtotal"] == D("7800.00") and priced["discount_total"] == D("780.00")
    assert priced["tax_total"] == D("1263.60") and priced["total"] == D("8283.60")
    kinds = [(r["kind"], r["line_subtotal"], r["line_tax"], r["line_total"]) for r in priced["lines"]]
    assert kinds == [("product", D("7800.00"), D("1404.00"), D("9204.00")), ("discount", D("-780.00"), D("-140.40"), D("-920.40"))]


def test_total_without_discount_and_zero_rate():
    assert engine.price_lines([line()])["total"] == D("9204.00")
    assert engine.price_lines([line(rate="0")])["total"] == D("7800.00")


def test_multiple_taxes_add_up_and_rounding_is_half_up():
    p = engine.price_lines([line(qty=1, unit="0.05", rate="10")])  # 0.005 tax -> 0.01 (half up)
    assert p["tax_total"] == D("0.01") and p["total"] == D("0.06")
    p = engine.price_lines([line(qty=3, unit="33.33", rate="18")])
    assert p["subtotal"] == D("99.99") and p["tax_total"] == D("18.00") and p["total"] == D("117.99")


class StubDiscounts:
    """What the Phase 5 discounts app will provide: pick -> reserve -> record."""

    def __init__(self, amount="780.00", reserve_ok=True):
        self.amount, self.reserve_ok, self.recorded = D(amount), reserve_ok, []

    def pick_discounts(self, sub, product_lines, start, end, as_of):
        return [engine.DiscountLine("10% launch", self.amount, product_lines[0]["tax_rate"], product_lines[0]["taxes"])]

    def reserve(self, picks):
        return picks if self.reserve_ok else []

    def record(self, invoice, picks):
        self.recorded.append((invoice.pk, picks))


def test_engine_builds_the_worked_example_invoice_through_the_hooks(make_sub):
    sub = make_sub(date(2026, 11, 1))
    hooks = StubDiscounts()
    r = engine.run_billing(date(2026, 11, 1), hooks=hooks)
    inv = Invoice.objects.get()
    assert r.created_count == 1
    assert (inv.subtotal, inv.discount_total, inv.tax_total, inv.total) == (D("7800.00"), D("780.00"), D("1263.60"), D("8283.60"))
    assert inv.amount_due == D("8283.60") and inv.amount_paid == 0
    assert [(l.kind, l.line_subtotal) for l in inv.lines.all()] == [("product", D("7800.00")), ("discount", D("-780.00"))]
    assert hooks.recorded and hooks.recorded[0][0] == inv.pk


def test_discount_that_cannot_be_reserved_is_left_off(make_sub):
    make_sub(date(2026, 11, 1))
    engine.run_billing(date(2026, 11, 1), hooks=StubDiscounts(reserve_ok=False))  # limit hit between pick and reserve
    inv = Invoice.objects.get()
    assert inv.discount_total == 0 and inv.total == D("9204.00") and inv.lines.count() == 1


# --- period arithmetic ------------------------------------------------------------------------------

@pytest.mark.parametrize("start,period,anchor,expected", [
    (date(2026, 1, 31), "monthly", date(2026, 1, 31), date(2026, 2, 28)),
    (date(2026, 2, 28), "monthly", date(2026, 1, 31), date(2026, 3, 31)),  # back on the 31st: no drift
    (date(2028, 1, 31), "monthly", date(2028, 1, 31), date(2028, 2, 29)),  # leap year
    (date(2026, 12, 15), "monthly", date(2026, 1, 15), date(2027, 1, 15)),
    (date(2026, 3, 10), "daily", date(2026, 3, 10), date(2026, 3, 11)),
    (date(2026, 3, 10), "weekly", date(2026, 3, 10), date(2026, 3, 17)),
    (date(2027, 2, 28), "yearly", date(2028, 2, 29), date(2028, 2, 29)),  # anchored on the 29th: back on it in a leap year
    (date(2028, 2, 29), "yearly", date(2028, 2, 29), date(2029, 2, 28)),
])
def test_next_period_start(start, period, anchor, expected):
    assert engine.next_period_start(start, period, anchor) == expected


# --- mandatory 1: running twice creates nothing new ---------------------------------------------------

def test_run_twice_creates_no_new_invoices(make_sub):
    subs = [make_sub(date(2026, 11, 1)) for _ in range(20)]
    first = run(date(2026, 11, 1))
    assert (first.created_count, first.skipped_count, first.error_count) == (20, 0, 0)
    before = list(Invoice.objects.order_by("id").values_list("id", "period_start"))
    second = run(date(2026, 11, 1))
    assert (second.created_count, second.skipped_count, second.error_count) == (0, 0, 0)
    assert list(Invoice.objects.order_by("id").values_list("id", "period_start")) == before and len(before) == 20
    assert all(s.next_invoice_date == date(2026, 12, 1) for s in Subscription.objects.all())
    assert BillingRun.objects.count() == 2 and first.finished_at


# --- mandatory 2: concurrent / interrupted runs never duplicate ------------------------------------------

def test_cursor_behind_the_data_is_repaired_not_rebilled(make_sub):
    """What a crash between insert and cursor update (or a cancelled period) leaves behind."""
    sub = make_sub(date(2026, 11, 1))
    run(date(2026, 11, 1))
    Subscription.objects.filter(pk=sub.pk).update(next_invoice_date=date(2026, 11, 1))  # cursor rewound
    r = run(date(2026, 11, 1))
    assert (r.created_count, r.skipped_count) == (0, 1) and Invoice.objects.count() == 1
    assert Subscription.objects.get(pk=sub.pk).next_invoice_date == date(2026, 12, 1)


def test_unique_constraint_is_the_last_safety_net(make_sub):
    from django.db import IntegrityError, transaction

    sub = make_sub(date(2026, 11, 1))
    run(date(2026, 11, 1))
    inv = Invoice.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        Invoice.objects.create(subscription=sub, customer=sub.customer, invoice_date=inv.invoice_date, due_date=inv.due_date,
                               period_start=inv.period_start, period_end=inv.period_end, subtotal=0, discount_total=0,
                               tax_total=0, total=0, amount_due=0)


@pytest.mark.skipif(connection.vendor != "postgresql", reason="needs real row locks (Postgres)")
@pytest.mark.django_db(transaction=True)
def test_concurrent_runs_create_no_duplicates(make_sub):
    for _ in range(10):
        make_sub(date(2026, 11, 1))
    errors = []

    def worker():
        try:
            engine.run_billing(date(2026, 11, 1))
        except Exception as e:  # pragma: no cover
            errors.append(e)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    assert Invoice.objects.count() == 10 and Invoice.objects.values("subscription", "period_start").distinct().count() == 10


# --- mandatory 3: catch-up bills every missed period --------------------------------------------------------

def test_catch_up_creates_each_missed_period(make_sub):
    sub = make_sub(date(2026, 1, 1))
    r = run(date(2026, 4, 15))
    got = invoices(sub)
    assert r.created_count == 4
    assert [(i.period_start, i.period_end) for i in got] == [
        (date(2026, 1, 1), date(2026, 1, 31)), (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2026, 3, 1), date(2026, 3, 31)), (date(2026, 4, 1), date(2026, 4, 30))]
    assert all(i.invoice_date == date(2026, 4, 15) and i.due_date == date(2026, 4, 30) for i in got)  # dated at the run, term 15 days
    assert Subscription.objects.get(pk=sub.pk).next_invoice_date == date(2026, 5, 1)
    assert run(date(2026, 4, 15)).created_count == 0


def test_catch_up_is_capped_at_12_periods_per_run(make_sub):
    sub = make_sub(date(2024, 1, 1))
    assert run(date(2026, 10, 31)).created_count == 12
    assert Subscription.objects.get(pk=sub.pk).next_invoice_date == date(2025, 1, 1)
    assert run(date(2026, 10, 31)).created_count == 12  # the next run carries on
    assert Invoice.objects.filter(subscription=sub).count() == 24


@pytest.mark.parametrize("period,start,as_of,count", [
    ("daily", date(2026, 3, 1), date(2026, 3, 5), 5),
    ("weekly", date(2026, 3, 1), date(2026, 3, 22), 4),
    ("yearly", date(2024, 2, 29), date(2026, 3, 1), 3),
])
def test_other_billing_periods(make_sub, period, start, as_of, count):
    sub = make_sub(start, period=period)
    run(as_of)
    got = invoices(sub)
    assert len(got) == count
    for a, b in zip(got, got[1:]):
        assert b.period_start == a.period_end + timedelta(days=1)  # no gaps, no overlaps


def test_monthly_periods_keep_the_anchor_day(make_sub):
    sub = make_sub(date(2026, 1, 31))
    run(date(2026, 4, 30))
    assert [i.period_start for i in invoices(sub)] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


# --- mandatory 4: nothing beyond expiry; auto-close only with the flag ---------------------------------------

def test_nothing_billed_beyond_expiry(make_sub):
    sub = make_sub(date(2026, 1, 1), expiry=date(2026, 3, 31))
    run(date(2026, 12, 1))
    assert [i.period_start for i in invoices(sub)] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    assert run(date(2026, 12, 1)).created_count == 0


def test_auto_close_only_when_the_plan_flag_is_on(make_sub):
    keep = make_sub(date(2026, 1, 1), expiry=date(2026, 2, 28))
    closing = make_sub(date(2026, 1, 1), expiry=date(2026, 2, 28), auto_close=True)
    run(date(2026, 6, 1))
    assert Subscription.objects.get(pk=keep.pk).status == "active"
    c = Subscription.objects.get(pk=closing.pk)
    assert c.status == "closed" and c.status_log.last().to_status == "closed" and c.status_log.last().by_user is None
    assert Invoice.objects.filter(subscription=closing).count() == 2


def test_auto_close_waits_until_the_expiry_has_passed(make_sub):
    sub = make_sub(date(2026, 1, 1), expiry=date(2026, 2, 15), auto_close=True)
    run(date(2026, 2, 10))  # last period (Feb) billed, but the term is not over yet
    assert Subscription.objects.get(pk=sub.pk).status == "active" and Invoice.objects.count() == 2
    run(date(2026, 2, 16))
    assert Subscription.objects.get(pk=sub.pk).status == "closed"


def test_last_period_is_billed_in_full_even_if_it_runs_past_expiry(make_sub):
    sub = make_sub(date(2026, 1, 1), expiry=date(2026, 1, 10))
    run(date(2026, 1, 10))
    (inv,) = invoices(sub)
    assert (inv.period_start, inv.period_end) == (date(2026, 1, 1), date(2026, 1, 31))


# --- mandatory 5: only active subscriptions are billed ---------------------------------------------------------

@pytest.mark.parametrize("status", ["draft", "quotation", "confirmed_future", "paused", "closed"])
def test_non_active_subscriptions_are_skipped(make_sub, status):
    if status == "confirmed_future":
        sub = make_sub(date(2027, 1, 1), status="confirmed")
        Subscription.objects.filter(pk=sub.pk).update(next_invoice_date=date(2027, 1, 1))
    else:
        sub = make_sub(date(2026, 1, 1), status=status)
        Subscription.objects.filter(pk=sub.pk).update(next_invoice_date=date(2026, 1, 1))
    r = run(date(2026, 6, 1))
    assert r.created_count == 0 and Invoice.objects.count() == 0


def test_run_activates_due_confirmed_subscriptions_then_bills_them(make_sub):
    sub = make_sub(date(2026, 6, 1), status="confirmed")
    Subscription.objects.filter(pk=sub.pk).update(next_invoice_date=date(2026, 6, 1))
    r = run(date(2026, 6, 1))
    assert Subscription.objects.get(pk=sub.pk).status == "active" and r.created_count == 1


def test_paused_period_is_not_back_billed_after_resume(make_sub, staff):
    from apps.core.subscriptions import services

    sub = make_sub(date(2026, 1, 1), allow_pause=True)
    run(date(2026, 1, 1))
    services.transition(sub, "paused", staff, today=date(2026, 2, 1))
    run(date(2026, 4, 1))  # nothing while paused
    assert Invoice.objects.count() == 1
    services.transition(Subscription.objects.get(pk=sub.pk), "active", staff, today=date(2026, 4, 1))
    run(date(2026, 4, 1))
    assert [i.period_start for i in invoices(sub)] == [date(2026, 1, 1), date(2026, 4, 1)]  # Feb and Mar were never billed


# --- mandatory 7: one bad subscription never stops the run ----------------------------------------------------

def test_one_failing_subscription_does_not_stop_the_run(make_sub):
    good1 = make_sub(date(2026, 11, 1))
    broken = make_sub(date(2026, 11, 1), lines=False)  # nothing to bill: the engine raises for it
    good2 = make_sub(date(2026, 11, 1))
    r = run(date(2026, 11, 1))
    assert (r.created_count, r.error_count) == (2, 1)
    assert broken.number in r.log or str(broken.pk) in r.log
    assert Invoice.objects.filter(subscription__in=[good1, good2]).count() == 2 and not invoices(broken)
    assert Subscription.objects.get(pk=broken.pk).next_invoice_date == date(2026, 11, 1)  # untouched, visible, retried next run


def test_failure_in_a_later_period_keeps_the_earlier_ones(make_sub, monkeypatch):
    sub = make_sub(date(2026, 1, 1))
    real, calls = engine.build_invoice, {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("boom")
        return real(*a, **k)

    monkeypatch.setattr(engine, "build_invoice", flaky)
    r = run(date(2026, 6, 1))
    assert (r.created_count, r.error_count) == (2, 1) and "boom" in r.log
    assert len(invoices(sub)) == 2 and Subscription.objects.get(pk=sub.pk).next_invoice_date == date(2026, 3, 1)
    monkeypatch.setattr(engine, "build_invoice", real)
    run(date(2026, 6, 1))
    assert len(invoices(sub)) == 6  # picks up exactly where it stopped, no duplicates


# --- mandatory 8: Odoo down -> the local invoice exists, marked pending ------------------------------------------

def test_odoo_down_leaves_a_pending_local_invoice(make_sub, odoo, django_capture_on_commit_callbacks):
    odoo("down")
    make_sub(date(2026, 11, 1))
    with django_capture_on_commit_callbacks(execute=True):
        r = run(date(2026, 11, 1))
    inv = Invoice.objects.get()
    assert r.created_count == 1 and r.error_count == 0
    assert inv.status == "draft" and inv.odoo_sync_status == "pending" and "refused" in inv.odoo_error and inv.odoo_move_id is None


def test_odoo_up_mirrors_the_draft_invoice(make_sub, cat, odoo, django_capture_on_commit_callbacks):
    fake = odoo()
    make_sub(date(2026, 11, 1))
    with django_capture_on_commit_callbacks(execute=True):
        run(date(2026, 11, 1))
    inv = Invoice.objects.get()
    assert inv.odoo_sync_status == "synced" and inv.odoo_move_id
    move = next(c for c in fake.calls if c[:2] == ("create", "account.move"))[2]
    (_, _, vals), = move["invoice_line_ids"]
    assert move["move_type"] == "out_invoice" and move["invoice_date_due"] == "2026-11-16"
    cat["gst"].refresh_from_db()
    assert vals["quantity"] == 5 and vals["price_unit"] == 1560.0
    assert cat["gst"].odoo_tax_id and vals["tax_ids"] == [(6, 0, [cat["gst"].odoo_tax_id])]  # tax pushed to Odoo first, then referenced
    inv.customer.profile.refresh_from_db()
    assert inv.customer.profile.odoo_partner_id  # partner created once and remembered


def test_odoo_disabled_marks_nothing_but_skipped(make_sub, settings, django_capture_on_commit_callbacks):
    settings.ODOO_ENABLED = False
    make_sub(date(2026, 11, 1))
    with django_capture_on_commit_callbacks(execute=True):
        run(date(2026, 11, 1))
    assert Invoice.objects.get().odoo_sync_status == "skipped"


def test_sync_odoo_command_retries_pending_invoices(make_sub, odoo, django_capture_on_commit_callbacks):
    odoo("down")
    make_sub(date(2026, 11, 1))
    with django_capture_on_commit_callbacks(execute=True):
        run(date(2026, 11, 1))
    assert Invoice.objects.get().odoo_sync_status == "pending"
    odoo()  # Odoo is back
    call_command("sync_odoo")
    assert Invoice.objects.get().odoo_sync_status == "synced"


# --- the run record, the command and the endpoint -------------------------------------------------------------------

def test_run_billing_command(make_sub, capsys):
    make_sub(date(2026, 11, 1))
    call_command("run_billing", "--as-of", "2026-11-01")
    assert "created=1 skipped=0 errors=0" in capsys.readouterr().out
    call_command("run_billing", "--as-of", "2026-11-01")
    assert "created=0" in capsys.readouterr().out


def test_billing_run_endpoint_and_history(make_sub, staff, cust):
    make_sub(date(2026, 11, 1))
    c = api_for(staff)
    r = c.post("/api/billing/run/", {"as_of": "2026-11-01"}, format="json")
    assert r.status_code == 200
    d = r.json()
    assert (d["created"], d["skipped"], d["errors"], d["as_of_date"]) == (1, 0, 0, "2026-11-01")
    assert c.post("/api/billing/run/", {"as_of": "2026-11-01"}, format="json").json()["created"] == 0
    runs = c.get("/api/billing/runs/").json()["results"]
    assert [x["created_count"] for x in runs] == [0, 1] and runs[0]["triggered_by_email"] == "staff@shop.com"
    assert c.get(f"/api/billing/runs/{d['run_id']}/").json()["log"] == ""
    assert c.post("/api/billing/run/", {"as_of": "not-a-date"}, format="json").status_code == 400


def test_billing_endpoints_are_staff_only(cust):
    for c in (api_for(cust), api_for()):
        assert c.post("/api/billing/run/", {}, format="json").status_code == 403
        assert c.get("/api/billing/runs/").status_code == 403
    assert Invoice.objects.count() == 0
