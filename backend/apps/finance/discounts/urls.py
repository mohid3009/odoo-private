from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.include_root_view = False
router.register("discounts", views.DiscountViewSet, basename="discount")

urlpatterns = router.urls
