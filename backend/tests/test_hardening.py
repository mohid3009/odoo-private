"""Phase 9 hardening: production settings guard, security headers, JSON errors for the API."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client, RequestFactory

from config.urls import server_error

BACKEND = Path(__file__).resolve().parent.parent


def boot(**env):
    """Import the settings in a fresh interpreter with the given environment; returns (exit code, stderr)."""
    e = {k: v for k, v in os.environ.items() if k not in ("DJANGO_SECRET_KEY", "DEBUG")}
    e.update(env, DJANGO_SETTINGS_MODULE="config.settings")
    r = subprocess.run([sys.executable, "-c", "import django; django.setup()"], cwd=BACKEND, env=e, capture_output=True, text=True)
    return r.returncode, r.stderr


def test_production_refuses_the_dev_secret_key():
    code, err = boot(DEBUG="false")
    assert code != 0 and "DJANGO_SECRET_KEY" in err
    assert boot(DEBUG="false", DJANGO_SECRET_KEY="x" * 50)[0] == 0
    assert boot(DEBUG="true")[0] == 0   # dev keeps working with no setup


@pytest.mark.django_db
def test_security_headers():
    r = Client().get("/api/healthz")
    assert r["X-Frame-Options"] == "DENY"
    assert r["X-Content-Type-Options"] == "nosniff"
    assert r["Referrer-Policy"] == "same-origin"


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/nope/", "/api/", "/api/invoices/1/nope/"])
def test_unknown_api_paths_are_json_404(url):
    r = Client().get(url)
    assert r.status_code == 404 and r["Content-Type"] == "application/json" and r.json() == {"detail": "Not found."}


@pytest.mark.django_db
def test_slashless_api_url_still_redirects():
    r = Client().get("/api/plans")
    assert r.status_code == 301 and r["Location"] == "/api/plans/"


def test_server_error_is_json_for_the_api_and_leaks_nothing():
    api = server_error(RequestFactory().get("/api/invoices/"))
    assert api.status_code == 500 and "Traceback" not in json.loads(api.content)["detail"]
    page = server_error(RequestFactory().get("/dashboard"))
    assert page.status_code == 500 and b"<h1>" in page.content
