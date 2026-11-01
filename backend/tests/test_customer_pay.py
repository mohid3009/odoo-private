"""POST /api/invoices/{id}/pay/: a customer pays their own invoice through the demo gateway (flag-gated)."""
from datetime import date

import pytest

from apps.core.billing import engine
from apps.core.billing import services as billing_services
from apps.core.billing.models import Invoice
from apps.finance.payments.models import Payment
from conftest import api_for, mk_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def on(settings):
    settings.DEMO_PAYMENTS_ENABLED = True


@pytest.fixture
def inv(make_sub, staff):
    """A confirmed, unpaid invoice (9204.00) owned by the `cust` fixture."""
    make_sub(date(2026, 1, 1))
    engine.run_billing(date(2026, 1, 1))
    return billing_services.confirm(Invoice.objects.get(), staff)


def pay(c, invoice, method="upi"):
    return c.post(f"/api/invoices/{invoice.pk}/pay/", {"method": method}, format="json")


def test_customer_pays_in_full(inv, cust):
    r = pay(api_for(cust), inv, "card")
    assert r.status_code == 201 and r.data["payment"]["amount"] == "9204.00"
    assert r.data["invoice_state"]["status"] == "paid" and r.data["invoice_state"]["amount_due"] == "0.00"
    p = Payment.objects.get()
    assert p.method == "card" and p.status == "completed" and p.recorded_by == cust


def test_paid_invoice_cannot_be_paid_again(inv, cust):
    c = api_for(cust)
    assert pay(c, inv).status_code == 201
    assert pay(c, inv).status_code == 409
    assert Payment.objects.count() == 1


def test_someone_elses_invoice_is_404(inv):
    other = mk_user("other@shop.com", "customer")
    assert pay(api_for(other), inv).status_code == 404
    assert not Payment.objects.exists()


def test_staff_and_anonymous_cannot_use_it(inv, staff):
    assert pay(api_for(staff), inv).status_code == 403
    assert pay(api_for(), inv).status_code in (401, 403)


def test_off_by_flag(inv, cust, settings):
    settings.DEMO_PAYMENTS_ENABLED = False
    assert pay(api_for(cust), inv).status_code == 404
    assert not Payment.objects.exists()


def test_bad_method_and_draft(inv, cust, make_sub):
    assert pay(api_for(cust), inv, "cash").status_code == 400  # only card / upi / bank_transfer online
    Invoice.objects.filter(pk=inv.pk).update(status="draft")
    assert pay(api_for(cust), inv).status_code == 404  # drafts are invisible to customers
