"""Quick demo sign-in: gated by DEMO_LOGIN_ENABLED, never touches real accounts or the Firebase path."""
import pytest
from rest_framework.test import APIClient

from apps.core.accounts import demo
from apps.core.accounts.models import Role, User
from apps.core.billing.models import Invoice
from apps.core.subscriptions.models import Subscription
from tests.conftest import mk_user

URL = "/api/auth/demo/"


def test_disabled_by_default_flag(db, settings):
    settings.DEMO_LOGIN_ENABLED = False
    assert APIClient().post(URL, {"role": "admin"}, format="json").status_code == 404
    assert not User.objects.filter(email="admin1@gmail.com").exists()


@pytest.mark.parametrize("key,email,role", [("user", "user1@gmail.com", "customer"), ("staff", "staff1@gmail.com", "staff"), ("admin", "admin1@gmail.com", "admin")])
def test_each_role_logs_in(db, settings, key, email, role):
    settings.DEMO_LOGIN_ENABLED = True
    c = APIClient()
    r = c.post(URL, {"role": key}, format="json")
    assert r.status_code == 200 and r.data["email"] == email and r.data["role"] == role
    assert c.get("/api/auth/me/").data["email"] == email  # a real session cookie, same as any login


def test_unknown_role_rejected(db, settings):
    settings.DEMO_LOGIN_ENABLED = True
    assert APIClient().post(URL, {"role": "root"}, format="json").status_code == 400


def test_demo_customer_gets_sample_data_once(db, settings):
    settings.DEMO_LOGIN_ENABLED = True
    other = mk_user("real@shop.com", Role.CUSTOMER)
    for _ in range(2):
        APIClient().post(URL, {"role": "user"}, format="json")
    user = User.objects.get(email="user1@gmail.com")
    assert Subscription.objects.filter(customer=user).count() == 2  # idempotent: second click adds nothing
    invoices = Invoice.objects.filter(customer=user)
    assert invoices.count() >= 2 and invoices.filter(status="paid").exists()
    assert not Invoice.objects.filter(customer=other).exists()  # no one else was billed


def test_never_hands_out_a_real_account(db, settings):
    settings.DEMO_LOGIN_ENABLED = True
    real = User.objects.create_user("admin1@gmail.com", "Other@Passw0rd!", role=Role.CUSTOMER)  # same email, a real person
    r = APIClient().post(URL, {"role": "admin"}, format="json")
    assert r.status_code == 409
    real.refresh_from_db()
    assert real.role == Role.CUSTOMER and not real.is_superuser
    assert demo.DEMO_PASSWORD  # sanity: the shared password constant exists
