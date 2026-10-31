"""Phase 7: reminders, the Twilio adapter, the retry sweep, the notification API and the event wiring."""
import io
import json
import urllib.error
from datetime import date, timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from apps.core.billing import engine
from apps.core.billing import services as billing_services
from apps.core.billing.models import Invoice
from apps.finance.notifications.models import NotificationLog
from apps.finance.notifications.reminders import run_reminders
from apps.finance.notifications.services import dispatch, notify, send_pending
from conftest import api_for, mk_user
from integrations import whatsapp

pytestmark = pytest.mark.django_db
BILLED = date(2026, 1, 1)  # invoice date; Net 15 -> due 2026-01-16


@pytest.fixture
def inv(make_sub, staff):
    make_sub(BILLED, expiry=date(2026, 1, 25))
    engine.run_billing(BILLED)
    return billing_services.confirm(Invoice.objects.get(), staff)


def codes(code):
    return NotificationLog.objects.filter(event__code=code, channel="email").count()


# --- mandatory test 8: reminder windows ---------------------------------------------

@pytest.mark.parametrize("day,due_soon,overdue,expiring", [
    (date(2026, 1, 12), 0, 0, 0),
    (date(2026, 1, 13), 1, 0, 0),   # exactly 3 days before the 16th
    (date(2026, 1, 14), 0, 0, 0),
    (date(2026, 1, 17), 0, 1, 0),   # day 1 overdue
    (date(2026, 1, 20), 0, 0, 0),
    (date(2026, 1, 23), 0, 1, 0),   # day 7 overdue
    (date(2026, 1, 24), 0, 0, 0),
    (date(2026, 1, 18), 0, 0, 1),   # expiry 2026-01-25 - 7 days
])
def test_reminder_windows(inv, day, due_soon, overdue, expiring):
    r = run_reminders(day)
    assert (r["due_soon"], r["overdue"], r["expiring"]) == (due_soon, overdue, expiring)


def test_overdue_reminder_states_the_amount_still_owed(inv, staff):
    from apps.finance.payments import services as pay_services

    pay_services.record_payment(inv, staff, {"amount": "1000.00", "method": "cash", "status": "completed"})
    run_reminders(date(2026, 1, 17))
    body = NotificationLog.objects.get(event__code="INVOICE_OVERDUE", channel="email").body
    assert "8204.00" in body and "9204.00" not in body


def test_draft_invoices_get_no_reminders(make_sub):
    make_sub(BILLED)
    engine.run_billing(BILLED)  # leaves a draft invoice
    assert run_reminders(date(2026, 1, 17))["overdue"] == 0


# --- mandatory test 5: reruns create no new rows --------------------------------------

def test_rerunning_billing_and_reminders_creates_no_new_log_rows(inv):
    engine.run_billing(date(2026, 1, 17))  # also runs the reminders for that day
    n = NotificationLog.objects.count()
    assert codes("INVOICE_OVERDUE") == 1
    engine.run_billing(date(2026, 1, 17))
    run_reminders(date(2026, 1, 17))
    call_command("run_notifications", "--as-of", "2026-01-17")
    assert NotificationLog.objects.count() == n


def test_reminder_failure_never_fails_the_billing_run(make_sub, monkeypatch):
    make_sub(BILLED)
    monkeypatch.setattr("apps.finance.notifications.reminders.run_reminders", lambda *a: 1 / 0)
    assert engine.run_billing(BILLED).created_count == 1


# --- Twilio adapter (HTTP mocked: no network in tests) ----------------------------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def twilio(settings):
    settings.WHATSAPP_PROVIDER = "twilio"
    settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN = "ACtest", "secret"
    settings.TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"


def test_twilio_request_shape_and_message_id(twilio, monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen.update(url=req.full_url, body=req.data.decode(), auth=req.get_header("Authorization"))
        return _Resp(json.dumps({"sid": "SM123"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert whatsapp.send("+919876543210", "Hello ₹5", 1) == "SM123"
    assert seen["url"].endswith("/Accounts/ACtest/Messages.json")
    assert "To=whatsapp%3A%2B919876543210" in seen["body"] and "From=whatsapp%3A%2B14155238886" in seen["body"]
    assert seen["auth"].startswith("Basic ") and whatsapp.status() == {"provider": "twilio", "configured": True, "sandbox": True}


def test_twilio_error_message_reaches_the_log_row(twilio, monkeypatch, django_capture_on_commit_callbacks):
    def refuse(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"message": "not joined to the sandbox"}'))

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    u = mk_user("w@shop.com", "customer", whatsapp_number="+919876543210", whatsapp_opt_in=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify("WELCOME", u, u, context={"customer_name": "W"})
    w = NotificationLog.objects.get(channel="whatsapp")
    assert w.status == "failed" and "not joined to the sandbox" in w.error and w.attempts == 1
    assert NotificationLog.objects.get(channel="email").status == "sent"


# --- retry sweep (mandatory test 7, command form) ------------------------------------------

def test_send_notifications_retries_due_failed_rows_only(cust, make_sub, monkeypatch, django_capture_on_commit_callbacks):
    sub = make_sub(BILLED)
    monkeypatch.setattr("apps.finance.notifications.services.send_mail", lambda *a, **k: 1 / 0)
    with django_capture_on_commit_callbacks(execute=True):
        notify("WELCOME", cust, sub, context={}, channels=["email"])
    row = NotificationLog.objects.get()
    assert row.status == "failed" and row.attempts == 1
    assert send_pending() == 0  # backoff has not passed yet
    monkeypatch.setattr("apps.finance.notifications.services.send_mail", lambda *a, **k: 1)
    assert send_pending(timezone.now() + timedelta(minutes=2)) == 1
    row.refresh_from_db()
    assert row.status == "sent" and row.attempts == 2
    NotificationLog.objects.filter(pk=row.pk).update(status="failed", attempts=3, next_attempt_at=None)
    assert send_pending(timezone.now() + timedelta(days=1)) == 0  # gave up after 3
    call_command("send_notifications")


# --- API ---------------------------------------------------------------------------------------

def test_log_list_is_admin_only_with_a_scoped_exception_for_staff(inv, admin, staff, cust):
    assert api_for(admin).get("/api/notifications/logs/").status_code == 200
    assert api_for(staff).get("/api/notifications/logs/").status_code == 403
    assert api_for(cust).get("/api/notifications/logs/").status_code == 403
    assert api_for(None).get("/api/notifications/logs/").status_code in (401, 403)
    r = api_for(staff).get(f"/api/notifications/logs/?object_type=invoice&object_id={inv.pk}")
    assert r.status_code == 200 and {x["object_id"] for x in r.json()["results"]} == {inv.pk}
    assert api_for(staff).get("/api/notifications/logs/?object_type=invoice").status_code == 403
    assert api_for(cust).get(f"/api/notifications/logs/?object_type=invoice&object_id={inv.pk}").status_code == 403


def test_log_filters(inv, admin):
    c = api_for(admin)
    assert c.get("/api/notifications/logs/?event=INVOICE_READY&channel=email").json()["count"] == 1
    assert c.get("/api/notifications/logs/?status=skipped").json()["count"] >= 1
    assert c.get("/api/notifications/logs/?event=NOPE").json()["count"] == 0


def test_admin_retry_resets_attempts_and_only_works_on_failed_rows(inv, admin, staff):
    row = NotificationLog.objects.get(event__code="INVOICE_READY", channel="email")
    assert api_for(admin).post(f"/api/notifications/logs/{row.pk}/retry/").status_code == 409  # already sent
    NotificationLog.objects.filter(pk=row.pk).update(status="failed", attempts=3, error="boom")
    assert api_for(staff).post(f"/api/notifications/logs/{row.pk}/retry/").status_code == 403
    r = api_for(admin).post(f"/api/notifications/logs/{row.pk}/retry/")
    assert r.status_code == 200 and r.json()["status"] == "sent" and r.json()["attempts"] == 1


def test_events_list_and_patch(admin, staff):
    r = api_for(admin).get("/api/notifications/events/")
    assert {e["code"] for e in r.json()} >= {"WELCOME", "INVOICE_READY", "PAYMENT_RECEIVED", "INVOICE_OVERDUE"}
    p = api_for(admin).patch("/api/notifications/events/WELCOME/", {"enabled_whatsapp": False, "template_body": "Hi {customer_name}!"}, format="json")
    assert p.status_code == 200 and p.json()["enabled_whatsapp"] is False
    assert api_for(admin).patch("/api/notifications/events/WELCOME/", {"template_body": ""}, format="json").status_code == 400
    assert api_for(staff).get("/api/notifications/events/").status_code == 403
    assert api_for(staff).patch("/api/notifications/events/WELCOME/", {"enabled_email": False}, format="json").status_code == 403


def test_a_disabled_event_is_skipped_and_an_edited_body_is_used(cust, admin):
    api_for(admin).get("/api/notifications/events/")
    api_for(admin).patch("/api/notifications/events/WELCOME/", {"enabled_email": False}, format="json")
    api_for(admin).patch("/api/notifications/events/QUOTATION_READY/", {"template_body": "Custom {subscription_number}"}, format="json")
    notify("WELCOME", cust, cust, context={})
    notify("QUOTATION_READY", cust, cust, context={"subscription_number": "SUB-9"}, channels=["email"])
    assert NotificationLog.objects.get(event__code="WELCOME", channel="email").skip_reason == "event_disabled"
    assert NotificationLog.objects.get(event__code="QUOTATION_READY").body == "Custom SUB-9"


def test_test_send(admin, staff):
    c = api_for(admin)
    r = c.post("/api/notifications/test-send/", {"channel": "email", "to": "me@x.com", "body": "hi"}, format="json")
    assert r.json() == {"ok": True, "provider": "email", "detail": "sent"} and mail.outbox[-1].to == ["me@x.com"]
    r = c.post("/api/notifications/test-send/", {"channel": "whatsapp", "to": "9876543210", "body": "hi"}, format="json")
    assert r.json()["ok"] is True and r.json()["provider"] == "console" and NotificationLog.objects.count() == 0
    assert c.post("/api/notifications/test-send/", {"channel": "whatsapp", "to": "12", "body": "hi"}, format="json").status_code == 400
    assert c.post("/api/notifications/test-send/", {"channel": "email", "to": "nope", "body": "hi"}, format="json").status_code == 400
    assert api_for(staff).post("/api/notifications/test-send/", {"channel": "email", "to": "a@b.co", "body": "x"}, format="json").status_code == 403


def test_test_send_reports_provider_failure_as_a_result(admin, settings):
    settings.WHATSAPP_PROVIDER = "twilio"
    settings.TWILIO_ACCOUNT_SID = ""
    r = api_for(admin).post("/api/notifications/test-send/", {"channel": "whatsapp", "to": "+919876543210", "body": "hi"}, format="json")
    assert r.status_code == 200 and r.json()["ok"] is False and "not configured" in r.json()["detail"]


def test_run_reminders_endpoint_and_provider_status(inv, admin, staff):
    assert api_for(staff).post("/api/notifications/run-reminders/", {}, format="json").status_code == 403
    r = api_for(admin).post("/api/notifications/run-reminders/", {"as_of": "2026-01-13"}, format="json")
    assert r.status_code == 200 and r.json()["due_soon"] == 1
    assert api_for(admin).post("/api/notifications/run-reminders/", {"as_of": "2026-01-13"}, format="json").json()["due_soon"] == 0
    assert api_for(admin).get("/api/notifications/provider-status/").json() == {"provider": "console", "configured": True, "sandbox": False}
    assert api_for(staff).get("/api/notifications/provider-status/").status_code == 403


def test_my_notification_settings(cust, staff):
    c = api_for(cust)
    assert c.get("/api/me/notification-settings/").json() == {"email_notifications": True, "whatsapp_number": "", "whatsapp_opt_in": False}
    assert c.patch("/api/me/notification-settings/", {"whatsapp_opt_in": True}, format="json").status_code == 400  # needs a number
    r = c.patch("/api/me/notification-settings/", {"whatsapp_number": "9876543210", "whatsapp_opt_in": True, "email_notifications": False}, format="json")
    assert r.status_code == 200 and r.json()["whatsapp_number"] == "+919876543210" and r.json()["whatsapp_opt_in"] is True
    cust.profile.refresh_from_db()
    assert cust.profile.whatsapp_opted_in_at is not None and cust.profile.email_notifications is False
    assert api_for(staff).get("/api/me/notification-settings/").status_code == 404
    assert api_for(None).get("/api/me/notification-settings/").status_code in (401, 403)


def test_my_notifications_shows_only_my_sent_messages_with_safe_fields(inv, cust):
    other = mk_user("other@shop.com", "customer")
    notify("WELCOME", other, other, context={}, channels=["email"])
    for pk in NotificationLog.objects.values_list("pk", flat=True):
        dispatch(pk)  # on_commit does not fire inside a test transaction
    assert NotificationLog.objects.filter(recipient_user=other, status="sent").exists()
    rows = api_for(cust).get("/api/me/notifications/").json()["results"]
    assert rows and all(set(r) == {"id", "event_label", "channel", "status", "body", "created_at", "sent_at"} for r in rows)
    assert all(r["status"] == "sent" for r in rows) and len(rows) == NotificationLog.objects.filter(recipient_user=cust, status="sent").count()


# --- event wiring ---------------------------------------------------------------------------------

def test_signup_sends_welcome(client, django_capture_on_commit_callbacks):
    body = {"email": "new@shop.com", "password": "Strong@Pass1", "name": "New", "whatsapp_number": "9876543210", "whatsapp_opt_in": True}
    with django_capture_on_commit_callbacks(execute=True):
        r = client.post("/api/auth/signup/", body, content_type="application/json")
    assert r.status_code == 201
    assert {(n.channel, n.status) for n in NotificationLog.objects.filter(event__code="WELCOME")} == {("email", "sent"), ("whatsapp", "sent")}


def test_quotation_and_activation_notify_the_customer_once(staff, make_sub, django_capture_on_commit_callbacks):
    from apps.core.subscriptions import services as sub_services

    sub = make_sub(date.today(), status="draft")
    with django_capture_on_commit_callbacks(execute=True):
        sub_services.transition(sub, "quotation", staff)
        sub_services.transition(sub, "confirmed", staff)
        sub_services.transition(sub, "active", staff)
    assert codes("QUOTATION_READY") == 1 and codes("SUBSCRIPTION_ACTIVATED") == 1
    assert sub.number in NotificationLog.objects.get(event__code="QUOTATION_READY", channel="email").body


def test_recording_a_payment_notifies_and_a_failed_attempt_does_not(inv, staff, django_capture_on_commit_callbacks):
    from apps.finance.payments import services as pay_services

    with django_capture_on_commit_callbacks(execute=True):
        pay_services.record_payment(inv, staff, {"amount": "500.00", "method": "card", "status": "failed", "failure_reason": "declined"})
        assert codes("PAYMENT_RECEIVED") == 0
        pay_services.record_payment(inv, staff, {"amount": "500.00", "method": "cash", "status": "completed"})
    assert codes("PAYMENT_RECEIVED") == 1


def test_invoice_send_picks_channels(inv, staff, cust):
    cust.profile.whatsapp_number, cust.profile.whatsapp_opt_in = "+919876543210", True
    cust.profile.save()
    r = api_for(staff).post(f"/api/invoices/{inv.pk}/send/", {"channels": ["whatsapp"]}, format="json")
    assert r.status_code == 200
    forced = NotificationLog.objects.filter(event__code="INVOICE_READY", dedupe_key__contains=":f")
    assert [n.channel for n in forced] == ["whatsapp"]
