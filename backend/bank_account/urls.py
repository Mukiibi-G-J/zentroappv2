from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BankAccountViewSet,
    BankAccountLedgerEntryViewSet,
    BankAccountPostingGroupViewSet,
)

app_name = "bank_account"

router = DefaultRouter()
router.register(r"bank-accounts", BankAccountViewSet, basename="bank-account")
router.register(
    r"bank-account-ledger-entries",
    BankAccountLedgerEntryViewSet,
    basename="bank-account-ledger-entry",
)
router.register(
    r"bank-account-posting-groups",
    BankAccountPostingGroupViewSet,
    basename="bank-account-posting-group",
)

urlpatterns = [
    path("api/", include(router.urls)),
]

