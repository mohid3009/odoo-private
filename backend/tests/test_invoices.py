from datetime import date
from decimal import Decimal

import pytest
from django.core import mail

from apps.core.billing import engine
from apps.core.billing.models import Invoice
from apps.finance.notifications.models import NotificationLog
from conftest import api_for, mk_user
from test_billing_engine import StubDiscounts

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def draft(make_sub):
    """One draft invoice (worked example: 5 x 1560 + 18% tax = 9204.00), billed on 2026-01-01 so it is long past due."""
    make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    return Invoice.objects.get()


def post(c, inv, action, body=None):
    return c.post(f"/api/invoices/{inv.pk}/{action}/", body or {}, format="json")


# --- confirm ------------------------------------------------------------------------------------------------

def test_confirm_assigns_sequential_numbers(draft, make_sub, staff):
    make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    c = api_for(staff)
    first, second = Invoice.objects.order_by("id")
    r = post(c, first, "confirm")
    assert r.status_code == 200 and r.json()["number"] == "INV-000001" and r.json()["status"] == "confirmed"
    assert post(c, second, "confirm").json()["number"] == "INV-000002"
    assert Invoice.objects.filter(status="draft").count() == 0


def test_drafts_have_no_number_and_confirm_is_once_only(draft, staff):
    assert draft.number is None
    c = api_for(staff)
    assert post(c, draft, "confirm").status_code == 200
    r = post(c, draft, "confirm")
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition"
    assert Invoice.objects.get().number == "INV-000001"  # the number did not change


def test_confirm_needs_a_product_line(draft, staff):
    draft.lines.all().delete()
    r = post(api_for(staff), draft, "confirm")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"


def test_zero_total_invoice_is_paid_on_confirm(draft, staff):
    Invoice.objects.filter(pk=draft.pk).update(total=0, amount_due=0)
    assert post(api_for(staff), draft, "confirm").json()["status"] == "paid"


def test_confirm_posts_to_odoo_after_commit(draft, staff, odoo, django_capture_on_commit_callbacks):
    fake = odoo(total=9204.0)
    with django_capture_on_commit_callbacks(execute=True):
        r = post(api_for(staff), draft, "confirm")
    assert r.status_code == 200
    inv = Invoice.objects.get()
    assert inv.odoo_sync_status == "synced" and inv.odoo_move_id and inv.odoo_error == ""
    assert any(c[:3] == ("execute", "account.move", "action_post") for c in fake.calls)


def test_odoo_total_mismatch_is_noted_but_local_stays_authoritative(draft, staff, odoo, django_capture_on_commit_callbacks):
    odoo(total=9000.0)
    with django_capture_on_commit_callbacks(execute=True):
        post(api_for(staff), draft, "confirm")
    inv = Invoice.objects.get()
    assert inv.odoo_sync_status == "synced" and "differs" in inv.odoo_error and inv.total == D("9204.00")


def test_odoo_down_does_not_block_the_confirm(draft, staff, odoo, django_capture_on_commit_callbacks):
    odoo("down")
    with django_capture_on_commit_callbacks(execute=True):
        r = post(api_for(staff), draft, "confirm")
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    inv = Invoice.objects.get()
    assert inv.odoo_sync_status == "pending" and inv.number == "INV-000001"


def test_confirm_sends_invoice_ready_once(draft, staff, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        post(api_for(staff), draft, "confirm")
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["c1@shop.com"] and "INV-000001" in mail.outbox[0].body
    assert "9204.00" in mail.outbox[0].body
    rows = {n.channel: n for n in NotificationLog.objects.all()}
    assert rows["email"].status == "sent" and rows["whatsapp"].status == "skipped" and rows["whatsapp"].skip_reason == "no_opt_in"


def test_a_failing_email_provider_never_fails_the_confirm(draft, staff, monkeypatch, django_capture_on_commit_callbacks):
    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr("apps.finance.notifications.services.send_mail", boom)
    with django_capture_on_commit_callbacks(execute=True):
        r = post(api_for(staff), draft, "confirm")
    assert r.status_code == 200 and Invoice.objects.get().status == "confirmed"
    row = NotificationLog.objects.get(channel="email")
    assert row.status == "failed" and row.attempts == 1 and "smtp down" in row.error and row.next_attempt_at


# --- cancel -------------------------------------------------------------------------------------------------

def test_staff_cancels_a_draft_but_the_period_is_never_rebilled(draft, staff):
    assert post(api_for(staff), draft, "cancel").json()["status"] == "cancelled"
    sub = draft.subscription
    sub.refresh_from_db()
    from apps.core.subscriptions.models import Subscription

    Subscription.objects.filter(pk=sub.pk).update(next_invoice_date=draft.period_start)  # even with the cursor rewound
    r = engine.run_billing(date(2026, 1, 1))
    assert r.created_count == 0 and r.skipped_count == 1 and Invoice.objects.count() == 1  # D-019


def test_confirmed_invoice_can_only_be_cancelled_by_admin(draft, staff, admin):
    post(api_for(staff), draft, "confirm")
    r = post(api_for(staff), draft, "cancel")
    assert r.status_code == 403 and Invoice.objects.get().status == "confirmed"
    assert post(api_for(admin), draft, "cancel").json()["status"] == "cancelled"


def test_cannot_cancel_with_payments_paid_or_already_cancelled(draft, staff, admin):
    post(api_for(staff), draft, "confirm")
    Invoice.objects.filter(pk=draft.pk).update(amount_paid=D("100.00"), amount_due=D("9104.00"))
    r = post(api_for(admin), draft, "cancel")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"
    Invoice.objects.filter(pk=draft.pk).update(status="paid")
    assert post(api_for(admin), draft, "cancel").json()["code"] == "illegal_transition"
    Invoice.objects.filter(pk=draft.pk).update(status="cancelled")
    assert post(api_for(admin), draft, "cancel").json()["code"] == "illegal_transition"
    assert post(api_for(admin), draft, "confirm").json()["code"] == "illegal_transition"


# --- send ---------------------------------------------------------------------------------------------------

def test_send_is_a_forced_resend_and_stamps_sent_at(draft, staff, django_capture_on_commit_callbacks):
    c = api_for(staff)
    assert post(c, draft, "send").json()["code"] == "illegal_transition"  # drafts cannot be sent
    with django_capture_on_commit_callbacks(execute=True):
        post(c, draft, "confirm")
    assert len(mail.outbox) == 1 and Invoice.objects.get().sent_at is None
    with django_capture_on_commit_callbacks(execute=True):
        r = post(c, draft, "send", {"channels": ["email"]})
    assert r.status_code == 200 and r.json()["sent_at"]
    assert len(mail.outbox) == 2  # a manual send always goes out
    assert NotificationLog.objects.filter(channel="email").count() == 2 and NotificationLog.objects.filter(channel="whatsapp").count() == 1


def test_send_rejects_unknown_channel(draft, staff):
    post(api_for(staff), draft, "confirm")
    assert post(api_for(staff), draft, "send", {"channels": ["sms"]}).status_code == 400


# --- permissions + row-level access ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", ["confirm", "cancel", "send"])
def test_customers_and_anonymous_cannot_act(draft, cust, action):
    for c in (api_for(cust), api_for()):
        assert post(c, draft, action).status_code == 403
    assert Invoice.objects.get().status == "draft"


def test_customer_sees_only_their_own_issued_invoices(make_sub, staff, cust):
    other = mk_user("c2@shop.com", "customer")
    make_sub(date(2026, 1, 1))
    make_sub(date(2026, 1, 1), customer=other)
    engine.run_billing(date(2026, 1, 1))
    mine, theirs = Invoice.objects.get(customer=cust), Invoice.objects.get(customer=other)
    c = api_for(cust)
    assert c.get("/api/invoices/").json()["count"] == 0 and c.get(f"/api/invoices/{mine.pk}/").status_code == 404  # still a draft
    post(api_for(staff), mine, "confirm")
    post(api_for(staff), theirs, "confirm")
    assert [i["id"] for i in c.get("/api/invoices/").json()["results"]] == [mine.pk]
    assert c.get(f"/api/invoices/{mine.pk}/").status_code == 200
    assert c.get(f"/api/invoices/{theirs.pk}/").status_code == 404
    assert c.get(f"/api/invoices/{theirs.pk}/print/").status_code == 404
    assert c.get(f"/api/invoices/?customer={other.pk}").json()["count"] == 0
    assert c.get(f"/api/invoices/?search={theirs.number}").json()["count"] == 0


def test_anonymous_cannot_list_invoices():
    assert api_for().get("/api/invoices/").status_code == 403


def test_staff_sees_everything_including_drafts(draft, staff):
    assert api_for(staff).get("/api/invoices/").json()["count"] == 1


# --- overdue (D-013) ---------------------------------------------------------------------------------------------

def test_overdue_rule_filter_and_days(make_sub, staff):
    from django.utils import timezone

    make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))  # due 2026-01-16
    inv = Invoice.objects.get()
    c = api_for(staff)
    post(c, inv, "confirm")
    d = c.get(f"/api/invoices/{inv.pk}/").json()
    expected = (timezone.localdate() - date(2026, 1, 16)).days
    assert d["is_overdue"] and d["days_overdue"] == expected > 0
    assert c.get("/api/invoices/?overdue=true").json()["count"] == 1
    Invoice.objects.filter(pk=inv.pk).update(amount_due=0, status="paid")  # settled
    assert c.get("/api/invoices/?overdue=true").json()["count"] == 0 and c.get(f"/api/invoices/{inv.pk}/").json()["days_overdue"] == 0
    Invoice.objects.filter(pk=inv.pk).update(status="confirmed", amount_due=D("5.00"), due_date=timezone.localdate())
    assert c.get("/api/invoices/?overdue=true").json()["count"] == 0  # due today is not overdue yet


def test_draft_and_cancelled_are_never_overdue(draft, staff):
    assert api_for(staff).get("/api/invoices/?overdue=true").json()["count"] == 0
    Invoice.objects.filter(pk=draft.pk).update(status="cancelled")
    assert api_for(staff).get("/api/invoices/?overdue=true").json()["count"] == 0


# --- read shape --------------------------------------------------------------------------------------------------------

def test_detail_shows_lines_totals_and_actions(make_sub, staff, admin):
    make_sub(date(2026, 11, 1))
    engine.run_billing(date(2026, 11, 1), hooks=StubDiscounts())
    inv = Invoice.objects.get()
    d = api_for(staff).get(f"/api/invoices/{inv.pk}/").json()
    assert (d["subtotal"], d["discount_total"], d["tax_total"], d["total"], d["amount_due"]) == ("7800.00", "780.00", "1263.60", "8283.60", "8283.60")
    assert [(l["kind"], l["quantity"], l["unit_price"], l["tax_rate"], l["line_subtotal"], l["line_total"]) for l in d["lines"]] == [
        ("product", 5, "1560.00", "18.00", "7800.00", "9204.00"), ("discount", 1, "-780.00", "18.00", "-780.00", "-920.40")]
    assert d["invoice_date"] == "2026-11-01" and d["due_date"] == "2026-11-16"
    assert (d["period_start"], d["period_end"]) == ("2026-11-01", "2026-11-30")
    assert d["number"] is None and d["subscription_number"] == "SUB-000001" and d["actions"] == ["confirm", "cancel"]
    assert api_for(admin).get(f"/api/invoices/{inv.pk}/").json()["actions"] == ["confirm", "cancel"]


@pytest.mark.parametrize("status,paid,role,expected", [
    ("confirmed", "0.00", "staff", ["send", "pay"]), ("confirmed", "0.00", "admin", ["send", "pay", "cancel"]),
    ("confirmed", "50.00", "admin", ["send", "pay"]), ("paid", "9204.00", "staff", ["send"]), ("cancelled", "0.00", "admin", []),
])
def test_available_actions(draft, status, paid, role, expected):
    Invoice.objects.filter(pk=draft.pk).update(status=status, amount_paid=D(paid))
    assert api_for(mk_user(f"{role}@x.com", role)).get(f"/api/invoices/{draft.pk}/").json()["actions"] == expected


def test_list_filters_search_ordering_and_no_n_plus_one(make_sub, staff, django_assert_max_num_queries):
    for _ in range(30):
        make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    first = Invoice.objects.order_by("id").first()
    post(api_for(staff), first, "confirm")
    c = api_for(staff)
    with django_assert_max_num_queries(6):  # session, user, count, page: constant, not per row
        d = c.get("/api/invoices/").json()
    assert d["count"] == 30 and len(d["results"]) == 25 and d["next"]
    assert c.get("/api/invoices/?status=confirmed").json()["count"] == 1
    assert c.get("/api/invoices/?status=draft").json()["count"] == 29
    assert c.get(f"/api/invoices/?subscription={first.subscription_id}").json()["count"] == 1
    assert c.get("/api/invoices/?search=INV-000001").json()["count"] == 1
    assert c.get("/api/invoices/?search=SUB-000030").json()["count"] == 1
    assert c.get("/api/invoices/?ordering=id").json()["results"][0]["id"] == first.pk


# --- print data ------------------------------------------------------------------------------------------------------------

def test_print_data_for_staff_and_the_owning_customer(draft, staff, cust):
    cust.name, cust.save()
    cust.profile.company_name, cust.profile.address = "Shop Ltd", "1 Main St"
    cust.profile.save()
    post(api_for(staff), draft, "confirm")
    for c in (api_for(staff), api_for(cust)):
        d = c.get(f"/api/invoices/{draft.pk}/print/").json()
        assert d["number"] == "INV-000001" and d["seller"] == {"name": "Brightloop Software"}
        assert d["customer_details"]["company_name"] == "Shop Ltd" and d["customer_details"]["address"] == "1 Main St"
        assert len(d["lines"]) == 1
