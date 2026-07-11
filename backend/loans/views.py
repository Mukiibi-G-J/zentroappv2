from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from utils.decorators import require_module

from dimension.branch_filter import filter_queryset_by_branch

from .models import Loan, LoanRepayment
from .serializers import LoanSerializer, LoanRepaymentSerializer
from .filters import LoanFilter, LoanRepaymentFilter
from .processors import (
    LoanPostingProcessor,
    LoanPostingFinalPoster,
    LoanRepaymentPostingProcessor,
    LoanRepaymentPostingFinalPoster,
)
import uuid


@method_decorator(require_module("loans"), name="dispatch")
class LoanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Loan model with CRUD operations and posting functionality.
    Page Object ID: 10801 (Loan Registration)
    """

    PAGE_OBJECT_ID = 10806
    queryset = (
        Loan.objects.select_related("bank_account", "posted_by")
        .all()
        .order_by("-disbursement_date", "-loan_no")
    )
    serializer_class = LoanSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_class = LoanFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["loan_no", "lender_name", "purpose"]
    ordering_fields = ["loan_no", "disbursement_date", "loan_amount", "lender_name"]
    ordering = ["-disbursement_date", "-loan_no"]

    def get_queryset(self):
        """Filter queryset with search functionality and branch filtering"""
        queryset = self.queryset

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(loan_no__icontains=search)
                | Q(lender_name__icontains=search)
                | Q(purpose__icontains=search)
            )

        queryset = filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )
        return queryset

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
            return self._deny(source, "You need read permission to view loans.")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view loans.")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(source, "You need insert permission to create loans.")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to update loans.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to update loans.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(source, "You need delete permission to remove loans.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def preview_posting(self, request, pk=None):
        """
        Preview the journal entries that will be created when posting the loan.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to preview the posting entries."
            )
        try:
            loan = self.get_object()

            if loan.posted:
                return Response(
                    {"error": "Loan has already been posted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            processor = LoanPostingProcessor(loan, request, receipt_no)
            preview_data = processor.process()

            if isinstance(preview_data, dict) and not preview_data.get("success", True):
                return Response(
                    {"error": preview_data.get("message", "Unknown error")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(preview_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error generating preview: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def post_loan(self, request, pk=None):
        """
        Post the loan to the general ledger.
        """
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(source, "You need modify permission to post loans.")

        try:
            loan = self.get_object()

            if loan.posted:
                return Response(
                    {"error": "Loan has already been posted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            # Generate preview first
            processor = LoanPostingProcessor(loan, request, receipt_no)
            preview_data = processor.process()

            if isinstance(preview_data, dict) and not preview_data.get("success", True):
                return Response(
                    {"error": preview_data.get("message", "Unknown error")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Post to tables
            with transaction.atomic():
                poster = LoanPostingFinalPoster(
                    preview_data, loan, request.user, receipt_no
                )
                result = poster.post_to_tables()

                if result["success"]:
                    # Update loan status
                    loan.posted = True
                    loan.posted_date = timezone.now().date()
                    loan.posted_by = request.user
                    loan.status = "Posted"
                    loan.save()

                    return Response(
                        {
                            "success": True,
                            "message": f"Loan {loan.loan_no} posted successfully",
                            "entries_created": result["entries_created"],
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"error": result.get("message", "Unknown error")},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Exception as e:
            return Response(
                {"error": f"Error posting loan: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(require_module("loans"), name="dispatch")
class LoanRepaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for LoanRepayment model with CRUD operations and posting functionality.
    Page Object ID: 10802 (Loan Repayment)
    """

    PAGE_OBJECT_ID = 10807
    queryset = (
        LoanRepayment.objects.select_related("loan", "bank_account", "posted_by")
        .all()
        .order_by("-payment_date", "-repayment_no")
    )
    serializer_class = LoanRepaymentSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filterset_class = LoanRepaymentFilter
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["repayment_no", "loan__loan_no", "loan__lender_name"]
    ordering_fields = ["repayment_no", "payment_date", "amount_paid"]
    ordering = ["-payment_date", "-repayment_no"]

    def get_queryset(self):
        """Filter queryset with search functionality and branch filtering"""
        queryset = self.queryset

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(repayment_no__icontains=search)
                | Q(loan__loan_no__icontains=search)
                | Q(loan__lender_name__icontains=search)
            )

        queryset = filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )
        return queryset

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
            return self._deny(
                source, "You need read permission to view loan repayments."
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view loan repayments."
            )
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(
                source, "You need insert permission to create loan repayments."
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update loan repayments."
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update loan repayments."
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(
                source, "You need delete permission to remove loan repayments."
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def preview_posting(self, request, pk=None):
        """
        Preview the journal entries that will be created when posting the loan repayment.
        """
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to preview the posting entries."
            )
        try:
            repayment = self.get_object()

            if repayment.posted:
                return Response(
                    {"error": "Loan repayment has already been posted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            processor = LoanRepaymentPostingProcessor(repayment, request, receipt_no)
            preview_data = processor.process()

            if isinstance(preview_data, dict) and not preview_data.get("success", True):
                return Response(
                    {"error": preview_data.get("message", "Unknown error")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(preview_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error generating preview: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def post_repayment(self, request, pk=None):
        """
        Post the loan repayment to the general ledger.
        """
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to post loan repayments."
            )

        try:
            repayment = self.get_object()

            if repayment.posted:
                return Response(
                    {"error": "Loan repayment has already been posted."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            # Generate preview first
            processor = LoanRepaymentPostingProcessor(repayment, request, receipt_no)
            preview_data = processor.process()

            if isinstance(preview_data, dict) and not preview_data.get("success", True):
                return Response(
                    {"error": preview_data.get("message", "Unknown error")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Post to tables
            with transaction.atomic():
                poster = LoanRepaymentPostingFinalPoster(
                    preview_data, repayment, request.user, receipt_no
                )
                result = poster.post_to_tables()

                if result["success"]:
                    # Save calculated principal and interest amounts
                    repayment.save()

                    # Update repayment status
                    repayment.posted = True
                    repayment.posted_date = timezone.now().date()
                    repayment.posted_by = request.user
                    repayment.status = "Posted"
                    repayment.save()

                    return Response(
                        {
                            "success": True,
                            "message": f"Loan repayment {repayment.repayment_no} posted successfully",
                            "entries_created": result["entries_created"],
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {"error": result.get("message", "Unknown error")},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        except Exception as e:
            return Response(
                {"error": f"Error posting loan repayment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
