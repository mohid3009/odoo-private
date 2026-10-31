from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.billing.models import Invoice
from apps.core.subscriptions.models import Subscription
from apps.finance.payments.models import Payment

MONTHS = 6
ZERO = Decimal("0.00")


def money(v):
    return str((v or ZERO).quantize(Decimal("0.01")))


def month_starts(today, n):
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(today.replace(year=y, month=m, day=1))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[::-1]


class SummaryView(APIView):
    """Finance dashboard (rule 8: every queryset goes through for_user, so customers only see their own numbers)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user, today = request.user, timezone.localdate()
        subs = Subscription.objects.for_user(user)
        invoices = Invoice.objects.for_user(user)
        payments = Payment.objects.for_user(user).filter(status=Payment.Status.COMPLETED, reversed_at__isnull=True)

        issued = invoices.exclude(status=Invoice.Status.DRAFT)
        open_ = invoices.filter(status=Invoice.Status.CONFIRMED)
        overdue = open_.filter(due_date__lt=today)
        sub_counts = dict(subs.values_list("status").annotate(n=Count("id")))
        inv_counts = dict(invoices.values_list("status").annotate(n=Count("id")))
        overdue_agg = overdue.aggregate(n=Count("id"), amount=Sum("amount_due"))

        months = month_starts(today, MONTHS)
        invoiced = {r["m"]: r["s"] for r in issued.filter(invoice_date__gte=months[0])
                    .annotate(m=TruncMonth("invoice_date")).values("m").annotate(s=Sum("total")).values("m", "s")}
        collected = {r["m"]: r["s"] for r in payments.filter(payment_date__gte=months[0])
                     .annotate(m=TruncMonth("payment_date")).values("m").annotate(s=Sum("amount")).values("m", "s")}

        recent = Payment.objects.for_user(user).select_related("invoice").order_by("-created_at")[:6]
        return Response({
            "kpis": {
                "active_subscriptions": sub_counts.get("active", 0),
                "revenue_collected": money(payments.aggregate(s=Sum("amount"))["s"]),
                "outstanding": money(open_.aggregate(s=Sum("amount_due"))["s"]),
                "overdue_count": overdue_agg["n"],
                "overdue_amount": money(overdue_agg["amount"]),
            },
            "subscriptions": {k: sub_counts.get(k, 0) for k in ("active", "paused", "quotation", "confirmed", "closed")},
            "invoices": {k: inv_counts.get(k, 0) for k in ("draft", "confirmed", "paid")},
            "by_month": [
                {"month": m.strftime("%b"), "invoiced": money(invoiced.get(m)), "collected": money(collected.get(m))}
                for m in months
            ],
            "recent_payments": [
                {"id": p.id, "status": p.status, "method": p.method, "amount": money(p.amount),
                 "invoice": p.invoice.number or "Draft", "at": p.created_at.isoformat()}
                for p in recent
            ],
        })
