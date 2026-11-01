"""POST /api/auth/check-code/ backs the sign-up code verify animation: same answer sign-up itself would give."""
import pytest
from rest_framework.test import APIClient

URL = "/api/auth/check-code/"


@pytest.fixture(autouse=True)
def codes(settings):
    settings.STAFF_SIGNUP_CODE, settings.ADMIN_SIGNUP_CODE = "246813", "123456"


@pytest.mark.parametrize("kind,code,ok", [
    ("staff", "246813", True), ("admin", "123456", True),
    ("staff", "123456", False), ("admin", "246813", False), ("admin", "000000", False),
    ("customer", "123456", False), ("root", "123456", False), ("admin", "", False),
])
def test_check_code(db, kind, code, ok):
    r = APIClient().post(URL, {"account_type": kind, "code": code}, format="json")
    assert r.status_code == 200 and r.data == {"valid": ok}


def test_disabled_type_never_valid(db, settings):
    settings.ADMIN_SIGNUP_CODE = ""  # empty = that account type is off, even for an empty guess
    assert APIClient().post(URL, {"account_type": "admin", "code": ""}, format="json").data == {"valid": False}
