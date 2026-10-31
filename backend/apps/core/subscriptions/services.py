"""Subscription lifecycle rules (docs/STATE_MACHINES.md). Views never set `status` directly."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from .models import Counter, StatusLog, Subscription

ZERO = Decimal("0.00")
S = Subscription.Status
DEFAULT_VALIDITY_DAYS = 30

# from -> allowed targets (who/guards are applied in transition())
TRANSITIONS = {
    S.DRAFT: {S.QUOTATION, S.CLOSED},
    S.QUOTATION: {S.DRAFT, S.CONFIRMED, S.CLOSED},
    S.CONFIRMED: {S.ACTIVE, S.CLOSED},
    S.ACTIVE: {S.PAUSED, S.CLOSED},
    S.PAUSED: {S.ACTIVE, S.CLOSED},
}


class TransitionError(APIException):
    """HTTP 409 with a machine-readable code: illegal_transition | guard_failed | not_editable."""

    status_code = 409

    def __init__(self, code, detail):
        super().__init__(detail)
        self.detail = {"detail": detail, "code": code}


def q2(value):
    return Decimal(value).quantize(ZERO, rounding=ROUND_HALF_UP)


def is_staff(user):
    return bool(user) and user.role in ("admin", "staff")


# --- numbering ---------------------------------------------------------------------------

def next_sequence(name, prefix):
    """PREFIX000001, PREFIX000002, ... per named counter; safe under concurrency (row lock on the counter)."""
    for _ in range(3):  # the first call races to create the counter row; the loser retries
        try:
            with transaction.atomic():
                counter, _ = Counter.objects.select_for_update().get_or_create(name=name)
                counter.value += 1
                counter.save(update_fields=["value"])
                return f"{prefix}{counter.value:06d}"
        except IntegrityError:
            continue
    raise RuntimeError(f"could not allocate a {name} number")


def next_number():
    """SUB-000001, SUB-000002, ..."""
    return next_sequence("subscription", "SUB-")


# --- pricing (D-001) ---------------------------------------------------------------------

def line_price(plan, product, variant=None):
    """Plan's primary product costs plan.price + extra; anything else product.sales_price + extra."""
    extra = variant.extra_price if variant else ZERO
    base = plan.price if product.pk == plan.product_id else product.sales_price
    return q2(base + extra)


def primary_qty_problem(plan, lines):
    """FR-SUB-03: the plan's primary product must meet plan.min_quantity. `lines` = iterable of (product_id, qty)."""
    for product_id, qty in lines:
        if product_id == plan.product_id and qty < plan.min_quantity:
            return f"Minimum quantity for {plan.product.name} on plan '{plan.name}' is {plan.min_quantity}."
    return None


# --- state machine -----------------------------------------------------------------------

def actions_for(sub, user):
    """What `user` may attempt now (role + plan flags only; data guards run in transition())."""
    if not is_staff(user):
        return []
    plan, out = sub.plan, []
    for to in sorted(TRANSITIONS.get(sub.status, ())):
        if to == S.PAUSED and not plan.allow_pause:
            continue
        if to == S.CLOSED and sub.status in (S.ACTIVE, S.PAUSED) and not (plan.allow_early_close or user.role == "admin"):
            continue
        out.append(to.value)
    if sub.status == S.ACTIVE and sub.expiry_date and plan.allow_renew:
        out.append("renew")
    return out


def _guard(ok, message):
    if not ok:
        raise TransitionError("guard_failed", message)


@transaction.atomic
def transition(sub, to, user=None, today=None):
    """Move `sub` to status `to`. `user=None` means the system (activate_due, billing auto-close)."""
    today = today or timezone.localdate()
    # of=("self",): lock only the subscription row. Without it PostgreSQL also locks the joined rows and refuses outright
    # when a joined relation is nullable ("FOR UPDATE cannot be applied to the nullable side of an outer join": `template`).
    sub = Subscription.objects.select_for_update(of=("self",)).select_related("plan__product", "template").get(pk=sub.pk)
    frm, plan = sub.status, sub.plan
    if user is not None and not is_staff(user):
        raise TransitionError("illegal_transition", "Only staff or admin can change a subscription's status.")
    if to not in TRANSITIONS.get(frm, ()):
        raise TransitionError("illegal_transition", f"A subscription cannot move from {frm} to {to}.")

    if to == S.QUOTATION:
        lines = [(l.product_id, l.quantity) for l in sub.lines.all()]
        _guard(lines, "Add at least one line before sending a quotation.")
        problem = primary_qty_problem(plan, lines)
        _guard(problem is None, problem)
        _guard(plan.is_available_on(sub.start_date), f"Plan '{plan.name}' is not available on {sub.start_date}.")
        days = sub.template.validity_days if sub.template else DEFAULT_VALIDITY_DAYS
        sub.quotation_valid_until = today + timedelta(days=days)
    elif to == S.DRAFT:
        sub.quotation_valid_until = None
    elif to == S.CONFIRMED:
        _guard(not (sub.quotation_valid_until and sub.quotation_valid_until < today),
               f"The quotation expired on {sub.quotation_valid_until}. Move it back to draft and re-send it.")
        sub.next_invoice_date = sub.start_date
    elif to == S.ACTIVE:
        if frm == S.CONFIRMED:
            _guard(sub.start_date <= today, f"This subscription starts on {sub.start_date}; it cannot be activated earlier.")
        else:  # resume from pause: never back-bill the paused period (D-014)
            sub.next_invoice_date = max(sub.next_invoice_date or today, today)
    elif to == S.PAUSED:
        _guard(plan.allow_pause, f"Plan '{plan.name}' does not allow pausing.")
    elif to == S.CLOSED and frm in (S.ACTIVE, S.PAUSED):
        _guard(plan.allow_early_close or (user is None or user.role == "admin"),
               f"Plan '{plan.name}' does not allow early close (an admin can override).")

    sub.status = to
    sub.save()
    StatusLog.objects.create(subscription=sub, from_status=frm, to_status=to, by_user=user)
    # TODO(phase 4/7): notify(QUOTATION_READY) on quotation, notify(SUBSCRIPTION_ACTIVATED) on active.
    return sub


@transaction.atomic
def renew(sub, user):
    """D-014: extend the expiry by the original term (expiry - start). Needs plan.allow_renew."""
    sub = Subscription.objects.select_for_update(of=("self",)).select_related("plan").get(pk=sub.pk)
    if not is_staff(user):
        raise TransitionError("illegal_transition", "Only staff or admin can renew a subscription.")
    _guard(sub.status == S.ACTIVE, "Only an active subscription can be renewed.")
    _guard(sub.expiry_date is not None, "This subscription has no expiry date to extend.")
    _guard(sub.plan.allow_renew, f"Plan '{sub.plan.name}' does not allow renewal.")
    sub.expiry_date = sub.expiry_date + (sub.expiry_date - sub.start_date)
    sub.save(update_fields=["expiry_date"])
    return sub


def activate_due(as_of=None):
    """confirmed -> active for every subscription whose start date has arrived (called by billing)."""
    as_of = as_of or timezone.localdate()
    n = 0
    for sub in Subscription.objects.filter(status=S.CONFIRMED, start_date__lte=as_of):
        transition(sub, S.ACTIVE, None, today=as_of)
        n += 1
    return n
