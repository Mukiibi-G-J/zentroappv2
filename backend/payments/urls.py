from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentJournalViewSet

app_name = "payments"

router = DefaultRouter()
router.register(r"api/payments/payment-journal", PaymentJournalViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
