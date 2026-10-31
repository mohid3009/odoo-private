import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.password_validation import validate_password
from django.core import mail
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.core.accounts.models import CustomerProfile, Role

User = get_user_model()
GOOD = "Strong@Pass1"
pytestmark = pytest.mark.django_db


def make(email, role, pw=GOOD):
    u = User.objects.create_user(email, pw, role=role, name=email.split("@")[0])
    if role == Role.CUSTOMER:
        CustomerProfile.objects.create(user=u)
    return u


def as_user(user):
    c = APIClient()
    c.force_login(user)
    return c


def signup(c, **over):
    body = {"email": "new@shop.com", "password": GOOD, "name": "New"} | over
    return c.post("/api/auth/signup/", body, format="json")


# --- password policy (FR-AUTH-03) -------------------------------------------------

@pytest.mark.parametrize("pw", ["Strong@Pass1", "Abcdefg#1x", "aB!aaaaaa"])
def test_valid_passwords(pw):
    validate_password(pw)


@pytest.mark.parametrize(
    "pw",
    ["Short@1A", "alllower@123", "ALLUPPER@123", "NoSpecial123", "", "Aa!"],
    ids=["exactly-8-chars", "no-upper", "no-lower", "no-special", "empty", "too-short"],
)
def test_invalid_passwords(pw):
    with pytest.raises(ValidationError):
        validate_password(pw)


# --- signup -----------------------------------------------------------------------

def test_signup_creates_customer_and_ignores_role():
    r = signup(APIClient(), role="admin")
    assert r.status_code == 201
    assert r.json()["role"] == "customer"
    u = User.objects.get(email="new@shop.com")
    assert u.role == Role.CUSTOMER and u.check_password(GOOD) and u.profile


def test_signup_weak_password_rejected():
    r = signup(APIClient(), password="weakpass")
    assert r.status_code == 400 and "password" in r.json()


def test_duplicate_email_in_other_case_rejected():
    assert signup(APIClient(), email="Dup@Shop.com").status_code == 201
    r = signup(APIClient(), email="DUP@shop.COM")
    assert r.status_code == 400 and "email" in r.json()
    assert User.objects.count() == 1


def test_signup_whatsapp_normalised_and_consent():
    r = signup(APIClient(), whatsapp_number="98765 43210", whatsapp_opt_in=True)
    p = r.json()["profile"]
    assert r.status_code == 201 and p["whatsapp_number"] == "+919876543210" and p["whatsapp_opt_in"] is True
    assert p["whatsapp_opted_in_at"]


@pytest.mark.parametrize("extra", [{"whatsapp_opt_in": True}, {"whatsapp_number": "12345"}])
def test_signup_whatsapp_validation(extra):
    assert signup(APIClient(), **extra).status_code == 400


# --- login / logout / me ----------------------------------------------------------

def test_login_me_logout():
    make("u@shop.com", Role.CUSTOMER)
    c = APIClient()
    assert c.get("/api/auth/me/").status_code == 403
    r = c.post("/api/auth/login/", {"email": "U@Shop.com", "password": GOOD}, format="json")  # case-insensitive
    assert r.status_code == 200 and r.json()["email"] == "u@shop.com"
    assert c.get("/api/auth/me/").json()["role"] == "customer"
    assert c.post("/api/auth/logout/").status_code == 204
    assert c.get("/api/auth/me/").status_code == 403


def test_bad_login_is_generic():
    make("u@shop.com", Role.CUSTOMER)
    a = APIClient().post("/api/auth/login/", {"email": "u@shop.com", "password": "nope"}, format="json")
    b = APIClient().post("/api/auth/login/", {"email": "ghost@shop.com", "password": "nope"}, format="json")
    assert a.status_code == b.status_code == 400 and a.json() == b.json()


def test_seeded_demo_style_email_can_log_in():
    make("admin@demo", Role.ADMIN)
    r = APIClient().post("/api/auth/login/", {"email": "admin@demo", "password": GOOD}, format="json")
    assert r.status_code == 200


def test_csrf_enforced_on_login():
    make("u@shop.com", Role.CUSTOMER)
    c = APIClient(enforce_csrf_checks=True)
    body = {"email": "u@shop.com", "password": GOOD}
    assert c.post("/api/auth/login/", body, format="json").status_code == 403
    c.get("/api/auth/csrf/")
    token = c.cookies["csrftoken"].value
    assert c.post("/api/auth/login/", body, format="json", HTTP_X_CSRFTOKEN=token).status_code == 200


def test_me_patch_updates_name_and_profile():
    c = as_user(make("u@shop.com", Role.CUSTOMER))
    r = c.patch("/api/auth/me/", {"name": "Uma", "profile": {"phone": "123", "whatsapp_number": "9876543210", "whatsapp_opt_in": True}}, format="json")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Uma" and d["profile"]["phone"] == "123" and d["profile"]["whatsapp_number"] == "+919876543210"
    off = c.patch("/api/auth/me/", {"profile": {"whatsapp_opt_in": False}}, format="json").json()
    assert off["profile"]["whatsapp_opt_in"] is False and off["profile"]["whatsapp_opted_in_at"] is None


def test_staff_user_has_no_profile():
    r = as_user(make("s@shop.com", Role.STAFF)).get("/api/auth/me/")
    assert r.json()["profile"] is None


# --- password reset (FR-AUTH-05) --------------------------------------------------

def reset_link():
    m = re.search(r"/reset-password/([^/\s]+)/([^/\s]+)", mail.outbox[-1].body)
    return m.group(1), m.group(2)


def test_password_reset_flow():
    make("u@shop.com", Role.CUSTOMER)
    c = APIClient()
    assert c.post("/api/auth/password-reset/request/", {"email": "U@shop.com"}, format="json").status_code == 200
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["u@shop.com"]
    uid, token = reset_link()
    confirm = "/api/auth/password-reset/confirm/"

    weak = c.post(confirm, {"uid": uid, "token": token, "new_password": "weakpass"}, format="json")
    assert weak.status_code == 400 and "new_password" in weak.json()

    ok = c.post(confirm, {"uid": uid, "token": token, "new_password": "Brand@New123"}, format="json")
    assert ok.status_code == 200
    assert c.post("/api/auth/login/", {"email": "u@shop.com", "password": "Brand@New123"}, format="json").status_code == 200
    assert APIClient().post("/api/auth/login/", {"email": "u@shop.com", "password": GOOD}, format="json").status_code == 400

    reuse = c.post(confirm, {"uid": uid, "token": token, "new_password": "Other@Pass123"}, format="json")
    assert reuse.status_code == 400  # single use


def test_reset_unknown_email_same_answer_and_no_mail():
    a = APIClient().post("/api/auth/password-reset/request/", {"email": "ghost@shop.com"}, format="json")
    assert a.status_code == 200 and len(mail.outbox) == 0


def test_reset_garbage_token_rejected():
    r = APIClient().post("/api/auth/password-reset/confirm/", {"uid": "zz", "token": "bad", "new_password": GOOD}, format="json")
    assert r.status_code == 400


# --- staff creation + role matrix (FR-AUTH-06/07) ---------------------------------

def test_admin_creates_staff_who_can_log_in():
    c = as_user(make("a@shop.com", Role.ADMIN))
    r = c.post("/api/staff/", {"email": "Ops@Shop.com", "name": "Ops", "password": "Temp@Pass123"}, format="json")
    assert r.status_code == 201 and r.json()["role"] == "staff" and "password" not in r.json()
    login = APIClient().post("/api/auth/login/", {"email": "ops@shop.com", "password": "Temp@Pass123"}, format="json")
    assert login.status_code == 200 and login.json()["role"] == "staff"


def test_staff_creation_validation():
    c = as_user(make("a@shop.com", Role.ADMIN))
    base = {"email": "ops@shop.com", "password": GOOD}
    assert c.post("/api/staff/", base | {"password": "weakpass"}, format="json").status_code == 400
    assert c.post("/api/staff/", base | {"role": "customer"}, format="json").status_code == 400
    assert c.post("/api/staff/", base, format="json").status_code == 201
    assert c.post("/api/staff/", base | {"email": "OPS@shop.com"}, format="json").status_code == 400


@pytest.mark.parametrize("role,expected", [("admin", 200), ("staff", 403), ("customer", 403), (None, 403)])
def test_staff_endpoint_role_matrix(role, expected):
    c = as_user(make(f"{role}@shop.com", role)) if role else APIClient()
    assert c.get("/api/staff/").status_code == expected
    assert c.post("/api/staff/", {"email": "x@shop.com", "password": GOOD}, format="json").status_code == expected + (1 if expected == 200 else 0)


def test_staff_list_excludes_customers():
    make("a@shop.com", Role.ADMIN)
    make("s@shop.com", Role.STAFF)
    make("c@shop.com", Role.CUSTOMER)
    r = as_user(User.objects.get(email="a@shop.com")).get("/api/staff/")
    assert sorted(x["email"] for x in r.json()["results"]) == ["a@shop.com", "s@shop.com"]


# --- row-level scoping (rule 8) ---------------------------------------------------

def test_for_user_scopes_rows():
    c1, c2 = make("c1@shop.com", Role.CUSTOMER), make("c2@shop.com", Role.CUSTOMER)
    staff = make("s@shop.com", Role.STAFF)
    assert [p.user for p in CustomerProfile.objects.for_user(c1)] == [c1]
    assert CustomerProfile.objects.for_user(staff).count() == 2
    assert CustomerProfile.objects.for_user(AnonymousUser()).count() == 0
    assert not CustomerProfile.objects.for_user(c2).filter(user=c1).exists()


# --- staff / admin self-registration (D-044) ---------------------------------------------

@pytest.mark.parametrize("kind,setting", [("staff", "STAFF_SIGNUP_CODE"), ("admin", "ADMIN_SIGNUP_CODE")])
def test_staff_and_admin_signup_need_the_right_code(settings, kind, setting):
    setattr(settings, setting, "s3cret-code")
    c = APIClient()
    assert signup(c, account_type=kind).status_code == 400  # no code
    r = signup(c, account_type=kind, signup_code="wrong")
    assert r.status_code == 400 and "signup_code" in r.json() and not User.objects.filter(email="new@shop.com").exists()
    r = signup(c, account_type=kind, signup_code="s3cret-code")
    assert r.status_code == 201 and r.json()["role"] == kind and r.json()["profile"] is None
    u = User.objects.get(email="new@shop.com")
    assert u.role == kind and u.is_superuser == (kind == "admin") and not hasattr(u, "profile")


def test_a_staff_code_does_not_open_admin_signup(settings):
    settings.STAFF_SIGNUP_CODE, settings.ADMIN_SIGNUP_CODE = "staff-code", "admin-code"
    assert signup(APIClient(), account_type="admin", signup_code="staff-code").status_code == 400


@pytest.mark.parametrize("kind", ["staff", "admin"])
def test_staff_admin_signup_is_disabled_when_no_code_is_configured(settings, kind):
    settings.STAFF_SIGNUP_CODE = settings.ADMIN_SIGNUP_CODE = ""
    r = signup(APIClient(), account_type=kind, signup_code="")
    assert r.status_code == 400 and "account_type" in r.json() and User.objects.count() == 0


def test_customer_signup_ignores_a_code_and_unknown_types_are_rejected(settings):
    settings.ADMIN_SIGNUP_CODE = "admin-code"
    r = signup(APIClient(), account_type="customer", signup_code="admin-code")
    assert r.status_code == 201 and r.json()["role"] == "customer"
    assert signup(APIClient(), email="x@shop.com", account_type="superhero").status_code == 400
