from django.urls import path
from . import views

app_name = "home"

urlpatterns = [
    # path("", views.landing_page, name="landing-page"),
    path("api/pricing/", views.landing_page_api, name="pricing-api"),
    path("api/on-boarding/", views.onboarding_api, name="onboarding-api"),
    path("onboarding/", views.onboarding, name="onboarding"),
    # Accept both slash variants so Next.js trailing-slash 308 + Django APPEND_SLASH
    # 301 cannot form a redirect loop when proxied through next.config rewrites.
    path(
        "api/home/on-boarding", views.get_onboarding_data, name="get-onboarding-data"
    ),
    path(
        "api/home/on-boarding/",
        views.get_onboarding_data,
        name="get-onboarding-data-slash",
    ),
]
