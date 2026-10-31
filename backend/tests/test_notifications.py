import pytest
from django.core import mail

from apps.finance.notifications.models import NotificationEvent, NotificationLog
from apps.finance.notifications.services import dispatch, notify
from conftest import mk_user

pytestmark = pytest.mark.django_db
CTX = {"customer_name": "Cara", "invoice_number": "INV-000007", "amount": "9204.00", "due_date": "2026-11-16", "link": "http://x/i/7"}


@pytest.fixture
def obj(make_sub):
    return make_sub(__import__("datetime").date(2026, 11, 1))  # any model instance works as the "object"


def rows():
    return {n.channel: n for n in NotificationLog.objects.order_by("id")}


def test_notify_logs_both_channels_and_sends_after_commit(cust, obj, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True) as cbs:
        made = notify("INVOICE_READY", cust, obj, context=CTX)
    assert len(made) == 2 and len(cbs) == 1  # only the email is queued; WhatsApp was skipped
    r = rows()
    assert r["email"].status == "sent" and r["email"].recipient_address == "c1@shop.com" and r["email"].sent_at
    assert "INV-000007" in r["email"].body and "9204.00" in r["email"].body and "Cara" in r["email"].body
    assert r["whatsapp"].status == "skipped" and r["whatsapp"].skip_reason == "no_opt_in"
    assert len(mail.outbox) == 1 and mail.outbox[0].subject == "Your invoice is ready"


def test_nothing_is_sent_until_the_transaction_commits(cust, obj):
    notify("INVOICE_READY", cust, obj, context=CTX)  # on_commit callbacks do not run inside the test transaction
    assert len(mail.outbox) == 0 and rows()["email"].status == "queued"


def test_whatsapp_goes_out_on_the_console_provider_when_opted_in(obj, django_capture_on_commit_callbacks):
    u = mk_user("w@shop.com", "customer", whatsapp_number="+919876543210", whatsapp_opt_in=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify("INVOICE_READY", u, obj, context=CTX)
    w = rows()["whatsapp"]
    assert w.status == "sent" and w.recipient_address == "+919876543210" and w.provider == "console" and w.provider_message_id.startswith("console-")


@pytest.mark.parametrize("profile,reason", [
    ({"whatsapp_opt_in": False, "whatsapp_number": "+919876543210"}, "no_opt_in"),
    ({"whatsapp_opt_in": True, "whatsapp_number": ""}, "invalid_number"),
])
def test_whatsapp_skip_reasons(obj, profile, reason):
    u = mk_user("w@shop.com", "customer", **profile)
    notify("INVOICE_READY", u, obj, context=CTX)
    assert rows()["whatsapp"].status == "skipped" and rows()["whatsapp"].skip_reason == reason


def test_email_opt_out_and_disabled_events_are_skipped(obj):
    u = mk_user("q@shop.com", "customer", email_notifications=False)
    notify("INVOICE_READY", u, obj, context=CTX)
    assert rows()["email"].status == "skipped" and rows()["email"].skip_reason == "email_opt_out"
    NotificationEvent.objects.filter(code="INVOICE_READY").update(enabled_email=False, enabled_whatsapp=False)
    u2 = mk_user("r@shop.com", "customer")
    notify("INVOICE_READY", u2, obj, context=CTX, variant="second")  # same object+channel as above would be deduped
    mine = NotificationLog.objects.filter(recipient_user=u2)
    assert {n.skip_reason for n in mine} == {"event_disabled"} and not mail.outbox


def test_same_event_object_channel_is_deduplicated_but_force_sends_again(cust, obj, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        first = notify("INVOICE_READY", cust, obj, context=CTX)
        again = notify("INVOICE_READY", cust, obj, context=CTX)
    assert len(first) == 2 and again == [] and NotificationLog.objects.count() == 2 and len(mail.outbox) == 1
    with django_capture_on_commit_callbacks(execute=True):
        forced = notify("INVOICE_READY", cust, obj, context=CTX, force=True)
    assert len(forced) == 2 and NotificationLog.objects.count() == 4 and len(mail.outbox) == 2


def test_variant_distinguishes_reminder_stages(cust, obj):
    notify("INVOICE_OVERDUE", cust, obj, context=CTX, variant="d1")
    notify("INVOICE_OVERDUE", cust, obj, context=CTX, variant="d7")
    notify("INVOICE_OVERDUE", cust, obj, context=CTX, variant="d1")  # rerun of the day-1 reminder
    assert NotificationLog.objects.filter(channel="email").count() == 2


def test_channels_argument_limits_what_is_logged(cust, obj):
    notify("INVOICE_READY", cust, obj, context=CTX, channels=["email"])
    assert list(rows()) == ["email"]


def test_provider_failure_is_recorded_not_raised(cust, obj, monkeypatch, django_capture_on_commit_callbacks):
    def boom(*a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr("apps.finance.notifications.services.send_mail", boom)
    with django_capture_on_commit_callbacks(execute=True):
        notify("INVOICE_READY", cust, obj, context=CTX)  # must not raise
    e = rows()["email"]
    assert e.status == "failed" and e.attempts == 1 and "smtp down" in e.error and e.next_attempt_at and e.sent_at is None


def test_twilio_without_credentials_is_skipped_as_provider_disabled(obj, settings, django_capture_on_commit_callbacks):
    settings.WHATSAPP_PROVIDER, settings.TWILIO_ACCOUNT_SID = "twilio", ""
    u = mk_user("w@shop.com", "customer", whatsapp_number="+919876543210", whatsapp_opt_in=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify("INVOICE_READY", u, obj, context=CTX)
    w = rows()["whatsapp"]
    assert w.status == "skipped" and w.skip_reason == "provider_disabled" and rows()["email"].status == "sent"  # email unaffected


def test_unknown_provider_fails_cleanly_on_the_row(obj, settings, django_capture_on_commit_callbacks):
    settings.WHATSAPP_PROVIDER = "meta"  # not built (stretch): configured() is False -> skipped, never an exception
    u = mk_user("w@shop.com", "customer", whatsapp_number="+919876543210", whatsapp_opt_in=True)
    with django_capture_on_commit_callbacks(execute=True):
        notify("INVOICE_READY", u, obj, context=CTX)
    assert rows()["whatsapp"].skip_reason == "provider_disabled"


@pytest.mark.parametrize("raw,sent_to", [("9876543210", "+919876543210"), ("+91 98765-43210", "+919876543210")])
def test_numbers_are_normalised_to_e164(obj, raw, sent_to, django_capture_on_commit_callbacks):
    u = mk_user("w@shop.com", "customer", whatsapp_number=raw, whatsapp_opt_in=True)  # stored raw, e.g. by an older client
    with django_capture_on_commit_callbacks(execute=True):
        notify("INVOICE_READY", u, obj, context=CTX)
    w = rows()["whatsapp"]
    assert w.recipient_address == sent_to and w.status == "sent"


@pytest.mark.parametrize("raw", ["12345", "abc", "+0123456789"])
def test_unusable_numbers_are_skipped_as_invalid(obj, raw):
    u = mk_user("w@shop.com", "customer", whatsapp_number=raw, whatsapp_opt_in=True)
    notify("INVOICE_READY", u, obj, context=CTX)
    w = rows()["whatsapp"]
    assert w.status == "skipped" and w.skip_reason == "invalid_number"


def test_a_failed_row_can_be_retried_and_gives_up_after_three(cust, obj, monkeypatch, django_capture_on_commit_callbacks):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("temporary")

    monkeypatch.setattr("apps.finance.notifications.services.send_mail", flaky)
    with django_capture_on_commit_callbacks(execute=True):
        notify("INVOICE_READY", cust, obj, context=CTX, channels=["email"])
    e = rows()["email"]
    dispatch(e.pk)
    e.refresh_from_db()
    assert e.status == "failed" and e.attempts == 2 and e.next_attempt_at
    dispatch(e.pk)
    e.refresh_from_db()
    assert e.status == "sent" and e.attempts == 3 and e.next_attempt_at is None
    dispatch(e.pk)  # already sent: nothing happens
    e.refresh_from_db()
    assert e.attempts == 3


def test_console_email_backend_survives_a_stdout_that_cannot_encode_the_rupee_sign():
    import io

    from django.core.mail import EmailMessage

    from apps.finance.notifications.email_backend import ConsoleEmailBackend

    raw = io.BytesIO()
    cp1252 = io.TextIOWrapper(raw, encoding="cp1252", write_through=True)  # what a Windows console looks like
    backend = ConsoleEmailBackend(stream=cp1252)
    assert backend.send_messages([EmailMessage("Invoice", "Total ₹9204.00", "a@x.com", ["b@x.com"])]) == 1
    out = raw.getvalue().decode("cp1252")
    assert "Total" in out and "9204.00" in out  # printed (escaped), not raised


def test_notify_never_raises_even_for_bad_input(cust, obj):
    assert notify("NO_SUCH_EVENT", cust, obj) == []
    assert notify("INVOICE_READY", None, obj) == []
    assert NotificationLog.objects.count() == 0


def test_missing_template_values_render_empty_instead_of_failing(cust, obj):
    (row, *_) = notify("INVOICE_READY", cust, obj, context={"customer_name": "Cara"}, channels=["email"])
    assert row.body.startswith("Hi Cara, invoice  for ₹ is ready")
