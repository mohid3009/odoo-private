"""notify(): the one door for email/WhatsApp messages (docs/NOTIFICATIONS.md, D-020..D-025).
It never raises into the caller: any problem ends up on the NotificationLog row or in the server log."""
import logging
import time
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from apps.core.accounts.validators import normalize_whatsapp
from integrations import whatsapp

from .models import NotificationEvent, NotificationLog

log = logging.getLogger(__name__)
CHANNELS = ("email", "whatsapp")
BACKOFF = [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30)]

# code -> (label, default template). The admin can edit the body per event (Notifications page).
DEFAULT_EVENTS = {
    "WELCOME": ("Welcome to Brightloop", "Hi {customer_name}, welcome to Brightloop! Your account is ready."),
    "QUOTATION_READY": ("Your quotation is ready", "Hi {customer_name}, quotation {subscription_number} is ready for your review."),
    "SUBSCRIPTION_ACTIVATED": ("Your subscription is active", "Hi {customer_name}, subscription {subscription_number} is now active."),
    "INVOICE_READY": ("Your invoice is ready", "Hi {customer_name}, invoice {invoice_number} for ₹{amount} is ready. Due {due_date}. View: {link}"),
    "PAYMENT_RECEIVED": ("Payment received", "Hi {customer_name}, we received ₹{amount} for invoice {invoice_number}. {balance_note}"),
    "INVOICE_DUE_SOON": ("Invoice due soon", "Hi {customer_name}, invoice {invoice_number} for ₹{amount} is due on {due_date}. View: {link}"),
    "INVOICE_OVERDUE": ("Invoice overdue", "Hi {customer_name}, invoice {invoice_number} (₹{amount}) was due on {due_date}. Please pay soon. View: {link}"),
    "SUBSCRIPTION_EXPIRING": ("Subscription expiring", "Hi {customer_name}, subscription {subscription_number} expires on {expiry_date}."),
}


class _Safe(dict):
    def __missing__(self, key):
        return ""


def get_event(code):
    label, body = DEFAULT_EVENTS[code]
    event, _ = NotificationEvent.objects.get_or_create(code=code, defaults={"label": label, "template_body": body})
    return event


def _plan_channels(user, event, wanted):
    """-> list of (channel, address, skip_reason). skip_reason '' means send."""
    profile = getattr(user, "profile", None)
    out = []
    if "email" in wanted:
        ok = event.enabled_email and (profile.email_notifications if profile else True)
        out.append(("email", user.email, "" if ok else ("event_disabled" if not event.enabled_email else "email_opt_out")))
    if "whatsapp" in wanted:
        number = profile.whatsapp_number if profile else ""
        reason = ""
        if not event.enabled_whatsapp:
            reason = "event_disabled"
        elif not (profile and profile.whatsapp_opt_in):
            reason = "no_opt_in"
        else:
            try:
                number = normalize_whatsapp(number) or None
            except ValidationError:
                number = None
            if not number:
                reason, number = "invalid_number", profile.whatsapp_number
            elif not whatsapp.configured():
                reason = "provider_disabled"
        out.append(("whatsapp", number, reason))
    return out


def notify(code, user, obj, *, context=None, force=False, channels=None, variant=""):
    """Create one log row per channel (deduped) and send after commit. Returns the rows created."""
    try:
        with transaction.atomic():  # savepoint: a problem here must not poison the caller's transaction
            event = get_event(code)
            body = event.template_body.format_map(_Safe(context or {}))
            created = []
            for channel, address, reason in _plan_channels(user, event, channels or CHANNELS):
                key = f"{code}:{type(obj).__name__.lower()}:{obj.pk}:{channel}:{variant}"
                if force:
                    key += f":f{time.time_ns()}"  # manual send: an explicit, separate message
                row, is_new = NotificationLog.objects.get_or_create(
                    dedupe_key=key,
                    defaults=dict(
                        event=event, channel=channel, recipient_user=user, recipient_address=address, body=body,
                        object_type=type(obj).__name__.lower(), object_id=obj.pk,
                        provider=("email" if channel == "email" else settings.WHATSAPP_PROVIDER),
                        status="skipped" if reason else "queued", skip_reason=reason,
                    ),
                )
                if not is_new:
                    continue  # already sent for this event/object/channel: reruns never duplicate
                created.append(row)
                if row.status == "queued":
                    transaction.on_commit(lambda pk=row.pk: dispatch(pk))
            return created
    except Exception:
        log.exception("notify(%s) failed; the originating action is unaffected", code)
        return []


def dispatch(row_id):
    """Send one queued row. Updates the row; never raises."""
    try:
        row = NotificationLog.objects.select_related("event").filter(pk=row_id, status__in=["queued", "failed"]).first()
        if row is None:
            return
        row.attempts += 1
        try:
            if row.channel == "email":
                send_mail(row.event.label, row.body, settings.DEFAULT_FROM_EMAIL, [row.recipient_address], fail_silently=False)
                row.provider_message_id = ""
            else:
                row.provider_message_id = whatsapp.send(row.recipient_address, row.body, row.pk)
            row.status, row.sent_at, row.error, row.next_attempt_at = "sent", timezone.now(), "", None
        except Exception as e:
            row.status, row.error = "failed", f"{type(e).__name__}: {e}"[:500]
            row.next_attempt_at = timezone.now() + BACKOFF[min(row.attempts - 1, len(BACKOFF) - 1)] if row.attempts < 3 else None
        row.save()
    except Exception:
        log.exception("dispatch(%s) crashed", row_id)


def send_pending(now=None):
    """The retry sweep: queued rows that never got dispatched and failed rows whose backoff has passed."""
    now = now or timezone.now()
    ids = list(
        NotificationLog.objects.filter(attempts__lt=3)
        .filter(models.Q(status="queued", created_at__lte=now - BACKOFF[0]) | models.Q(status="failed", next_attempt_at__lte=now))
        .values_list("pk", flat=True)
    )
    for pk in ids:
        dispatch(pk)
    return len(ids)
