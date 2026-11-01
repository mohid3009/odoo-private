import hmac
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
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.finance.notifications.services import notify

from . import demo, firebase
from .models import Role
from .permissions import IsAdmin, IsStaffOrAdmin
from .serializers import (
    CustomerPickSerializer, FirebaseLoginSerializer, LoginSerializer, MeNameSerializer, ProfileSerializer, ResetConfirmSerializer,
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


@anon_post
class FirebaseLoginView(APIView):
    """Exchange a Firebase ID token (Google or email/password sign-in) for the normal Django session cookie."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        s = FirebaseLoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        try:
            claims = firebase.verify(v["id_token"])
        except ValueError:
            return Response({"detail": "Sign-in expired or invalid. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)
        email = (claims.get("email") or "").strip().lower()
        if not email or not claims.get("email_verified"):  # unverified emails could impersonate an existing account
            return Response({"detail": "Verify your email address, then sign in again."}, status=status.HTTP_403_FORBIDDEN)
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = s.create({**v, "email": email, "password": None, "name": v["name"] or claims.get("name", "")})
            if user.role == Role.CUSTOMER:
                notify("WELCOME", user, user, context={"customer_name": user.name or user.email})
        elif not user.is_active:
            return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)
        login(request, user)
        return Response(UserSerializer(user).data)


@anon_post
class CodeCheckView(APIView):
    """Does this staff/admin registration code match? Drives the verify animation on the sign-up page. Same comparison as
    sign-up itself (D-044), rate limited because it answers yes/no."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "code_check"

    def post(self, request):
        expected = {Role.STAFF: settings.STAFF_SIGNUP_CODE, Role.ADMIN: settings.ADMIN_SIGNUP_CODE}.get(request.data.get("account_type"), "")
        code = str(request.data.get("code") or "")
        valid = bool(expected) and hmac.compare_digest(code.encode(), expected.encode())
        return Response({"valid": valid})


@anon_post
class DemoLoginView(APIView):
    """Quick sign-in for the three demo accounts. Off unless DEMO_LOGIN_ENABLED; a separate path, real auth is untouched."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not settings.DEMO_LOGIN_ENABLED:
            return Response({"detail": "Demo sign-in is disabled."}, status=status.HTTP_404_NOT_FOUND)
        key = request.data.get("role")
        if key not in demo.DEMO:
            return Response({"detail": "role must be user, staff or admin."}, status=status.HTTP_400_BAD_REQUEST)
        user = demo.ensure(key)
        if user is None:
            return Response({"detail": "That demo email belongs to a real account."}, status=status.HTTP_409_CONFLICT)
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
