from rest_framework.routers import DefaultRouter
from django.urls import path, include

from prepayment.views import PrepaymentViewSet

app_name = "prepayment"

router = DefaultRouter()
router.register(r"prepayments", PrepaymentViewSet, basename="prepayments")

urlpatterns = [
    path("api/", include(router.urls)),
]

