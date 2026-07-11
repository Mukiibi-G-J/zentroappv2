from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PurchaseViewSet,
    VendorViewSet,
    VendorLedgerViewSet,
    DocumentAttachmentViewSet,
    GenerateInvoiceNoView,
    update_vendor_payment_method,
)

router = DefaultRouter()
router.register(r"purchases", PurchaseViewSet, basename="purchases-viewset")
router.register(r"vendors", VendorViewSet, basename="vendors-viewset")
router.register(r"vendor-ledger", VendorLedgerViewSet, basename="vendor-ledger-viewset")
router.register(
    r"document-attachments",
    DocumentAttachmentViewSet,
    basename="document-attachments",
)

urlpatterns = [
     path(
        "api/purchases/generate-invoice-no/",
        GenerateInvoiceNoView.as_view(),
        name="generate-invoice-no",
    ),
    path(
        "api/purchases/update-vendor-payment-method/",
        update_vendor_payment_method,
        name="update-vendor-payment-method",
    ),
    path("api/", include(router.urls)),
   
]
