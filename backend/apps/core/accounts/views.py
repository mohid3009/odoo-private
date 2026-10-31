import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.notifications.services import notify

from .models import Role
from .permissions import IsAdmin, IsStaffOrAdmin
from .serializers import (
    CustomerPickSerializer, LoginSerializer, MeNameSerializer, ProfileSerializer, ResetConfirmSerializer,
    ResetRequestSerializer, SignupSerializer, StaffSerializer, UserSerializer,
)

User = get_user_model()
log = logging.getLogger(__name__)

# Anonymous POSTs have no session for DRF to CSRF-check, so enforce it explicitly.
anon_post = method_decorator(csrf_protect, name="dispatch")


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"detail": "ok"})


@anon_post
class SignupView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = SignupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        notify("WELCOME", user, user, context={"customer_name": user.name or user.email})  # never raises, never blocks
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@anon_post
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(request, username=s.validated_data["email"].strip().lower(), password=s.validated_data["password"])
        if not user:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        user = request.user
        name = MeNameSerializer(data=request.data)
        name.is_valid(raise_exception=True)
        profile = getattr(user, "profile", None)
        ps = None
        if profile is not None and "profile" in request.data:
            ps = ProfileSerializer(profile, data=request.data["profile"], partial=True)
            ps.is_valid(raise_exception=True)
        if "name" in name.validated_data:
            user.name = name.validated_data["name"]
            user.save(update_fields=["name"])
        if ps:
            ps.save()
        return Response(UserSerializer(user).data)


@anon_post
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = ResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=s.validated_data["email"].strip(), is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            link = f"{settings.SITE_URL}/reset-password/{uid}/{default_token_generator.make_token(user)}"
            try:  # D-020: email-only, and never fails the request. Moves behind notify() in Phase 4.
                send_mail(
                    "Reset your Brightloop password",
                    f"Hi {user.name or user.email},\n\nChoose a new password here (valid 24 hours, one use):\n{link}\n\n"
                    "If you did not ask for this, ignore this email.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
            except Exception:
                log.exception("password reset email failed for user %s", user.pk)
        # same answer whether or not the account exists: no account enumeration
        return Response({"detail": "If that email is registered, a reset link has been sent."})


@anon_post
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = ResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(v["uid"])), is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(user, v["token"]):
            return Response({"detail": "This reset link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(v["new_password"])  # changes the hash, so the token is now spent
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated. You can log in now."})


class CustomerListView(generics.ListAPIView):
    """Picker for forms (subscription customer): staff and admin only."""

    permission_classes = [IsStaffOrAdmin]
    serializer_class = CustomerPickSerializer
    search_fields = ["email", "name"]

    def get_queryset(self):
        return User.objects.filter(role=Role.CUSTOMER).order_by("email")


class StaffListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = StaffSerializer
    search_fields = ["email", "name"]

    def get_queryset(self):
        return User.objects.filter(role__in=[Role.STAFF, Role.ADMIN]).order_by("email")
