from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.core.accounts.models import Role, User
from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax, Variant
from integrations.odoo import sync
from integrations.odoo.client import OdooUnavailable, OdooValidationError

pytestmark = pytest.mark.django_db
PW = "Strong@Pass1"


def client_for(role):
    c = APIClient()
    if role:
        c.force_login(User.objects.create_user(f"{role}@shop.com", PW, role=role))
    return c


@pytest.fixture
def admin():
    return client_for("admin")


def brand_product(admin, **over):
    body = {
        "name": "Brightloop CRM", "type": "software", "sales_price": "1000.00", "cost_price": "400.00",
        "variants": [{"attribute": "Brand", "value": "Odoo", "extra_price": "560.00"}],
    } | over
    r = admin.post("/api/products/", body, format="json")
    assert r.status_code == 201, r.json()
    return r.json()


# --- S2 acceptance: product + Brand variant + monthly plan ---------------------------

def test_admin_builds_product_variant_and_monthly_plan(admin):
    tax = admin.post("/api/taxes/", {"name": "GST 18%", "rate": "18"}, format="json").json()
    p = brand_product(admin, taxes=[tax["id"]])
    assert p["taxes"] == [tax["id"]]
    assert p["variants"][0]["effective_unit_price"] == "1560.00"  # 1000 + 560

    r = admin.post("/api/plans/", {
        "name": "CRM Monthly", "product": p["id"], "price": "1000.00", "billing_period": "monthly",
        "min_quantity": 1, "available_from": "2026-01-01", "available_to": "2027-12-31",
        "auto_close": True, "allow_pause": True, "allow_renew": True, "allow_early_close": True,
    }, format="json")
    assert r.status_code == 201 and r.json()["product_name"] == "Brightloop CRM"

    plan, variant = Plan.objects.get(), Variant.objects.get()
    assert plan.unit_price(variant) == Decimal("1560.00")
    assert plan.unit_price() == Decimal("1000.00")


def test_money_is_serialised_as_string(admin):
    p = brand_product(admin)
    assert p["sales_price"] == "1000.00" and isinstance(p["cost_price"], str)


# --- validation ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "over,field",
    [
        ({"available_from": "2026-06-01", "available_to": "2026-05-31"}, "available_to"),
        ({"min_quantity": 0}, "min_quantity"),
        ({"billing_period": "hourly"}, "billing_period"),
        ({"price": "-1"}, "price"),
    ],
)
def test_plan_validation(admin, over, field):
    pid = Product.objects.create(name="X", sales_price=1).pk
    body = {"name": "P", "product": pid, "price": "10.00"} | over
    r = admin.post("/api/plans/", body, format="json")
    assert r.status_code == 400 and field in r.json()


def test_plan_availability_window():
    p = Plan(available_from=None, available_to=None)
    from datetime import date

    assert p.is_available_on(date(2030, 1, 1))
    p = Plan(available_from=date(2026, 1, 1), available_to=date(2026, 12, 31))
    assert p.is_available_on(date(2026, 6, 1)) and not p.is_available_on(date(2027, 1, 1)) and not p.is_available_on(date(2025, 12, 31))


def test_duplicate_variant_in_payload_rejected(admin):
    r = admin.post("/api/products/", {
        "name": "P", "sales_price": "5", "variants": [
            {"attribute": "Brand", "value": "Odoo", "extra_price": "1"},
            {"attribute": "brand", "value": "ODOO", "extra_price": "2"},
        ]}, format="json")
    assert r.status_code == 400 and "variants" in r.json()
    assert Product.objects.count() == 0


def test_tax_rate_range(admin):
    assert admin.post("/api/taxes/", {"name": "Bad", "rate": "101"}, format="json").status_code == 400
    assert admin.post("/api/taxes/", {"name": "Bad", "rate": "-1"}, format="json").status_code == 400


def test_variants_are_a_full_replacement_list(admin):
    p = brand_product(admin)
    keep = p["variants"][0]
    r = admin.patch(f"/api/products/{p['id']}/", {"variants": [
        {"id": keep["id"], "attribute": "Brand", "value": "Odoo", "extra_price": "600.00"},
        {"attribute": "Support", "value": "Gold", "extra_price": "100.00"},
    ]}, format="json")
    assert r.status_code == 200
    vs = {v["value"]: v for v in r.json()["variants"]}
    assert vs["Odoo"]["id"] == keep["id"] and vs["Odoo"]["extra_price"] == "600.00" and "Gold" in vs
    r = admin.patch(f"/api/products/{p['id']}/", {"variants": []}, format="json")
    assert r.json()["variants"] == [] and Variant.objects.count() == 0


def test_payment_term_default_is_exclusive():
    a = PaymentTerm.objects.create(name="Immediate", days=0)
    assert a.is_default  # first one becomes the default
    b = PaymentTerm.objects.create(name="Net 15", days=15, is_default=True)
    a.refresh_from_db()
    assert b.is_default and not a.is_default
    c = PaymentTerm.objects.create(name="Net 30", days=30)
    assert not c.is_default and PaymentTerm.objects.filter(is_default=True).count() == 1


def test_delete_product_used_by_plan_is_409(admin):
    p = brand_product(admin)
    admin.post("/api/plans/", {"name": "P", "product": p["id"], "price": "1.00"}, format="json")
    r = admin.delete(f"/api/products/{p['id']}/")
    assert r.status_code == 409 and Product.objects.count() == 1
    Plan.objects.all().delete()
    assert admin.delete(f"/api/products/{p['id']}/").status_code == 204


# --- permissions (admin write, staff read-only, customer/anon nothing) -----------------

ENDPOINTS = ["products", "taxes", "payment-terms", "plans"]


@pytest.mark.parametrize("path", ENDPOINTS)
@pytest.mark.parametrize("role,read,write", [("admin", 200, 400), ("staff", 200, 403), ("customer", 403, 403), (None, 403, 403)])
def test_catalog_permission_matrix(path, role, read, write):
    c = client_for(role)
    assert c.get(f"/api/{path}/").status_code == read
    # an empty body is invalid (400) for admin, so 400 proves the write was allowed through to validation
    assert c.post(f"/api/{path}/", {}, format="json").status_code == write


def test_staff_cannot_edit_or_delete(admin):
    p = brand_product(admin)
    staff = client_for("staff")
    assert staff.get(f"/api/products/{p['id']}/").status_code == 200
    assert staff.patch(f"/api/products/{p['id']}/", {"name": "Hax"}, format="json").status_code == 403
    assert staff.delete(f"/api/products/{p['id']}/").status_code == 403
    assert Product.objects.get().name == "Brightloop CRM"


# --- list behaviour (rule 9) -----------------------------------------------------------

def test_lists_are_paginated_filterable_and_have_no_n_plus_one(admin, django_assert_max_num_queries):
    t = Tax.objects.create(name="GST", rate=18)
    for i in range(30):
        pr = Product.objects.create(name=f"P{i:02}", sales_price=10, type="software" if i % 2 else "addon")
        pr.taxes.add(t)
        Variant.objects.create(product=pr, attribute="Brand", value="Odoo", extra_price=5)
        Variant.objects.create(product=pr, attribute="Tier", value="Gold", extra_price=9)
    with django_assert_max_num_queries(8):  # session + user + count + products + variants + taxes (not per row)
        r = admin.get("/api/products/")
    d = r.json()
    assert d["count"] == 30 and len(d["results"]) == 25 and d["next"]
    assert len(admin.get("/api/products/?page_size=100").json()["results"]) == 30
    assert admin.get("/api/products/?type=addon").json()["count"] == 15
    assert admin.get("/api/products/?search=P07").json()["count"] == 1


def test_plan_list_uses_select_related(admin, django_assert_max_num_queries):
    pr = Product.objects.create(name="X", sales_price=1)
    for i in range(10):
        Plan.objects.create(name=f"Plan {i}", product=pr, price=1)
    with django_assert_max_num_queries(5):
        assert len(admin.get("/api/plans/").json()["results"]) == 10


# --- Odoo mirror: failure never blocks the save ---------------------------------------

class FakeOdoo:
    def __init__(self, fail=None):
        self.fail, self.calls, self._next = fail, [], 100

    def _go(self, *call):
        self.calls.append(call)
        if self.fail == "down":
            raise OdooUnavailable("connection refused")
        if self.fail == "reject":
            raise OdooValidationError("Invalid field 'foo'")

    def search_read(self, model, domain=None, fields=None, limit=None):
        self._go("search_read", model)
        return []

    def create(self, model, vals):
        self._go("create", model, vals)
        self._next += 1
        return self._next

    def write(self, model, ids, vals):
        self._go("write", model, ids)
        return True


@pytest.fixture
def odoo(settings, monkeypatch):
    settings.ODOO_ENABLED = True

    def install(fail=None):
        fake = FakeOdoo(fail)
        monkeypatch.setattr(sync, "get_client", lambda: fake)
        return fake

    return install


def test_odoo_success_marks_synced_and_pushes_taxes_first(admin, odoo, django_capture_on_commit_callbacks):
    fake = odoo()
    with django_capture_on_commit_callbacks(execute=True):
        tax = admin.post("/api/taxes/", {"name": "GST 18%", "rate": "18"}, format="json").json()
    t = Tax.objects.get()
    assert t.odoo_sync_status == "synced" and t.odoo_tax_id == 101

    with django_capture_on_commit_callbacks(execute=True):
        brand_product(admin, taxes=[tax["id"]])
    p = Product.objects.get()
    assert p.odoo_sync_status == "synced" and p.odoo_product_id
    create = next(c for c in fake.calls if c[:2] == ("create", "product.product"))
    assert create[2]["taxes_id"] == [(6, 0, [101])] and create[2]["list_price"] == 1000.0


def test_odoo_down_marks_pending_and_save_still_succeeds(admin, odoo, django_capture_on_commit_callbacks):
    odoo("down")
    with django_capture_on_commit_callbacks(execute=True):
        r = admin.post("/api/products/", {"name": "P", "sales_price": "5"}, format="json")
    assert r.status_code == 201
    p = Product.objects.get()
    assert p.odoo_sync_status == "pending" and "refused" in p.odoo_error


def test_odoo_rejection_marks_error_and_save_still_succeeds(admin, odoo, django_capture_on_commit_callbacks):
    odoo("reject")
    with django_capture_on_commit_callbacks(execute=True):
        r = admin.post("/api/taxes/", {"name": "T", "rate": "5"}, format="json")
    assert r.status_code == 201
    t = Tax.objects.get()
    assert t.odoo_sync_status == "error" and "foo" in t.odoo_error


def test_odoo_disabled_is_skipped(admin, settings, django_capture_on_commit_callbacks):
    settings.ODOO_ENABLED = False
    with django_capture_on_commit_callbacks(execute=True):
        admin.post("/api/products/", {"name": "P", "sales_price": "5"}, format="json")
    assert Product.objects.get().odoo_sync_status == "skipped"


def test_sync_pending_retries_failed_rows(admin, odoo, django_capture_on_commit_callbacks):
    odoo("down")
    with django_capture_on_commit_callbacks(execute=True):
        admin.post("/api/taxes/", {"name": "T", "rate": "5"}, format="json")
    assert Tax.objects.get().odoo_sync_status == "pending"
    odoo()  # Odoo is back
    sync.sync_pending()
    assert Tax.objects.get().odoo_sync_status == "synced"


def test_odoo_sync_status_is_read_only_via_api(admin):
    r = admin.post("/api/taxes/", {"name": "T", "rate": "5", "odoo_sync_status": "synced", "odoo_tax_id": 9}, format="json")
    t = Tax.objects.get(pk=r.json()["id"])
    assert t.odoo_sync_status == "skipped" and t.odoo_tax_id is None
