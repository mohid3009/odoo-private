from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.billing import engine
from apps.core.billing.models import Invoice
from apps.core.catalog.models import Product, Tax
from apps.core.subscriptions.models import Subscription, SubscriptionLine
from apps.finance.discounts import services
from apps.finance.discounts.models import Discount, DiscountRedemption
from conftest import api_for, mk_user

pytestmark = pytest.mark.django_db
D = Decimal


def rule(cat, **kw):
    scope = kw.pop("scope", "product")
    d = Discount.objects.create(name=kw.pop("name", "Launch 10%"), type=kw.pop("type", "percent"), value=kw.pop("value", 10), scope=scope, **kw)
    if scope == "product":
        d.products.add(cat["crm"])
    return d


def bill(as_of):
    return engine.run_billing(as_of)


def only_invoice():
    return Invoice.objects.get()


def body(**over):
    return {"name": "Launch 10%", "type": "percent", "value": "10", "scope": "product", "products": [1]} | over


# --- admin API ----------------------------------------------------------------------------------------------

def test_admin_creates_a_product_rule(admin, cat):
    r = api_for(admin).post("/api/discounts/", body(products=[cat["crm"].pk], usage_limit=2, end_date="2027-03-31", code=""), format="json")
    assert r.status_code == 201, r.json()
    d = r.json()
    assert d["code"] is None and d["used_count"] == 0 and d["state"] == "active" and d["products"] == [cat["crm"].pk]
    assert d["created_by"] == admin.pk and d["value"] == "10.00"
    assert api_for(admin).post("/api/discounts/", body(name="Other", products=[cat["crm"].pk], code=" "), format="json").status_code == 201  # two blank codes


def test_codes_are_unique_case_insensitively(admin, cat):
    c = api_for(admin)
    assert c.post("/api/discounts/", body(products=[cat["crm"].pk], code="WELCOME"), format="json").status_code == 201
    r = c.post("/api/discounts/", body(products=[cat["crm"].pk], code="welcome"), format="json")
    assert r.status_code == 400 and "code" in r.json()


@pytest.mark.parametrize("over,field", [
    ({"value": "0"}, "value"), ({"value": "100.01"}, "value"), ({"value": "-5"}, "value"),
    ({"type": "fixed", "value": "0"}, "value"), ({"type": "fixed", "value": "-1"}, "value"),
    ({"start_date": "2026-06-01", "end_date": "2026-05-31"}, "end_date"),
    ({"usage_limit": 0}, "usage_limit"), ({"min_quantity": 0}, "min_quantity"), ({"min_purchase_amount": "-1"}, "min_purchase_amount"),
    ({"products": []}, "products"), ({"scope": "subscription"}, "products"), ({"scope": "everything"}, "scope"), ({"type": "bogo"}, "type"),
])
def test_rule_validation(admin, cat, over, field):
    r = api_for(admin).post("/api/discounts/", body(products=[cat["crm"].pk]) | over, format="json")
    assert r.status_code == 400 and field in r.json(), r.json()


def test_percent_100_and_fixed_amounts_are_valid(admin, cat):
    c = api_for(admin)
    assert c.post("/api/discounts/", body(products=[cat["crm"].pk], value="100"), format="json").status_code == 201
    assert c.post("/api/discounts/", body(name="F", products=[cat["crm"].pk], type="fixed", value="250.50"), format="json").status_code == 201
    assert c.post("/api/discounts/", body(name="S", scope="subscription", products=[]), format="json").status_code == 201


@pytest.mark.parametrize("role,read,write", [("admin", 200, 400), ("staff", 200, 403), ("customer", 403, 403), (None, 403, 403)])
def test_permission_matrix(role, read, write):
    c = api_for(mk_user(f"{role}@x.com", role) if role else None)
    assert c.get("/api/discounts/").status_code == read
    assert c.post("/api/discounts/", {}, format="json").status_code == write  # 400 = allowed through to validation


def test_staff_cannot_edit_or_delete(admin, staff, cat):
    d = rule(cat)
    c = api_for(staff)
    assert c.get(f"/api/discounts/{d.pk}/").status_code == 200
    assert c.patch(f"/api/discounts/{d.pk}/", {"value": "99"}, format="json").status_code == 403
    assert c.delete(f"/api/discounts/{d.pk}/").status_code == 403
    d.refresh_from_db()
    assert d.value == 10


def test_used_count_cannot_be_set_through_the_api(admin, cat):
    c = api_for(admin)
    r = c.post("/api/discounts/", body(products=[cat["crm"].pk], used_count=99), format="json")
    assert Discount.objects.get(pk=r.json()["id"]).used_count == 0
    c.patch(f"/api/discounts/{r.json()['id']}/", {"used_count": 50, "name": "Renamed"}, format="json")
    d = Discount.objects.get()
    assert d.used_count == 0 and d.name == "Renamed"


def test_state_is_computed(cat):
    today = timezone.localdate()
    assert rule(cat, name="a").state() == "active"
    assert rule(cat, name="b", is_active=False).state() == "inactive"
    assert rule(cat, name="c", start_date=today + timedelta(days=1)).state() == "scheduled"
    assert rule(cat, name="d", end_date=today - timedelta(days=1)).state() == "expired"
    assert rule(cat, name="e", usage_limit=1, used_count=1).state() == "exhausted"
    assert rule(cat, name="f", end_date=today).state() == "active"  # the end date itself is still valid


def test_delete_unused_rule_ok_but_redeemed_rule_is_409(admin, cat, make_sub):
    d1, d2 = rule(cat, name="unused"), rule(cat, name="used", value=5)
    c = api_for(admin)
    assert c.delete(f"/api/discounts/{d1.pk}/").status_code == 204
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    r = c.delete(f"/api/discounts/{d2.pk}/")
    assert r.status_code == 409 and "Deactivate" in r.json()["detail"] and Discount.objects.filter(pk=d2.pk).exists()


def test_list_filters_and_search(admin, cat):
    rule(cat, name="Spring sale", code="SPRING")
    rule(cat, name="Whole bundle", scope="subscription", is_active=False)
    c = api_for(admin)
    assert c.get("/api/discounts/?scope=subscription").json()["count"] == 1
    assert c.get("/api/discounts/?is_active=false").json()["count"] == 1
    assert c.get("/api/discounts/?search=SPRING").json()["count"] == 1
    assert c.get("/api/discounts/?type=fixed").json()["count"] == 0


# --- S5 acceptance: auto-appears on the next invoice, stops at the limit ---------------------------------------------

def test_worked_example_through_the_real_engine(cat, make_sub):
    d = rule(cat, usage_limit=2, end_date=date(2027, 3, 31), start_date=date(2026, 11, 1))
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    inv = only_invoice()
    assert (inv.subtotal, inv.discount_total, inv.tax_total, inv.total) == (D("7800.00"), D("780.00"), D("1263.60"), D("8283.60"))
    assert inv.amount_due == D("8283.60")
    product, disc = inv.lines.all()
    assert product.kind == "product" and disc.kind == "discount"
    assert disc.line_subtotal == D("-780.00") and disc.tax_rate_snapshot == D("18.00") and "Launch 10%" in disc.description and "10% off" in disc.description
    d.refresh_from_db()
    assert d.used_count == 1
    red = DiscountRedemption.objects.get()
    assert (red.discount, red.invoice, red.amount) == (d, inv, D("780.00"))


def test_limit_two_shows_on_the_next_two_invoices_not_the_third(cat, make_sub):
    d = rule(cat, usage_limit=2, start_date=date(2026, 11, 1), end_date=date(2027, 3, 31))
    sub = make_sub(date(2026, 11, 1))
    for as_of in (date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)):
        bill(as_of)
    totals = list(Invoice.objects.filter(subscription=sub).order_by("period_start").values_list("total", "discount_total"))
    assert totals == [(D("8283.60"), D("780.00")), (D("8283.60"), D("780.00")), (D("9204.00"), D("0.00"))]
    d.refresh_from_db()
    assert d.used_count == 2 and d.state() == "exhausted" and DiscountRedemption.objects.count() == 2


def test_limit_two_with_three_eligible_invoices_in_one_run_gives_exactly_two(cat, make_sub):
    d = rule(cat, usage_limit=2)
    for _ in range(3):
        make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    assert sorted(Invoice.objects.values_list("discount_total", flat=True)) == [D("0.00"), D("780.00"), D("780.00")]
    d.refresh_from_db()
    assert d.used_count == 2 and DiscountRedemption.objects.count() == 2


def test_no_limit_means_unlimited(cat, make_sub):
    d = rule(cat)
    for _ in range(5):
        make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    d.refresh_from_db()
    assert d.used_count == 5 and Invoice.objects.filter(discount_total__gt=0).count() == 5


# --- eligibility -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("window,as_of,applies", [
    ({"start_date": date(2026, 11, 1)}, date(2026, 10, 31), False),   # before start
    ({"start_date": date(2026, 11, 1)}, date(2026, 11, 1), True),     # on the start date
    ({"end_date": date(2026, 11, 30)}, date(2026, 11, 30), True),     # on the end date
    ({"end_date": date(2026, 11, 30)}, date(2026, 12, 1), False),     # after the end
    ({"start_date": date(2026, 11, 1), "end_date": date(2026, 12, 31)}, date(2026, 12, 15), True),
])
def test_date_window_uses_the_billing_date(cat, make_sub, window, as_of, applies):
    rule(cat, **window)
    make_sub(date(2026, 1, 1), expiry=as_of)  # one period due on `as_of`... billed from January
    sub = Subscription.objects.get()
    Subscription.objects.filter(pk=sub.pk).update(start_date=as_of, next_invoice_date=as_of)
    bill(as_of)
    assert (only_invoice().discount_total > 0) is applies


@pytest.mark.parametrize("over,applies", [
    ({"min_quantity": 5}, True), ({"min_quantity": 6}, False),
    ({"min_purchase_amount": "7800.00"}, True), ({"min_purchase_amount": "7800.01"}, False),
    ({"min_quantity": 5, "min_purchase_amount": "9000"}, False),
    ({"is_active": False}, False),
])
def test_minimums_and_inactive_rules(cat, make_sub, over, applies):
    rule(cat, **over)
    make_sub(date(2026, 11, 1))  # 5 x 1560 = 7800
    bill(date(2026, 11, 1))
    assert (only_invoice().discount_total > 0) is applies


def test_rule_for_another_product_does_not_apply(cat, make_sub):
    other = Product.objects.create(name="Other", sales_price=10)
    d = rule(cat)
    d.products.set([other])
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    assert only_invoice().discount_total == 0 and not DiscountRedemption.objects.exists()


def test_fixed_amount_is_capped_at_the_line(cat, make_sub):
    rule(cat, name="big", type="fixed", value=99999)
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    inv = only_invoice()
    assert inv.discount_total == D("7800.00") and inv.total == D("0.00") and inv.amount_due == D("0.00")


def test_fixed_amount(cat, make_sub):
    rule(cat, name="flat", type="fixed", value="100.50")
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    inv = only_invoice()
    assert inv.discount_total == D("100.50") and inv.tax_total == D("1385.91") and inv.total == D("9085.41")  # 7800 - 100.50 + 18% of 7699.50


# --- stacking (D-010) ----------------------------------------------------------------------------------------------------

def test_largest_saving_wins_per_line_and_the_loser_is_not_counted(cat, make_sub):
    ten = rule(cat, name="ten", value=10)  # 780
    flat = rule(cat, name="flat", type="fixed", value=1000)
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    inv = only_invoice()
    assert [l.kind for l in inv.lines.all()] == ["product", "discount"] and inv.discount_total == D("1000.00")
    ten.refresh_from_db(), flat.refresh_from_db()
    assert (ten.used_count, flat.used_count) == (0, 1)


def test_equal_savings_pick_the_older_rule(cat, make_sub):
    first = rule(cat, name="first", type="fixed", value=780)
    second = rule(cat, name="second", value=10)  # also 780
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    first.refresh_from_db(), second.refresh_from_db()
    assert (first.used_count, second.used_count) == (1, 0)


def test_a_rule_counts_once_per_invoice_even_when_it_discounts_two_lines(cat, make_sub):
    d = rule(cat)
    sub = make_sub(date(2026, 11, 1), qty=3)
    line = SubscriptionLine.objects.create(subscription=sub, product=cat["crm"], quantity=2, unit_price=D("1000.00"), amount=D("2000.00"), description="CRM extra")
    line.taxes.add(cat["gst"])
    bill(date(2026, 11, 1))
    inv = only_invoice()
    assert [l.kind for l in inv.lines.all()] == ["product", "product", "discount", "discount"]
    d.refresh_from_db()
    red = DiscountRedemption.objects.get()
    assert d.used_count == 1 and red.amount == inv.discount_total == D("468.00") + D("200.00")  # 10% of 4680 and 10% of 2000


def test_subscription_rule_applies_only_when_attached(cat, make_sub):
    rule(cat, scope="subscription", name="bundle 5%", value=5)
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    assert only_invoice().discount_total == 0


def test_subscription_rule_stacks_on_top_of_the_line_rule(cat, make_sub):
    rule(cat, name="line 10%", value=10)
    bundle = rule(cat, scope="subscription", name="bundle 5%", value=5)
    sub = make_sub(date(2026, 11, 1))
    Subscription.objects.filter(pk=sub.pk).update(discount=bundle)
    bill(date(2026, 11, 1))
    inv = only_invoice()
    # 7800 - 780 (line) = 7020; 5% of that = 351.00; tax = 18% of 6669.00 = 1200.42
    assert inv.subtotal == D("7800.00") and inv.discount_total == D("1131.00") and inv.tax_total == D("1200.42") and inv.total == D("7869.42")
    assert sorted(inv.lines.filter(kind="discount").values_list("line_subtotal", flat=True)) == [D("-780.00"), D("-351.00")]
    assert DiscountRedemption.objects.count() == 2 and Discount.objects.get(pk=bundle.pk).used_count == 1


def test_subscription_rule_is_spread_over_lines_and_taxed_at_each_lines_rate(cat, make_sub):
    cheap_tax = Tax.objects.create(name="GST 5%", rate=5)
    b = Product.objects.create(name="Support", sales_price=2000)
    b.taxes.add(cheap_tax)
    bundle = rule(cat, scope="subscription", name="bundle 10%", value=10)
    sub = make_sub(date(2026, 11, 1))
    line = SubscriptionLine.objects.create(subscription=sub, product=b, quantity=1, unit_price=D("2000.00"), amount=D("2000.00"), description="Support")
    line.taxes.add(cheap_tax)
    Subscription.objects.filter(pk=sub.pk).update(discount=bundle)
    bill(date(2026, 11, 1))
    inv = only_invoice()
    # subtotal 9800, 10% = 980 split 780 / 200; tax (1404-140.40) + (100-10) = 1353.60
    assert sorted(inv.lines.filter(kind="discount").values_list("line_subtotal", "tax_rate_snapshot")) == [(D("-780.00"), D("18.00")), (D("-200.00"), D("5.00"))]
    assert (inv.discount_total, inv.tax_total, inv.total) == (D("980.00"), D("1353.60"), D("10173.60"))
    assert inv.discount_total == -sum(l.line_subtotal for l in inv.lines.filter(kind="discount"))  # the split adds up exactly


@pytest.mark.parametrize("over,applies", [({"min_quantity": 5}, True), ({"min_quantity": 6}, False), ({"min_purchase_amount": "7800"}, True), ({"min_purchase_amount": "7801"}, False)])
def test_subscription_rule_minimums(cat, make_sub, over, applies):
    bundle = rule(cat, scope="subscription", **over)
    sub = make_sub(date(2026, 11, 1))
    Subscription.objects.filter(pk=sub.pk).update(discount=bundle)
    bill(date(2026, 11, 1))
    assert (only_invoice().discount_total > 0) is applies


def test_subscription_rule_respects_window_and_limit(cat, make_sub):
    bundle = rule(cat, scope="subscription", usage_limit=1, end_date=date(2026, 12, 15))
    sub = make_sub(date(2026, 11, 1))
    Subscription.objects.filter(pk=sub.pk).update(discount=bundle)
    for as_of in (date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)):
        bill(as_of)
    assert list(Invoice.objects.order_by("period_start").values_list("discount_total", flat=True)) == [D("780.00"), D("0.00"), D("0.00")]


# --- race safety + rollback -------------------------------------------------------------------------------------------------

def test_reserve_never_hands_out_the_last_use_twice(cat, make_sub):
    d = rule(cat, usage_limit=1)
    lines = [{"description": "CRM", "quantity": 5, "unit_price": D("1560.00"), "tax_rate": D("18"), "taxes": [], "product": cat["crm"]}]
    sub = make_sub(date(2026, 11, 1))
    a = services.pick_discounts(sub, lines, date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 1))
    b = services.pick_discounts(sub, lines, date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 1))  # both saw "1 use left"
    assert len(a) == len(b) == 1
    assert len(services.reserve(a)) == 1 and services.reserve(b) == []  # the conditional UPDATE lets only one through
    d.refresh_from_db()
    assert d.used_count == 1


def test_a_rolled_back_invoice_gives_the_use_back(cat, make_sub, monkeypatch):
    d = rule(cat, usage_limit=1)
    sub = make_sub(date(2026, 11, 1))

    def boom(*a, **k):
        raise RuntimeError("redemption write failed")

    monkeypatch.setattr(services, "record", boom)
    r = bill(date(2026, 11, 1))
    assert r.error_count == 1 and r.created_count == 0 and not Invoice.objects.exists()
    d.refresh_from_db()
    assert d.used_count == 0  # reserved inside the billing transaction, so it rolled back with it
    monkeypatch.undo()
    assert bill(date(2026, 11, 1)).created_count == 1 and Discount.objects.get().used_count == 1
    assert Subscription.objects.get(pk=sub.pk).next_invoice_date == date(2026, 12, 1)


def test_rerunning_billing_never_uses_a_rule_twice(cat, make_sub):
    d = rule(cat, usage_limit=5)
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    d.refresh_from_db()
    assert d.used_count == 1 and DiscountRedemption.objects.count() == 1


def test_cancelling_an_invoice_does_not_free_the_use(cat, make_sub, staff):
    d = rule(cat, usage_limit=1)
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    inv = only_invoice()
    assert api_for(staff).post(f"/api/invoices/{inv.pk}/cancel/").status_code == 200  # D-019: the period stays used, so does the use
    d.refresh_from_db()
    assert d.used_count == 1 and DiscountRedemption.objects.count() == 1


def test_discount_lines_are_visible_on_the_invoice_api(cat, make_sub, staff):
    rule(cat)
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    d = api_for(staff).get(f"/api/invoices/{only_invoice().pk}/").json()
    kinds = [(l["kind"], l["line_subtotal"]) for l in d["lines"]]
    assert kinds == [("product", "7800.00"), ("discount", "-780.00")] and d["discount_total"] == "780.00" and d["total"] == "8283.60"


# --- redemptions API ----------------------------------------------------------------------------------------------------------------

def test_redemptions_list(cat, make_sub, staff, cust):
    d = rule(cat)
    make_sub(date(2026, 11, 1))
    make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    r = api_for(staff).get(f"/api/discounts/{d.pk}/redemptions/").json()
    assert r["count"] == 2
    row = r["results"][0]
    assert row["amount"] == "780.00" and row["customer_email"] == "c1@shop.com" and row["subscription_number"].startswith("SUB-") and row["invoice"]
    assert api_for(cust).get(f"/api/discounts/{d.pk}/redemptions/").status_code == 403
    assert api_for().get(f"/api/discounts/{d.pk}/redemptions/").status_code == 403


# --- attach / detach ------------------------------------------------------------------------------------------------------------------

def attach(c, sub, discount):
    return c.post(f"/api/subscriptions/{sub.pk}/discount/", {"discount": discount.pk}, format="json")


def test_staff_attaches_and_detaches_a_subscription_rule(cat, make_sub, staff):
    bundle = rule(cat, scope="subscription", name="bundle 5%", value=5)
    sub = make_sub(date(2026, 11, 1))
    c = api_for(staff)
    r = attach(c, sub, bundle)
    assert r.status_code == 200 and r.json()["discount"] == bundle.pk and r.json()["discount_name"] == "bundle 5%"
    assert c.get(f"/api/subscriptions/{sub.pk}/").json()["discount"] == bundle.pk
    d = c.delete(f"/api/subscriptions/{sub.pk}/discount/")
    assert d.status_code == 200 and d.json()["discount"] is None and d.json()["discount_name"] == ""


def test_attaching_applies_from_the_next_invoice_only(cat, make_sub, staff):
    bundle = rule(cat, scope="subscription", value=5)
    sub = make_sub(date(2026, 11, 1))
    bill(date(2026, 11, 1))
    attach(api_for(staff), sub, bundle)
    bill(date(2026, 12, 1))
    assert list(Invoice.objects.order_by("period_start").values_list("discount_total", flat=True)) == [D("0.00"), D("390.00")]


def test_only_active_subscription_scope_rules_can_be_attached(cat, make_sub, staff):
    sub = make_sub(date(2026, 11, 1))
    c = api_for(staff)
    assert attach(c, sub, rule(cat, name="product one")).status_code == 400
    assert attach(c, sub, rule(cat, scope="subscription", name="off", is_active=False)).status_code == 400
    assert c.post(f"/api/subscriptions/{sub.pk}/discount/", {"discount": 9999}, format="json").status_code == 400
    assert Subscription.objects.get().discount is None


def test_attaching_replaces_the_previous_rule(cat, make_sub, staff):
    one, two = rule(cat, scope="subscription", name="one"), rule(cat, scope="subscription", name="two")
    sub = make_sub(date(2026, 11, 1))
    attach(api_for(staff), sub, one)
    assert attach(api_for(staff), sub, two).json()["discount"] == two.pk


def test_closed_subscription_cannot_be_changed(cat, make_sub, staff):
    bundle = rule(cat, scope="subscription")
    sub = make_sub(date(2026, 11, 1), status="closed")
    r = attach(api_for(staff), sub, bundle)
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"
    assert api_for(staff).delete(f"/api/subscriptions/{sub.pk}/discount/").status_code == 409


def test_customers_cannot_attach(cat, make_sub, cust):
    bundle = rule(cat, scope="subscription")
    sub = make_sub(date(2026, 11, 1))
    assert attach(api_for(cust), sub, bundle).status_code == 403
    assert api_for(cust).delete(f"/api/subscriptions/{sub.pk}/discount/").status_code == 403
    assert attach(api_for(), sub, bundle).status_code == 403


def test_deleting_a_rule_detaches_it_from_subscriptions(admin, cat, make_sub):
    bundle = rule(cat, scope="subscription")
    sub = make_sub(date(2026, 11, 1))
    Subscription.objects.filter(pk=sub.pk).update(discount=bundle)
    assert api_for(admin).delete(f"/api/discounts/{bundle.pk}/").status_code == 204
    assert Subscription.objects.get(pk=sub.pk).discount is None
