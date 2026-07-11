from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExpenseViewSet, ExpenseTypeViewSet, ExpenseCategoryViewSet

app_name = "expenses"

router = DefaultRouter()
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"expense-types", ExpenseTypeViewSet, basename="expense-type")
router.register(
    r"expense-categories", ExpenseCategoryViewSet, basename="expense-category"
)

urlpatterns = [
    path("api/", include(router.urls)),
]
