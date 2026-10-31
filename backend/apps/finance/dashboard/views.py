"""Finance dashboard (S7): one endpoint, aggregate queries only (no per-row Python work). Contract: docs/API.md Phase 8."""
from datetime import date
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.accounts.permissions import IsStaffOrAdmin
from apps.core.billing.models import Invoice
from apps.core.catalog.models import Plan
from apps.core.subscriptions.models import Subscription, SubscriptionLine
from apps.finance.payments.models import Payment
from config.pagination import StandardPagination

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
# D-017: multiply a period's amount by this to get a monthly amount
TO_MONTHLY = {"daily": Decimal(30), "weekly": Decimal(52) / 12, "monthly": Decimal(1), "yearly": Decimal(1) / 12}


def money(v):
    return str((v or ZERO).quantize(CENT))


def months_back(d, n):
    """First day of the month `n` months before `d` (negative n = forward)."""
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    return date(y, m + 1, 1)


class FilterSerializer(serializers.Serializer):
    from_ = serializers.DateField(required=False)
    to = serializers.DateField(required=False)
    customer = serializers.IntegerField(required=False, min_value=1)
    plan = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=Subscription.Status.choices, required=False)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")  # `from` is a Python keyword
        return fields

    def validate(self, data):
        data.setdefault("to", timezone.localdate())
        data.setdefault("from", months_back(data["to"], 11))
        if data["from"] > data["to"]:
            raise serializers.ValidationError({"from": "Must be on or before `to`."})
        return data


def scope(qs, f, prefix):
    """Apply the customer / plan / subscription-status filters through `prefix`, the lookup path to the Subscription."""
    p = f"{prefix}__" if prefix else ""
    for key in ("customer", "plan", "status"):
        if key in f:
            qs = qs.filter(**{p + key: f[key]})
    return qs


def summary(f, today):
    subs = scope(Subscription.objects.all(), f, "")
    invoices = scope(Invoice.objects.all(), f, "subscription")
    payments = scope(Payment.objects.filter(status=Payment.Status.COMPLETED), f, "invoice__subscription")
    in_range = dict(invoice_date__gte=f["from"], invoice_date__lte=f["to"])
    paid_range = dict(payment_date__gte=f["from"], payment_date__lte=f["to"])
    issued = invoices.filter(status__in=[Invoice.Status.CONFIRMED, Invoice.Status.PAID], **in_range)
    paid = payments.filter(**paid_range)
    overdue_q = Q(status=Invoice.Status.CONFIRMED, amount_due__gt=0, due_date__lt=today)  # D-013

    # MRR: line amounts of active subscriptions summed per (plan, period) in SQL, normalised in Decimal here
    mrr_by_plan, mrr = {}, ZERO
    lines = scope(SubscriptionLine.objects.filter(subscription__status=Subscription.Status.ACTIVE), f, "subscription")
    for r in lines.values("subscription__plan", "subscription__plan__billing_period").annotate(s=Sum("amount")):
        m = r["s"] * TO_MONTHLY[r["subscription__plan__billing_period"]]
        mrr_by_plan[r["subscription__plan"]] = mrr_by_plan.get(r["subscription__plan"], ZERO) + m
        mrr += m
    mrr = mrr.quantize(CENT)

    inv = invoices.aggregate(
        outstanding=Sum("amount_due", filter=Q(status=Invoice.Status.CONFIRMED)),
        overdue_count=Count("id", filter=overdue_q),
        overdue_amount=Sum("amount_due", filter=overdue_q),
    )
    kpis = {
        "active_subscriptions": subs.filter(status=Subscription.Status.ACTIVE).count(),
        "mrr": money(mrr),
        "arr": money(mrr * 12),
        "revenue_collected": money(paid.aggregate(s=Sum("amount"))["s"]),
        "invoiced": money(issued.aggregate(s=Sum("total"))["s"]),
        "outstanding": money(inv["outstanding"]),
        "overdue_count": inv["overdue_count"],
        "overdue_amount": money(inv["overdue_amount"]),
    }

    # by plan: one grouped query per measure, merged here (plans are few)
    plans = {}

    def row(pid):
        return plans.setdefault(pid, {"plan_id": pid, "active_subscriptions": 0, "mrr": ZERO, "invoiced": ZERO, "collected": ZERO})

    for r in subs.filter(status=Subscription.Status.ACTIVE).values("plan").annotate(n=Count("id")):
        row(r["plan"])["active_subscriptions"] = r["n"]
    for pid, m in mrr_by_plan.items():
        row(pid)["mrr"] = m
    for r in issued.values("subscription__plan").annotate(s=Sum("total")):
        row(r["subscription__plan"])["invoiced"] = r["s"]
    for r in paid.values("invoice__subscription__plan").annotate(s=Sum("amount")):
        row(r["invoice__subscription__plan"])["collected"] = r["s"]
    names = {p.id: p for p in Plan.objects.filter(id__in=plans).only("id", "name", "billing_period")}
    by_plan = [
        {**r, "plan_name": names[r["plan_id"]].name, "billing_period": names[r["plan_id"]].billing_period,
         "mrr": money(r["mrr"]), "invoiced": money(r["invoiced"]), "collected": money(r["collected"])}
        for r in sorted(plans.values(), key=lambda r: (names[r["plan_id"]].name, r["plan_id"]))
    ]

    # by month: every month in range, zeros included
    months, d = {}, date(f["from"].year, f["from"].month, 1)
    while d <= f["to"]:
        months[d] = {"month": d.strftime("%Y-%m"), "invoiced": ZERO, "collected": ZERO}
        d = months_back(d, -1)
    for r in issued.annotate(m=TruncMonth("invoice_date")).values("m").annotate(s=Sum("total")):
        months[r["m"]]["invoiced"] = r["s"]
    for r in paid.annotate(m=TruncMonth("payment_date")).values("m").annotate(s=Sum("amount")):
        months[r["m"]]["collected"] = r["s"]
    by_month = [{**m, "invoiced": money(m["invoiced"]), "collected": money(m["collected"])} for m in months.values()]

    return kpis, by_plan, by_month, invoices.filter(overdue_q)


class OverdueSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source="customer.email")
    subscription_number = serializers.CharField(source="subscription.number")
    plan_name = serializers.CharField(source="subscription.plan.name")
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = ["id", "number", "customer_email", "subscription_number", "plan_name", "due_date", "days_overdue", "amount_due"]

    def get_days_overdue(self, obj):
        return (self.context["today"] - obj.due_date).days


class SummaryView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def get(self, request):
        s = FilterSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        f, today = s.validated_data, timezone.localdate()
        kpis, by_plan, by_month, overdue = summary(f, today)

        overdue = overdue.select_related("customer", "subscription__plan").order_by(F("due_date").asc(), "id")
        pager = StandardPagination()
        page = pager.paginate_queryset(overdue, request, view=self)
        return Response({
            "filters": {"from": f["from"], "to": f["to"], "customer": f.get("customer"), "plan": f.get("plan"), "status": f.get("status")},
            "kpis": kpis,
            "by_plan": by_plan,
            "by_month": by_month,
            "overdue": pager.get_paginated_response(OverdueSerializer(page, many=True, context={"today": today}).data).data,
        })
