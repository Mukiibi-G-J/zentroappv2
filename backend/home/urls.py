from django.urls import path
from . import views

app_name = "home"

urlpatterns = [
    # path("", views.landing_page, name="landing-page"),
    path("api/pricing/", views.landing_page_api, name="pricing-api"),
    path("api/on-boarding/", views.onboarding_api, name="onboarding-api"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path(
        "api/home/on-boarding/", views.get_onboarding_data, name="get-onboarding-data"
    ),
]
