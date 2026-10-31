from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("quotation-templates", views.QuotationTemplateViewSet, basename="quotation-template")
router.register("subscriptions", views.SubscriptionViewSet, basename="subscription")

urlpatterns = router.urls
