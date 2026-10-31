from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower

from .scoping import scoped_manager


class Role(models.TextChoices):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("email is required")
        user = self.model(email=email.strip().lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.update(role=Role.ADMIN, is_superuser=True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)  # Django requires this; the Lower() constraint adds case-insensitivity
    name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="uniq_user_email_ci")]

    @property
    def is_staff(self):  # Django admin site access only; app roles use `role`
        return self.is_superuser

    def __str__(self):
        return self.email


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    company_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    odoo_partner_id = models.PositiveIntegerField(null=True, blank=True)
    odoo_sync_status = models.CharField(max_length=10, default="skipped")
    whatsapp_number = models.CharField(max_length=20, blank=True)  # E.164, normalised by validators.normalize_whatsapp
    whatsapp_opt_in = models.BooleanField(default=False)
    whatsapp_opted_in_at = models.DateTimeField(null=True, blank=True)
    email_notifications = models.BooleanField(default=True)

    objects = scoped_manager("user")

    def __str__(self):
        return f"profile<{self.user.email}>"
