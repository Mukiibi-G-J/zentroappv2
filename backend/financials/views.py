from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from django.db.models import Sum, Q
from rest_framework.exceptions import ValidationError

from financials.models import (
    G_LAccount,
    GeneralLedgerEntry,
    PaymentMethod,
    Payment,
)
from financials.serializers import (
    G_LAccountSerializer,
    GeneralLedgerEntrySerializer,
    PaymentMethodSerializer,
    PaymentSerializer,
)

from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from rest_framework.permissions import IsAuthenticated

from financials.services.balance_sheet_service import BalanceSheetService
from financials.services.profit_loss_statement_service import (
    ProfitLossStatementService,
)

from dimension.branch_filter import branch_scope_is_all, get_branch_for_request

class ChartOfAccountView(View):
    template_name = "financials/chart-of-account.html"

    def get(self, request):
        accounts = G_LAccount.objects.all().order_by("no")
        return render(
            request,
            self.template_name,
            {
                "accounts": accounts,
                "account_types": dict(
                    G_LAccount._meta.get_field("accounttype").choices
                ),
            },
        )

    def post(self, request, pk):
        try:
            account = G_LAccount.objects.get(pk=pk)
            account_name = account.name
            account.delete()
            messages.success(
                request, f"Account '{account_name}' was successfully deleted."
            )
        except Exception as e:
            messages.error(request, f"Error deleting account: {str(e)}")

        return redirect("financials:chart_of_account")

    # def get9(self, request):


class DeleteChartOfAccountView(View):
    def post(self, request, pk):
        try:
            account = get_object_or_404(G_LAccount, pk=pk)
            account_name = account.name
            account.delete()
            messages.success(
                request, f"Account '{account_name}' was successfully deleted."
            )
        except Exception as e:
            messages.error(request, f"Error deleting account: {str(e)}")

        return HttpResponseRedirect(reverse_lazy("financials:chart_of_account"))


class G_LAccountViewSet(viewsets.ModelViewSet):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = G_LAccount.objects.all()
    serializer_class = G_LAccountSerializer
    lookup_field = "no"  # Since 'no' is the primary key
    pagination_class = None

    def _resolve_dimension_ids(self, request):
        """
        Resolve effective dimension filters for Financials endpoints.

        - Explicit query params win (backward compatible)
        - X-Branch-Scope: all -> no branch filter
        - Otherwise default to X-Branch-Id / user branch (get_branch_for_request)
        """
        dim1_param = request.query_params.get("global_dimension_1_id")
        dim2_param = request.query_params.get("global_dimension_2_id")

        dim1_id = None
        dim2_id = None

        if dim1_param:
            try:
                dim1_id = int(dim1_param)
            except (TypeError, ValueError):
                dim1_id = None
        if dim2_param:
            try:
                dim2_id = int(dim2_param)
            except (TypeError, ValueError):
                dim2_id = None

        if dim1_id is None and not branch_scope_is_all(request):
            try:
                from financials.models import GeneralLedgerSetup

                gl_setup = GeneralLedgerSetup.objects.first()
                if gl_setup and getattr(gl_setup, "enable_multiple_branches", False):
                    branch = get_branch_for_request(request)
                    if branch:
                        dim1_id = branch.id
            except Exception:
                pass

        return dim1_id, dim2_id

    def _get_as_of_date(self, request):
        as_of_date_param = request.query_params.get("as_of_date")
        if not as_of_date_param:
            return timezone.now().date()
        return datetime.strptime(as_of_date_param, "%Y-%m-%d").date()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")
        as_of_date_param = request.query_params.get("as_of_date")
        dim1_id, dim2_id = self._resolve_dimension_ids(request)

        # BC-style: explicit param overrides; when no param and multi-branch,
        # we've defaulted to user's branch above

        # Build base Q filter for dimension constraints
        gle_filter = Q()
        if dim1_id is not None:
            gle_filter &= Q(general_ledger_entries__global_dimension_1_id=dim1_id)
        if dim2_id is not None:
            gle_filter &= Q(general_ledger_entries__global_dimension_2_id=dim2_id)

        has_dimension_filter = dim1_id is not None or dim2_id is not None
        has_date_filter = False

        # As-of date (Balance at Date): cumulative balance up to and including date
        if as_of_date_param:
            try:
                as_of_date = datetime.strptime(as_of_date_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid as_of_date format. Expected YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            has_date_filter = True
            date_filter = Q(general_ledger_entries__posting_date__lte=as_of_date)
            combined = gle_filter & date_filter
            queryset = queryset.annotate(
                balance_at_date=Sum(
                    "general_ledger_entries__amount",
                    filter=combined,
                )
            )

        # Date range (Net Change): sum in period
        elif start_date_param or end_date_param:
            if not start_date_param or not end_date_param:
                return Response(
                    {"detail": "Both start_date and end_date are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Expected YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            has_date_filter = True
            date_filter = Q(
                general_ledger_entries__posting_date__gte=start_date,
                general_ledger_entries__posting_date__lte=end_date,
            )
            combined = gle_filter & date_filter
            queryset = queryset.annotate(
                balance_range=Sum(
                    "general_ledger_entries__amount",
                    filter=combined,
                )
            )

        # Dimensions only (no date filter): filtered balance
        elif has_dimension_filter:
            queryset = queryset.annotate(
                balance_filtered=Sum(
                    "general_ledger_entries__amount",
                    filter=gle_filter,
                )
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="balance-sheet")
    def balance_sheet(self, request):
        """
        Return a Balance Sheet snapshot by aggregating G/L entries.
        Supports global_dimension_1_id for branch filtering (all/single branch).
        """
        try:
            as_of_date = self._get_as_of_date(request)
        except ValueError:
            return Response(
                {"detail": "Invalid as_of_date. Expected format YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_qs = GeneralLedgerEntry.objects.all()
        dim1_id, _dim2_id = self._resolve_dimension_ids(request)
        if dim1_id is not None:
            base_qs = base_qs.filter(global_dimension_1_id=dim1_id)
        service = BalanceSheetService(queryset=base_qs)
        data = service.generate(as_of_date)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="balance-sheet/export")
    def balance_sheet_export(self, request):
        """
        Export the Balance Sheet snapshot as a PDF document.
        Supports global_dimension_1_id for branch filtering.
        """
        try:
            as_of_date = self._get_as_of_date(request)
        except ValueError:
            return Response(
                {"detail": "Invalid as_of_date. Expected format YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_qs = GeneralLedgerEntry.objects.all()
        dim1_id, _dim2_id = self._resolve_dimension_ids(request)
        if dim1_id is not None:
            base_qs = base_qs.filter(global_dimension_1_id=dim1_id)
        service = BalanceSheetService(queryset=base_qs)
        pdf_bytes = service.generate_pdf(as_of_date)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response[
            "Content-Disposition"
        ] = f'attachment; filename="balance-sheet-{as_of_date.isoformat()}.pdf"'
        return response

    @action(detail=False, methods=["get"], url_path="profit-loss/export")
    def profit_loss_export(self, request):
        """
        Export Profit & Loss (Income Statement) for a date range as PDF.
        Supports global_dimension_1_id for branch filtering (same as balance sheet).
        """
        start_date_param = request.query_params.get("start_date")
        end_date_param = request.query_params.get("end_date")
        if not start_date_param or not end_date_param:
            return Response(
                {"detail": "Both start_date and end_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Expected YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_qs = GeneralLedgerEntry.objects.all()
        dim1_id, _dim2_id = self._resolve_dimension_ids(request)
        if dim1_id is not None:
            base_qs = base_qs.filter(global_dimension_1_id=dim1_id)
        service = ProfitLossStatementService(queryset=base_qs)
        pdf_bytes = service.generate_pdf(start_date, end_date)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="profit-loss-{start_date.isoformat()}_'
            f'{end_date.isoformat()}.pdf"'
        )
        return response


class GeneralLedgerEntryViewSet(viewsets.ModelViewSet):
    queryset = GeneralLedgerEntry.objects.all()
    serializer_class = GeneralLedgerEntrySerializer
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "user", "global_dimension_1", "global_dimension_2"
        )
        dim1_param = self.request.query_params.get("global_dimension_1_id")
        dim2_param = self.request.query_params.get("global_dimension_2_id")
        # When multi-branch is enabled and no branch param passed, default to user's
        # current branch so drill-downs only show entries for their branch
        if dim1_param is None:
            try:
                from financials.models import GeneralLedgerSetup
                from dimension.branch_filter import get_branch_for_request
                gl_setup = GeneralLedgerSetup.objects.first()
                if gl_setup and getattr(gl_setup, "enable_multiple_branches", False):
                    branch = get_branch_for_request(self.request)
                    if branch:
                        dim1_param = str(branch.id)
            except ImportError:
                pass
        if dim1_param is not None or dim2_param is not None:
            try:
                if dim1_param is not None:
                    queryset = queryset.filter(
                        global_dimension_1_id=int(dim1_param)
                    )
                if dim2_param is not None:
                    queryset = queryset.filter(
                        global_dimension_2_id=int(dim2_param)
                    )
            except (TypeError, ValueError):
                pass
        gl_account = self.request.query_params.get("gl_account", None)
        if gl_account:
            queryset = queryset.filter(gl_account=gl_account)
        start_date_param = self.request.query_params.get("start_date")
        end_date_param = self.request.query_params.get("end_date")
        if start_date_param and end_date_param:
            try:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d").date()
            except ValueError:
                raise ValidationError("Invalid date format. Expected YYYY-MM-DD.")
            queryset = queryset.filter(posting_date__range=[start_date, end_date])
        return queryset


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """
    API surface for managing payment methods.
    Page Object ID: 10403 (Payment Methods)
    """
    
    PAGE_OBJECT_ID = 10403
    
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    lookup_field = "id"
    pagination_class = None
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    
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
            return self._deny(source, "You need read permission to view payment methods.")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view payment methods.")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(
                source, "You need insert permission to create payment methods."
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update payment methods."
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update payment methods."
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(
                source, "You need delete permission to delete payment methods."
            )
        return super().destroy(request, *args, **kwargs)


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    queryset = Payment.objects.all()
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter payments based on query parameters"""
        queryset = super().get_queryset()

        # Filter by status
        status = self.request.query_params.get("status", None)
        if status:
            queryset = queryset.filter(status=status)

        # Filter by date range
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)
        if start_date and end_date:
            queryset = queryset.filter(payment_date__range=[start_date, end_date])

        # Filter by account type
        account_type = self.request.query_params.get("account_type", None)
        if account_type:
            queryset = queryset.filter(account_type=account_type)

        return queryset.order_by("-payment_date")

    @action(detail=True, methods=["post"])
    def post_payment(self, request, pk=None):
        """Post a payment and create the necessary ledger entries"""
        payment = self.get_object()

        try:
            with transaction.atomic():
                # Validate payment status
                if payment.status != "Open":
                    return Response(
                        {"error": "Only open payments can be posted"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Create ledger entries based on payment type
                if payment.account_type == "G/L Account":
                    from dimension.models import get_posting_dimension_payload

                    dim_payload = get_posting_dimension_payload(
                        global_dimension_1=getattr(request.user, "global_dimension_1", None)
                    )
                    # Create G/L entries
                    GeneralLedgerEntry.objects.create(
                        gl_account=payment.gl_account,
                        posting_date=payment.payment_date,
                        document_type=payment.document_type,
                        document_no=payment.document_no,
                        description=payment.description,
                        amount=payment.amount,
                        user=request.user,
                        dimension_set=dim_payload["dimension_set"],
                        global_dimension_1=dim_payload["global_dimension_1"],
                        global_dimension_2=dim_payload["global_dimension_2"],
                    )

                    # Create balancing entry
                    GeneralLedgerEntry.objects.create(
                        gl_account=payment.gl_balancing_account,
                        posting_date=payment.payment_date,
                        document_type=payment.document_type,
                        document_no=payment.document_no,
                        description=payment.description,
                        amount=-payment.amount,  # Opposite amount for balancing
                        user=request.user,
                        dimension_set=dim_payload["dimension_set"],
                        global_dimension_1=dim_payload["global_dimension_1"],
                        global_dimension_2=dim_payload["global_dimension_2"],
                    )

                # Update payment status
                payment.status = "Posted"
                payment.save()

                return Response(
                    {
                        "message": "Payment posted successfully",
                        "payment": PaymentSerializer(payment).data,
                    }
                )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get payment summary statistics"""
        total_payments = self.get_queryset().count()
        open_payments = self.get_queryset().filter(status="Open").count()
        posted_payments = self.get_queryset().filter(status="Posted").count()
        total_amount = (
            self.get_queryset().aggregate(total=models.Sum("amount"))["total"] or 0
        )

        return Response(
            {
                "total_payments": total_payments,
                "open_payments": open_payments,
                "posted_payments": posted_payments,
                "total_amount": total_amount,
            }
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def list_currencies(request):
    """Return ISO 4217 currency catalog for local currency selection."""
    from financials.currency import list_currencies_for_api

    return Response({"results": list_currencies_for_api()})
