from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("invoices", views.InvoiceViewSet, basename="invoice")
router.register("billing/runs", views.BillingRunViewSet, basename="billing-run")

urlpatterns = [path("billing/run/", views.RunBillingView.as_view())] + router.urls
