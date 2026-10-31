from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("payments", views.PaymentViewSet, basename="payment")

urlpatterns = router.urls
