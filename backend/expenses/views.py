from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import ValidationError
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.db import transaction
from django.contrib import admin
from datetime import datetime, timedelta

from .models import (
    Expense,
    ExpenseType as ExpenseTypeModel,
    ExpenseCategory as ExpenseCategoryModel,
)
from .serializers import (
    ExpenseSerializer,
    ExpensePreviewSerializer,
    ExpenseTypeSerializer,
    ExpenseCategorySerializer,
)
from .enums import ExpenseStatus
from financials.models import PaymentMethod
from dimension.branch_filter import filter_queryset_by_branch


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Expense model with CRUD operations and posting functionality.
    """

    PAGE_OBJECT_ID = 10601
    queryset = (
        Expense.objects.select_related(
            "expense_type",
            "expense_type__category",
            "gl_account",
            "balancing_account",
            "payment_method",
            "global_dimension_1",
            "dimension_set",
        )
        .all()
        .order_by("-posting_date", "-document_no")
    )
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get_queryset(self):
        """Filter queryset by company and add search functionality"""
        queryset = self.queryset

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(document_no__icontains=search)
                | Q(description__icontains=search)
                | Q(expense_type__name__icontains=search)
                | Q(expense_type__code__icontains=search)
                | Q(external_document_no__icontains=search)
            )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        expense_type = self.request.query_params.get("expense_type")
        if expense_type:
            queryset = queryset.filter(expense_type=expense_type)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(posting_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(posting_date__lte=end_date)

        return filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------
    def _has_permission(self, user, action: str):
        has_permission, reason = user.check_object_permission(
            self.PAGE_OBJECT_ID, action
        )
        return has_permission, reason

    def _deny(self, reason, detail):
        return Response(
            {"error": "Insufficient permissions", "detail": detail, "reason": reason},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ------------------------------------------------------------------
    # CRUD overrides with permission checks
    # ------------------------------------------------------------------
    def list(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view expenses.")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view expenses.")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(source, "You need insert permission to create expenses.")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to update expenses.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to update expenses.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(source, "You need delete permission to remove expenses.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def preview_posting(self, request, pk=None):
        """
        Preview the journal entries that will be created when posting the expense.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to preview the posting entries."
            )
        try:
            expense = self.get_object()

            # Check if expense can be posted
            if expense.status != ExpenseStatus.OPEN.value:
                return Response(
                    {"error": "Only open expenses can be previewed for posting"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not expense.gl_account or not expense.balancing_account:
                return Response(
                    {"error": "G/L accounts must be set before previewing posting"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate preview
            serializer = ExpensePreviewSerializer(expense)
            return Response(serializer.data)

        except Expense.DoesNotExist:
            return Response(
                {"error": "Expense not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error generating preview: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def post_expense(self, request, pk=None):
        """
        Post the expense to G/L accounts.
        """
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to post expense entries."
            )
        try:
            expense = self.get_object()

            # Validate expense before posting
            if expense.status == ExpenseStatus.POSTED.value:
                return Response(
                    {"error": "This expense has already been posted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not expense.amount or expense.amount <= 0:
                return Response(
                    {"error": "Amount must be greater than zero to post expense."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not expense.payment_method:
                return Response(
                    {"error": "Payment method is required to post expense."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not expense.gl_account:
                return Response(
                    {"error": "G/L account is required to post expense."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not expense.balancing_account:
                return Response(
                    {
                        "error": "Balancing account is required to post expense. Please select a payment method and save the expense first."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Post the expense directly using the model method
            with transaction.atomic():
                posted_entries = expense.post_expense(request.user)

                # Refresh the expense object to get updated data
                expense.refresh_from_db()

                return Response(
                    {
                        "message": f"Expense {expense.document_no} posted successfully. {len(posted_entries)} G/L entries created.",
                        "expense": self.get_serializer(expense).data,
                    }
                )

        except Expense.DoesNotExist:
            return Response(
                {"error": "Expense not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error posting expense: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def expense_types(self, request):
        """
        Get list of expense types with their G/L account mappings.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view expense types."
            )
        queryset = ExpenseTypeModel.objects.filter(is_active=True).select_related(
            "category", "gl_account"
        )
        serializer = ExpenseTypeSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def payment_methods(self, request):
        """
        Get list of available payment methods.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view payment methods."
            )
        try:
            payment_methods = PaymentMethod.objects.all()
            data = [
                {"id": pm.id, "description": pm.description, "code": pm.code}
                for pm in payment_methods
            ]

            return Response(data)

        except Exception as e:
            return Response(
                {"error": f"Error fetching payment methods: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def dashboard_summary(self, request):
        """
        Get expense dashboard summary statistics.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view the dashboard summary."
            )
        try:
            # Get date range from query params
            days = int(request.query_params.get("days", 30))
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)

            queryset = self.get_queryset().filter(
                posting_date__range=[start_date, end_date]
            )

            # Calculate statistics
            total_expenses = (
                queryset.filter(status=ExpenseStatus.POSTED.value).aggregate(
                    total=Sum("amount")
                )["total"]
                or 0
            )

            expense_count = queryset.filter(status=ExpenseStatus.POSTED.value).count()

            draft_count = queryset.filter(status=ExpenseStatus.OPEN.value).count()

            # Top expense types
            top_expense_types = (
                queryset.filter(status=ExpenseStatus.POSTED.value)
                .values("expense_type")
                .annotate(total=Sum("amount"), count=Count("id"))
                .order_by("-total")[:5]
            )

            # Recent expenses
            recent_expenses = queryset.filter(
                status=ExpenseStatus.POSTED.value
            ).order_by("-posting_date")[:10]

            # Monthly trend
            monthly_trend = (
                queryset.filter(status=ExpenseStatus.POSTED.value)
                .extra(select={"month": "EXTRACT(month FROM posting_date)"})
                .values("month")
                .annotate(total=Sum("amount"))
                .order_by("month")
            )

            return Response(
                {
                    "total_expenses": total_expenses,
                    "expense_count": expense_count,
                    "draft_count": draft_count,
                    "top_expense_types": list(top_expense_types),
                    "recent_expenses": ExpenseSerializer(
                        recent_expenses, many=True
                    ).data,
                    "monthly_trend": list(monthly_trend),
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Error generating dashboard summary: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def expense_report(self, request):
        """
        Generate expense report with filtering options.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to generate expense reports."
            )
        try:
            queryset = self.get_queryset()

            # Apply filters
            start_date = request.query_params.get("start_date", None)
            end_date = request.query_params.get("end_date", None)
            expense_type = request.query_params.get("expense_type", None)
            status_filter = request.query_params.get("status", None)

            if start_date:
                queryset = queryset.filter(posting_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(posting_date__lte=end_date)
            if expense_type:
                queryset = queryset.filter(expense_type=expense_type)
            if status_filter:
                queryset = queryset.filter(status=status_filter)

            # Group by expense type
            expense_summary = (
                queryset.values("expense_type")
                .annotate(total_amount=Sum("amount"), count=Count("id"))
                .order_by("-total_amount")
            )

            # Group by month
            monthly_summary = (
                queryset.extra(select={"month": "EXTRACT(month FROM posting_date)"})
                .values("month")
                .annotate(total_amount=Sum("amount"), count=Count("id"))
                .order_by("month")
            )

            return Response(
                {
                    "expense_summary": list(expense_summary),
                    "monthly_summary": list(monthly_summary),
                    "total_records": queryset.count(),
                    "total_amount": queryset.aggregate(total=Sum("amount"))["total"]
                    or 0,
                }
            )

        except Exception as e:
            return Response(
                {"error": f"Error generating expense report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ExpenseTypeViewSet(viewsets.ModelViewSet):
    """
    Manage expense types (user-defined + system defaults).
    Protected by Expense Setup page permissions.
    """

    PAGE_OBJECT_ID = 10602
    queryset = (
        ExpenseTypeModel.objects.select_related(
            "category", "category__default_gl_account", "gl_account"
        )
        .all()
        .order_by("name")
    )
    serializer_class = ExpenseTypeSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["is_active", "category", "is_user_defined"]
    search_fields = ["code", "name", "description", "category__name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["name"]

    def _has_permission(self, user, action: str):
        has_permission, reason = user.check_object_permission(
            self.PAGE_OBJECT_ID, action
        )
        return has_permission, reason

    def _deny(self, reason, detail):
        return Response(
            {"error": "Insufficient permissions", "detail": detail, "reason": reason},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view expense types."
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view this expense type."
            )
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(
                source, "You need insert permission to create expense types."
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update expense types."
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update expense types."
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(
                source, "You need delete permission to remove expense types."
            )
        instance = self.get_object()
        if not instance.is_user_defined:
            raise ValidationError(
                "System-defined expense types cannot be deleted. Disable them instead."
            )
        return super().destroy(request, *args, **kwargs)


class ExpenseCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset exposing expense categories for the setup wizard.
    """

    PAGE_OBJECT_ID = 10602
    queryset = ExpenseCategoryModel.objects.filter(is_active=True).order_by("name")
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["name", "code"]
    ordering = ["name"]

    def _has_permission(self, user, action: str):
        return user.check_object_permission(self.PAGE_OBJECT_ID, action)

    def _deny(self, reason, detail):
        return Response(
            {"error": "Insufficient permissions", "detail": detail, "reason": reason},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view expense categories."
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view this expense category."
            )
        return super().retrieve(request, *args, **kwargs)
