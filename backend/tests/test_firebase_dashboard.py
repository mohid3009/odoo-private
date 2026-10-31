"""Firebase login (token verification stubbed: no network) and the real dashboard summary."""
import pytest
from rest_framework.test import APIClient

from apps.core.accounts import firebase
from apps.core.accounts.models import Role, User
from tests.conftest import api_for, mk_user

URL = "/api/auth/firebase/"


@pytest.fixture
def token(monkeypatch):
    """token("a@b.com") -> id_token string; verify() returns the claims registered for it."""
    claims = {}

    def verify(t):
        if t not in claims:
            raise ValueError("bad token")
        return claims[t]

    monkeypatch.setattr(firebase, "verify", verify)

    def make(email, verified=True, name="Gia Google"):
        claims[email] = {"email": email, "email_verified": verified, "name": name}
        return email

    return make


def test_new_google_user_becomes_customer_with_session(db, token):
    c = APIClient()
    r = c.post(URL, {"id_token": token("New.User@Gmail.com")}, format="json")
    assert r.status_code == 200 and r.data["role"] == "customer" and r.data["email"] == "new.user@gmail.com"
    assert c.get("/api/auth/me/").status_code == 200
    assert not User.objects.get(email="new.user@gmail.com").has_usable_password()


def test_existing_staff_keeps_role_and_cannot_self_promote(db, token):
    mk_user("ops@shop.com", Role.STAFF)
    r = APIClient().post(URL, {"id_token": token("ops@shop.com"), "account_type": "admin", "signup_code": "x"}, format="json")
    assert r.status_code == 400  # a wrong code is still rejected, even for existing users
    r = APIClient().post(URL, {"id_token": token("ops@shop.com")}, format="json")
    assert r.status_code == 200 and r.data["role"] == "staff"


def test_staff_signup_needs_server_code(db, token, settings):
    settings.STAFF_SIGNUP_CODE = "s3cret"
    bad = APIClient().post(URL, {"id_token": token("s1@x.com"), "account_type": "staff", "signup_code": "nope"}, format="json")
    assert bad.status_code == 400 and not User.objects.filter(email="s1@x.com").exists()
    ok = APIClient().post(URL, {"id_token": token("s2@x.com"), "account_type": "staff", "signup_code": "s3cret"}, format="json")
    assert ok.status_code == 200 and ok.data["role"] == "staff"


def test_unverified_or_bad_token_is_refused(db, token):
    assert APIClient().post(URL, {"id_token": token("u@x.com", verified=False)}, format="json").status_code == 403
    assert APIClient().post(URL, {"id_token": "garbage"}, format="json").status_code == 401
    assert not User.objects.filter(email="u@x.com").exists()


def test_disabled_account_refused(db, token):
    u = mk_user("off@shop.com", Role.STAFF)
    u.is_active = False
    u.save()
    assert APIClient().post(URL, {"id_token": token("off@shop.com")}, format="json").status_code == 403


def test_dashboard_summary_is_scoped_and_empty_safe(db):
    staff = mk_user("st@shop.com", Role.STAFF)
    r = api_for(staff).get("/api/dashboard/summary/")
    assert r.status_code == 200
    assert r.data["kpis"]["revenue_collected"] == "0.00" and len(r.data["by_month"]) == 6 and r.data["recent_payments"] == []
    assert APIClient().get("/api/dashboard/summary/").status_code in (401, 403)


def test_dashboard_counts_real_subscriptions(make_sub, cust, staff):
    make_sub("2026-01-01")
    other = mk_user("c2@shop.com", Role.CUSTOMER)
    make_sub("2026-01-01", customer=other)
    assert api_for(staff).get("/api/dashboard/summary/").data["kpis"]["active_subscriptions"] == 2
    assert api_for(cust).get("/api/dashboard/summary/").data["kpis"]["active_subscriptions"] == 1
