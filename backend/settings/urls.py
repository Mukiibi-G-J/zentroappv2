from django.urls import path

from settings.views import MobileAppSettingsView

app_name = "settings"

urlpatterns = [
    path("api/settings/mobile/", MobileAppSettingsView.as_view(), name="mobile-settings"),
]
