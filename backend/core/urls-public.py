from django.urls import path, include, re_path
from django.contrib import sitemaps
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

from company.admin import global_admin_site
from authentication.views import SendContactEmailView

urlpatterns = [
    # Move the React app route to the top to catch the root URL
    # re_path(r"^$", TemplateView.as_view(template_name="index.html")),  # Handle root URL
    # Public API endpoints (not tenant-specific)
    path(
        "api/auth/send-contact-email/",
        SendContactEmailView.as_view(),
        name="send-contact-email",
    ),
    # Public app update endpoints (download + version check)
    path("", include("app_updates.urls")),
    path("api/base/", include("base.urls", namespace="base")),  # Base URLs for objects
    # Your other URLs
    path("", include("home.urls", namespace="home")),
    path("", include("authentication.urls", namespace="authentication")),
    path("", include("company.urls", namespace="company")),
    path("admin/", global_admin_site.urls),
    # Page engine — accessible from public domain (views switch schema via JWT)
    path("", include("pages.urls", namespace="pages")),
    # Global search / activity — same JWT schema switch pattern as pages
    path("", include("common.urls", namespace="common")),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# React app - catch all other routes
urlpatterns += [
    re_path(
        r"^(?!static/)(?!admin/)(?!api/).*$",
        TemplateView.as_view(template_name="index.html"),
    ),
]
