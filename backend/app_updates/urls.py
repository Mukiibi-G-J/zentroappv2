from django.urls import path

from . import views


urlpatterns = [
    path(
        "download/",
        views.DownloadLatestAndroidView.as_view(),
        name="app-download-latest-android",
    ),
    path(
        "download/windows/",
        views.DownloadLatestWindowsView.as_view(),
        name="app-download-latest-windows",
    ),
    path(
        "download/desktop/",
        views.DownloadLatestWindowsView.as_view(),
        name="app-download-latest-desktop",
    ),
    path(
        "api/app/version-check/",
        views.AppVersionCheckView.as_view(),
        name="app-version-check",
    ),
]
