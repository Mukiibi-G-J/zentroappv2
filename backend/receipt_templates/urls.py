from rest_framework.routers import DefaultRouter

from receipt_templates import views
from receipt_templates.report_views import ReceiptReportViewSet

router = DefaultRouter()
router.register(
    r"api/company/receipt-templates",
    views.ReceiptTemplateViewSet,
    basename="receipt-template",
)
router.register(
    r"api/company/receipt-template-assignments",
    views.ReceiptTemplateAssignmentViewSet,
    basename="receipt-template-assignment",
)
router.register(
    r"api/receipt-reports",
    ReceiptReportViewSet,
    basename="receipt-report",
)

urlpatterns = router.urls
