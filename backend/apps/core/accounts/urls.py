from django.conf import settings
from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/firebase/", views.FirebaseLoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("staff/", views.StaffListCreateView.as_view()),
    path("customers/", views.CustomerListView.as_view()),
]

# Local password auth (dev, seeded demo users, tests). Production sets LOCAL_PASSWORD_AUTH=false: Firebase is the only way in.
if settings.LOCAL_PASSWORD_AUTH:
    urlpatterns += [
        path("auth/signup/", views.SignupView.as_view()),
        path("auth/login/", views.LoginView.as_view()),
        path("auth/password-reset/request/", views.PasswordResetRequestView.as_view()),
        path("auth/password-reset/confirm/", views.PasswordResetConfirmView.as_view()),
    ]
