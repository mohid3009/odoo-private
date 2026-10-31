import threading
import time
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.billing import engine
from apps.core.billing import services as billing_services
from apps.core.billing.models import Invoice
from apps.core.subscriptions.services import TransitionError
from apps.finance.discounts.models import Discount
from apps.finance.notifications.models import NotificationLog
from apps.finance.payments import services
from apps.finance.payments.models import Payment, PaymentEvent
from conftest import api_for, mk_user

pytestmark = pytest.mark.django_db
D = Decimal
TOTAL = D("9204.00")  # 5 x 1560.00 + 18% tax


@pytest.fixture
def inv(make_sub, staff):
    """A confirmed, unpaid invoice of 9204.00, billed on 2026-01-01 so it is long past its due date (2026-01-16)."""
    make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    return billing_services.confirm(Invoice.objects.get(), staff)


def pay(c, invoice, amount, **over):
    body = {"amount": str(amount), "method": "bank_transfer"} | over
    return c.post(f"/api/invoices/{invoice.pk}/payments/", body, format="json")


def fail(c, invoice, amount="1000.00", reason="card declined", **over):
    return pay(c, invoice, amount, status="failed", failure_reason=reason, method="card", **over)


def fresh(invoice):
    invoice.refresh_from_db()
    return invoice


def check_invariants(invoice):
    """The denormalised totals must always equal a recomputation from the payment rows."""
    inv = fresh(invoice)
    completed = Payment.objects.filter(invoice=inv, status="completed").aggregate(s=Sum("amount"))["s"] or D("0")
    assert inv.amount_paid == completed and inv.amount_due == inv.total - completed
    assert (inv.status == "paid") == (inv.amount_due == 0)
    assert inv.failed_attempts >= 0 and inv.payment_needs_attention == (inv.failed_attempts >= 3)


# --- recording + partial payments (FR-PAY-01..03) ------------------------------------------------------------------

def test_partial_then_full_payment_flips_to_paid_exactly_at_the_sum(inv, staff):
    c = api_for(staff)
    r = pay(c, inv, "3000.00", note="first part")
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "completed" and d["attempt_number"] == 1 and d["retry_of"] is None and d["note"] == "first part"
    assert d["invoice_state"] == {"status": "confirmed", "amount_paid": "3000.00", "amount_due": "6204.00", "failed_attempts": 0, "payment_needs_attention": False}
    assert d["recorded_by_email"] == "staff@shop.com" and d["invoice_number"] == inv.number and d["customer_email"] == "c1@shop.com"
    r = pay(c, inv, "6204.00")
    assert r.status_code == 201 and r.json()["invoice_state"]["status"] == "paid" and r.json()["invoice_state"]["amount_due"] == "0.00"
    check_invariants(inv)


def test_paid_flips_on_the_last_paisa_not_before(inv, staff):
    c = api_for(staff)
    assert pay(c, inv, "9203.99").json()["invoice_state"]["status"] == "confirmed"
    assert fresh(inv).amount_due == D("0.01")
    assert pay(c, inv, "0.01").json()["invoice_state"]["status"] == "paid"
    check_invariants(inv)


def test_many_small_payments_add_up_without_drift(inv, staff):
    c = api_for(staff)
    for i in range(3):
        r = pay(c, inv, "3068.00")
        assert r.json()["invoice_state"]["status"] == ("paid" if i == 2 else "confirmed")
    assert fresh(inv).amount_paid == TOTAL
    check_invariants(inv)


def test_payment_defaults_and_validation(inv, staff):
    c = api_for(staff)
    d = pay(c, inv, "10.00").json()
    assert d["payment_date"] == str(timezone.localdate()) and d["note"] == ""
    assert pay(c, inv, "10.00", payment_date="2026-02-01").json()["payment_date"] == "2026-02-01"
    bad = [
        ({"payment_date": str(timezone.localdate() + timedelta(days=1))}, "payment_date"),
        ({"method": "bitcoin"}, "method"), ({"amount": "0"}, "amount"), ({"amount": "-5.00"}, "amount"),
        ({"amount": "10.005"}, "amount"), ({"amount": "abc"}, "amount"), ({"status": "reversed"}, "status"), ({"status": "pending"}, "status"),
    ]
    for over, field in bad:
        r = c.post(f"/api/invoices/{inv.pk}/payments/", {"amount": "10.00", "method": "bank_transfer"} | over, format="json")
        assert r.status_code == 400 and field in r.json(), (over, r.json())
    assert c.post(f"/api/invoices/{inv.pk}/payments/", {"amount": "5.00"}, format="json").status_code == 400  # method is required
    assert Payment.objects.count() == 2
    check_invariants(inv)


# --- overpayments (FR-PAY-02) -----------------------------------------------------------------------------------------

def test_overpayment_is_rejected_and_changes_nothing(inv, staff):
    c = api_for(staff)
    r = pay(c, inv, "9204.01")
    assert r.status_code == 400 and "more than the balance" in r.json()["amount"] and Payment.objects.count() == 0
    pay(c, inv, "9000.00")
    assert pay(c, inv, "204.01").status_code == 400  # one paisa over the remaining balance
    assert fresh(inv).amount_paid == D("9000.00") and Payment.objects.count() == 1
    assert pay(c, inv, "204.00").json()["invoice_state"]["status"] == "paid"  # exactly the balance is fine
    check_invariants(inv)


def test_a_failed_attempt_cannot_exceed_the_balance_either(inv, staff):
    assert fail(api_for(staff), inv, "99999.00").status_code == 400
    assert Payment.objects.count() == 0 and fresh(inv).failed_attempts == 0


# --- invoice state + authorization -------------------------------------------------------------------------------------

def test_payment_on_draft_cancelled_or_paid_invoices_is_refused(make_sub, staff):
    make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    invoice = Invoice.objects.get()
    c = api_for(staff)
    r = pay(c, invoice, "10.00")
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition" and "Confirm" in r.json()["detail"]  # draft
    Invoice.objects.filter(pk=invoice.pk).update(status="cancelled")
    assert pay(c, invoice, "10.00").status_code == 409
    Invoice.objects.filter(pk=invoice.pk).update(status="paid", amount_due=0, amount_paid=TOTAL)
    r = pay(c, invoice, "10.00")
    assert r.status_code == 409 and "already paid" in r.json()["detail"]
    assert Payment.objects.count() == 0


@pytest.mark.parametrize("who", ["customer", "anonymous"])
def test_customers_and_anonymous_cannot_record_retry_or_reverse(inv, who, cust, staff):
    c = api_for(cust if who == "customer" else None)
    failed = fail(api_for(staff), inv).json()
    done = pay(api_for(staff), inv, "100.00").json()
    assert pay(c, inv, "10.00").status_code == 403
    assert c.post(f"/api/payments/{failed['id']}/retry/", {"amount": "10", "method": "cash"}, format="json").status_code == 403
    assert c.post(f"/api/payments/{done['id']}/reverse/", {"reason": "x"}, format="json").status_code == 403
    assert c.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {"reason": "x"}, format="json").status_code == 403
    assert Payment.objects.filter(status="completed").count() == 1 and Payment.objects.count() == 2


def test_only_admin_can_reverse_or_reset(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    done = pay(s, inv, "100.00").json()
    r = s.post(f"/api/payments/{done['id']}/reverse/", {"reason": "typo"}, format="json")
    assert r.status_code == 403 and Payment.objects.get().status == "completed"
    for _ in range(3):
        fail(s, inv, "10.00")
    assert s.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {"reason": "x"}, format="json").status_code == 403
    assert fresh(inv).payment_needs_attention
    assert a.post(f"/api/payments/{done['id']}/reverse/", {"reason": "typo"}, format="json").status_code == 200
    assert a.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {"reason": "reviewed"}, format="json").status_code == 200


# --- failed attempts (FR: failed attempts never touch balances) ---------------------------------------------------------

def test_a_failed_attempt_does_not_touch_the_balance(inv, staff):
    c = api_for(staff)
    pay(c, inv, "1000.00")
    before = fresh(inv)
    r = fail(c, inv, "2000.00", reason="insufficient funds")
    assert r.status_code == 201
    d = r.json()
    assert d["status"] == "failed" and d["failure_reason"] == "insufficient funds" and d["attempt_number"] == 1
    assert d["invoice_state"] == {"status": "confirmed", "amount_paid": "1000.00", "amount_due": "8204.00", "failed_attempts": 1, "payment_needs_attention": False}
    after = fresh(inv)
    assert (after.amount_paid, after.amount_due, after.status) == (before.amount_paid, before.amount_due, before.status)
    check_invariants(inv)


def test_a_failed_attempt_needs_a_reason(inv, staff):
    r = pay(api_for(staff), inv, "10.00", status="failed", failure_reason="  ")
    assert r.status_code == 400 and "failure_reason" in r.json() and Payment.objects.count() == 0


def test_a_failed_attempt_sends_no_receipt(inv, staff, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        fail(api_for(staff), inv)
    assert not NotificationLog.objects.filter(event__code="PAYMENT_RECEIVED").exists()


def test_attempt_numbers_count_failures_and_a_success_resets_the_streak(inv, staff):
    c = api_for(staff)
    assert [fail(c, inv).json()["attempt_number"] for _ in range(2)] == [1, 2]
    ok = pay(c, inv, "500.00").json()
    assert ok["attempt_number"] == 3 and ok["invoice_state"]["failed_attempts"] == 0  # the 3rd attempt succeeded; counter cleared
    assert fail(c, inv).json()["attempt_number"] == 1  # a new streak starts over


# --- maximum attempts + attention flag -------------------------------------------------------------------------------------

def test_third_failure_flags_the_invoice_and_blocks_more_attempts(inv, staff):
    c = api_for(staff)
    assert fail(c, inv).json()["invoice_state"]["payment_needs_attention"] is False
    assert fail(c, inv).json()["invoice_state"]["payment_needs_attention"] is False
    third = fail(c, inv).json()
    assert third["attempt_number"] == 3 and third["invoice_state"]["payment_needs_attention"] is True and third["invoice_state"]["failed_attempts"] == 3
    for attempt in (lambda: pay(c, inv, "10.00"), lambda: fail(c, inv, "10.00")):
        r = attempt()
        assert r.status_code == 409 and r.json()["code"] == "max_attempts_reached"
    assert Payment.objects.count() == 3 and fresh(inv).status == "confirmed"
    check_invariants(inv)


def test_the_limit_is_configurable(inv, staff, settings):
    settings.PAYMENT_MAX_ATTEMPTS = 2
    c = api_for(staff)
    fail(c, inv)
    assert fail(c, inv).json()["invoice_state"]["payment_needs_attention"] is True
    assert pay(c, inv, "10.00").json()["code"] == "max_attempts_reached"
    settings.PAYMENT_MAX_ATTEMPTS = 5  # raising the limit unblocks further attempts without data changes
    assert pay(c, inv, "10.00").status_code == 201


def test_attention_flag_is_visible_to_staff_filterable_and_hidden_from_the_customer(inv, staff, cust):
    s = api_for(staff)
    assert s.get("/api/invoices/?needs_attention=true").json()["count"] == 0
    for _ in range(3):
        fail(s, inv)
    d = s.get(f"/api/invoices/{inv.pk}/").json()
    assert d["payment_needs_attention"] is True and d["failed_attempts"] == 3 and "pay" not in d["actions"]
    assert s.get("/api/invoices/?needs_attention=true").json()["count"] == 1
    assert s.get("/api/payments/?needs_attention=true").json()["count"] == 3
    c = api_for(cust).get(f"/api/invoices/{inv.pk}/").json()
    assert "payment_needs_attention" not in c and "failed_attempts" not in c
    assert "payment_needs_attention" not in api_for(cust).get("/api/invoices/").json()["results"][0]


def test_admin_reset_clears_the_flag_keeps_the_history_and_is_audited(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    for _ in range(3):
        fail(s, inv)
    assert a.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {}, format="json").status_code == 400  # a reason is required
    assert "reset_attempts" in a.get(f"/api/invoices/{inv.pk}/").json()["actions"] and "reset_attempts" not in s.get(f"/api/invoices/{inv.pk}/").json()["actions"]
    r = a.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {"reason": "called the customer"}, format="json")
    assert r.status_code == 200 and r.json()["payment_needs_attention"] is False and r.json()["failed_attempts"] == 0
    assert Payment.objects.filter(status="failed").count() == 3  # nothing is erased
    reset = PaymentEvent.objects.get(kind="attention_reset")
    assert reset.detail == "called the customer" and reset.by_user == admin and reset.payment is None
    assert pay(s, inv, "100.00").status_code == 201
    r = a.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {"reason": "again"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"  # nothing to reset any more


# --- retries -----------------------------------------------------------------------------------------------------------------

def test_retry_links_the_attempts_and_increments_the_number(inv, staff):
    c = api_for(staff)
    first = fail(c, inv, "2000.00").json()
    r = c.post(f"/api/payments/{first['id']}/retry/", {"amount": "2000.00", "method": "card"}, format="json")
    assert r.status_code == 201
    second = r.json()
    assert second["retry_of"] == first["id"] and second["attempt_number"] == 2 and second["status"] == "completed"
    assert second["invoice_state"]["amount_paid"] == "2000.00"
    assert c.get(f"/api/payments/{first['id']}/").json()["retried_by"] == second["id"]
    kinds = list(PaymentEvent.objects.filter(payment_id=second["id"]).values_list("kind", flat=True))
    assert kinds == ["retried", "recorded"]
    check_invariants(inv)


def test_retry_chain_can_fail_again_and_count_toward_the_limit(inv, staff):
    c = api_for(staff)
    a = fail(c, inv).json()
    b = c.post(f"/api/payments/{a['id']}/retry/", {"amount": "1000", "method": "card", "status": "failed", "failure_reason": "declined"}, format="json").json()
    third = c.post(f"/api/payments/{b['id']}/retry/", {"amount": "1000", "method": "card", "status": "failed", "failure_reason": "declined"}, format="json").json()
    assert [a["attempt_number"], b["attempt_number"], third["attempt_number"]] == [1, 2, 3]
    assert (b["retry_of"], third["retry_of"]) == (a["id"], b["id"]) and third["invoice_state"]["payment_needs_attention"] is True
    r = c.post(f"/api/payments/{third['id']}/retry/", {"amount": "1000", "method": "card"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "max_attempts_reached" and Payment.objects.count() == 3


def test_only_a_failed_attempt_can_be_retried_and_only_once(inv, staff):
    c = api_for(staff)
    ok = pay(c, inv, "100.00").json()
    r = c.post(f"/api/payments/{ok['id']}/retry/", {"amount": "10", "method": "cash"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition"
    failed = fail(c, inv).json()
    assert c.post(f"/api/payments/{failed['id']}/retry/", {"amount": "10", "method": "cash"}, format="json").status_code == 201
    r = c.post(f"/api/payments/{failed['id']}/retry/", {"amount": "10", "method": "cash"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"
    assert Payment.objects.filter(retry_of=failed["id"]).count() == 1


def test_the_database_itself_allows_one_retry_per_failed_attempt(inv, staff):
    failed = Payment.objects.get(pk=fail(api_for(staff), inv).json()["id"])
    Payment.objects.create(invoice=inv, amount=D("5"), method="cash", payment_date=date(2026, 1, 2), retry_of=failed, attempt_number=2)
    with pytest.raises(IntegrityError), transaction.atomic():
        Payment.objects.create(invoice=inv, amount=D("5"), method="cash", payment_date=date(2026, 1, 2), retry_of=failed, attempt_number=2)


def test_retry_validates_like_a_new_payment(inv, staff):
    c = api_for(staff)
    failed = fail(c, inv).json()
    r = c.post(f"/api/payments/{failed['id']}/retry/", {"amount": "99999", "method": "cash"}, format="json")
    assert r.status_code == 400 and "amount" in r.json()
    r = c.post(f"/api/payments/{failed['id']}/retry/", {"amount": "10", "method": "cash", "status": "failed"}, format="json")
    assert r.status_code == 400 and "failure_reason" in r.json()
    assert not Payment.objects.filter(retry_of=failed["id"]).exists()


def test_cannot_retry_once_the_invoice_is_paid_or_unknown_ids(inv, staff):
    c = api_for(staff)
    failed = fail(c, inv).json()
    pay(c, inv, "9204.00")  # settled another way
    r = c.post(f"/api/payments/{failed['id']}/retry/", {"amount": "10", "method": "cash"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition"
    assert c.post("/api/payments/99999/retry/", {"amount": "10", "method": "cash"}, format="json").status_code == 404


# --- reversals ------------------------------------------------------------------------------------------------------------------

def test_reversing_a_payment_restores_the_balance_and_paid_goes_back_to_confirmed(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    pay(s, inv, "4000.00")
    last = pay(s, inv, "5204.00").json()
    assert fresh(inv).status == "paid"
    r = a.post(f"/api/payments/{last['id']}/reverse/", {"reason": "bounced cheque"}, format="json")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "reversed" and d["reversal_reason"] == "bounced cheque" and d["reversed_by_email"] == "admin@shop.com" and d["reversed_at"]
    assert d["invoice_state"] == {"status": "confirmed", "amount_paid": "4000.00", "amount_due": "5204.00", "failed_attempts": 0, "payment_needs_attention": False}
    assert Payment.objects.count() == 2  # the reversed row is history, not deleted
    check_invariants(inv)


def test_reversal_makes_a_past_due_invoice_overdue_again(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    done = pay(s, inv, "9204.00").json()
    assert s.get(f"/api/invoices/{inv.pk}/").json()["is_overdue"] is False and s.get("/api/invoices/?overdue=true").json()["count"] == 0
    a.post(f"/api/payments/{done['id']}/reverse/", {"reason": "refunded"}, format="json")
    d = s.get(f"/api/invoices/{inv.pk}/").json()
    assert d["status"] == "confirmed" and d["is_overdue"] is True and d["days_overdue"] > 0 and d["amount_due"] == "9204.00"
    assert s.get("/api/invoices/?overdue=true").json()["count"] == 1


def test_partial_overdue_stays_overdue_until_the_final_payment(inv, staff):
    s = api_for(staff)
    pay(s, inv, "1000.00")
    assert s.get(f"/api/invoices/{inv.pk}/").json()["is_overdue"] is True  # D-013: the balance is still > 0
    pay(s, inv, "8204.00")
    assert s.get(f"/api/invoices/{inv.pk}/").json()["is_overdue"] is False


def test_reversal_needs_a_reason_and_a_completed_payment(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    done = pay(s, inv, "100.00").json()
    failed = fail(s, inv).json()
    for body in ({}, {"reason": ""}, {"reason": "   "}):
        r = a.post(f"/api/payments/{done['id']}/reverse/", body, format="json")
        assert r.status_code == 400 and "reason" in r.json()
    assert Payment.objects.get(pk=done["id"]).status == "completed"
    r = a.post(f"/api/payments/{failed['id']}/reverse/", {"reason": "x"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition"
    assert a.post(f"/api/payments/{done['id']}/reverse/", {"reason": "typo"}, format="json").status_code == 200
    r = a.post(f"/api/payments/{done['id']}/reverse/", {"reason": "again"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition"  # cannot reverse twice
    assert a.post("/api/payments/99999/reverse/", {"reason": "x"}, format="json").status_code == 404


def test_reversal_leaves_the_attempt_counter_alone_and_the_invoice_payable_again(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    fail(s, inv)
    done = pay(s, inv, "9204.00").json()
    fail_after = Invoice.objects.get(pk=inv.pk)
    assert fail_after.failed_attempts == 0
    a.post(f"/api/payments/{done['id']}/reverse/", {"reason": "refund"}, format="json")
    assert fresh(inv).failed_attempts == 0
    assert pay(s, inv, "9204.00").json()["invoice_state"]["status"] == "paid"  # paid again after the reversal
    assert Payment.objects.filter(status="reversed").count() == 1 and Payment.objects.filter(status="completed").count() == 1
    check_invariants(inv)


def test_cancel_is_blocked_while_a_completed_payment_exists_but_allowed_after_a_full_reversal(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    done = pay(s, inv, "100.00").json()
    r = a.post(f"/api/invoices/{inv.pk}/cancel/")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"
    a.post(f"/api/payments/{done['id']}/reverse/", {"reason": "oops"}, format="json")
    assert a.post(f"/api/invoices/{inv.pk}/cancel/").json()["status"] == "cancelled"
    assert Payment.objects.count() == 1  # the reversed payment is still on file


def test_a_payment_on_a_cancelled_invoice_cannot_be_reversed(inv, admin):
    p = Payment.objects.create(invoice=inv, amount=D("5"), method="cash", payment_date=date(2026, 1, 2))
    Invoice.objects.filter(pk=inv.pk).update(status="cancelled")
    r = api_for(admin).post(f"/api/payments/{p.pk}/reverse/", {"reason": "x"}, format="json")
    assert r.status_code == 409 and Payment.objects.get(pk=p.pk).status == "completed"


# --- audit trail + immutability -------------------------------------------------------------------------------------------------

def test_the_audit_trail_records_every_step_in_order(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    f1 = fail(s, inv, reason="declined").json()
    retry = s.post(f"/api/payments/{f1['id']}/retry/", {"amount": "500", "method": "upi"}, format="json").json()
    a.post(f"/api/payments/{retry['id']}/reverse/", {"reason": "customer asked"}, format="json")
    events = a.get(f"/api/payments/{retry['id']}/").json()["events"]
    assert [(e["kind"], e["by_user_email"], e["detail"]) for e in events] == [
        ("retried", "staff@shop.com", f"retry of payment #{f1['id']} (attempt 1)"), ("recorded", "staff@shop.com", ""), ("reversed", "admin@shop.com", "customer asked")]
    assert [e["kind"] for e in a.get(f"/api/payments/{f1['id']}/").json()["events"]] == ["failed"]


def test_payments_cannot_be_edited_or_deleted_over_the_api(inv, staff, admin):
    p = pay(api_for(staff), inv, "100.00").json()
    for c in (api_for(staff), api_for(admin)):
        assert c.patch(f"/api/payments/{p['id']}/", {"amount": "1.00"}, format="json").status_code == 405
        assert c.put(f"/api/payments/{p['id']}/", {"amount": "1.00"}, format="json").status_code == 405
        assert c.delete(f"/api/payments/{p['id']}/").status_code == 405
        assert c.post("/api/payments/", {"amount": "1.00"}, format="json").status_code == 405
    assert Payment.objects.get().amount == D("100.00")


# --- notifications ------------------------------------------------------------------------------------------------------------------

def test_a_completed_payment_sends_one_receipt_with_the_balance(inv, staff, django_capture_on_commit_callbacks):
    s = api_for(staff)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        pay(s, inv, "1000.00")
        pay(s, inv, "8204.00")
    bodies = [m.body for m in mail.outbox if "payment" in m.subject.lower() or "received" in m.body]
    assert len(bodies) == 2
    assert "1000.00" in bodies[0] and "Remaining balance: ₹8204.00" in bodies[0]
    assert "8204.00" in bodies[1] and "paid in full" in bodies[1]


def test_a_failing_email_provider_never_fails_a_payment(inv, staff, monkeypatch, django_capture_on_commit_callbacks):
    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr("apps.finance.notifications.services.send_mail", boom)
    with django_capture_on_commit_callbacks(execute=True):
        r = pay(api_for(staff), inv, "9204.00")
    assert r.status_code == 201 and fresh(inv).status == "paid"


# --- reads + scoping ------------------------------------------------------------------------------------------------------------------

def test_invoice_detail_lists_its_payments_and_offers_pay(inv, staff):
    s = api_for(staff)
    assert "pay" in s.get(f"/api/invoices/{inv.pk}/").json()["actions"]
    pay(s, inv, "100.00")
    fail(s, inv)
    d = s.get(f"/api/invoices/{inv.pk}/").json()
    assert [(p["status"], p["amount"]) for p in d["payments"]] == [("failed", "1000.00"), ("completed", "100.00")]
    assert [p["id"] for p in s.get(f"/api/invoices/{inv.pk}/payments/").json()["results"]] == [p["id"] for p in d["payments"]]
    pay(s, inv, "9104.00")
    assert "pay" not in s.get(f"/api/invoices/{inv.pk}/").json()["actions"]  # paid


def test_payment_list_filters_search_ordering_and_pagination(inv, staff, cust):
    s = api_for(staff)
    pay(s, inv, "100.00", method="cash", payment_date="2026-01-05", note="front desk")
    pay(s, inv, "200.00", method="upi", payment_date="2026-02-10")
    fail(s, inv, "300.00")
    assert s.get("/api/payments/").json()["count"] == 3
    assert s.get("/api/payments/?status=failed").json()["count"] == 1
    assert s.get("/api/payments/?method=upi").json()["count"] == 1
    assert s.get(f"/api/payments/?invoice={inv.pk}").json()["count"] == 3
    assert s.get(f"/api/payments/?customer={cust.pk}").json()["count"] == 3
    assert s.get("/api/payments/?payment_date_after=2026-02-01&payment_date_before=2026-02-28").json()["count"] == 1
    assert s.get("/api/payments/?payment_date_before=2026-01-05").json()["count"] == 1  # inclusive
    assert s.get("/api/payments/?search=front").json()["count"] == 1
    assert s.get(f"/api/payments/?search={inv.number}").json()["count"] == 3
    assert [p["amount"] for p in s.get("/api/payments/?ordering=amount").json()["results"]] == ["100.00", "200.00", "300.00"]
    assert s.get("/api/payments/?status=reversed").json()["count"] == 0


def test_payment_list_has_no_n_plus_one(inv, staff, django_assert_max_num_queries):
    s = api_for(staff)
    for _ in range(2):
        fail(s, inv, "10.00")
    for _ in range(25):
        pay(s, inv, "10.00")
    with django_assert_max_num_queries(8):  # session, user, count, page, retries prefetch: constant, not per row
        d = s.get("/api/payments/").json()
    assert d["count"] == 27 and len(d["results"]) == 25


def test_customers_see_only_their_own_payments_and_fewer_fields(make_sub, staff, cust):
    other = mk_user("c2@shop.com", "customer")
    make_sub(date(2026, 1, 1))
    make_sub(date(2026, 1, 1), customer=other)
    engine.run_billing(date(2026, 1, 1))
    mine, theirs = [billing_services.confirm(i, staff) for i in Invoice.objects.order_by("id")]
    mine, theirs = (mine, theirs) if mine.customer_id == cust.pk else (theirs, mine)
    s = api_for(staff)
    pay(s, mine, "100.00", note="internal note")
    fail(s, mine, "50.00", reason="internal reason")
    other_payment = pay(s, theirs, "700.00").json()
    c = api_for(cust)
    rows = c.get("/api/payments/").json()
    assert rows["count"] == 2
    assert set(rows["results"][0]) == {"id", "invoice", "invoice_number", "amount", "method", "payment_date", "status", "attempt_number", "created_at"}
    assert c.get(f"/api/payments/{rows['results'][0]['id']}/").status_code == 200
    assert c.get(f"/api/payments/{other_payment['id']}/").status_code == 404
    assert c.get(f"/api/invoices/{theirs.pk}/payments/").status_code == 404
    assert c.get(f"/api/payments/?customer={other.pk}").json()["count"] == 0  # filters cannot widen the scope
    assert len(c.get(f"/api/invoices/{mine.pk}/payments/").json()["results"]) == 2
    d = c.get(f"/api/invoices/{mine.pk}/").json()
    assert all(set(p) <= {"id", "invoice", "invoice_number", "amount", "method", "payment_date", "status", "attempt_number", "created_at"} for p in d["payments"])
    assert "internal" not in str(c.get(f"/api/payments/").json())
    assert api_for().get("/api/payments/").status_code == 403


# --- compatibility with phases 4 and 5, and Odoo ----------------------------------------------------------------------------------------

def test_paying_an_invoice_with_a_discount_line(make_sub, cat, staff):
    d = Discount.objects.create(name="Launch 10%", type="percent", value=10, scope="product", usage_limit=2)
    d.products.add(cat["crm"])
    make_sub(date(2026, 11, 1))
    engine.run_billing(date(2026, 11, 1))
    invoice = billing_services.confirm(Invoice.objects.get(), staff)
    assert invoice.total == D("8283.60")
    s = api_for(staff)
    assert pay(s, invoice, "8283.61").status_code == 400
    assert pay(s, invoice, "8283.60").json()["invoice_state"]["status"] == "paid"
    assert Discount.objects.get().used_count == 1  # paying does not touch the discount
    assert engine.run_billing(date(2026, 11, 1)).created_count == 0  # nor does it make billing re-bill the period


def test_payments_never_call_odoo_and_work_with_odoo_enabled_or_not(inv, staff, odoo):
    fake = odoo("down")  # any Odoo call would raise OdooUnavailable
    calls_before = len(fake.calls)
    r = pay(api_for(staff), inv, "100.00")
    assert r.status_code == 201 and r.json()["odoo_sync_status"] == "skipped" and len(fake.calls) == calls_before
    assert fresh(inv).amount_paid == D("100.00")


def test_payments_work_with_odoo_disabled(inv, staff, settings):
    settings.ODOO_ENABLED = False
    assert pay(api_for(staff), inv, "9204.00").json()["invoice_state"]["status"] == "paid"


def test_invoice_list_still_filters_paid_outstanding_overdue(make_sub, staff):
    for _ in range(3):
        make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    a, b, c3 = [billing_services.confirm(i, staff) for i in Invoice.objects.order_by("id")]
    s = api_for(staff)
    pay(s, a, "9204.00")
    pay(s, b, "100.00")
    assert s.get("/api/invoices/?status=paid").json()["count"] == 1
    assert s.get("/api/invoices/?status=confirmed").json()["count"] == 2  # outstanding
    assert s.get("/api/invoices/?overdue=true").json()["count"] == 2  # the partial one and the untouched one
    assert {i["id"] for i in s.get("/api/invoices/?overdue=true").json()["results"]} == {b.pk, c3.pk}


# --- invariants under a random-ish sequence ---------------------------------------------------------------------------------------------------

def test_totals_always_match_a_recomputation_over_a_long_sequence(inv, staff, admin):
    s, a = api_for(staff), api_for(admin)
    steps = [("pay", "1000.00"), ("fail", "500.00"), ("pay", "2204.00"), ("rev", 0), ("fail", "10.00"), ("pay", "7000.00"),
             ("rev", 1), ("reset", None), ("pay", "9204.00"), ("rev", 0), ("pay", "0.01"), ("fail", "1.00"), ("rev", -1)]
    for kind, arg in steps:
        completed = list(Payment.objects.filter(status="completed").order_by("id"))
        if kind == "pay":
            pay(s, inv, arg)
        elif kind == "fail":
            fail(s, inv, arg)
        elif kind == "rev" and completed:
            a.post(f"/api/payments/{completed[min(arg, len(completed) - 1)].pk}/reverse/", {"reason": "test"}, format="json")
        elif kind == "reset":
            a.post(f"/api/invoices/{inv.pk}/reset-payment-attempts/", {"reason": "test"}, format="json")
        check_invariants(inv)


def test_service_layer_enforces_roles_even_without_the_http_permission_classes(inv, cust, staff):
    with pytest.raises(PermissionDenied):
        services.record_payment(inv, cust, {"amount": D("1"), "method": "cash"})
    p = services.record_payment(inv, staff, {"amount": D("1"), "method": "cash"})[0]
    with pytest.raises(PermissionDenied):
        services.reverse_payment(p.pk, staff, "x")  # reversal is admin-only
    with pytest.raises(ValidationError):
        services.reverse_payment(p.pk, mk_user("a2@shop.com", "admin"), " ")


# --- concurrency: real row locks, so these run only on PostgreSQL --------------------------------------------------------------------------------
# Skipped (never "passed") on sqlite. Run the suite with DATABASE_URL pointing at Postgres to execute them.

needs_pg = pytest.mark.skipif(connection.vendor != "postgresql", reason="needs real row locks (PostgreSQL)")


@pytest.fixture
def widen_race(monkeypatch):
    """A check-then-write race on a fast machine often "works" by luck. Pausing inside Payment.save (after the service's
    checks, before the write) makes an unlocked implementation fail reliably; with the invoice row lock it changes nothing,
    because the other threads wait at the lock. Verified by removing the lock: these tests then fail."""
    real_save = Payment.save

    def slow_save(self, *a, **k):
        time.sleep(0.05)
        return real_save(self, *a, **k)

    monkeypatch.setattr(Payment, "save", slow_save)


def race(n, fn):
    """Run fn(i) in n threads released together; returns (results, errors)."""
    barrier, results, errors = threading.Barrier(n), [], []

    def worker(i):
        try:
            barrier.wait(timeout=10)
            results.append(fn(i))
        except Exception as e:
            errors.append(e)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results, errors


@needs_pg
@pytest.mark.django_db(transaction=True)
def test_concurrent_full_payments_only_one_wins(inv, staff, widen_race):
    results, errors = race(8, lambda i: services.record_payment(inv, staff, {"amount": TOTAL, "method": "cash"}))
    assert len(results) == 1 and len(errors) == 7
    assert all(isinstance(e, (ValidationError, TransitionError)) for e in errors)
    assert Payment.objects.filter(status="completed").count() == 1
    check_invariants(inv)
    assert fresh(inv).status == "paid" and fresh(inv).amount_paid == TOTAL


@needs_pg
@pytest.mark.django_db(transaction=True)
def test_concurrent_partial_payments_never_lose_an_update(inv, staff, widen_race):
    results, errors = race(12, lambda i: services.record_payment(inv, staff, {"amount": D("767.00"), "method": "cash"}))  # 12 x 767 = 9204
    assert len(results) == 12 and not errors
    assert fresh(inv).status == "paid" and fresh(inv).amount_paid == TOTAL and fresh(inv).amount_due == 0
    assert Payment.objects.filter(status="completed").count() == 12
    check_invariants(inv)


@needs_pg
@pytest.mark.django_db(transaction=True)
def test_concurrent_overpayment_race_never_exceeds_the_total(inv, staff, widen_race):
    results, errors = race(6, lambda i: services.record_payment(inv, staff, {"amount": D("3000.00"), "method": "cash"}))  # only 3 fit in 9204
    assert len(results) == 3 and len(errors) == 3
    assert fresh(inv).amount_paid == D("9000.00") and fresh(inv).amount_due == D("204.00") and fresh(inv).status == "confirmed"
    check_invariants(inv)


@needs_pg
@pytest.mark.django_db(transaction=True)
def test_concurrent_failures_never_exceed_the_attempt_limit(inv, staff, widen_race):
    data = {"amount": D("10.00"), "method": "card", "status": "failed", "failure_reason": "declined"}
    results, errors = race(10, lambda i: services.record_payment(inv, staff, data))
    assert len(results) == 3 and len(errors) == 7  # exactly the configured maximum was recorded
    assert all(isinstance(e, TransitionError) and e.detail["code"] == "max_attempts_reached" for e in errors)
    inv = fresh(inv)
    assert inv.failed_attempts == 3 and inv.payment_needs_attention
    assert sorted(Payment.objects.values_list("attempt_number", flat=True)) == [1, 2, 3]
    assert PaymentEvent.objects.filter(kind="attention_flagged").count() == 1


@needs_pg
@pytest.mark.django_db(transaction=True)
def test_concurrent_reversals_of_one_payment_apply_once(inv, staff, admin, widen_race):
    p = services.record_payment(inv, staff, {"amount": TOTAL, "method": "cash"})[0]
    results, errors = race(6, lambda i: services.reverse_payment(p.pk, admin, "duplicate click"))
    assert len(results) == 1 and len(errors) == 5
    assert Payment.objects.get(pk=p.pk).status == "reversed" and PaymentEvent.objects.filter(kind="reversed").count() == 1
    assert fresh(inv).status == "confirmed" and fresh(inv).amount_paid == 0
    check_invariants(inv)


@needs_pg
@pytest.mark.django_db(transaction=True)
def test_concurrent_retries_of_one_failed_attempt_create_one_retry(inv, staff, widen_race):
    failed = services.record_payment(inv, staff, {"amount": D("10.00"), "method": "card", "status": "failed", "failure_reason": "declined"})[0]
    results, errors = race(6, lambda i: services.retry_payment(failed.pk, staff, {"amount": D("10.00"), "method": "card"}))
    assert len(results) == 1 and len(errors) == 5
    assert Payment.objects.filter(retry_of=failed).count() == 1
    check_invariants(inv)
