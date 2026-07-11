from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    G_LAccountViewSet,
    GeneralLedgerEntryViewSet,
    PaymentMethodViewSet,
    PaymentViewSet,
    list_currencies,
)

app_name = "financials"

router = DefaultRouter()
router.register(r"api/financials/gl-accounts", G_LAccountViewSet)
router.register(r"api/financials/gl-entries", GeneralLedgerEntryViewSet)
router.register(r"api/financials/payment-methods", PaymentMethodViewSet)
router.register(r"api/financials/payments", PaymentViewSet)

urlpatterns = [
    path("api/financials/currencies/", list_currencies, name="currency-list"),
    path("", include(router.urls)),
]
