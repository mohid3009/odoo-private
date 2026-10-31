import django_filters
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.accounts.permissions import IsAdmin
from apps.core.accounts.validators import normalize_whatsapp
from integrations import whatsapp

from . import reminders
from .models import NotificationEvent, NotificationLog
from .serializers import (
    EventSerializer, LogSerializer, MyLogSerializer, RunRemindersSerializer, SettingsSerializer, TestSendSerializer,
)
from .services import DEFAULT_EVENTS, dispatch, get_event


class LogFilter(django_filters.FilterSet):
    event = django_filters.CharFilter(field_name="event__code")
    user = django_filters.NumberFilter(field_name="recipient_user_id")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = NotificationLog
        fields = ["channel", "status", "object_type", "object_id"]


class LogAccess(BasePermission):
    """Admin: everything. Staff: only one object's timeline (both object filters present). Customers: nothing."""

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.role == "admin":
            return True
        q = request.query_params
        return u.role == "staff" and view.action == "list" and bool(q.get("object_type") and q.get("object_id"))


class LogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LogSerializer
    permission_classes = [LogAccess]
    filterset_class = LogFilter
    ordering_fields = ["id", "created_at", "status"]

    def get_queryset(self):
        return NotificationLog.objects.select_related("event", "recipient_user")

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        row = self.get_object()
        if row.status != "failed":
            return Response(
                {"detail": f"Only a failed message can be retried (this one is {row.status}).", "code": "illegal_transition"},
                status=status.HTTP_409_CONFLICT,
            )
        NotificationLog.objects.filter(pk=row.pk).update(attempts=0, next_attempt_at=None)  # a manual retry gets a fresh set of attempts
        dispatch(row.pk)
        return Response(self.get_serializer(self.get_queryset().get(pk=row.pk)).data)


class EventViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdmin]
    lookup_field = "code"
    pagination_class = None
    http_method_names = ["get", "patch", "head", "options"]
    queryset = NotificationEvent.objects.order_by("id")

    def list(self, request, *args, **kwargs):
        for code in DEFAULT_EVENTS:
            get_event(code)  # the catalog is created lazily; the admin always sees every event
        return super().list(request, *args, **kwargs)


class TestSendView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        s = TestSendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        ch, to, body = s.validated_data["channel"], s.validated_data["to"].strip(), s.validated_data["body"]
        provider = "email" if ch == "email" else whatsapp.provider()
        try:
            if ch == "email":
                validate_email(to)
                send_mail("Brightloop test message", body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)
                detail = "sent"
            else:
                detail = whatsapp.send(normalize_whatsapp(to), body, "test")
            return Response({"ok": True, "provider": provider, "detail": detail})
        except DjangoValidationError as e:
            return Response({"to": e.messages}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:  # provider trouble is a result to show, not a server error
            return Response({"ok": False, "provider": provider, "detail": f"{type(e).__name__}: {e}"[:500]})


class RunRemindersView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        s = RunRemindersSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(reminders.run_reminders(s.validated_data.get("as_of")))


class ProviderStatusView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(whatsapp.status())


class MyNotificationsView(generics.ListAPIView):
    serializer_class = MyLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationLog.objects.filter(recipient_user=self.request.user, status__in=["sent", "delivered", "read"]).select_related("event")


class MySettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def _profile(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise NotFound("Only customers have notification settings.")
        return profile

    def get(self, request):
        return Response(SettingsSerializer(self._profile(request)).data)

    def patch(self, request):
        s = SettingsSerializer(self._profile(request), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
