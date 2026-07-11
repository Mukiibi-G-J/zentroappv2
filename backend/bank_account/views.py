from rest_framework import viewsets, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django.db.models import Q
from django.core.exceptions import ValidationError
from .models import BankAccount, BankAccountLedgerEntry, BankAccountPostingGroup
from .serializers import (
    BankAccountSerializer,
    BankAccountLedgerEntrySerializer,
    BankAccountPostingGroupSerializer,
)
from dimension.branch_filter import filter_queryset_by_branch


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class BankAccountPostingGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for Bank Account Posting Groups"""

    queryset = BankAccountPostingGroup.objects.all()
    serializer_class = BankAccountPostingGroupSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(description__icontains=search)
            )
        return queryset.order_by("code")


class BankAccountViewSet(viewsets.ModelViewSet):
    """ViewSet for Bank Accounts with permission checks"""

    queryset = BankAccount.objects.all()
    serializer_class = BankAccountSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    PAGE_OBJECT_ID = 11001  # Bank Account Management page object ID

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", None)
        if search:
            queryset = queryset.filter(
                Q(no__icontains=search)
                | Q(name__icontains=search)
                | Q(bank_account_no__icontains=search)
            )
        return queryset.order_by("no")

    def _has_permission(self, user, action: str):
        """Check if user has permission for the action"""
        has_permission, reason = user.check_object_permission(
            self.PAGE_OBJECT_ID, action
        )
        return has_permission, reason

    def _deny(self, reason, detail):
        """Return permission denied response"""
        return Response(
            {"error": "Insufficient permissions", "detail": detail, "reason": reason},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        """List bank accounts - requires READ permission"""
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view bank accounts.")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get single bank account - requires READ permission"""
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view bank accounts.")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create bank account - requires INSERT permission"""
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(
                source, "You need insert permission to create bank accounts."
            )
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError as e:
            # Handle ValidationError from model save method
            error_message = str(e)
            if hasattr(e, "message_dict"):
                error_message = "; ".join(
                    [f"{k}: {', '.join(v)}" for k, v in e.message_dict.items()]
                )
            return Response(
                {
                    "error": "Validation failed",
                    "detail": error_message,
                    "errors": e.message_dict if hasattr(e, "message_dict") else {"non_field_errors": [error_message]},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Catch any other exceptions and return a proper error response
            return Response(
                {
                    "error": "Failed to create bank account",
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def update(self, request, *args, **kwargs):
        """Update bank account - requires MODIFY permission"""
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update bank accounts."
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Partial update bank account - requires MODIFY permission"""
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update bank accounts."
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete bank account - requires DELETE permission"""
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(
                source, "You need delete permission to delete bank accounts."
            )
        return super().destroy(request, *args, **kwargs)


class BankAccountLedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Bank Account Ledger Entries (read-only)"""

    queryset = BankAccountLedgerEntry.objects.all()
    serializer_class = BankAccountLedgerEntrySerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    PAGE_OBJECT_ID = 11002  # Bank Account Ledger Entries page object ID

    def get_queryset(self):
        queryset = super().get_queryset()
        bank_account_no = self.request.query_params.get("bank_account_no", None)
        search = self.request.query_params.get("search", None)
        document_type = self.request.query_params.get("document_type", None)
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)

        if bank_account_no:
            queryset = queryset.filter(bank_account_no__no=bank_account_no)

        if search:
            queryset = queryset.filter(
                Q(document_no__icontains=search)
                | Q(description__icontains=search)
                | Q(statement_no__icontains=search)
            )

        if document_type:
            queryset = queryset.filter(document_type=document_type)

        if start_date:
            queryset = queryset.filter(posting_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(posting_date__lte=end_date)

        queryset = filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )

        return queryset.order_by("-posting_date", "-entry_no")

    def _has_permission(self, user, action: str):
        """Check if user has permission for the action"""
        has_permission, reason = user.check_object_permission(
            self.PAGE_OBJECT_ID, action
        )
        return has_permission, reason

    def _deny(self, reason, detail):
        """Return permission denied response"""
        return Response(
            {"error": "Insufficient permissions", "detail": detail, "reason": reason},
            status=status.HTTP_403_FORBIDDEN,
        )

    def list(self, request, *args, **kwargs):
        """List ledger entries - requires READ permission"""
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view bank account ledger entries."
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """Get single ledger entry - requires READ permission"""
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to view bank account ledger entries."
            )
        return super().retrieve(request, *args, **kwargs)
