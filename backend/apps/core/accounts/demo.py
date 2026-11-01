"""Demo accounts behind the quick sign-in buttons (only when DEMO_LOGIN_ENABLED). Separate from real auth: Firebase login is untouched."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from .models import CustomerProfile, Role, User

DEMO_PASSWORD = "Demo@Brightloop1"  # passes the app's password rule; also works for local password login in dev
DEMO = {
    "user": ("user1@gmail.com", "Demo User", Role.CUSTOMER),
    "staff": ("staff1@gmail.com", "Demo Staff", Role.STAFF),
    "admin": ("admin1@gmail.com", "Demo Admin", Role.ADMIN),
}


def _account(key):
    """The demo user, created on first use. None if that email already belongs to a real account (never hand those out)."""
    email, name, role = DEMO[key]
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(email, DEMO_PASSWORD, name=name, role=role, is_superuser=role == Role.ADMIN)
    elif not user.check_password(DEMO_PASSWORD):  # real (Firebase) accounts have no usable password
        return None
    return user


def ensure(key):
    user = _account(key)
    if user is not None and user.role == Role.CUSTOMER:
        CustomerProfile.objects.get_or_create(user=user, defaults={"company_name": "Demo Traders"})
        _sample_data(user)
    return user


@transaction.atomic
def _sample_data(customer):
    """A few subscriptions, invoices and payments for the demo customer only. Bills these subscriptions one by one,
    never run_billing(), so real customers are never invoiced by a demo click."""
    from apps.core.billing import engine, services as billing
    from apps.core.billing.models import Invoice
    from apps.core.catalog.models import PaymentTerm, Plan, Product, Tax
    from apps.core.subscriptions.models import Subscription, SubscriptionLine
    from apps.core.subscriptions.services import next_number
    from apps.finance.payments import services as pay

    if Subscription.objects.filter(customer=customer).exists():
        return
    admin = _account("admin")
    today = timezone.localdate()
    gst, _ = Tax.objects.get_or_create(name="GST 18%", defaults={"rate": 18})
    term, _ = PaymentTerm.objects.get_or_create(name="Net 15", defaults={"days": 15, "is_default": True})
    product, made = Product.objects.get_or_create(name="Demo CRM Suite", defaults={"type": "software", "sales_price": Decimal("1560.00")})
    if made:
        product.taxes.add(gst)
    monthly, _ = Plan.objects.get_or_create(name="Demo Monthly", defaults={"product": product, "price": Decimal("1560.00"), "billing_period": "monthly", "min_quantity": 1, "allow_pause": True, "allow_renew": True})
    yearly, _ = Plan.objects.get_or_create(name="Demo Yearly", defaults={"product": product, "price": Decimal("15600.00"), "billing_period": "yearly", "min_quantity": 1, "allow_renew": True})

    def subscription(plan, qty, days_ago, status):
        start = today - timedelta(days=days_ago)
        sub = Subscription.objects.create(
            number=next_number(), customer=customer, plan=plan, start_date=start, payment_term=term, status=status,
            next_invoice_date=start if status == "active" else None,
        )
        line = SubscriptionLine.objects.create(subscription=sub, product=product, quantity=qty, unit_price=product.sales_price,
                                               amount=product.sales_price * qty, description=product.name)
        line.taxes.add(gst)
        return sub

    active = subscription(monthly, 3, 70, "active")
    subscription(yearly, 1, -7, "quotation")
    engine.bill_subscription(active.pk, today, SimpleNamespace(created_count=0, skipped_count=0))
    invoices = list(Invoice.objects.filter(subscription=active).order_by("id"))
    for inv in invoices[:-1]:  # the newest stays a draft
        billing.confirm(inv, admin)
    for inv, share in zip(invoices[:2], (Decimal(1), Decimal("0.4"))):  # oldest paid in full, next part paid, the rest unpaid
        inv.refresh_from_db()
        pay.record_payment(inv, admin, {"amount": (inv.amount_due * share).quantize(Decimal("0.01")), "method": "upi", "status": "completed"})
