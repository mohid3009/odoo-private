"""WhatsApp provider adapters (D-021, D-025). The only place that talks to Twilio; stdlib only."""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)
TWILIO_SANDBOX_FROM = "whatsapp:+14155238886"
TIMEOUT = 10


def provider():
    return settings.WHATSAPP_PROVIDER


def configured():
    if provider() == "console":
        return True
    if provider() == "twilio":
        return bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM)
    return False  # 'meta' is not built (stretch); anything else is unknown


def status():
    return {
        "provider": provider(),
        "configured": configured(),
        "sandbox": provider() == "twilio" and settings.TWILIO_WHATSAPP_FROM == TWILIO_SANDBOX_FROM,
    }


def _twilio(to, body):
    sid = settings.TWILIO_ACCOUNT_SID
    data = urllib.parse.urlencode({"To": f"whatsapp:{to}", "From": settings.TWILIO_WHATSAPP_FROM, "Body": body}).encode()
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data)
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{settings.TWILIO_AUTH_TOKEN}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.load(resp)["sid"]
    except urllib.error.HTTPError as e:  # Twilio explains itself in the JSON body (e.g. 63015: not joined to the sandbox)
        try:
            detail = json.load(e).get("message", "")
        except Exception:
            detail = ""
        raise RuntimeError(f"Twilio HTTP {e.code}: {detail}".strip()) from None


def send(to, body, ref=""):
    """Send one WhatsApp message and return the provider's message id. Raises on any failure (the caller records it)."""
    p = provider()
    if p == "console":
        log.info("[whatsapp:console] to %s: %s", to, body)
        return f"console-{ref}"
    if p == "twilio":
        if not configured():
            raise RuntimeError("Twilio is not configured (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM)")
        return _twilio(to, body)
    raise RuntimeError(f"WhatsApp provider '{p}' is not available; use WHATSAPP_PROVIDER=console or twilio")
