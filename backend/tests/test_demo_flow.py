"""Phase 9 rehearsal: the S1-S7 demo (docs/DEMO_SCRIPT.md) end to end through the public API on an empty database.
If this passes, the live demo's data path works; the browser run then only checks the screens."""
import re
from datetime import timedelta

from django.core import mail
from django.utils import timezone

from apps.core.accounts.models import Role
from apps.core.billing.engine import add_months
from apps.finance.notifications.models import NotificationLog
from tests.conftest import api_for, mk_user

TODAY = timezone.localdate()
START = TODAY - timedelta(days=100)  # four monthly periods are already due, the first one overdue


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.content[:300])
    return r.json()


def month(n):
    return add_months(START, n, START.day).isoformat()


def test_demo_s1_to_s7(db):
    anon = api_for()
    admin = mk_user("admin@demo.com", Role.ADMIN)
    a = api_for(admin)

    # --- S1 sign-up, roles, reset ---------------------------------------------------------------
    assert anon.post("/api/auth/signup/", {"email": "new@demo.com", "password": "weakpass"}, format="json").status_code == 400
    user = ok(anon.post("/api/auth/signup/", {"email": "new@demo.com", "password": "Strong@Pass1", "name": "New Shop",
                                              "whatsapp_number": "9876543210", "whatsapp_opt_in": True}, format="json"), 201)
    assert user["role"] == "customer"
    assert "email" in ok(anon.post("/api/auth/signup/", {"email": "NEW@demo.com", "password": "Strong@Pass1"}, format="json"), 400)
    ok(anon.post("/api/auth/password-reset/request/", {"email": "new@demo.com"}, format="json"))
    uid, token = re.search(r"/reset-password/([^/]+)/([^/\s]+)", mail.outbox[-1].body).groups()
    ok(anon.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "Another@Pass2"}, format="json"))
    cust = api_for()
    ok(cust.post("/api/auth/login/", {"email": "new@demo.com", "password": "Another@Pass2"}, format="json"))
    ok(a.post("/api/staff/", {"email": "ops@demo.com", "password": "Staff@Pass1", "name": "Ops"}, format="json"), 201)
    s = api_for()
    ok(s.post("/api/auth/login/", {"email": "ops@demo.com", "password": "Staff@Pass1"}, format="json"))
    assert s.post("/api/staff/", {"email": "x@demo.com", "password": "Staff@Pass1"}, format="json").status_code == 403

    # --- S2 catalog and plan (admin) ------------------------------------------------------------
    gst = ok(a.post("/api/taxes/", {"name": "GST 18%", "rate": "18"}, format="json"), 201)
    term = ok(a.post("/api/payment-terms/", {"name": "Net 15", "days": 15, "is_default": True}, format="json"), 201)
    crm = ok(a.post("/api/products/", {
        "name": "Brightloop CRM", "type": "software", "sales_price": "1000.00", "cost_price": "400.00", "taxes": [gst["id"]],
        "variants": [{"attribute": "Brand", "value": "Odoo", "extra_price": "560.00"}]}, format="json"), 201)
    assert crm["variants"][0]["effective_unit_price"] == "1560.00"
    plan = ok(a.post("/api/plans/", {
        "name": "CRM Monthly", "product": crm["id"], "price": "1000.00", "billing_period": "monthly", "min_quantity": 1,
        "available_from": (START - timedelta(days=30)).isoformat(), "available_to": (TODAY + timedelta(days=700)).isoformat(),
        "auto_close": True, "allow_early_close": True, "allow_pause": True, "allow_renew": True}, format="json"), 201)
    assert s.patch(f"/api/products/{crm['id']}/", {"name": "x"}, format="json").status_code == 403

    # --- S3 template -> subscription (staff) ----------------------------------------------------
    tpl = ok(s.post("/api/quotation-templates/", {"name": "CRM Starter", "plan": plan["id"], "validity_days": 15,
                                                  "lines": [{"product": crm["id"], "variant": crm["variants"][0]["id"], "quantity": 5}]}, format="json"), 201)
    sub = ok(s.post("/api/subscriptions/from-template/", {"template": tpl["id"], "customer": user["id"], "start_date": START.isoformat(),
                                                          "expiry_date": (START + timedelta(days=364)).isoformat(), "payment_term": term["id"]}, format="json"), 201)
    assert sub["lines_total"] == "7800.00"
    for to in ("quotation", "confirmed", "active"):
        sub = ok(s.post(f"/api/subscriptions/{sub['id']}/transition/", {"to": to}, format="json"))
    assert [x["to_status"] for x in sub["status_log"]] == ["quotation", "confirmed", "active"]
    assert s.post(f"/api/subscriptions/{sub['id']}/transition/", {"to": "draft"}, format="json").status_code == 409

    # --- S4 billing day -------------------------------------------------------------------------
    run = ok(s.post("/api/billing/run/", {"as_of": month(0)}, format="json"))
    assert (run["created"], run["errors"]) == (1, 0)
    assert ok(s.post("/api/billing/run/", {"as_of": month(0)}, format="json"))["created"] == 0   # nothing billed twice
    first = ok(s.get("/api/invoices/", {"subscription": sub["id"]}))["results"][0]
    assert (first["subtotal"], first["tax_total"], first["total"]) == ("7800.00", "1404.00", "9204.00")
    first = ok(s.post(f"/api/invoices/{first['id']}/confirm/"))
    assert first["number"].startswith("INV-") and first["status"] == "confirmed"
    assert ok(s.post(f"/api/invoices/{first['id']}/send/", {"channels": ["email"]}, format="json"))["sent_at"]
    assert ok(cust.get(f"/api/invoices/{first['id']}/print/"))["customer_details"]["email"] == "new@demo.com"

    # --- S5 discount with a usage limit of 2 (admin) -------------------------------------------
    assert s.post("/api/discounts/", {"name": "x", "type": "percent", "value": "10", "scope": "subscription"}, format="json").status_code == 403
    disc = ok(a.post("/api/discounts/", {"name": "Launch 10%", "type": "percent", "value": "10", "scope": "product", "products": [crm["id"]],
                                         "min_quantity": 5, "start_date": month(1), "usage_limit": 2}, format="json"), 201)
    totals = []
    for n in (1, 2, 3):
        ok(s.post("/api/billing/run/", {"as_of": month(n)}, format="json"))
        inv = ok(s.get("/api/invoices/", {"subscription": sub["id"], "ordering": "-id"}))["results"][0]
        totals.append(inv["total"])
    assert totals == ["8283.60", "8283.60", "9204.00"]   # the worked example twice, then the limit is reached
    assert ok(a.get(f"/api/discounts/{disc['id']}/"))["state"] == "exhausted"

    # --- S6 payments ----------------------------------------------------------------------------
    dec = ok(s.get("/api/invoices/", {"subscription": sub["id"], "ordering": "id"}))["results"][1]
    dec = ok(s.post(f"/api/invoices/{dec['id']}/confirm/"))
    p = ok(s.post(f"/api/invoices/{dec['id']}/payments/", {"amount": "5000.00", "method": "upi", "note": "first part"}, format="json"), 201)
    assert p["invoice_state"]["amount_due"] == "3283.60" and p["invoice_state"]["status"] == "confirmed"
    assert s.post(f"/api/invoices/{dec['id']}/payments/", {"amount": "4000.00", "method": "upi"}, format="json").status_code == 400
    p = ok(s.post(f"/api/invoices/{dec['id']}/payments/", {"amount": "3283.60", "method": "cash"}, format="json"), 201)
    assert p["invoice_state"]["status"] == "paid"
    overdue = ok(s.get("/api/invoices/", {"overdue": "true"}))["results"]
    assert [i["id"] for i in overdue] == [first["id"]] and overdue[0]["days_overdue"] > 0

    # --- S7 finance view ------------------------------------------------------------------------
    k = ok(s.get("/api/dashboard/summary/"))["kpis"]
    assert (k["active_subscriptions"], k["mrr"], k["revenue_collected"], k["outstanding"], k["overdue_count"]) == (
        1, "7800.00", "8283.60", "9204.00", 1)
    assert [i["id"] for i in ok(cust.get("/api/invoices/"))["results"]] == [dec["id"], first["id"]]  # confirmed only, own only
    assert cust.get("/api/dashboard/summary/").status_code == 403

    # --- notifications: reruns add nothing ------------------------------------------------------
    assert NotificationLog.objects.exists()
    for n in range(4):
        ok(s.post("/api/billing/run/", {"as_of": month(n)}, format="json"))
    ok(a.post("/api/notifications/run-reminders/", {}, format="json"))
    after_first = NotificationLog.objects.count()
    ok(a.post("/api/notifications/run-reminders/", {}, format="json"))
    assert NotificationLog.objects.count() == after_first   # reminders are deduplicated
    assert set(NotificationLog.objects.values_list("event__code", flat=True)) >= {
        "WELCOME", "QUOTATION_READY", "SUBSCRIPTION_ACTIVATED", "INVOICE_READY", "PAYMENT_RECEIVED"}
