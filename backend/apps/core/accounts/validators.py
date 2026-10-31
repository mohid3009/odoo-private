import re

from django.core.exceptions import ValidationError


class PasswordRuleValidator:
    """D-006: length >= 9 with an uppercase, a lowercase and a special character."""

    def validate(self, password, user=None):
        missing = []
        if len(password) < 9:
            missing.append("at least 9 characters")
        if not re.search(r"[A-Z]", password):
            missing.append("an uppercase letter")
        if not re.search(r"[a-z]", password):
            missing.append("a lowercase letter")
        if not re.search(r"[^A-Za-z0-9\s]", password):
            missing.append("a special character")
        if missing:
            raise ValidationError("Password needs " + ", ".join(missing) + ".", code="password_rules")

    def get_help_text(self):
        return "At least 9 characters with an uppercase letter, a lowercase letter and a special character."


def normalize_whatsapp(raw):
    """E.164 or '' (D-022). A bare 10-digit number is assumed to be Indian (+91)."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if not s:
        return ""
    if re.fullmatch(r"\d{10}", s):
        s = "+91" + s
    if not re.fullmatch(r"\+[1-9]\d{7,14}", s):
        raise ValidationError("Enter a valid WhatsApp number, e.g. +919876543210 or a 10-digit Indian number.")
    return s
