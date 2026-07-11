from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DimensionViewSet, DimensionValueViewSet, DimensionSetViewSet

router = DefaultRouter()
router.register(r"dimensions", DimensionViewSet, basename="dimension")
router.register(r"dimension-values", DimensionValueViewSet, basename="dimension-value")
router.register(r"dimension-sets", DimensionSetViewSet, basename="dimension-set")

urlpatterns = [
    path("", include(router.urls)),
]



