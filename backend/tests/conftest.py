"""Shared fixtures for the billing/invoice/notification tests (older test files keep their own local helpers)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.accounts.models import CustomerProfile, Role, User
from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax
from apps.core.subscriptions.models import Subscription, SubscriptionLine
from apps.core.subscriptions.services import next_number
from integrations.odoo import sync
from integrations.odoo.client import OdooUnavailable, OdooValidationError

PW = "Strong@Pass1"


def mk_user(email, role, **profile):
    u = User.objects.create_user(email, PW, role=role, name=email.split("@")[0].title())
    if role == Role.CUSTOMER:
        CustomerProfile.objects.create(user=u, **profile)
    return u


def api_for(user=None):
    c = APIClient()
    if user:
        c.force_login(user)
    return c


@pytest.fixture
def cat(db):
    """CRM 1000/month (GST 18% on the product), Net 15 payment term."""
    gst = Tax.objects.create(name="GST 18%", rate=18)
    crm = Product.objects.create(name="CRM", type="software", sales_price=1000)
    crm.taxes.add(gst)
    plan = Plan.objects.create(name="CRM Monthly", product=crm, price=1000, billing_period="monthly", min_quantity=1)
    term = PaymentTerm.objects.create(name="Net 15", days=15)
    return dict(gst=gst, crm=crm, plan=plan, term=term)


@pytest.fixture
def cust(db):
    return mk_user("c1@shop.com", Role.CUSTOMER)


@pytest.fixture
def staff(db):
    return mk_user("staff@shop.com", Role.STAFF)


@pytest.fixture
def admin(db):
    return mk_user("admin@shop.com", Role.ADMIN)


@pytest.fixture
def make_sub(cat, cust):
    """Factory: an ACTIVE subscription with one line (qty x 1560 = the worked example when qty=5)."""

    def make(start, expiry=None, qty=5, unit="1560.00", status="active", customer=None, period=None, lines=True, **plan_flags):
        plan = cat["plan"]
        if period or plan_flags:
            plan = Plan.objects.create(name=f"P{Plan.objects.count()}", product=cat["crm"], price=1000,
                                       billing_period=period or "monthly", min_quantity=1, **plan_flags)
        sub = Subscription.objects.create(
            number=next_number(), customer=customer or cust, plan=plan, start_date=start, expiry_date=expiry,
            payment_term=cat["term"], status=status, next_invoice_date=start if status == "active" else None,
        )
        if lines:
            line = SubscriptionLine.objects.create(
                subscription=sub, product=cat["crm"], quantity=qty, unit_price=Decimal(unit),
                amount=Decimal(unit) * qty, description="CRM (Brand=Odoo)",
            )
            line.taxes.add(cat["gst"])
        return sub

    return make


class FakeOdoo:
    """Stands in for integrations.odoo.client: records calls; fail='down' | 'reject' simulates Odoo problems."""

    def __init__(self, fail=None, total=None):
        self.fail, self.total, self.calls, self._id = fail, total, [], 100

    def _go(self, *call):
        self.calls.append(call)
        if self.fail == "down":
            raise OdooUnavailable("connection refused")
        if self.fail == "reject":
            raise OdooValidationError("Invalid field 'foo'")

    def search_read(self, model, domain=None, fields=None, limit=None):
        self._go("search_read", model)
        if model == "account.move":
            return [{"amount_total": self.total if self.total is not None else 0}]
        return []

    def create(self, model, vals):
        self._go("create", model, vals)
        self._id += 1
        return self._id

    def write(self, model, ids, vals):
        self._go("write", model, ids)
        return True

    def execute(self, model, method, *args, **kwargs):
        self._go("execute", model, method, *args)
        return True


@pytest.fixture
def odoo(settings, monkeypatch):
    settings.ODOO_ENABLED = True

    def install(fail=None, total=None):
        fake = FakeOdoo(fail, total)
        monkeypatch.setattr(sync, "get_client", lambda: fake)
        return fake

    return install
