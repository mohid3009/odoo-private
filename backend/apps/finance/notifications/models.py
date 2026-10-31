from django.conf import settings
from django.db import models


class NotificationEvent(models.Model):
    code = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=100)
    enabled_email = models.BooleanField(default=True)
    enabled_whatsapp = models.BooleanField(default=True)
    template_body = models.TextField()
    meta_template_name = models.CharField(max_length=100, blank=True)  # Meta provider only (Phase 7)

    def __str__(self):
        return self.code


class NotificationLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        SENT = "sent"
        DELIVERED = "delivered"
        READ = "read"
        FAILED = "failed"
        SKIPPED = "skipped"

    event = models.ForeignKey(NotificationEvent, on_delete=models.PROTECT, related_name="logs")
    channel = models.CharField(max_length=10)  # email | whatsapp
    provider = models.CharField(max_length=20, blank=True)
    recipient_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications")
    recipient_address = models.CharField(max_length=254, blank=True)
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUEUED)
    skip_reason = models.CharField(max_length=40, blank=True)
    provider_message_id = models.CharField(max_length=100, blank=True)
    error = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=200, unique=True)  # event:object:id:channel:variant -> reruns never double-send
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["object_type", "object_id"]), models.Index(fields=["status"])]
