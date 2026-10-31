from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("notifications/logs", views.LogViewSet, basename="notification-log")
router.register("notifications/events", views.EventViewSet, basename="notification-event")

urlpatterns = [
    path("notifications/test-send/", views.TestSendView.as_view()),
    path("notifications/run-reminders/", views.RunRemindersView.as_view()),
    path("notifications/provider-status/", views.ProviderStatusView.as_view()),
    path("me/notifications/", views.MyNotificationsView.as_view()),
    path("me/notification-settings/", views.MySettingsView.as_view()),
] + router.urls
