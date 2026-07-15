import os
from django.db import transaction
from django.contrib import admin
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.http import FileResponse
from django.core.files.storage import default_storage
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.exceptions import ValidationError
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.http import HttpRequest, Http404
from django.db.models import Sum
from rest_framework.views import APIView
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.parsers import MultiPartParser, FormParser

from purchases.invoice_numbers import generate_unique_vendor_invoice_no

from .models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    Vendor,
    VendorLedger,
    DetailedVendorLedgerEntry,
    PostedPurchaseInvoice,
    PurchaseCreditMemo,
    DocumentAttachment,
)
from financials.models import PaymentMethod
from .admin import (
    PurchaseInvoiceAdmin,
    PostedPurchaseInvoiceAdmin,
    PurchaseCreditMemoAdmin,
)
from items.models import (
    Item,
    Location,
    ItemUnitOfMeasure,
    UnitOfMeasure,
    TrackingSpecification,
)

from .serializers import (
    PurchaseInvoiceSerializer,
    PurchaseInvoiceLineSerializer,
    VendorSerializer,
    VendorLedgerSerializer,
    DocumentAttachmentSerializer,
)
from dimension.branch_filter import filter_queryset_by_branch, get_branch_for_request


class DocumentAttachmentViewSet(viewsets.ModelViewSet):
    """
    List/Create/Delete attachments for a purchase invoice.
    List supports ?purchase_invoice=<id>. Create accepts multipart: purchase_invoice, file, optional name.
    """
    serializer_class = DocumentAttachmentSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = DocumentAttachment.objects.all().order_by("-created_at")
        purchase_invoice = self.request.query_params.get("purchase_invoice")
        if purchase_invoice:
            qs = qs.filter(purchase_invoice_id=purchase_invoice)
        return qs

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        """Stream the file for download with Content-Disposition: attachment."""
        attachment = self.get_object()
        if not attachment.file or not attachment.file.name:
            return Response(
                {"detail": "File not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not default_storage.exists(attachment.file.name):
            return Response(
                {"detail": "File does not exist in storage."},
                status=status.HTTP_404_NOT_FOUND,
            )
        filename = attachment.name or os.path.basename(attachment.file.name)
        file_handle = default_storage.open(attachment.file.name, "rb")
        response = FileResponse(
            file_handle,
            content_type="application/octet-stream",
            as_attachment=True,
            filename=filename,
        )
        return response


class VendorFilter(filters.FilterSet):
    class Meta:
        model = Vendor
        fields = {
            "name": ["exact", "icontains"],
            "no": ["exact", "icontains"],
            "blocked": ["exact"],
            "city": ["exact", "icontains"],
            "state": ["exact", "icontains"],
        }


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    filterset_class = VendorFilter
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    search_fields = ["name", "no", "email", "phone"]
    ordering_fields = ["name", "no", "city", "state"]
    ordering = ["name"]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class PurchaseFilter(filters.FilterSet):
    date_range = filters.DateFromToRangeFilter(field_name="document_date")

    class Meta:
        model = PurchaseInvoice
        fields = {
            "vendor": ["exact"],
            "status": ["exact"],
            "document_date": ["exact", "gte", "lte"],
            "posting_date": ["exact", "gte", "lte"],
        }


class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = PurchaseInvoice.objects.all()
    serializer_class = PurchaseInvoiceSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PurchaseFilter
    search_fields = ["vendor__name", "vendor_invoice_no"]
    ordering_fields = [
        "invoice_no",
        "vendor__name",
        "document_date",
        "posting_date",
        "vendor_invoice_no",
        "status",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        return filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )

    def _may_read_cross_branch_purchase(self):
        """Allow loading an invoice by PK when it belongs to another branch (stale UI / correction)."""
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True
        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
            if not gl_setup or not getattr(gl_setup, "enable_multiple_branches", False):
                return False
        except Exception:
            return False
        return getattr(user, "can_switch_branch", True)

    def _resolve_purchase_pk(self, queryset, pk):
        """Resolve by numeric id, else by system_id when pk looks like a UUID string."""
        pk_str = str(pk).strip()
        try:
            return queryset.get(id=int(pk_str))
        except (ValueError, OverflowError, TypeError):
            pass
        except PurchaseInvoice.DoesNotExist:
            raise Http404("Purchase invoice not found.")

        if "-" in pk_str:
            try:
                return queryset.get(system_id=pk_str)
            except PurchaseInvoice.DoesNotExist:
                pass

        raise Http404("Purchase invoice not found.")

    def get_object(self):
        """
        Lookup scoped like list (branch filter). If missing, users who may switch branch
        can still open by id to edit dimensions / recover from wrong-branch drafts.
        Always raises Http404 (never bare DoesNotExist) so DRF returns 404, not 500.
        """
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        pk = self.kwargs[lookup_url_kwarg]

        try:
            return self._resolve_purchase_pk(queryset, pk)
        except Http404:
            if self._may_read_cross_branch_purchase():
                base = PurchaseInvoice.objects.all()
                return self._resolve_purchase_pk(base, pk)
            raise

    def retrieve(self, request, *args, **kwargs):
        """
        Handle GET request for a single purchase
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Http404:
            return Response(
                {"detail": "Purchase not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def post_purchase(self, request, pk=None):
        try:
            purchase = self.get_object()
            print("purchase", purchase)

            # Check if user can post previous dates
            from authentication.models import UserSetup
            from django.utils import timezone

            user_setup = UserSetup.get_or_create_for_user(request.user)
            today = timezone.now().date()

            # Check document_date if it exists
            if purchase.document_date and purchase.document_date < today:
                if not user_setup.can_post_previous_dates:
                    return Response(
                        {
                            "error": "Cannot post purchase with previous document date",
                            "detail": f"Document date ({purchase.document_date}) is in the past. You do not have permission to post purchases for previous dates.",
                            "invoice_no": purchase.invoice_no,
                            "document_date": purchase.document_date,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Check posting_date if it exists
            if purchase.posting_date and purchase.posting_date < today:
                if not user_setup.can_post_previous_dates:
                    return Response(
                        {
                            "error": "Cannot post purchase with previous posting date",
                            "detail": f"Posting date ({purchase.posting_date}) is in the past. You do not have permission to post purchases for previous dates.",
                            "invoice_no": purchase.invoice_no,
                            "posting_date": purchase.posting_date,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Get the admin instance
            mock_admin = PurchaseInvoiceAdmin(PurchaseInvoice, admin.site)

            # Call the post_invoice action directly with a queryset containing the purchase
            with transaction.atomic():
                mock_admin.post_invoice(request, [purchase])

            return Response(
                {
                    "message": "Purchase posted successfully",
                    "purchase": self.get_serializer(purchase).data,
                }
            )

        except Http404:
            raise
        except Exception as e:
            import traceback
            import logging

            # Log the full error for debugging
            logger = logging.getLogger(__name__)
            logger.error(f"Error posting purchase: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Extract the actual error message without redundant prefixes
            error_message = str(e)
            if error_message.startswith("Error posting purchase: "):
                error_message = error_message.replace("Error posting purchase: ", "")
            if error_message.startswith("Error posting invoice: "):
                error_message = error_message.replace("Error posting invoice: ", "")
            if error_message.startswith("Error processing invoice: "):
                error_message = error_message.replace("Error processing invoice: ", "")

            # Return detailed error information
            error_response = {
                "error": error_message,
                "error_type": type(e).__name__,
                "error_details": error_message,
                "traceback": traceback.format_exc() if settings.DEBUG else None,
            }

            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="edit-dimension-set")
    def edit_dimension_set(self, request, pk=None):
        """BC-style Edit Dimension Set: update header dimensions and propagate to lines."""
        from dimension.models import (
            Dimension,
            DimensionValue,
            get_or_create_dimension_set,
            update_global_dim_from_dimension_set,
            update_all_line_dim,
        )

        purchase = self.get_object()
        dimensions = request.data.get("dimensions") or {}

        if not isinstance(dimensions, dict):
            return Response(
                {"error": "dimensions must be a dict of dimension_code: value_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dim_values = {}
        for dim_code, value_id in dimensions.items():
            if not value_id:
                continue
            dim = Dimension.objects.filter(code=dim_code).first()
            if not dim:
                continue
            try:
                dv = DimensionValue.objects.get(pk=value_id)
            except (DimensionValue.DoesNotExist, (TypeError, ValueError)):
                continue
            if dv.dimension_code_id != dim.pk:
                continue
            dim_values[dim] = dv

        new_set = get_or_create_dimension_set(dim_values) if dim_values else None
        old_dim_set_id = purchase.dimension_set_id
        purchase.dimension_set = new_set
        update_global_dim_from_dimension_set(purchase)
        purchase.save()

        if purchase.dimension_set_id != old_dim_set_id:
            update_all_line_dim(purchase, purchase.dimension_set_id, old_dim_set_id)

        serializer = self.get_serializer(purchase)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def upsert(self, request):
        system_id = request.data.get("system_id")
        vendor_name = request.data.get("vendor_name")
        deleted = request.data.get("deleted", False)
        id = request.data.get("id")

        with transaction.atomic():
            if system_id:
                try:
                    # Try to find by system_id and id if both provided, or just system_id
                    if id:
                        purchase = PurchaseInvoice.objects.get(
                            system_id=system_id, id=id
                        )
                    else:
                        purchase = PurchaseInvoice.objects.get(system_id=system_id)
                    if deleted:
                        purchase.delete()
                        return Response(
                            {"message": "Purchase deleted successfully"},
                            status=status.HTTP_200_OK,
                        )
                    else:
                        # Update existing purchase
                        serializer = self.get_serializer(
                            purchase, data=request.data, partial=True
                        )

                        if serializer.is_valid(raise_exception=True):
                            # Log the validated data before save
                            purchase = serializer.save()
                            return Response(serializer.data, status=status.HTTP_200_OK)
                except PurchaseInvoice.DoesNotExist:
                    serializer = self.get_serializer(data=request.data)
                    if serializer.is_valid(raise_exception=True):
                        purchase = serializer.save()
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
            elif id:
                # Handle update by ID only (no system_id)
                try:
                    purchase = PurchaseInvoice.objects.get(id=id)
                    if deleted:
                        purchase.delete()
                        return Response(
                            {"message": "Purchase deleted successfully"},
                            status=status.HTTP_200_OK,
                        )
                    else:
                        # Update existing purchase by ID
                        serializer = self.get_serializer(
                            purchase, data=request.data, partial=True
                        )
                        if serializer.is_valid(raise_exception=True):
                            purchase = serializer.save()
                            return Response(serializer.data, status=status.HTTP_200_OK)
                except PurchaseInvoice.DoesNotExist:
                    return Response(
                        {"error": f"Purchase invoice with id {id} not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )
            else:
                # Create new purchase - requires vendor_name
                if not vendor_name:
                    return Response(
                        {"vendor_name": "Vendor name is required"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                serializer = self.get_serializer(data=request.data)
                if serializer.is_valid(raise_exception=True):
                    purchase = serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)

            return Response(
                {"detail": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def update_lines(self, request, pk=None):
        purchase = self.get_object()
        lines_data = request.data.get("lines", [])

        try:
            with transaction.atomic():
                existing_lines = {line.id: line for line in purchase.lines.all()}
                processed_line_ids = set()

                for line_data in lines_data:
                    # remove total_amount from line_data
                    line_data.pop("total_amount", None)
                    print("line_data", line_data)
                    line_id = line_data.get("id")
                    line_system_id = line_data.get("system_id")

                    # Handle deletion
                    if line_data.get("deleted"):
                        if line_id in existing_lines:
                            existing_lines[line_id].delete()
                            processed_line_ids.add(line_id)
                        continue

                    # remove total_amount from line_data
                    line_data.pop("total_amount", None)
                    item_system_id = line_data.get("item_system_id")
                    item_no = line_data.get("item_no")
                    item_name = line_data.get("item_name")

                    try:
                        item = Item.objects.get(item_name=item_name, no=item_no)
                    except Item.DoesNotExist:
                        raise ValidationError(
                            f"Item with system_id {item_system_id} not found"
                        )

                    # Convert unit_cost to Decimal, handling string values with commas
                    from decimal import Decimal

                    unit_cost_val = line_data.get("unit_cost", 0)
                    if isinstance(unit_cost_val, str):
                        # Remove commas if present (e.g., "2,999.78" -> "2999.78")
                        unit_cost_val = unit_cost_val.replace(",", "").strip()
                        unit_cost = Decimal(unit_cost_val)
                    elif isinstance(unit_cost_val, (int, float)):
                        # Use string conversion to preserve precision for floats
                        unit_cost = Decimal(str(unit_cost_val))
                    elif isinstance(unit_cost_val, Decimal):
                        unit_cost = unit_cost_val
                    else:
                        unit_cost = Decimal("0")

                    # Convert quantity to int
                    quantity_val = line_data.get("quantity")
                    if isinstance(quantity_val, str):
                        quantity = int(float(quantity_val))
                    else:
                        quantity = int(quantity_val) if quantity_val else 0

                    branch = get_branch_for_request(request)
                    loc = None
                    if branch:
                        loc = Location.objects.filter(code=branch.code).first()
                    if loc is None and getattr(request.user, "global_dimension_1", None):
                        loc = Location.objects.filter(
                            code=request.user.global_dimension_1.code
                        ).first()
                    if loc is None:
                        loc = Location.objects.first()

                    # Prepare common line data
                    prepared_line_data = {
                        "item": item,  # Use ForeignKey, not item_id
                        "quantity": quantity,
                        "unit_cost": unit_cost,
                        "description": line_data.get("description", ""),
                        "item_unit_of_measure": ItemUnitOfMeasure.objects.get(
                            unit_of_measure__code=line_data.get("unit_of_measure"),
                            item=item,
                        ),
                        "unit_of_measure": UnitOfMeasure.objects.get(
                            code=line_data.get("unit_of_measure")
                        ),
                        "location_code": loc,
                    }

                    # Merge default dimensions (Vendor, Item) with user and explicit
                    vendor_no = (
                        getattr(purchase.vendor, "no", None)
                        if purchase.vendor
                        else None
                    )
                    from dimension.models import get_merged_line_dimensions

                    dims = get_merged_line_dimensions(
                        vendor_no=vendor_no,
                        item=item,
                        request_user=request.user,
                        line_data=line_data,
                        header_dimensions=purchase,
                    )
                    prepared_line_data["dimension_set"] = dims.get("dimension_set")
                    prepared_line_data["global_dimension_1"] = dims.get("global_dimension_1")

                    if line_id and line_system_id and line_id in existing_lines:
                        # Update existing line
                        line = existing_lines[line_id]
                        for field, value in prepared_line_data.items():
                            if value is not None:
                                setattr(line, field, value)
                        line.save()
                        processed_line_ids.add(line_id)
                    else:
                        # Create new line
                        print("prepared_line_data", prepared_line_data)
                        PurchaseInvoiceLine.objects.create(
                            purchase_invoice=purchase, **prepared_line_data
                        )

                # Delete lines that weren't in the request
                lines_to_delete = set(existing_lines.keys()) - processed_line_ids
                # if lines_to_delete:
                #     purchase.lines.filter(id__in=lines_to_delete).delete()

                # Refresh purchase from db to get updated data
                purchase.refresh_from_db()
                serializer = self.get_serializer(purchase)
                return Response(serializer.data)

        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def reverse_purchase(self, request, pk=None):
        """
        Reverse a posted purchase invoice by:
        1. Creating a credit memo from the posted purchase invoice
        2. Automatically posting the credit memo
        """
        try:
            purchase = self.get_object()

            # Check user permission to reverse purchase invoices
            # This permission is controlled in User Setup (can_reverse_purchase_invoice)
            from authentication.models import UserSetup

            try:
                user_setup = UserSetup.objects.get(user=request.user)
            except UserSetup.DoesNotExist:
                # If no setup exists, deny by default (security-first approach)
                return Response(
                    {
                        "error": "Permission denied",
                        "detail": "You do not have permission to reverse purchase invoices. Please contact your administrator to enable this permission in your User Setup.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Check the permission flag
            if not user_setup.can_reverse_purchase_invoice:
                return Response(
                    {
                        "error": "Permission denied",
                        "detail": "You do not have permission to reverse purchase invoices. Please contact your administrator to enable this permission in your User Setup.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Validate purchase is posted
            if purchase.status != "Posted":
                return Response(
                    {
                        "error": "Cannot reverse purchase invoice",
                        "detail": f"Purchase invoice {purchase.invoice_no} is not posted. Only posted invoices can be reversed.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if already reversed
            from purchases.models import PostedPurchaseCreditMemo

            posted_invoice = PostedPurchaseInvoice.objects.filter(
                vendor_invoice_no=purchase.vendor_invoice_no
            ).first()

            if posted_invoice:
                # Check if already reversed
                is_reversed = PostedPurchaseCreditMemo.objects.filter(
                    original_posted_invoice=posted_invoice
                ).exists()
                if is_reversed:
                    return Response(
                        {
                            "error": "Purchase invoice already reversed",
                            "detail": f"Purchase invoice {purchase.invoice_no} has already been reversed.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Get reason from request (optional)
            reason = request.data.get(
                "reason", f"Manual reversal by {request.user.username}"
            )

            # Step 1: Create credit memo from posted purchase invoice
            # Find the PostedPurchaseInvoice
            if not posted_invoice:
                return Response(
                    {
                        "error": "Posted purchase invoice not found",
                        "detail": f"Could not find posted invoice for {purchase.invoice_no}. The invoice may not have been properly posted.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get admin instance for creating credit memo
            posted_invoice_admin = PostedPurchaseInvoiceAdmin(
                PostedPurchaseInvoice, admin.site
            )

            # Create credit memo directly (replicating admin logic)
            with transaction.atomic():
                from purchases.models import PurchaseCreditMemoLine
                from django.utils import timezone
                import uuid

                # Create the credit memo with status "Open" (copy dimensions from posted invoice)
                credit_memo = PurchaseCreditMemo.objects.create(
                    vendor=posted_invoice.vendor,
                    vendor_name=posted_invoice.vendor.name,
                    document_date=posted_invoice.document_date,
                    posting_date=posted_invoice.posting_date,
                    due_date=posted_invoice.due_date,
                    expected_receipt_date=None,
                    original_invoice_no=posted_invoice.no,
                    original_posted_invoice=posted_invoice,
                    status="Open",
                    global_dimension_1=posted_invoice.global_dimension_1,
                    global_dimension_2=posted_invoice.global_dimension_2,
                    dimension_set=posted_invoice.dimension_set,
                )

                # Copy all lines from the posted invoice (including dimensions)
                lines_created = 0
                for line in posted_invoice.posted_purchase_invoice_lines.all():
                    PurchaseCreditMemoLine.objects.create(
                        credit_memo=credit_memo,
                        item=line.item,
                        description=line.description,
                        location_code=line.location_code,
                        quantity=line.quantity,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=line.unit_of_measure,
                        unit_cost=line.unit_cost,
                        global_dimension_1=line.global_dimension_1
                        or posted_invoice.global_dimension_1,
                        global_dimension_2=line.global_dimension_2,
                        dimension_set=line.dimension_set,
                    )
                    lines_created += 1

                # Step 2: Post the credit memo automatically
                receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

                from purchases.admin import PurchaseCreditMemoPostingProcessor

                # Create posting processor and post the credit memo
                processor = PurchaseCreditMemoPostingProcessor(
                    credit_memo, request, receipt_no
                )

                # Post the credit memo (this creates all reversal entries)
                result = processor.post()

                if not result.get("success", False):
                    error_msg = result.get("message", "Unknown error during posting")
                    raise Exception(error_msg)

                # Refresh credit memo to get updated status
                credit_memo.refresh_from_db()

                return Response(
                    {
                        "message": "Purchase invoice reversed successfully",
                        "purchase_invoice_no": purchase.invoice_no,
                        "credit_memo_no": credit_memo.no,
                        "credit_memo_id": credit_memo.id,
                        "status": credit_memo.status,
                    },
                    status=status.HTTP_200_OK,
                )

        except Exception as e:
            import traceback
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error reversing purchase invoice: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            error_message = str(e)
            # Clean up error message
            if error_message.startswith("Error creating credit memo: "):
                error_message = error_message.replace(
                    "Error creating credit memo: ", ""
                )
            if error_message.startswith("Error posting credit memo: "):
                error_message = error_message.replace("Error posting credit memo: ", "")

            return Response(
                {
                    "error": "Failed to reverse purchase invoice",
                    "detail": error_message,
                    "traceback": traceback.format_exc() if settings.DEBUG else None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class VendorLedgerFilter(filters.FilterSet):
    date_range = filters.DateFromToRangeFilter(field_name="posting_date")
    amount_range = filters.NumericRangeFilter(field_name="amount")
    vendor_no = filters.CharFilter(field_name="vendor__no", lookup_expr="iexact")

    class Meta:
        model = VendorLedger
        fields = {
            "vendor": ["exact"],
            "document_type": ["exact"],
            "open": ["exact"],
            "posting_date": ["exact", "gte", "lte"],
            "due_date": ["exact", "gte", "lte"],
        }


class VendorLedgerViewSet(viewsets.ModelViewSet):
    queryset = VendorLedger.objects.all()
    serializer_class = VendorLedgerSerializer
    filterset_class = VendorLedgerFilter
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    search_fields = ["document_no", "external_document_no", "vendor__name"]
    ordering_fields = ["posting_date", "due_date", "amount"]
    ordering = ["-posting_date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = filter_queryset_by_branch(
            queryset, self.request.user, request=self.request
        )
        if self.action == "list":
            return queryset.select_related("vendor", "payment_method").order_by(
                "-posting_date"
            )
        return queryset.order_by("-posting_date")

    @action(detail=True, methods=["get"])
    def ledger_entries(self, request, pk=None):
        vendor = get_object_or_404(Vendor, id=pk)
        queryset = VendorLedger.objects.filter(vendor=vendor, open=True).order_by(
            "-posting_date"
        )
        queryset = filter_queryset_by_branch(
            queryset, request.user, request=request
        )
        total_amount = 0
        for entry in queryset:
            details = DetailedVendorLedgerEntry.objects.filter(
                vendor_ledger_entry=entry
            )
            for detail in details:
                total_amount += detail.amount

        # Get summary data
        # summary = queryset.aggregate(total_amount=Sum("amount"))
        summary = {
            "total_amount": total_amount,
            "total_remaining": total_amount,
        }

        # Serialize the ledger entries
        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                "ledger_entries": serializer.data,
                "summary": {
                    "total_amount": float(summary["total_amount"] or 0),
                    "total_remaining": float(
                        sum(entry.remaining_amount or 0 for entry in queryset) or 0
                    ),
                },
            }
        )


class GenerateInvoiceNoView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        vendor_invoice_no = generate_unique_vendor_invoice_no()

        invoice_no = request.data.get("invoice_no")
        if invoice_no:
            PurchaseInvoice.objects.filter(invoice_no=invoice_no).update(
                vendor_invoice_no=vendor_invoice_no
            )

        return Response({"vendor_invoice_no": vendor_invoice_no})


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@authentication_classes([SessionAuthentication, JWTAuthentication])
def update_vendor_payment_method(request):
    """Update vendor's preferred payment method and optionally invoice's payment method"""
    try:
        vendor_id = request.data.get("vendor_id")
        payment_method_id = request.data.get("payment_method_id")
        invoice_id = request.data.get("invoice_id")  # Optional: invoice ID to update

        if not vendor_id:
            return Response(
                {"error": "Vendor ID is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not payment_method_id:
            return Response(
                {"error": "Payment method ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return Response(
                {"error": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get payment method
        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id)
        except PaymentMethod.DoesNotExist:
            return Response(
                {"error": "Payment method not found"}, status=status.HTTP_404_NOT_FOUND
            )

        vendor_no = (vendor.no or "").strip().lower()
        vendor_name = (vendor.name or "").strip().lower()
        is_general_vendor = (
            vendor_no == "vendor-000001"
            or "general" in vendor_no
            or "general" in vendor_name
        )
        if is_general_vendor and payment_method.code == "NOT_PAID":
            return Response(
                {
                    "error": "General vendor cannot have 'Not Paid Yet' as payment method. "
                    "Please select a different payment method."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update vendor's payment method
        vendor.payment_method = payment_method
        vendor.save(update_fields=["payment_method", "updated_at"])

        # If invoice_id is provided, also update the invoice's payment method
        if invoice_id:
            try:
                invoice = PurchaseInvoice.objects.get(id=invoice_id)
                # Only update if invoice is not yet posted
                if invoice.status != "Posted":
                    invoice.payment_method = payment_method
                    invoice.save(update_fields=["payment_method", "updated_at"])
            except PurchaseInvoice.DoesNotExist:
                # Invoice not found - not critical, continue
                pass

        return Response(
            {
                "message": f"Vendor payment method updated to {payment_method.description}",
                "vendor_id": vendor.id,
                "payment_method_id": payment_method.id,
                "payment_method_name": payment_method.description,
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to update vendor payment method: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
