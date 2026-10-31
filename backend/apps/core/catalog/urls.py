from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("taxes", views.TaxViewSet)
router.register("payment-terms", views.PaymentTermViewSet)
router.register("products", views.ProductViewSet)
router.register("plans", views.PlanViewSet)

urlpatterns = router.urls
