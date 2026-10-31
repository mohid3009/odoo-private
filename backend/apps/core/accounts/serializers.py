from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import CustomerProfile, Role
from .validators import normalize_whatsapp

User = get_user_model()


def unique_email(value):
    value = value.strip().lower()
    if User.objects.filter(email__iexact=value).exists():
        raise serializers.ValidationError("An account with this email already exists.")
    return value


def strong_password(value):
    try:
        validate_password(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(list(e.messages))
    return value


def whatsapp_number(value):
    try:
        return normalize_whatsapp(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(e.messages[0])


class ProfileSerializer(serializers.ModelSerializer):
    whatsapp_number = serializers.CharField(required=False, allow_blank=True)

    def validate_whatsapp_number(self, value):
        return whatsapp_number(value)

    class Meta:
        model = CustomerProfile
        fields = [
            "company_name", "phone", "address", "whatsapp_number", "whatsapp_opt_in",
            "email_notifications", "whatsapp_opted_in_at", "odoo_sync_status",
        ]
        read_only_fields = ["whatsapp_opted_in_at", "odoo_sync_status"]

    def validate(self, attrs):
        inst = self.instance
        number = attrs.get("whatsapp_number", inst.whatsapp_number if inst else "")
        opt_in = attrs.get("whatsapp_opt_in", inst.whatsapp_opt_in if inst else False)
        if opt_in and not number:
            raise serializers.ValidationError({"whatsapp_number": "A number is required to opt in to WhatsApp."})
        return attrs

    def update(self, instance, validated):
        if "whatsapp_opt_in" in validated and validated["whatsapp_opt_in"] != instance.whatsapp_opt_in:
            instance.whatsapp_opted_in_at = timezone.now() if validated["whatsapp_opt_in"] else None
        return super().update(instance, validated)


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "profile"]

    def get_profile(self, user):
        profile = getattr(user, "profile", None)
        return ProfileSerializer(profile).data if profile else None


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField(validators=[unique_email])
    password = serializers.CharField(write_only=True, validators=[strong_password])
    name = serializers.CharField(required=False, allow_blank=True, max_length=150, default="")
    whatsapp_number = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp_opt_in = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_whatsapp_number(self, value):
        return whatsapp_number(value)

    def validate(self, attrs):
        if attrs["whatsapp_opt_in"] and not attrs["whatsapp_number"]:
            raise serializers.ValidationError({"whatsapp_number": "A number is required to opt in to WhatsApp."})
        return attrs

    @transaction.atomic
    def create(self, v):
        # role is never read from input: public signup creates customers only (FR-AUTH-01)
        user = User.objects.create_user(v["email"], v["password"], name=v["name"], role=Role.CUSTOMER)
        CustomerProfile.objects.create(
            user=user,
            whatsapp_number=v["whatsapp_number"],
            whatsapp_opt_in=v["whatsapp_opt_in"],
            whatsapp_opted_in_at=timezone.now() if v["whatsapp_opt_in"] else None,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()  # CharField on purpose: seeded demo logins like admin@demo are not RFC-valid emails
    password = serializers.CharField()


class MeNameSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=150)


class StaffSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(validators=[unique_email])
    password = serializers.CharField(write_only=True, validators=[strong_password])
    role = serializers.ChoiceField(choices=[Role.STAFF, Role.ADMIN], default=Role.STAFF)

    class Meta:
        model = User
        fields = ["id", "email", "name", "role", "password", "is_active", "created_at"]
        read_only_fields = ["is_active", "created_at"]

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, v):
        return User.objects.create_user(v["email"], v["password"], name=v.get("name", ""), role=v["role"])


class ResetRequestSerializer(serializers.Serializer):
    email = serializers.CharField()


class ResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[strong_password])
