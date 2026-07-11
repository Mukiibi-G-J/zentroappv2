from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"", views.ReportsViewSet, basename="reports")
router.register(r"scheduled", views.ScheduledReportViewSet, basename="scheduled-reports")
router.register(r"logs", views.ReportLogViewSet, basename="report-logs")

app_name = "reports"

urlpatterns = [
    path("api/reports/", include(router.urls)),
]

