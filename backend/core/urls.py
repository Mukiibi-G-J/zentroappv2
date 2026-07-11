from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from django.urls import re_path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("app_updates.urls")),
    path("api/permissions/", include("permissions.urls")),  # NEW: Permission system API
    path("api/dimensions/", include("dimension.urls")),  # Dimension/Branch API
    path(
        "api/base/", include("base.urls", namespace="base")
    ),  # Base URLs for objects (tenant-specific)
    path("", include("authentication.urls", namespace="authentication")),
    path("", include("sales.urls", namespace="sales")),
    path("", include("items.urls", namespace="items")),
    # path("", include("config_packages.urls", namespace="config_packages")),
    path("", include("financials.urls", namespace="financials")),
    path("", include("postings.urls", namespace="postings")),
    path("", include("config_packages.urls")),
    path("", include("purchases.urls")),
    path("", include("payments.urls", namespace="payments")),
    path("", include("expenses.urls", namespace="expenses")),
    path("", include("reports.urls", namespace="reports")),
    path("", include("company.urls", namespace="company")),
    path("", include("common.urls", namespace="common")),
    path("", include("resources.urls", namespace="resources")),
    path("", include("production.urls", namespace="production")),
    path("", include("setup.urls", namespace="setup")),
    path("", include("prepayment.urls", namespace="prepayment")),
    path("", include("bank_account.urls", namespace="bank_account")),
    path("", include("restaurant_management.urls", namespace="restaurant_management")),
    path("api/loans/", include("loans.urls", namespace="loans")),
    path("api/hotel/", include("hotel_management.urls", namespace="hotel_management")),
    path("", include("settings.urls", namespace="settings")),
    path("", include("sync.urls", namespace="sync")),
    path("", include("receipt_templates.urls")),
    # Page engine
    path("", include("pages.urls", namespace="pages")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
