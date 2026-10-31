from rest_framework import serializers

from apps.core.accounts.serializers import ProfileSerializer

from .models import NotificationEvent, NotificationLog


class LogSerializer(serializers.ModelSerializer):
    event = serializers.CharField(source="event.code")
    event_label = serializers.CharField(source="event.label")
    recipient_email = serializers.CharField(source="recipient_user.email", default="", read_only=True)

    class Meta:
        model = NotificationLog
        fields = [
            "id", "event", "event_label", "channel", "provider", "recipient_user", "recipient_email", "recipient_address",
            "object_type", "object_id", "body", "status", "skip_reason", "error", "attempts", "next_attempt_at", "created_at", "sent_at",
        ]


class MyLogSerializer(serializers.ModelSerializer):
    """Customer-safe: no provider ids, errors or internal reasons."""
    event_label = serializers.CharField(source="event.label")

    class Meta:
        model = NotificationLog
        fields = ["id", "event_label", "channel", "status", "body", "created_at", "sent_at"]


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ["code", "label", "enabled_email", "enabled_whatsapp", "template_body"]
        read_only_fields = ["code", "label"]
        extra_kwargs = {"template_body": {"allow_blank": False}}


class SettingsSerializer(ProfileSerializer):
    class Meta(ProfileSerializer.Meta):
        fields = ["email_notifications", "whatsapp_number", "whatsapp_opt_in"]


class TestSendSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(choices=["email", "whatsapp"])
    to = serializers.CharField()
    body = serializers.CharField(max_length=1000)


class RunRemindersSerializer(serializers.Serializer):
    as_of = serializers.DateField(required=False)
