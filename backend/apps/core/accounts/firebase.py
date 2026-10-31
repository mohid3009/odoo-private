"""Verify a Firebase ID token (Google's public certs, no service account needed) and return its claims."""
from django.conf import settings
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token

_request = g_requests.Request()


def verify(token):
    """Claims dict, or raise ValueError (bad signature, expired, wrong project, ...)."""
    if not settings.FIREBASE_PROJECT_ID:
        raise ValueError("Firebase is not configured on this server.")
    return id_token.verify_firebase_token(token, _request, audience=settings.FIREBASE_PROJECT_ID, clock_skew_in_seconds=10)
