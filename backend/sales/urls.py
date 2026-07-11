from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SalesViewSet,
    CustomerViewSet,
    CustomerLedgerViewSet,
    GenerateInvoiceNoView,
    SalesDashboardViewSet,
    get_company_info,
    get_sales_setup,
    update_customer_payment_method,
    sales_history_detail,
    # Service sales endpoints
    process_service_sale,
    get_service_profitability,
    get_service_cost_breakdown,
    SalesOrderViewSet,
    SalesFavoritesView,
)

app_name = "sales"

router = DefaultRouter()
router.register(r"sales", SalesViewSet, basename="sales-viewset")
router.register(r"sales-orders", SalesOrderViewSet, basename="sales-order-viewset")
router.register(r"customers", CustomerViewSet, basename="customers-viewset")
router.register(
    r"customer-ledger", CustomerLedgerViewSet, basename="customer-ledger-viewset"
)
router.register(r"sales-dashboard", SalesDashboardViewSet, basename="sales-dashboard")

# Create a separate router for customers at root level
customer_router = DefaultRouter()
customer_router.register(r"customers", CustomerViewSet, basename="customers-viewset")
customer_router.register(
    r"customer-ledger", CustomerLedgerViewSet, basename="customer-ledger-viewset"
)

urlpatterns = [
    path(
        "api/sales/generate-invoice-no/",
        GenerateInvoiceNoView.as_view(),
        name="generate-invoice-no",
    ),
    path(
        "api/sales/company-info/",
        get_company_info,
        name="get-company-info",
    ),
    path(
        "api/sales/sales-history-detail/",
        sales_history_detail,
        name="sales-history-detail",
    ),
    path(
        "api/sales/setup/",
        get_sales_setup,
        name="get-sales-setup",
    ),
    path(
        "api/sales/update-customer-payment-method/",
        update_customer_payment_method,
        name="update-customer-payment-method",
    ),
    # Service sales endpoints
    path(
        "api/sales/process-service-sale/",
        process_service_sale,
        name="process-service-sale",
    ),
    path(
        "api/sales/service-profitability/",
        get_service_profitability,
        name="service-profitability",
    ),
    path(
        "api/sales/service-cost-breakdown/<str:service_id>/",
        get_service_cost_breakdown,
        name="service-cost-breakdown",
    ),
    path(
        "api/sales/favorites/",
        SalesFavoritesView.as_view(),
        name="sales-favorites",
    ),
    path("api/", include(router.urls)),
    # Add customer URLs at root level to match vendor pattern
    path("api/", include(customer_router.urls)),
    path(
        "api/sales/<int:pk>/update_lines/",
        SalesViewSet.as_view({"post": "update_lines"}),
        name="sales-update-lines",
    ),
]
