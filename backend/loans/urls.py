from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoanViewSet, LoanRepaymentViewSet

app_name = "loans"

router = DefaultRouter()
router.register(r"loans", LoanViewSet, basename="loan")
router.register(r"loan-repayments", LoanRepaymentViewSet, basename="loanrepayment")

urlpatterns = [
    path("", include(router.urls)),
]


