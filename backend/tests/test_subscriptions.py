import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.accounts.models import CustomerProfile, Role, User
from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax, Variant
from apps.core.subscriptions import services
from apps.core.subscriptions.models import Counter, QuotationTemplate, Subscription

pytestmark = pytest.mark.django_db
PW = "Strong@Pass1"
TODAY = timezone.localdate()


def user(email, role):
    u = User.objects.create_user(email, PW, role=role)
    if role == Role.CUSTOMER:
        CustomerProfile.objects.create(user=u)
    return u


def api(u=None):
    c = APIClient()
    if u:
        c.force_login(u)
    return c


@pytest.fixture
def cat():
    """Catalog from the S2 acceptance: CRM 1000, Brand=Odoo +560, GST 18%, monthly plan with every flag on."""
    gst = Tax.objects.create(name="GST 18%", rate=18)
    crm = Product.objects.create(name="CRM", type="software", sales_price=1000)
    crm.taxes.add(gst)
    odoo = Variant.objects.create(product=crm, attribute="Brand", value="Odoo", extra_price=560)
    addon = Product.objects.create(name="Support", type="addon", sales_price=200)
    plan = Plan.objects.create(
        name="CRM Monthly", product=crm, price=1000, billing_period="monthly", min_quantity=3,
        auto_close=True, allow_early_close=True, allow_pause=True, allow_renew=True,
    )
    term = PaymentTerm.objects.create(name="Net 15", days=15)
    return dict(gst=gst, crm=crm, odoo=odoo, addon=addon, plan=plan, term=term)


@pytest.fixture
def staff():
    return api(user("staff@shop.com", Role.STAFF))


@pytest.fixture
def admin():
    return api(user("admin@shop.com", Role.ADMIN))


@pytest.fixture
def cust():
    return user("c1@shop.com", Role.CUSTOMER)


def payload(cat, cust, **over):
    return {"customer": cust.pk, "plan": cat["plan"].pk, "start_date": str(TODAY), "expiry_date": str(TODAY + timedelta(days=364))} | over


def make_sub(client, cat, cust, **over):
    r = client.post("/api/subscriptions/", payload(cat, cust, **over), format="json")
    assert r.status_code == 201, r.json()
    return r.json()


def move(client, sub_id, to):
    return client.post(f"/api/subscriptions/{sub_id}/transition/", {"to": to}, format="json")


def walk(client, sub_id, *path):
    r = None
    for to in path:
        r = move(client, sub_id, to)
        assert r.status_code == 200, (to, r.json())
    return r.json() if r is not None else None


# --- numbering -----------------------------------------------------------------------------

def test_numbers_are_sequential_and_unique():
    nums = [services.next_number() for _ in range(25)]
    assert nums[:3] == ["SUB-000001", "SUB-000002", "SUB-000003"] and len(set(nums)) == 25
    assert Counter.objects.get(name="subscription").value == 25


@pytest.mark.skipif(connection.vendor != "postgresql", reason="needs real row locks (Postgres)")
@pytest.mark.django_db(transaction=True)
def test_concurrent_numbering_has_no_duplicates():
    out, errors = [], []

    def worker():
        try:
            out.extend(services.next_number() for _ in range(10))
        except Exception as e:  # pragma: no cover
            errors.append(e)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(out) == 80 and len(set(out)) == 80


# --- create / pricing (D-001) ----------------------------------------------------------------

def test_create_adds_primary_line_at_min_quantity(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    assert s["number"] == "SUB-000001" and s["status"] == "draft"
    assert s["payment_term"] == cat["term"].pk  # first term created is the default
    (line,) = s["lines"]
    assert line["product"] == cat["crm"].pk and line["quantity"] == 3
    assert line["unit_price"] == "1000.00" and line["amount"] == "3000.00" and line["taxes"] == [cat["gst"].pk]
    assert s["lines_total"] == "3000.00"


def test_worked_example_line_with_variant(staff, cat, cust):
    s = make_sub(staff, cat, cust, lines=[{"product": cat["crm"].pk, "variant": cat["odoo"].pk, "quantity": 5}])
    (line,) = s["lines"]
    assert line["unit_price"] == "1560.00" and line["amount"] == "7800.00"  # plan 1000 + Odoo 560, qty 5
    assert line["variant_label"] == "Brand=Odoo" and "Odoo" in line["description"]


def test_addon_line_uses_sales_price_and_explicit_price_wins(staff, cat, cust):
    s = make_sub(staff, cat, cust, lines=[
        {"product": cat["crm"].pk, "quantity": 3},
        {"product": cat["addon"].pk, "quantity": 2},
        {"product": cat["addon"].pk, "quantity": 1, "unit_price": "150.50", "taxes": []},
    ])
    prices = [(l["unit_price"], l["amount"], l["taxes"]) for l in s["lines"]]
    assert prices == [("1000.00", "3000.00", [cat["gst"].pk]), ("200.00", "400.00", []), ("150.50", "150.50", [])]
    assert s["lines_total"] == "3550.50"


@pytest.mark.parametrize("qty,ok", [(1, False), (2, False), (3, True), (10, True)])
def test_primary_line_minimum_quantity(staff, cat, cust, qty, ok):
    r = staff.post("/api/subscriptions/", payload(cat, cust, lines=[{"product": cat["crm"].pk, "quantity": qty}]), format="json")
    assert (r.status_code == 201) is ok
    if not ok:
        assert "lines" in r.json() and "Minimum quantity" in r.json()["lines"][0]


def test_minimum_quantity_does_not_apply_to_other_products(staff, cat, cust):
    s = make_sub(staff, cat, cust, lines=[{"product": cat["addon"].pk, "quantity": 1}])
    assert s["lines"][0]["quantity"] == 1


@pytest.mark.parametrize("over,field", [
    ({"expiry_date": str(TODAY - timedelta(days=1))}, "expiry_date"),
    ({"customer": 9999}, "customer"),
    ({"plan": 9999}, "plan"),
    ({"lines": [{"product": 1, "quantity": 0}]}, "lines"),
])
def test_create_validation(staff, cat, cust, over, field):
    over = {k: (cat["crm"].pk if k == "lines" else v) for k, v in over.items()} if False else over
    if field == "lines":
        over = {"lines": [{"product": cat["crm"].pk, "quantity": 0}]}
    r = staff.post("/api/subscriptions/", payload(cat, cust, **over), format="json")
    assert r.status_code == 400 and field in r.json()


def test_customer_must_have_customer_role(staff, cat):
    other = user("s2@shop.com", Role.STAFF)
    r = staff.post("/api/subscriptions/", payload(cat, other), format="json")
    assert r.status_code == 400 and "customer" in r.json()


def test_plan_availability_window_is_enforced(staff, cat, cust):
    Plan.objects.filter(pk=cat["plan"].pk).update(available_from=TODAY + timedelta(days=30), available_to=TODAY + timedelta(days=60))
    r = staff.post("/api/subscriptions/", payload(cat, cust), format="json")
    assert r.status_code == 400 and "start_date" in r.json()
    ok = staff.post("/api/subscriptions/", payload(cat, cust, start_date=str(TODAY + timedelta(days=40)), expiry_date=None), format="json")
    assert ok.status_code == 201


def test_variant_must_belong_to_product(staff, cat, cust):
    r = staff.post("/api/subscriptions/", payload(cat, cust, lines=[{"product": cat["addon"].pk, "variant": cat["odoo"].pk, "quantity": 1}]), format="json")
    assert r.status_code == 400


# --- editing -----------------------------------------------------------------------------------

def test_only_draft_is_editable(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    r = staff.patch(f"/api/subscriptions/{s['id']}/", {"notes": "hello", "lines": [{"product": cat["crm"].pk, "quantity": 4}]}, format="json")
    assert r.status_code == 200 and r.json()["notes"] == "hello" and r.json()["lines"][0]["quantity"] == 4
    assert staff.patch(f"/api/subscriptions/{s['id']}/", {"status": "active"}, format="json").json()["status"] == "draft"  # status is read-only
    move(staff, s["id"], "quotation")
    r = staff.patch(f"/api/subscriptions/{s['id']}/", {"notes": "late"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "not_editable"


# --- S3 acceptance: full lifecycle ---------------------------------------------------------------

def test_walk_draft_quotation_confirmed_active_with_log(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    assert s["actions"] == ["closed", "quotation"]
    d = walk(staff, s["id"], "quotation")
    assert d["quotation_valid_until"] == str(TODAY + timedelta(days=30))
    d = walk(staff, s["id"], "confirmed")
    assert d["next_invoice_date"] == str(TODAY)
    d = walk(staff, s["id"], "active")
    assert d["status"] == "active" and sorted(d["actions"]) == ["closed", "paused", "renew"]
    assert [(l["from_status"], l["to_status"]) for l in d["status_log"]] == [
        ("draft", "quotation"), ("quotation", "confirmed"), ("confirmed", "active")]
    assert {l["by_user_email"] for l in d["status_log"]} == {"staff@shop.com"}


@pytest.mark.parametrize("frm,to", [
    ("draft", "confirmed"), ("draft", "active"), ("draft", "paused"), ("quotation", "active"), ("quotation", "paused"),
    ("confirmed", "draft"), ("confirmed", "quotation"), ("confirmed", "paused"), ("active", "draft"),
    ("active", "confirmed"), ("active", "quotation"), ("paused", "confirmed"), ("closed", "draft"),
    ("closed", "active"), ("closed", "closed"), ("draft", "draft"),
])
def test_illegal_transitions_are_409(staff, cat, cust, frm, to):
    s = make_sub(staff, cat, cust)
    Subscription.objects.filter(pk=s["id"]).update(status=frm)
    r = move(staff, s["id"], to)
    assert r.status_code == 409 and r.json()["code"] == "illegal_transition"
    assert Subscription.objects.get(pk=s["id"]).status == frm  # nothing changed


def test_unknown_status_is_400(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    assert move(staff, s["id"], "nonsense").status_code == 400


def test_quotation_needs_lines(staff, cat, cust):
    s = make_sub(staff, cat, cust, lines=[])
    r = move(staff, s["id"], "quotation")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed" and "line" in r.json()["detail"]


def test_quotation_blocks_when_plan_no_longer_available(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    Plan.objects.filter(pk=cat["plan"].pk).update(available_to=TODAY - timedelta(days=1))
    assert move(staff, s["id"], "quotation").json()["code"] == "guard_failed"


def test_expired_quotation_cannot_be_confirmed_but_can_go_back_to_draft(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    walk(staff, s["id"], "quotation")
    Subscription.objects.filter(pk=s["id"]).update(quotation_valid_until=TODAY - timedelta(days=1))
    r = move(staff, s["id"], "confirmed")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed" and "expired" in r.json()["detail"]
    d = walk(staff, s["id"], "draft", "quotation", "confirmed")  # re-sending recomputes the validity
    assert d["status"] == "confirmed"


def test_cannot_activate_before_start_date(staff, cat, cust):
    s = make_sub(staff, cat, cust, start_date=str(TODAY + timedelta(days=10)), expiry_date=None)
    walk(staff, s["id"], "quotation", "confirmed")
    r = move(staff, s["id"], "active")
    assert r.status_code == 409 and r.json()["code"] == "guard_failed"


def test_activate_due_activates_only_started_subscriptions(staff, cat, cust):
    started = make_sub(staff, cat, cust)
    future = make_sub(staff, cat, cust, start_date=str(TODAY + timedelta(days=10)), expiry_date=None)
    for s in (started, future):
        walk(staff, s["id"], "quotation", "confirmed")
    assert services.activate_due(TODAY) == 1
    assert Subscription.objects.get(pk=started["id"]).status == "active"
    assert Subscription.objects.get(pk=future["id"]).status == "confirmed"
    assert Subscription.objects.get(pk=started["id"]).status_log.last().by_user is None  # system
    assert services.activate_due(TODAY) == 0


def test_pause_and_resume_do_not_back_bill(staff, cat, cust):
    s = make_sub(staff, cat, cust, start_date=str(TODAY - timedelta(days=60)), expiry_date=None)
    walk(staff, s["id"], "quotation", "confirmed", "active", "paused")
    Subscription.objects.filter(pk=s["id"]).update(next_invoice_date=TODAY - timedelta(days=30))
    d = walk(staff, s["id"], "active")
    assert d["next_invoice_date"] == str(TODAY)  # max(existing, today)
    Subscription.objects.filter(pk=s["id"]).update(status="paused", next_invoice_date=TODAY + timedelta(days=5))
    assert walk(staff, s["id"], "active")["next_invoice_date"] == str(TODAY + timedelta(days=5))  # never moved backwards


def test_plan_flags_gate_pause_close_and_renew(staff, admin, cat, cust):
    Plan.objects.filter(pk=cat["plan"].pk).update(allow_pause=False, allow_early_close=False, allow_renew=False)
    s = make_sub(staff, cat, cust)
    walk(staff, s["id"], "quotation", "confirmed", "active")
    detail = staff.get(f"/api/subscriptions/{s['id']}/").json()
    assert detail["actions"] == []  # nothing offered to staff
    assert move(staff, s["id"], "paused").json()["code"] == "guard_failed"
    assert move(staff, s["id"], "closed").json()["code"] == "guard_failed"
    assert staff.post(f"/api/subscriptions/{s['id']}/renew/").json()["code"] == "guard_failed"
    assert admin.get(f"/api/subscriptions/{s['id']}/").json()["actions"] == ["closed"]  # admin may override early close
    assert move(admin, s["id"], "closed").json()["status"] == "closed"


def test_close_before_activation_needs_no_flag(staff, cat, cust):
    Plan.objects.filter(pk=cat["plan"].pk).update(allow_early_close=False)
    for path in ([], ["quotation"], ["quotation", "confirmed"]):
        s = make_sub(staff, cat, cust)
        walk(staff, s["id"], *path)
        assert move(staff, s["id"], "closed").json()["status"] == "closed"


def test_renew_extends_expiry_by_the_term(staff, cat, cust):
    start, expiry = TODAY, TODAY + timedelta(days=364)
    s = make_sub(staff, cat, cust)
    walk(staff, s["id"], "quotation", "confirmed", "active")
    d = staff.post(f"/api/subscriptions/{s['id']}/renew/").json()
    assert d["expiry_date"] == str(expiry + (expiry - start)) and d["status"] == "active"


def test_renew_needs_active_and_an_expiry(staff, cat, cust):
    s = make_sub(staff, cat, cust, expiry_date=None)
    assert staff.post(f"/api/subscriptions/{s['id']}/renew/").json()["code"] == "guard_failed"  # not active
    walk(staff, s["id"], "quotation", "confirmed", "active")
    assert "no expiry" in staff.post(f"/api/subscriptions/{s['id']}/renew/").json()["detail"]


# --- templates -----------------------------------------------------------------------------------

def make_template(client, cat, **over):
    body = {"name": "CRM Starter", "plan": cat["plan"].pk, "validity_days": 15, "lines": [
        {"product": cat["crm"].pk, "variant": cat["odoo"].pk, "quantity": 5},
        {"product": cat["addon"].pk, "quantity": 2},
    ]} | over
    r = client.post("/api/quotation-templates/", body, format="json")
    assert r.status_code == 201, r.json()
    return r.json()


def test_template_crud_and_line_replacement(staff, cat):
    t = make_template(staff, cat)
    assert t["plan_name"] == "CRM Monthly" and len(t["lines"]) == 2 and t["lines"][0]["product_name"] == "CRM"
    r = staff.patch(f"/api/quotation-templates/{t['id']}/", {"lines": [{"product": cat["addon"].pk, "quantity": 1}]}, format="json")
    assert [l["product"] for l in r.json()["lines"]] == [cat["addon"].pk]
    assert staff.patch(f"/api/quotation-templates/{t['id']}/", {"validity_days": 0}, format="json").status_code == 400
    bad = staff.post("/api/quotation-templates/", {"name": "x", "plan": cat["plan"].pk, "lines": [{"product": cat["addon"].pk, "variant": cat["odoo"].pk, "quantity": 1}]}, format="json")
    assert bad.status_code == 400
    assert staff.delete(f"/api/quotation-templates/{t['id']}/").status_code == 204


def test_from_template_prefills_everything(staff, cat, cust):
    t = make_template(staff, cat)
    r = staff.post("/api/subscriptions/from-template/", {"template": t["id"], "customer": cust.pk, "start_date": str(TODAY)}, format="json")
    assert r.status_code == 201
    s = r.json()
    assert s["status"] == "draft" and s["plan"] == cat["plan"].pk and s["template"] == t["id"]
    assert s["quotation_valid_until"] == str(TODAY + timedelta(days=15))
    assert [(l["quantity"], l["unit_price"], l["amount"]) for l in s["lines"]] == [(5, "1560.00", "7800.00"), (2, "200.00", "400.00")]
    assert s["lines_total"] == "8200.00"
    d = walk(staff, s["id"], "quotation")
    assert d["quotation_valid_until"] == str(TODAY + timedelta(days=15))  # template validity, not the 30-day default


def test_from_template_rejects_inactive_template_and_bad_customer(staff, cat, cust):
    t = make_template(staff, cat, is_active=False)
    body = {"template": t["id"], "customer": cust.pk, "start_date": str(TODAY)}
    assert staff.post("/api/subscriptions/from-template/", body, format="json").status_code == 400
    t2 = make_template(staff, cat, name="Other")
    assert staff.post("/api/subscriptions/from-template/", body | {"template": t2["id"], "customer": 9999}, format="json").status_code == 400
    assert Subscription.objects.count() == 0


def test_from_template_enforces_plan_minimum(staff, cat, cust):
    t = make_template(staff, cat, lines=[{"product": cat["crm"].pk, "quantity": 1}])
    r = staff.post("/api/subscriptions/from-template/", {"template": t["id"], "customer": cust.pk, "start_date": str(TODAY)}, format="json")
    assert r.status_code == 400 and "lines" in r.json()


# --- permissions + row-level access ----------------------------------------------------------------

def test_customer_cannot_write_or_transition(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    c = api(cust)
    assert c.post("/api/subscriptions/", payload(cat, cust), format="json").status_code == 403
    assert c.patch(f"/api/subscriptions/{s['id']}/", {"notes": "x"}, format="json").status_code == 403
    assert move(c, s["id"], "quotation").status_code == 403
    assert c.post(f"/api/subscriptions/{s['id']}/renew/").status_code == 403
    assert c.post("/api/subscriptions/from-template/", {}, format="json").status_code == 403
    assert Subscription.objects.get(pk=s["id"]).status == "draft"


def test_customer_sees_only_their_own_subscriptions(staff, cat, cust):
    other = user("c2@shop.com", Role.CUSTOMER)
    mine, theirs = make_sub(staff, cat, cust), make_sub(staff, cat, other)
    c = api(cust)
    assert [r["id"] for r in c.get("/api/subscriptions/").json()["results"]] == [mine["id"]]
    assert c.get(f"/api/subscriptions/{mine['id']}/").status_code == 200
    assert c.get(f"/api/subscriptions/{theirs['id']}/").status_code == 404  # not 403: it does not exist for them
    assert c.get(f"/api/subscriptions/?customer={other.pk}").json()["count"] == 0  # filters cannot widen the scope
    assert c.get(f"/api/subscriptions/?search={theirs['number']}").json()["count"] == 0


def test_customer_detail_shows_no_actions(staff, cat, cust):
    s = make_sub(staff, cat, cust)
    assert api(cust).get(f"/api/subscriptions/{s['id']}/").json()["actions"] == []


@pytest.mark.parametrize("path", ["quotation-templates", "customers"])
def test_staff_only_endpoints(path, cust, staff):
    assert api(cust).get(f"/api/{path}/").status_code == 403
    assert api().get(f"/api/{path}/").status_code == 403
    assert staff.get(f"/api/{path}/").status_code == 200


def test_anonymous_cannot_read_subscriptions():
    assert api().get("/api/subscriptions/").status_code == 403


def test_customers_picker_lists_only_customers(staff, cust):
    user("c2@shop.com", Role.CUSTOMER)
    r = staff.get("/api/customers/?search=c2").json()
    assert [x["email"] for x in r["results"]] == ["c2@shop.com"] and set(r["results"][0]) == {"id", "email", "name"}
    assert staff.get("/api/customers/").json()["count"] == 2


# --- list behaviour (rule 9) ---------------------------------------------------------------------

def test_list_filters_search_and_no_n_plus_one(staff, cat, cust, django_assert_max_num_queries):
    other = user("c2@shop.com", Role.CUSTOMER)
    for i in range(30):
        make_sub(staff, cat, other if i % 3 == 0 else cust)
    first = Subscription.objects.order_by("id").first()
    walk(staff, first.pk, "quotation")
    with django_assert_max_num_queries(6):  # session, user, count, page: constant, not per row
        d = staff.get("/api/subscriptions/").json()
    assert d["count"] == 30 and len(d["results"]) == 25 and d["next"]
    assert d["results"][0]["number"] == "SUB-000030"  # newest first
    assert d["results"][0]["lines_total"] == "3000.00" and "lines" not in d["results"][0]
    assert staff.get("/api/subscriptions/?status=quotation").json()["count"] == 1
    assert staff.get(f"/api/subscriptions/?customer={other.pk}").json()["count"] == 10
    assert staff.get(f"/api/subscriptions/?plan={cat['plan'].pk}").json()["count"] == 30
    assert staff.get("/api/subscriptions/?search=SUB-000007").json()["count"] == 1
    assert staff.get("/api/subscriptions/?search=c2@").json()["count"] == 10


def test_deleting_a_variant_used_by_a_subscription_keeps_the_line(staff, admin, cat, cust):
    s = make_sub(staff, cat, cust, lines=[{"product": cat["crm"].pk, "variant": cat["odoo"].pk, "quantity": 3}])
    r = admin.patch(f"/api/products/{cat['crm'].pk}/", {"variants": []}, format="json")
    assert r.status_code == 200
    line = staff.get(f"/api/subscriptions/{s['id']}/").json()["lines"][0]
    assert line["variant"] is None and line["unit_price"] == "1560.00"  # price stays as it was quoted
