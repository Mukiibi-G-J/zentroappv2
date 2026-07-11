from decimal import Decimal
import logging

from django.db import transaction
from django.db.utils import ProgrammingError
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from dimension.branch_filter import filter_queryset_by_branch

from prepayment.models import (
    Preayment,
    PreaymentInstallmentDraft,
    PreaymentLine,
    PrepaymentStatus,
)
from prepayment.serializers import (
    PreaymentDetailSerializer,
    PreaymentListSerializer,
    PrepaymentPreviewSerializer,
)
from financials.models import PaymentMethod
from helpers.helpers import ConfigurationError
from reports.utils.formatters import format_currency


class PreaymentFilter(filters.FilterSet):
    posting_date = filters.DateFromToRangeFilter(field_name="posting_date")
    status = filters.CharFilter(field_name="status")

    class Meta:
        model = Preayment
        fields = {
            "customer": ["exact"],
            "status": ["exact"],
            "posting_date": ["exact", "gte", "lte"],
        }


class PrepaymentViewSet(viewsets.ModelViewSet):
    """
    API surface for managing customer prepayment documents.
    Page Object ID aligns with permission layer to keep parity with Business Central flow.
    """

    PAGE_OBJECT_ID = 11001

    queryset = (
        Preayment.objects.all()
        .select_related(
            "customer",
            "customer__payment_method",
            "posted_by",
        )
        .prefetch_related(
            "lines",
            "lines__item",
            "lines__item__itemunitofmeasure_set",
            "lines__item__itemunitofmeasure_set__unit_of_measure",
            "posted_sales_invoices",
            "posted_sales_invoices__posted_sales_invoice_lines",
        )
        .order_by("-posting_date", "-id")
    )
    filterset_class = PreaymentFilter
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    search_fields = ["document_no", "customer__name", "description"]
    ordering_fields = ["posting_date", "updated_at", "total_amount"]
    ordering = ["-posting_date", "-id"]

    def get_serializer_class(self):
        if self.action == "list":
            return PreaymentListSerializer
        return PreaymentDetailSerializer

    def get_queryset(self):
        """Get queryset, deferring new fields until migrations are run, with branch filtering."""
        queryset = super().get_queryset()
        # Temporarily defer new fields to avoid SELECT errors until migrations are run
        # The serializer will handle these via SerializerMethodField with defaults
        # TODO: Remove this defer after running migrations that add these columns
        queryset = queryset.defer("total_prepayment_to_deduct", "deposit_percent")
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
            return self._deny(source, "You need read permission to view prepayments.")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(source, "You need read permission to view prepayments.")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "insert")
        if not allowed:
            return self._deny(
                source, "You need insert permission to create prepayments."
            )
        try:
            return super().create(request, *args, **kwargs)
        except ConfigurationError as exc:
            return Response(
                {
                    "detail": str(exc),
                    "code": "prepayment_number_series_not_configured",
                    "hint": (
                        "Run for this tenant: python manage.py tenant_command "
                        "seed_sales_prepayment_numbers --schema=<schema>"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update prepayments."
            )
        try:
            self.get_object().assert_open_for_installments()
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update prepayments."
            )
        try:
            self.get_object().assert_open_for_installments()
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        allowed, source = self._has_permission(request.user, "delete")
        if not allowed:
            return self._deny(
                source, "You need delete permission to remove prepayments."
            )
        
        # Check if prepayment has posted invoices
        prepayment = self.get_object()
        posted_invoices_count = prepayment.posted_sales_invoices.count()
        
        if posted_invoices_count > 0:
            return Response(
                {
                    "detail": f"Cannot delete prepayment. This prepayment has {posted_invoices_count} posted invoice(s) associated with it. Please reverse or delete the invoices first."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)

    def _ensure_not_general_customer(self, document):
        from sales.enums import CustomerType

        if document.customer.customer_type == CustomerType.General.name:
            return Response(
                {
                    "detail": "Prepayments cannot be recorded or posted for the general/walk-in "
                    "customer. Select a named customer."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @action(detail=False, methods=["post"], url_path="record_from_pos")
    def record_from_pos(self, request):
        """
        Create a prepayment from POS cart lines, apply installment amount, and post in one transaction.

        Optional ``prepayment_id``: append cart lines to that document (same customer), then apply
        installment and post. Lines may be empty when ``prepayment_id`` is set (payment-only top-up).
        """
        ins_ok, ins_src = self._has_permission(request.user, "insert")
        if not ins_ok:
            return self._deny(
                ins_src,
                "You need insert permission to record prepayments from POS.",
            )
        mod_ok, mod_src = self._has_permission(request.user, "modify")
        if not mod_ok:
            return self._deny(
                mod_src,
                "You need modify permission to post prepayments from POS.",
            )

        customer_id = request.data.get("customer")
        document_date = request.data.get("document_date")
        posting_date = request.data.get("posting_date")
        raw_lines = request.data.get("lines")
        prepayment_id = request.data.get("prepayment_id")
        installment_amount = request.data.get("installment_amount")
        payment_method_id = request.data.get("payment_method_id")
        description = request.data.get("description", "") or ""

        if customer_id is None:
            return Response(
                {"detail": "customer is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if raw_lines is not None and not isinstance(raw_lines, list):
            return Response(
                {"detail": "lines must be a list when provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        lines = list(raw_lines) if raw_lines is not None else []

        try:
            prepayment_id_int = (
                int(prepayment_id) if prepayment_id is not None else None
            )
        except (TypeError, ValueError):
            return Response(
                {"detail": "prepayment_id must be a valid integer when provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if prepayment_id_int is None and not lines:
            return Response(
                {"detail": "lines must be a non-empty list for a new prepayment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if prepayment_id_int is not None and not lines:
            # Payment-only top-up on existing document (no new cart lines)
            pass

        if installment_amount is None:
            return Response(
                {"detail": "installment_amount is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not payment_method_id:
            return Response(
                {"detail": "payment_method_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            installment_decimal = Decimal(str(installment_amount))
            if installment_decimal <= Decimal("0.00"):
                return Response(
                    {"detail": "installment_amount must be greater than zero."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError, ArithmeticError):
            return Response(
                {"detail": "Invalid installment_amount format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment_method = PaymentMethod.objects.get(id=int(payment_method_id))
        except (PaymentMethod.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": f"Payment method with id {payment_method_id} not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from sales.enums import CustomerType
        from sales.models import Customer, CustomerPostingGroup
        from postings.models import GeneralBusinessPostingGroup

        try:
            customer_obj = Customer.objects.select_related(
                "general_business_posting_group",
                "customer_posting_group",
            ).get(pk=int(customer_id))
        except (Customer.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "Customer not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if customer_obj.customer_type == CustomerType.General.name:
            return Response(
                {
                    "detail": "Prepayments cannot be recorded or posted for the general/walk-in "
                    "customer. Select a named customer."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_updates = []
        if not customer_obj.customer_posting_group_id:
            cpg = CustomerPostingGroup.objects.first()
            if not cpg:
                return Response(
                    {
                        "detail": "No Customer Posting Group is configured. "
                        "Import tenant setup data or configure posting groups in admin."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            customer_obj.customer_posting_group = cpg
            customer_updates.append("customer_posting_group")

        if not customer_obj.general_business_posting_group_id:
            gbp = GeneralBusinessPostingGroup.objects.first()
            if not gbp:
                return Response(
                    {
                        "detail": "No General Business Posting Group is configured. "
                        "Import tenant setup data or configure posting groups in admin."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            customer_obj.general_business_posting_group = gbp
            customer_updates.append("general_business_posting_group")

        if customer_updates:
            customer_obj.save(update_fields=customer_updates)

        line_norm = PreaymentDetailSerializer(context={"request": request})

        try:
            with transaction.atomic():
                if prepayment_id_int is not None:
                    document = self.get_queryset().filter(pk=prepayment_id_int).first()
                    if not document:
                        raise ValidationError(
                            "Prepayment not found or not accessible in this branch."
                        )
                    try:
                        cid = int(customer_id)
                    except (TypeError, ValueError):
                        raise ValidationError("Invalid customer id.")
                    if document.customer_id != cid:
                        raise ValidationError(
                            "The selected prepayment belongs to a different customer."
                        )
                    if document.status == PrepaymentStatus.CANCELLED:
                        raise ValidationError("This prepayment is cancelled.")
                    document.assert_can_collect_installment()
                    for line_data in lines:
                        normalized = line_norm._normalize_line_payload(
                            dict(line_data or {})
                        )
                        has_item = normalized.get("item") is not None
                        has_desc = bool((normalized.get("description") or "").strip())
                        if not has_item and not has_desc:
                            continue
                        normalized = line_norm._apply_line_dimensions(
                            document, line_data, normalized
                        )
                        PreaymentLine.objects.create(document=document, **normalized)
                    document.refresh_from_db()
                    document.recalculate_totals()
                else:
                    payload = {
                        "customer": customer_id,
                        "document_date": document_date or timezone.now().date(),
                        "posting_date": posting_date or timezone.now().date(),
                        "description": description,
                        "lines": lines,
                    }
                    serializer = PreaymentDetailSerializer(
                        data=payload,
                        context={"request": request},
                    )
                    serializer.is_valid(raise_exception=True)
                    document = serializer.save()
                    document.refresh_from_db()
                    document.recalculate_totals()

                target = document.total_amount or Decimal("0.00")
                invoiced_pre = document.total_prepayment_invoiced or Decimal("0.00")
                remaining_collectible = target - invoiced_pre
                if remaining_collectible < Decimal("0.00"):
                    remaining_collectible = Decimal("0.00")

                if installment_decimal > remaining_collectible:
                    raise ValidationError(
                        f"Installment amount {installment_decimal} exceeds remaining "
                        f"collectible {remaining_collectible} for this prepayment."
                    )

                from financials.management.commands.seed_prepayment_accounts import (
                    ensure_prepayment_accounts,
                    ensure_prepayment_posting_setup_pair,
                )

                ensure_prepayment_accounts()
                ensure_prepayment_posting_setup_pair()

                draft, created = PreaymentInstallmentDraft.objects.get_or_create(
                    document=document,
                    defaults={
                        "amount": installment_decimal,
                        "updated_by": request.user,
                    },
                )
                if not created:
                    draft.amount = installment_decimal
                    draft.updated_by = request.user
                    draft.save(
                        update_fields=["amount", "updated_by", "updated_at"]
                    )

                posting_result = document.post_document(
                    request.user, payment_method=payment_method
                )
        except ValidationError as exc:
            if hasattr(exc, "detail"):
                if isinstance(exc.detail, dict):
                    return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
                return Response({"detail": exc.detail}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ConfigurationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logging.getLogger(__name__).exception("record_from_pos failed: %s", exc)
            return Response(
                {"detail": f"An unexpected error occurred: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        document.refresh_from_db()
        out_serializer = PreaymentDetailSerializer(
            document, context={"request": request}
        )
        total_amt = document.total_amount or Decimal("0.00")
        invoiced = document.total_prepayment_invoiced or Decimal("0.00")
        remaining = total_amt - invoiced
        if remaining < Decimal("0.00"):
            remaining = Decimal("0.00")

        return Response(
            {
                "prepayment": out_serializer.data,
                "posted_invoice_no": posting_result["posted_invoice"].no,
                "transaction_no": posting_result["transaction_no"],
                "installment_amount_applied": str(installment_decimal),
                "total_amount": str(total_amt),
                "total_prepayment_invoiced": str(invoiced),
                "remaining": str(remaining),
            }
        )

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="preview")
    def preview_posting(self, request, pk=None):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source, "You need read permission to preview the posting entries."
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except PaymentMethod.DoesNotExist:
                return Response(
                    {"detail": f"Payment method with id {payment_method_id} not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            preview_data = document.build_posting_preview(user=request.user, payment_method=payment_method)
            serialized = self._serialize_preview(preview_data)
            serializer = PrepaymentPreviewSerializer(data=serialized)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="post")
    def post_document(self, request, pk=None):
        import sys
        print(f"[POST PREPAYMENT] ===== METHOD CALLED =====", file=sys.stderr, flush=True)
        print(f"[POST PREPAYMENT] ===== METHOD CALLED =====", flush=True)
        
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            print(f"[POST PREPAYMENT] Permission denied", flush=True)
            return self._deny(
                source, "You need modify permission to post a prepayment invoice."
            )

        document = self.get_object()
        print(f"[POST PREPAYMENT] Document retrieved: {document.id}", flush=True)

        gen_resp = self._ensure_not_general_customer(document)
        if gen_resp is not None:
            return gen_resp

        # Get payment_method_id from request data if provided
        payment_method = None
        logger = logging.getLogger(__name__)
        
        # Try multiple ways to access the data
        print(f"[POST PREPAYMENT] Request data type: {type(request.data)}", flush=True)
        print(f"[POST PREPAYMENT] Request data: {request.data}", flush=True)
        print(f"[POST PREPAYMENT] Request data dict: {dict(request.data) if hasattr(request.data, '__iter__') else 'N/A'}", flush=True)
        print(f"[POST PREPAYMENT] Request body (raw): {request.body}", flush=True)
        print(f"[POST PREPAYMENT] Request content_type: {request.content_type}", flush=True)
        
        # Try different ways to get payment_method_id
        payment_method_id = None
        if hasattr(request.data, 'get'):
            payment_method_id = request.data.get("payment_method_id")
        elif isinstance(request.data, dict):
            payment_method_id = request.data.get("payment_method_id")
        else:
            # Try to convert to dict
            try:
                data_dict = dict(request.data)
                payment_method_id = data_dict.get("payment_method_id")
            except:
                pass
        
        # Also try direct attribute access
        if not payment_method_id and hasattr(request.data, 'payment_method_id'):
            payment_method_id = request.data.payment_method_id
            
        print(f"[POST PREPAYMENT] payment_method_id from request: {payment_method_id} (type: {type(payment_method_id)})", flush=True)
        logger.error(f"[POST PREPAYMENT] Request data: {request.data}")
        logger.error(f"[POST PREPAYMENT] payment_method_id from request: {payment_method_id} (type: {type(payment_method_id)})")
        
        if payment_method_id:
            try:
                # Convert to int in case it's a string
                payment_method_id = int(payment_method_id)
                print(f"[POST PREPAYMENT] Converted payment_method_id to int: {payment_method_id}")
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
                print(f"[POST PREPAYMENT] Found payment method: {payment_method} (id: {payment_method.id}, code: {payment_method.code})")
                logger.error(f"[POST PREPAYMENT] Found payment method: {payment_method} (id: {payment_method.id}, code: {payment_method.code})")
            except (PaymentMethod.DoesNotExist, ValueError, TypeError) as e:
                print(f"[POST PREPAYMENT] Error getting payment method: {type(e).__name__}: {e}")
                logger.error(f"[POST PREPAYMENT] Error getting payment method: {type(e).__name__}: {e}")
                if isinstance(e, PaymentMethod.DoesNotExist):
                    return Response(
                        {"detail": f"Payment method with id {payment_method_id} not found."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    return Response(
                        {"detail": f"Invalid payment_method_id: {payment_method_id}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        else:
            print(f"[POST PREPAYMENT] No payment_method_id provided in request data")
            logger.error(f"[POST PREPAYMENT] No payment_method_id provided in request data")
        
        print(f"[POST PREPAYMENT] Calling post_document with payment_method: {payment_method}")
        logger.error(f"[POST PREPAYMENT] Calling post_document with payment_method: {payment_method}")
        
        try:
            with transaction.atomic():
                posting_result = document.post_document(request.user, payment_method=payment_method)
            serializer = self.get_serializer(document)
            return Response(
                {
                    "prepayment": serializer.data,
                    "posted_invoice_no": posting_result["posted_invoice"].no,
                    "transaction_no": posting_result["transaction_no"],
                }
            )
        except (ValidationError, DjangoValidationError) as exc:
            logger.error(f"[POST PREPAYMENT] ValidationError caught: {exc} (type: {type(exc)})")
            error_detail = str(exc)
            if hasattr(exc, 'message_dict'):
                error_detail = exc.message_dict
            elif hasattr(exc, 'messages'):
                error_detail = list(exc.messages)
            logger.error(f"[POST PREPAYMENT] Error detail to return: {error_detail}")
            return Response({"detail": error_detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception(f"[POST PREPAYMENT] Unexpected error: {exc}")
            return Response({"detail": f"An unexpected error occurred: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["post"], url_path="preview-final-invoice")
    def preview_final_invoice_posting(self, request, pk=None):
        allowed, source = self._has_permission(request.user, "read")
        if not allowed:
            return self._deny(
                source,
                "You need read permission to preview the final invoice posting entries.",
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except PaymentMethod.DoesNotExist:
                return Response(
                    {"detail": f"Payment method with id {payment_method_id} not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            preview_data = document.build_final_invoice_posting_preview(
                user=request.user, payment_method=payment_method
            )
            serialized = self._serialize_final_invoice_preview(preview_data)
            serializer = PrepaymentPreviewSerializer(data=serialized)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="post-final-invoice")
    def post_final_invoice(self, request, pk=None):
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to post a final invoice."
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except PaymentMethod.DoesNotExist:
                return Response(
                    {"detail": f"Payment method with id {payment_method_id} not found."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            with transaction.atomic():
                posting_result = document.post_final_invoice(request.user, payment_method=payment_method)
            serializer = self.get_serializer(document)
            return Response(
                {
                    "prepayment": serializer.data,
                    "posted_invoice_no": posting_result["posted_invoice"].no,
                    "message": posting_result["message"],
                }
            )
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        """
        Mirror of Sales 'update_lines' to upsert/delete prepayment lines.
        Accepts payload:
        {
          "system_id": "<optional>",
          "id": <document id>,
          "lines": [{ id, ... } | { id, is_deleted: true } | { ...create... }]
        }
        """
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update prepayment lines."
            )

        document = self.get_object()
        try:
            document.assert_open_for_installments()
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        raw_lines = request.data.get("lines", []) or []

        # Get current invoiced amount before any changes
        current_invoiced = document.total_prepayment_invoiced or Decimal("0.00")

        # First pass: hard-delete any lines explicitly marked for deletion
        to_delete_ids = []
        remaining_lines = []
        for payload in raw_lines:
            line_id = payload.get("id")
            is_deleted = payload.get("is_deleted")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None
            if is_deleted and line_id:
                to_delete_ids.append(line_id)
            else:
                # strip is_deleted before serializer update/create path
                if "is_deleted" in payload:
                    payload = {k: v for k, v in payload.items() if k != "is_deleted"}
                remaining_lines.append(payload)

        # Calculate what the new total would be after changes
        # We need to simulate the changes to validate before applying them
        from prepayment.models import PreaymentLine

        # Get current lines that won't be deleted or updated
        existing_line_ids = set(
            document.lines.exclude(id__in=to_delete_ids).values_list("id", flat=True)
        )

        # Track which lines are being updated
        updated_line_ids = set()
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None
            if line_id:
                updated_line_ids.add(line_id)

        # Calculate new total: include unchanged lines + updated/new lines
        new_total = Decimal("0.00")

        # Add unchanged lines (lines that exist but aren't being updated or deleted)
        unchanged_line_ids = existing_line_ids - updated_line_ids - set(to_delete_ids)
        for line in document.lines.filter(id__in=unchanged_line_ids):
            new_total += line.amount or Decimal("0.00")

        # Process remaining lines (updated or new) to calculate new total
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            if line_id and line_id in existing_line_ids:
                # Update existing line - calculate from payload values
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price
            else:
                # New line - calculate from payload
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price

        # Validate that new total is not below invoiced amount
        if new_total < current_invoiced:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                f"Total amount cannot be less than the invoiced amount of {format_currency(current_invoiced)}. "
                f"Current total would be {format_currency(new_total)}."
            )

        # Apply changes if validation passes
        try:
            if to_delete_ids:
                document.lines.filter(id__in=to_delete_ids).delete()
            # Second pass: upsert remaining lines via serializer
            if remaining_lines:
                serializer = self.get_serializer(
                    document, data={"lines": remaining_lines}, partial=True
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
            # Recalculate totals after mutations
            document.refresh_from_db()
            document.recalculate_totals()
        except DjangoValidationError as exc:
            # Convert Django ValidationError to DRF ValidationError
            # Django ValidationError can have messages as a list or dict
            if hasattr(exc, "message_dict") and exc.message_dict:
                # Form validation error with field-specific messages
                error_message = str(exc.message_dict)
            elif hasattr(exc, "messages") and exc.messages:
                # List of error messages - get first message
                if isinstance(exc.messages, list) and len(exc.messages) > 0:
                    error_message = str(exc.messages[0])
                elif isinstance(exc.messages, dict):
                    error_message = str(exc.messages)
                else:
                    error_message = str(exc.messages)
            else:
                # Fallback to string representation
                error_message = str(exc)
            # Raise DRF ValidationError which will return 400 Bad Request
            raise ValidationError(error_message)
        # Return fresh document (avoid stale prefetch)
        fresh_serializer = self.get_serializer(self.get_object())
        return Response(fresh_serializer.data)

    @action(detail=True, methods=["post"], url_path="installments")
    def update_installment(self, request, pk=None):
        """
        Create or update document-level installment draft.
        Payload: { "amount": 200000 }
        """
        allowed, source = self._has_permission(request.user, "modify")
        if not allowed:
            return self._deny(
                source, "You need modify permission to update installments."
            )

        document = self.get_object()

        gen_resp = self._ensure_not_general_customer(document)
        if gen_resp is not None:
            return gen_resp

        try:
            document.assert_can_collect_installment()
        except (ValidationError, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        amount = request.data.get("amount", None)

        if amount is None:
            return Response(
                {"detail": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(str(amount))
            if amount < Decimal("0.00"):
                return Response(
                    {"detail": "Amount cannot be negative"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid amount format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate amount doesn't exceed remaining collectible
        # Remaining collectible = total amount - amount already invoiced
        # We don't subtract existing draft because we're replacing it with the new amount
        # This matches the logic in remaining_prepayment property
        target = document.total_amount or Decimal("0.00")
        invoiced = document.total_prepayment_invoiced or Decimal("0.00")
        remaining_collectible = target - invoiced
        if remaining_collectible < Decimal("0.00"):
            remaining_collectible = Decimal("0.00")

        if amount > remaining_collectible:
            return Response(
                {
                    "detail": f"Installment amount {amount} exceeds remaining collectible {remaining_collectible}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create draft installment
        # Temporarily handle missing table until migrations are run
        # TODO: Remove this try/except after running migrations
        try:
            draft, created = PreaymentInstallmentDraft.objects.get_or_create(
                document=document,
                defaults={"amount": amount, "updated_by": request.user},
            )

            if not created:
                draft.amount = amount
                draft.updated_by = request.user
                draft.save(update_fields=["amount", "updated_by", "updated_at"])
        except ProgrammingError:
            # If table doesn't exist yet, return error message
            return Response(
                {
                    "detail": "Installment functionality is not available yet. Please run database migrations first."
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Return updated document
        serializer = self.get_serializer(self.get_object())
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _serialize_preview(self, preview_payload):
        gl_entries = []
        for entry in preview_payload["entries"]["gl_entries"]:
            gl_entries.append(
                {
                    "account_no": getattr(entry["gl_account"], "no", None),
                    "account_name": getattr(entry["gl_account"], "name", ""),
                    "description": entry["description"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(entry.get("global_dimension_1"), "code", None),
                }
            )

        customer_entries = []
        for entry in preview_payload["entries"]["customer_entries"]:
            customer_entries.append(
                {
                    "document_type": entry["document_type"],
                    "document_no": entry["document_no"],
                    "description": entry["description"],
                    "amount": entry["amount"],
                    "open": entry["open"],
                    "due_date": entry["due_date"],
                }
            )

        detailed_entries = []
        for entry in preview_payload["entries"]["detailed_customer_entries"]:
            detailed_entries.append(
                {
                    "entry_type": entry["entry_type"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        line_context = []
        for ctx in preview_payload["line_context"]:
            line_context.append(
                {
                    "line_id": ctx["line"].id if ctx.get("line") else None,
                    "label": ctx["label"],
                    "amount": ctx["amount"],
                    "collected_amount": ctx["collected_amount"],
                    "invoiced_amount": ctx["invoiced_amount"],
                    "target_total": ctx["target_total"],
                    "prepayment_account_no": getattr(
                        ctx["prepayment_account"], "no", ""
                    ),
                    "prepayment_account_name": getattr(
                        ctx["prepayment_account"], "name", ""
                    ),
                }
            )

        return {
            "transaction_no": preview_payload["transaction_no"],
            "total_deposit": preview_payload["total_deposit"],
            "has_cash_payment": preview_payload["has_cash_payment"],
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": line_context,
        }

    def _serialize_final_invoice_preview(self, preview_data):
        """Shape final-invoice preview for API / PostingPreviewModal."""
        entries = preview_data.get("entries", {})
        gl_entries = []
        for entry in entries.get("gl_entries", []):
            gl_entries.append(
                {
                    "account_no": getattr(entry.get("gl_account"), "no", None),
                    "account_name": getattr(entry.get("gl_account"), "name", ""),
                    "description": entry.get("description"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(
                        entry.get("global_dimension_1"), "code", None
                    ),
                }
            )

        customer_entries = []
        for entry in entries.get("customer_entries", []):
            customer_entries.append(
                {
                    "document_type": entry.get("document_type"),
                    "document_no": entry.get("document_no"),
                    "description": entry.get("description"),
                    "amount": entry.get("amount"),
                    "open": entry.get("open"),
                    "due_date": entry.get("due_date"),
                }
            )

        detailed_entries = []
        for entry in entries.get("detailed_customer_entries", []):
            detailed_entries.append(
                {
                    "entry_type": entry.get("entry_type"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        has_cash_payment = any(
            e.get("document_type") in ("Payment", "payment")
            for e in entries.get("customer_entries", [])
        )

        return {
            "transaction_no": preview_data.get("transaction_no"),
            "total_deposit": preview_data.get("prepayment_to_deduct", 0),
            "total_invoice_amount": preview_data.get("total_invoice_amount"),
            "prepayment_to_deduct": preview_data.get("prepayment_to_deduct"),
            "net_receivables": preview_data.get("net_receivables"),
            "has_cash_payment": has_cash_payment,
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": [],
            "posted_invoice_lines": preview_data.get("posted_invoice_lines", []),
        }

    @action(detail=True, methods=["post"], url_path="post")
    def post_document(self, request, pk=None):

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to post a prepayment invoice."
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method_id = int(payment_method_id)
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except (PaymentMethod.DoesNotExist, ValueError, TypeError):
                pass

        try:

            with transaction.atomic():

                posting_result = document.post_document(request.user, payment_method=payment_method)

            serializer = self.get_serializer(document)

            return Response(
                {
                    "prepayment": serializer.data,
                    "posted_invoice_no": posting_result["posted_invoice"].no,
                    "transaction_no": posting_result["transaction_no"],
                }
            )

        except (ValidationError, DjangoValidationError) as exc:

            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        """

        Mirror of Sales 'update_lines' to upsert/delete prepayment lines.

        Accepts payload:

        {

          "system_id": "<optional>",

          "id": <document id>,

          "lines": [{ id, ... } | { id, is_deleted: true } | { ...create... }]

        }

        """

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to update prepayment lines."
            )

        document = self.get_object()

        raw_lines = request.data.get("lines", []) or []

        # Get current invoiced amount before any changes
        current_invoiced = document.total_prepayment_invoiced or Decimal("0.00")

        # First pass: hard-delete any lines explicitly marked for deletion

        to_delete_ids = []

        remaining_lines = []

        for payload in raw_lines:

            line_id = payload.get("id")

            is_deleted = payload.get("is_deleted")

            try:

                line_id = int(line_id) if line_id is not None else None

            except (TypeError, ValueError):

                line_id = None

            if is_deleted and line_id:

                to_delete_ids.append(line_id)

            else:

                # strip is_deleted before serializer update/create path

                if "is_deleted" in payload:

                    payload = {k: v for k, v in payload.items() if k != "is_deleted"}

                remaining_lines.append(payload)

        # Calculate what the new total would be after changes
        # We need to simulate the changes to validate before applying them
        from prepayment.models import PreaymentLine

        # Get current lines that won't be deleted or updated
        existing_line_ids = set(
            document.lines.exclude(id__in=to_delete_ids).values_list("id", flat=True)
        )

        # Track which lines are being updated
        updated_line_ids = set()
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None
            if line_id:
                updated_line_ids.add(line_id)

        # Calculate new total: include unchanged lines + updated/new lines
        new_total = Decimal("0.00")

        # Add unchanged lines (lines that exist but aren't being updated or deleted)
        unchanged_line_ids = existing_line_ids - updated_line_ids - set(to_delete_ids)
        for line in document.lines.filter(id__in=unchanged_line_ids):
            new_total += line.amount or Decimal("0.00")

        # Process remaining lines (updated or new) to calculate new total
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            if line_id and line_id in existing_line_ids:
                # Update existing line - calculate from payload values
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price
            else:
                # New line - calculate from payload
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price

        # Validate that new total is not below invoiced amount
        if new_total < current_invoiced:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                f"Total amount cannot be less than the invoiced amount of {format_currency(current_invoiced)}. "
                f"Current total would be {format_currency(new_total)}."
            )

        # Apply changes if validation passes
        try:
            if to_delete_ids:

                document.lines.filter(id__in=to_delete_ids).delete()

            # Second pass: upsert remaining lines via serializer

            if remaining_lines:

                serializer = self.get_serializer(
                    document, data={"lines": remaining_lines}, partial=True
                )

                serializer.is_valid(raise_exception=True)

                serializer.save()

            # Recalculate totals after mutations

            document.refresh_from_db()

            document.recalculate_totals()
        except DjangoValidationError as exc:
            # Convert Django ValidationError to DRF ValidationError
            # Django ValidationError can have messages as a list or dict
            if hasattr(exc, "message_dict") and exc.message_dict:
                # Form validation error with field-specific messages
                error_message = str(exc.message_dict)
            elif hasattr(exc, "messages") and exc.messages:
                # List of error messages - get first message
                if isinstance(exc.messages, list) and len(exc.messages) > 0:
                    error_message = str(exc.messages[0])
                elif isinstance(exc.messages, dict):
                    error_message = str(exc.messages)
                else:
                    error_message = str(exc.messages)
            else:
                # Fallback to string representation
                error_message = str(exc)
            # Raise DRF ValidationError which will return 400 Bad Request
            raise ValidationError(error_message)

        # Return fresh document (avoid stale prefetch)

        fresh_serializer = self.get_serializer(self.get_object())

        return Response(fresh_serializer.data)

    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------

    def _serialize_preview(self, preview_payload):

        gl_entries = []

        for entry in preview_payload["entries"]["gl_entries"]:

            gl_entries.append(
                {
                    "account_no": getattr(entry["gl_account"], "no", None),
                    "account_name": getattr(entry["gl_account"], "name", ""),
                    "description": entry["description"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(entry.get("global_dimension_1"), "code", None),
                }
            )

        customer_entries = []

        for entry in preview_payload["entries"]["customer_entries"]:

            customer_entries.append(
                {
                    "document_type": entry["document_type"],
                    "document_no": entry["document_no"],
                    "description": entry["description"],
                    "amount": entry["amount"],
                    "open": entry["open"],
                    "due_date": entry["due_date"],
                }
            )

        detailed_entries = []

        for entry in preview_payload["entries"]["detailed_customer_entries"]:

            detailed_entries.append(
                {
                    "entry_type": entry["entry_type"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        line_context = []

        for ctx in preview_payload["line_context"]:

            line_context.append(
                {
                    "line_id": ctx["line"].id if ctx.get("line") else None,
                    "label": ctx["label"],
                    "amount": ctx["amount"],
                    "collected_amount": ctx["collected_amount"],
                    "invoiced_amount": ctx["invoiced_amount"],
                    "target_total": ctx["target_total"],
                    "prepayment_account_no": getattr(
                        ctx["prepayment_account"], "no", ""
                    ),
                    "prepayment_account_name": getattr(
                        ctx["prepayment_account"], "name", ""
                    ),
                }
            )

        return {
            "transaction_no": preview_payload["transaction_no"],
            "total_deposit": preview_payload["total_deposit"],
            "has_cash_payment": preview_payload["has_cash_payment"],
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": line_context,
        }

    def _serialize_final_invoice_preview(self, preview_data):
        """Shape final-invoice preview for API / PostingPreviewModal."""
        entries = preview_data.get("entries", {})
        gl_entries = []
        for entry in entries.get("gl_entries", []):
            gl_entries.append(
                {
                    "account_no": getattr(entry.get("gl_account"), "no", None),
                    "account_name": getattr(entry.get("gl_account"), "name", ""),
                    "description": entry.get("description"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(
                        entry.get("global_dimension_1"), "code", None
                    ),
                }
            )

        customer_entries = []
        for entry in entries.get("customer_entries", []):
            customer_entries.append(
                {
                    "document_type": entry.get("document_type"),
                    "document_no": entry.get("document_no"),
                    "description": entry.get("description"),
                    "amount": entry.get("amount"),
                    "open": entry.get("open"),
                    "due_date": entry.get("due_date"),
                }
            )

        detailed_entries = []
        for entry in entries.get("detailed_customer_entries", []):
            detailed_entries.append(
                {
                    "entry_type": entry.get("entry_type"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        has_cash_payment = any(
            e.get("document_type") in ("Payment", "payment")
            for e in entries.get("customer_entries", [])
        )

        return {
            "transaction_no": preview_data.get("transaction_no"),
            "total_deposit": preview_data.get("prepayment_to_deduct", 0),
            "total_invoice_amount": preview_data.get("total_invoice_amount"),
            "prepayment_to_deduct": preview_data.get("prepayment_to_deduct"),
            "net_receivables": preview_data.get("net_receivables"),
            "has_cash_payment": has_cash_payment,
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": [],
            "posted_invoice_lines": preview_data.get("posted_invoice_lines", []),
        }

    @action(detail=True, methods=["post"], url_path="post")
    def post_document(self, request, pk=None):

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to post a prepayment invoice."
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method_id = int(payment_method_id)
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except (PaymentMethod.DoesNotExist, ValueError, TypeError):
                pass

        try:

            with transaction.atomic():

                posting_result = document.post_document(request.user, payment_method=payment_method)

            serializer = self.get_serializer(document)

            return Response(
                {
                    "prepayment": serializer.data,
                    "posted_invoice_no": posting_result["posted_invoice"].no,
                    "transaction_no": posting_result["transaction_no"],
                }
            )

        except (ValidationError, DjangoValidationError) as exc:

            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        """

        Mirror of Sales 'update_lines' to upsert/delete prepayment lines.

        Accepts payload:

        {

          "system_id": "<optional>",

          "id": <document id>,

          "lines": [{ id, ... } | { id, is_deleted: true } | { ...create... }]

        }

        """

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to update prepayment lines."
            )

        document = self.get_object()

        raw_lines = request.data.get("lines", []) or []

        # Get current invoiced amount before any changes
        current_invoiced = document.total_prepayment_invoiced or Decimal("0.00")

        # First pass: hard-delete any lines explicitly marked for deletion

        to_delete_ids = []

        remaining_lines = []

        for payload in raw_lines:

            line_id = payload.get("id")

            is_deleted = payload.get("is_deleted")

            try:

                line_id = int(line_id) if line_id is not None else None

            except (TypeError, ValueError):

                line_id = None

            if is_deleted and line_id:

                to_delete_ids.append(line_id)

            else:

                # strip is_deleted before serializer update/create path

                if "is_deleted" in payload:

                    payload = {k: v for k, v in payload.items() if k != "is_deleted"}

                remaining_lines.append(payload)

        # Calculate what the new total would be after changes
        # We need to simulate the changes to validate before applying them
        from prepayment.models import PreaymentLine

        # Get current lines that won't be deleted or updated
        existing_line_ids = set(
            document.lines.exclude(id__in=to_delete_ids).values_list("id", flat=True)
        )

        # Track which lines are being updated
        updated_line_ids = set()
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None
            if line_id:
                updated_line_ids.add(line_id)

        # Calculate new total: include unchanged lines + updated/new lines
        new_total = Decimal("0.00")

        # Add unchanged lines (lines that exist but aren't being updated or deleted)
        unchanged_line_ids = existing_line_ids - updated_line_ids - set(to_delete_ids)
        for line in document.lines.filter(id__in=unchanged_line_ids):
            new_total += line.amount or Decimal("0.00")

        # Process remaining lines (updated or new) to calculate new total
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            if line_id and line_id in existing_line_ids:
                # Update existing line - calculate from payload values
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price
            else:
                # New line - calculate from payload
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price

        # Validate that new total is not below invoiced amount
        if new_total < current_invoiced:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                f"Total amount cannot be less than the invoiced amount of {format_currency(current_invoiced)}. "
                f"Current total would be {format_currency(new_total)}."
            )

        # Apply changes if validation passes
        try:
            if to_delete_ids:

                document.lines.filter(id__in=to_delete_ids).delete()

            # Second pass: upsert remaining lines via serializer

            if remaining_lines:

                serializer = self.get_serializer(
                    document, data={"lines": remaining_lines}, partial=True
                )

                serializer.is_valid(raise_exception=True)

                serializer.save()

            # Recalculate totals after mutations

            document.refresh_from_db()

            document.recalculate_totals()
        except DjangoValidationError as exc:
            # Convert Django ValidationError to DRF ValidationError
            # Django ValidationError can have messages as a list or dict
            if hasattr(exc, "message_dict") and exc.message_dict:
                # Form validation error with field-specific messages
                error_message = str(exc.message_dict)
            elif hasattr(exc, "messages") and exc.messages:
                # List of error messages - get first message
                if isinstance(exc.messages, list) and len(exc.messages) > 0:
                    error_message = str(exc.messages[0])
                elif isinstance(exc.messages, dict):
                    error_message = str(exc.messages)
                else:
                    error_message = str(exc.messages)
            else:
                # Fallback to string representation
                error_message = str(exc)
            # Raise DRF ValidationError which will return 400 Bad Request
            raise ValidationError(error_message)

        # Return fresh document (avoid stale prefetch)

        fresh_serializer = self.get_serializer(self.get_object())

        return Response(fresh_serializer.data)

    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------

    def _serialize_preview(self, preview_payload):

        gl_entries = []

        for entry in preview_payload["entries"]["gl_entries"]:

            gl_entries.append(
                {
                    "account_no": getattr(entry["gl_account"], "no", None),
                    "account_name": getattr(entry["gl_account"], "name", ""),
                    "description": entry["description"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(entry.get("global_dimension_1"), "code", None),
                }
            )

        customer_entries = []

        for entry in preview_payload["entries"]["customer_entries"]:

            customer_entries.append(
                {
                    "document_type": entry["document_type"],
                    "document_no": entry["document_no"],
                    "description": entry["description"],
                    "amount": entry["amount"],
                    "open": entry["open"],
                    "due_date": entry["due_date"],
                }
            )

        detailed_entries = []

        for entry in preview_payload["entries"]["detailed_customer_entries"]:

            detailed_entries.append(
                {
                    "entry_type": entry["entry_type"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        line_context = []

        for ctx in preview_payload["line_context"]:

            line_context.append(
                {
                    "line_id": ctx["line"].id if ctx.get("line") else None,
                    "label": ctx["label"],
                    "amount": ctx["amount"],
                    "collected_amount": ctx["collected_amount"],
                    "invoiced_amount": ctx["invoiced_amount"],
                    "target_total": ctx["target_total"],
                    "prepayment_account_no": getattr(
                        ctx["prepayment_account"], "no", ""
                    ),
                    "prepayment_account_name": getattr(
                        ctx["prepayment_account"], "name", ""
                    ),
                }
            )

        return {
            "transaction_no": preview_payload["transaction_no"],
            "total_deposit": preview_payload["total_deposit"],
            "has_cash_payment": preview_payload["has_cash_payment"],
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": line_context,
        }

    def _serialize_final_invoice_preview(self, preview_data):
        """Shape final-invoice preview for API / PostingPreviewModal."""
        entries = preview_data.get("entries", {})
        gl_entries = []
        for entry in entries.get("gl_entries", []):
            gl_entries.append(
                {
                    "account_no": getattr(entry.get("gl_account"), "no", None),
                    "account_name": getattr(entry.get("gl_account"), "name", ""),
                    "description": entry.get("description"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(
                        entry.get("global_dimension_1"), "code", None
                    ),
                }
            )

        customer_entries = []
        for entry in entries.get("customer_entries", []):
            customer_entries.append(
                {
                    "document_type": entry.get("document_type"),
                    "document_no": entry.get("document_no"),
                    "description": entry.get("description"),
                    "amount": entry.get("amount"),
                    "open": entry.get("open"),
                    "due_date": entry.get("due_date"),
                }
            )

        detailed_entries = []
        for entry in entries.get("detailed_customer_entries", []):
            detailed_entries.append(
                {
                    "entry_type": entry.get("entry_type"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        has_cash_payment = any(
            e.get("document_type") in ("Payment", "payment")
            for e in entries.get("customer_entries", [])
        )

        return {
            "transaction_no": preview_data.get("transaction_no"),
            "total_deposit": preview_data.get("prepayment_to_deduct", 0),
            "total_invoice_amount": preview_data.get("total_invoice_amount"),
            "prepayment_to_deduct": preview_data.get("prepayment_to_deduct"),
            "net_receivables": preview_data.get("net_receivables"),
            "has_cash_payment": has_cash_payment,
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": [],
            "posted_invoice_lines": preview_data.get("posted_invoice_lines", []),
        }

    @action(detail=True, methods=["post"], url_path="post")
    def post_document(self, request, pk=None):

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to post a prepayment invoice."
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method_id = int(payment_method_id)
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except (PaymentMethod.DoesNotExist, ValueError, TypeError):
                pass

        try:

            with transaction.atomic():

                posting_result = document.post_document(request.user, payment_method=payment_method)

            serializer = self.get_serializer(document)

            return Response(
                {
                    "prepayment": serializer.data,
                    "posted_invoice_no": posting_result["posted_invoice"].no,
                    "transaction_no": posting_result["transaction_no"],
                }
            )

        except (ValidationError, DjangoValidationError) as exc:

            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        """

        Mirror of Sales 'update_lines' to upsert/delete prepayment lines.

        Accepts payload:

        {

          "system_id": "<optional>",

          "id": <document id>,

          "lines": [{ id, ... } | { id, is_deleted: true } | { ...create... }]

        }

        """

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to update prepayment lines."
            )

        document = self.get_object()

        raw_lines = request.data.get("lines", []) or []

        # Get current invoiced amount before any changes
        current_invoiced = document.total_prepayment_invoiced or Decimal("0.00")

        # First pass: hard-delete any lines explicitly marked for deletion

        to_delete_ids = []

        remaining_lines = []

        for payload in raw_lines:

            line_id = payload.get("id")

            is_deleted = payload.get("is_deleted")

            try:

                line_id = int(line_id) if line_id is not None else None

            except (TypeError, ValueError):

                line_id = None

            if is_deleted and line_id:

                to_delete_ids.append(line_id)

            else:

                # strip is_deleted before serializer update/create path

                if "is_deleted" in payload:

                    payload = {k: v for k, v in payload.items() if k != "is_deleted"}

                remaining_lines.append(payload)

        # Calculate what the new total would be after changes
        # We need to simulate the changes to validate before applying them
        from prepayment.models import PreaymentLine

        # Get current lines that won't be deleted or updated
        existing_line_ids = set(
            document.lines.exclude(id__in=to_delete_ids).values_list("id", flat=True)
        )

        # Track which lines are being updated
        updated_line_ids = set()
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None
            if line_id:
                updated_line_ids.add(line_id)

        # Calculate new total: include unchanged lines + updated/new lines
        new_total = Decimal("0.00")

        # Add unchanged lines (lines that exist but aren't being updated or deleted)
        unchanged_line_ids = existing_line_ids - updated_line_ids - set(to_delete_ids)
        for line in document.lines.filter(id__in=unchanged_line_ids):
            new_total += line.amount or Decimal("0.00")

        # Process remaining lines (updated or new) to calculate new total
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            if line_id and line_id in existing_line_ids:
                # Update existing line - calculate from payload values
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price
            else:
                # New line - calculate from payload
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price

        # Validate that new total is not below invoiced amount
        if new_total < current_invoiced:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                f"Total amount cannot be less than the invoiced amount of {format_currency(current_invoiced)}. "
                f"Current total would be {format_currency(new_total)}."
            )

        # Apply changes if validation passes
        try:
            if to_delete_ids:

                document.lines.filter(id__in=to_delete_ids).delete()

            # Second pass: upsert remaining lines via serializer

            if remaining_lines:

                serializer = self.get_serializer(
                    document, data={"lines": remaining_lines}, partial=True
                )

                serializer.is_valid(raise_exception=True)

                serializer.save()

            # Recalculate totals after mutations

            document.refresh_from_db()

            document.recalculate_totals()
        except DjangoValidationError as exc:
            # Convert Django ValidationError to DRF ValidationError
            # Django ValidationError can have messages as a list or dict
            if hasattr(exc, "message_dict") and exc.message_dict:
                # Form validation error with field-specific messages
                error_message = str(exc.message_dict)
            elif hasattr(exc, "messages") and exc.messages:
                # List of error messages - get first message
                if isinstance(exc.messages, list) and len(exc.messages) > 0:
                    error_message = str(exc.messages[0])
                elif isinstance(exc.messages, dict):
                    error_message = str(exc.messages)
                else:
                    error_message = str(exc.messages)
            else:
                # Fallback to string representation
                error_message = str(exc)
            # Raise DRF ValidationError which will return 400 Bad Request
            raise ValidationError(error_message)

        # Return fresh document (avoid stale prefetch)

        fresh_serializer = self.get_serializer(self.get_object())

        return Response(fresh_serializer.data)

    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------

    def _serialize_preview(self, preview_payload):

        gl_entries = []

        for entry in preview_payload["entries"]["gl_entries"]:

            gl_entries.append(
                {
                    "account_no": getattr(entry["gl_account"], "no", None),
                    "account_name": getattr(entry["gl_account"], "name", ""),
                    "description": entry["description"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(entry.get("global_dimension_1"), "code", None),
                }
            )

        customer_entries = []

        for entry in preview_payload["entries"]["customer_entries"]:

            customer_entries.append(
                {
                    "document_type": entry["document_type"],
                    "document_no": entry["document_no"],
                    "description": entry["description"],
                    "amount": entry["amount"],
                    "open": entry["open"],
                    "due_date": entry["due_date"],
                }
            )

        detailed_entries = []

        for entry in preview_payload["entries"]["detailed_customer_entries"]:

            detailed_entries.append(
                {
                    "entry_type": entry["entry_type"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        line_context = []

        for ctx in preview_payload["line_context"]:

            line_context.append(
                {
                    "line_id": ctx["line"].id if ctx.get("line") else None,
                    "label": ctx["label"],
                    "amount": ctx["amount"],
                    "collected_amount": ctx["collected_amount"],
                    "invoiced_amount": ctx["invoiced_amount"],
                    "target_total": ctx["target_total"],
                    "prepayment_account_no": getattr(
                        ctx["prepayment_account"], "no", ""
                    ),
                    "prepayment_account_name": getattr(
                        ctx["prepayment_account"], "name", ""
                    ),
                }
            )

        return {
            "transaction_no": preview_payload["transaction_no"],
            "total_deposit": preview_payload["total_deposit"],
            "has_cash_payment": preview_payload["has_cash_payment"],
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": line_context,
        }

    def _serialize_final_invoice_preview(self, preview_data):
        """Shape final-invoice preview for API / PostingPreviewModal."""
        entries = preview_data.get("entries", {})
        gl_entries = []
        for entry in entries.get("gl_entries", []):
            gl_entries.append(
                {
                    "account_no": getattr(entry.get("gl_account"), "no", None),
                    "account_name": getattr(entry.get("gl_account"), "name", ""),
                    "description": entry.get("description"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(
                        entry.get("global_dimension_1"), "code", None
                    ),
                }
            )

        customer_entries = []
        for entry in entries.get("customer_entries", []):
            customer_entries.append(
                {
                    "document_type": entry.get("document_type"),
                    "document_no": entry.get("document_no"),
                    "description": entry.get("description"),
                    "amount": entry.get("amount"),
                    "open": entry.get("open"),
                    "due_date": entry.get("due_date"),
                }
            )

        detailed_entries = []
        for entry in entries.get("detailed_customer_entries", []):
            detailed_entries.append(
                {
                    "entry_type": entry.get("entry_type"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        has_cash_payment = any(
            e.get("document_type") in ("Payment", "payment")
            for e in entries.get("customer_entries", [])
        )

        return {
            "transaction_no": preview_data.get("transaction_no"),
            "total_deposit": preview_data.get("prepayment_to_deduct", 0),
            "total_invoice_amount": preview_data.get("total_invoice_amount"),
            "prepayment_to_deduct": preview_data.get("prepayment_to_deduct"),
            "net_receivables": preview_data.get("net_receivables"),
            "has_cash_payment": has_cash_payment,
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": [],
            "posted_invoice_lines": preview_data.get("posted_invoice_lines", []),
        }

    @action(detail=True, methods=["post"], url_path="post")
    def post_document(self, request, pk=None):

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to post a prepayment invoice."
            )

        document = self.get_object()
        
        # Get payment_method_id from request data if provided
        payment_method = None
        payment_method_id = request.data.get("payment_method_id")
        if payment_method_id:
            try:
                payment_method_id = int(payment_method_id)
                payment_method = PaymentMethod.objects.get(id=payment_method_id)
            except (PaymentMethod.DoesNotExist, ValueError, TypeError):
                pass

        try:

            with transaction.atomic():

                posting_result = document.post_document(request.user, payment_method=payment_method)

            serializer = self.get_serializer(document)

            return Response(
                {
                    "prepayment": serializer.data,
                    "posted_invoice_no": posting_result["posted_invoice"].no,
                    "transaction_no": posting_result["transaction_no"],
                }
            )

        except (ValidationError, DjangoValidationError) as exc:

            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="update_lines")
    def update_lines(self, request, pk=None):
        """

        Mirror of Sales 'update_lines' to upsert/delete prepayment lines.

        Accepts payload:

        {

          "system_id": "<optional>",

          "id": <document id>,

          "lines": [{ id, ... } | { id, is_deleted: true } | { ...create... }]

        }

        """

        allowed, source = self._has_permission(request.user, "modify")

        if not allowed:

            return self._deny(
                source, "You need modify permission to update prepayment lines."
            )

        document = self.get_object()

        raw_lines = request.data.get("lines", []) or []

        # Get current invoiced amount before any changes
        current_invoiced = document.total_prepayment_invoiced or Decimal("0.00")

        # First pass: hard-delete any lines explicitly marked for deletion

        to_delete_ids = []

        remaining_lines = []

        for payload in raw_lines:

            line_id = payload.get("id")

            is_deleted = payload.get("is_deleted")

            try:

                line_id = int(line_id) if line_id is not None else None

            except (TypeError, ValueError):

                line_id = None

            if is_deleted and line_id:

                to_delete_ids.append(line_id)

            else:

                # strip is_deleted before serializer update/create path

                if "is_deleted" in payload:

                    payload = {k: v for k, v in payload.items() if k != "is_deleted"}

                remaining_lines.append(payload)

        # Calculate what the new total would be after changes
        # We need to simulate the changes to validate before applying them
        from prepayment.models import PreaymentLine

        # Get current lines that won't be deleted or updated
        existing_line_ids = set(
            document.lines.exclude(id__in=to_delete_ids).values_list("id", flat=True)
        )

        # Track which lines are being updated
        updated_line_ids = set()
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None
            if line_id:
                updated_line_ids.add(line_id)

        # Calculate new total: include unchanged lines + updated/new lines
        new_total = Decimal("0.00")

        # Add unchanged lines (lines that exist but aren't being updated or deleted)
        unchanged_line_ids = existing_line_ids - updated_line_ids - set(to_delete_ids)
        for line in document.lines.filter(id__in=unchanged_line_ids):
            new_total += line.amount or Decimal("0.00")

        # Process remaining lines (updated or new) to calculate new total
        for payload in remaining_lines:
            line_id = payload.get("id")
            try:
                line_id = int(line_id) if line_id is not None else None
            except (TypeError, ValueError):
                line_id = None

            if line_id and line_id in existing_line_ids:
                # Update existing line - calculate from payload values
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price
            else:
                # New line - calculate from payload
                quantity = Decimal(str(payload.get("quantity", 0)))
                unit_price = Decimal(str(payload.get("unit_price", 0)))
                new_total += quantity * unit_price

        # Validate that new total is not below invoiced amount
        if new_total < current_invoiced:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            raise DRFValidationError(
                f"Total amount cannot be less than the invoiced amount of {format_currency(current_invoiced)}. "
                f"Current total would be {format_currency(new_total)}."
            )

        # Apply changes if validation passes
        try:
            if to_delete_ids:

                document.lines.filter(id__in=to_delete_ids).delete()

            # Second pass: upsert remaining lines via serializer

            if remaining_lines:

                serializer = self.get_serializer(
                    document, data={"lines": remaining_lines}, partial=True
                )

                serializer.is_valid(raise_exception=True)

                serializer.save()

            # Recalculate totals after mutations

            document.refresh_from_db()

            document.recalculate_totals()
        except DjangoValidationError as exc:
            # Convert Django ValidationError to DRF ValidationError
            # Django ValidationError can have messages as a list or dict
            if hasattr(exc, "message_dict") and exc.message_dict:
                # Form validation error with field-specific messages
                error_message = str(exc.message_dict)
            elif hasattr(exc, "messages") and exc.messages:
                # List of error messages - get first message
                if isinstance(exc.messages, list) and len(exc.messages) > 0:
                    error_message = str(exc.messages[0])
                elif isinstance(exc.messages, dict):
                    error_message = str(exc.messages)
                else:
                    error_message = str(exc.messages)
            else:
                # Fallback to string representation
                error_message = str(exc)
            # Raise DRF ValidationError which will return 400 Bad Request
            raise ValidationError(error_message)

        # Return fresh document (avoid stale prefetch)

        fresh_serializer = self.get_serializer(self.get_object())

        return Response(fresh_serializer.data)

    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------

    def _serialize_preview(self, preview_payload):

        gl_entries = []

        for entry in preview_payload["entries"]["gl_entries"]:

            gl_entries.append(
                {
                    "account_no": getattr(entry["gl_account"], "no", None),
                    "account_name": getattr(entry["gl_account"], "name", ""),
                    "description": entry["description"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(entry.get("global_dimension_1"), "code", None),
                }
            )

        customer_entries = []

        for entry in preview_payload["entries"]["customer_entries"]:

            customer_entries.append(
                {
                    "document_type": entry["document_type"],
                    "document_no": entry["document_no"],
                    "description": entry["description"],
                    "amount": entry["amount"],
                    "open": entry["open"],
                    "due_date": entry["due_date"],
                }
            )

        detailed_entries = []

        for entry in preview_payload["entries"]["detailed_customer_entries"]:

            detailed_entries.append(
                {
                    "entry_type": entry["entry_type"],
                    "document_type": entry["document_type"],
                    "amount": entry["amount"],
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        line_context = []

        for ctx in preview_payload["line_context"]:

            line_context.append(
                {
                    "line_id": ctx["line"].id if ctx.get("line") else None,
                    "label": ctx["label"],
                    "amount": ctx["amount"],
                    "collected_amount": ctx["collected_amount"],
                    "invoiced_amount": ctx["invoiced_amount"],
                    "target_total": ctx["target_total"],
                    "prepayment_account_no": getattr(
                        ctx["prepayment_account"], "no", ""
                    ),
                    "prepayment_account_name": getattr(
                        ctx["prepayment_account"], "name", ""
                    ),
                }
            )

        return {
            "transaction_no": preview_payload["transaction_no"],
            "total_deposit": preview_payload["total_deposit"],
            "has_cash_payment": preview_payload["has_cash_payment"],
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": line_context,
        }

    def _serialize_final_invoice_preview(self, preview_data):
        """Shape final-invoice preview for API / PostingPreviewModal."""
        entries = preview_data.get("entries", {})
        gl_entries = []
        for entry in entries.get("gl_entries", []):
            gl_entries.append(
                {
                    "account_no": getattr(entry.get("gl_account"), "no", None),
                    "account_name": getattr(entry.get("gl_account"), "name", ""),
                    "description": entry.get("description"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "balance_account_type": entry.get("balance_account_type"),
                    "global_dimension_1": getattr(
                        entry.get("global_dimension_1"), "code", None
                    ),
                }
            )

        customer_entries = []
        for entry in entries.get("customer_entries", []):
            customer_entries.append(
                {
                    "document_type": entry.get("document_type"),
                    "document_no": entry.get("document_no"),
                    "description": entry.get("description"),
                    "amount": entry.get("amount"),
                    "open": entry.get("open"),
                    "due_date": entry.get("due_date"),
                }
            )

        detailed_entries = []
        for entry in entries.get("detailed_customer_entries", []):
            detailed_entries.append(
                {
                    "entry_type": entry.get("entry_type"),
                    "document_type": entry.get("document_type"),
                    "amount": entry.get("amount"),
                    "debit_amount": entry.get("debit_amount", 0),
                    "credit_amount": entry.get("credit_amount", 0),
                }
            )

        has_cash_payment = any(
            e.get("document_type") in ("Payment", "payment")
            for e in entries.get("customer_entries", [])
        )

        return {
            "transaction_no": preview_data.get("transaction_no"),
            "total_deposit": preview_data.get("prepayment_to_deduct", 0),
            "total_invoice_amount": preview_data.get("total_invoice_amount"),
            "prepayment_to_deduct": preview_data.get("prepayment_to_deduct"),
            "net_receivables": preview_data.get("net_receivables"),
            "has_cash_payment": has_cash_payment,
            "gl_entries": gl_entries,
            "customer_entries": customer_entries,
            "detailed_customer_entries": detailed_entries,
            "line_context": [],
            "posted_invoice_lines": preview_data.get("posted_invoice_lines", []),
        }
