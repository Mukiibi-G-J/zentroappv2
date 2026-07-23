from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, F, Q
from decimal import Decimal
import uuid

from django.contrib import admin
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
import uuid

from .models import (
    SalesInvoice,
    SalesInvoiceLine,
    Customer,
    CustomerLedgerEntry,
    CustomerPostingGroup,
    SalesReceivable,
    DetailedCustomerLedgerEntry,
    PostedSalesInvoice,
    PostedSalesInvoiceLine,
    SalesCreditMemo,
    SalesCreditMemoLine,
    SalesOrder,
    SalesOrderLine,
    SalesPriceList,
)
from financials.models import GeneralLedgerEntry
from postings.models import GeneralPostingSetup, InventoryPostingSetup

# Import sync utilities
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json
from items.models import (
    TrackingSpecification,
    ValueEntry,
    ItemLedgerEntries,
    Item,
    ItemUnitOfMeasure,
)
from resources.models import ResourceLedgerEntry
from django.utils.translation import gettext_lazy as _
from items.enums import DocumentType, EntryType, InventoryType
from financials.enums import BalacingAccountType, GeneralPostingType
from dimension.models import DimensionValue, Dimension
from dimension.admin_mixin import DefaultDimensionAdminMixin
from common.enums import (
    DocumentType as CommonDocumentType,
    EntryType as CommonEntryType,
)
from .filters import PostingReadinessFilter, BranchListFilter


class SalesInvoiceLineInline(admin.TabularInline):
    model = SalesInvoiceLine
    extra = 1
    fields = [
        "type",
        "item",
        "resource",
        "gl_account",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_price",
        "line_discount_amount",
        "tracking_code",
        "global_dimension_1",
        "dimension_set",
    ]
    readonly_fields = ["total_amount", "line_amount"]


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    class EmptyDimensionFieldsFilter(admin.SimpleListFilter):
        title = "Empty dimensions"
        parameter_name = "dimension_empty"

        def lookups(self, request, model_admin):
            return (
                ("no_set", "Missing dimension set"),
                ("no_dim1", "Missing global dimension 1"),
                ("no_dim2", "Missing global dimension 2"),
                ("any", "Missing any (set or global dimensions)"),
            )

        def queryset(self, request, queryset):
            from django.db.models import Q

            v = self.value()
            if v == "no_set":
                return queryset.filter(dimension_set__isnull=True)
            if v == "no_dim1":
                return queryset.filter(global_dimension_1__isnull=True)
            if v == "no_dim2":
                return queryset.filter(global_dimension_2__isnull=True)
            if v == "any":
                return queryset.filter(
                    Q(dimension_set__isnull=True)
                    | Q(global_dimension_1__isnull=True)
                    | Q(global_dimension_2__isnull=True)
                )
            return queryset

    list_display = [
        "invoice_no",
        "customer",
        "document_date",
        "customer_invoice_no",
        "status",
        "inventory_status",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
        "created_at",
    ]
    list_filter = ["status", "document_date", EmptyDimensionFieldsFilter]
    search_fields = ["customer__name", "customer_invoice_no", "invoice_no"]
    readonly_fields = ["created_at", "updated_at", "invoice_no"]
    list_select_related = (
        "customer",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
    )
    fieldsets = [
        ("Customer Information", {"fields": ("customer", "contact_person")}),
        (
            "Document Information",
            {
                "fields": (
                    "document_date",
                    "posting_date",
                    "vat_date",
                    "due_date",
                    "customer_invoice_no",
                    "status",
                    "global_dimension_1",
                    "global_dimension_2",
                    "dimension_set",
                )
            },
        ),
        (
            "Invoice Discount",
            {
                "fields": (
                    "invoice_discount_type",
                    "invoice_discount_amount",
                    "invoice_discount_percentage",
                ),
                "description": "Invoice-level discount applied after line discounts",
            },
        ),
        (
            "VAT",
            {
                "fields": ("total_vat_amount",),
                "description": "VAT settings (requires VAT enabled in General Ledger Setup). Amounts are always inclusive of VAT.",
            },
        ),
    ]
    inlines = [SalesInvoiceLineInline]

    actions = [
        "preview_posting",
        "post_invoice",
        "check_inventory_status",
        "preview_reversal",
        "reverse_invoice",
    ]

    def check_inventory_status(self, request, queryset):
        """Check inventory status for selected invoices."""
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single invoice to check inventory status.",
                level="ERROR",
            )
            return

        invoice = queryset[0]

        if invoice.status == "Posted":
            self.message_user(
                request,
                "This invoice has already been posted.",
                level="WARNING",
            )
            return

        can_post, message = self.can_post_invoice(invoice)

        if can_post:
            self.message_user(
                request,
                f"Inventory check passed for invoice {invoice.invoice_no}. Ready to post.",
                level="SUCCESS",
            )
        else:
            self.message_user(
                request,
                f"Cannot post invoice {invoice.invoice_no}: {message}",
                level="ERROR",
            )

    def preview_posting(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single invoice to preview posting.",
                level="ERROR",
            )
            return

        invoice = queryset[0]
        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            invoice.full_clean()
            invoice.clean()

            for line in invoice.lines.all():
                line.full_clean()
                line.clean()

            processor = SalesInvoiceProcessor(invoice, request, receipt_no)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing posting: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            preview_entries = {
                "invoice": f"Invoice {invoice.id} -> Invoice {invoice.invoice_no}",
                "steps": [
                    "Posting lines 1",
                    "Posting sales and VAT 1",
                    "Posting to customers 1",
                    "Posting to bal. account 1",
                    "Reducing inventory quantities 1",
                ],
                "entries": entries,
            }

            return TemplateResponse(
                request,
                template="admin/sales/salesinvoice/preview_posting.html",
                context={
                    "title": "Preview Posting",
                    "invoice": invoice,
                    "preview_entries": preview_entries,
                    "opts": self.model._meta,
                },
            )

        except ValidationError as e:
            if isinstance(e.message_dict.get("__all__"), list):
                error_message = e.message_dict["__all__"][0]
            else:
                error_message = str(e)
            self.message_user(
                request,
                f"Error previewing posting: {error_message}",
                level="ERROR",
            )
            return

        except Exception as e:
            self.message_user(
                request,
                f"Error previewing posting: {str(e)}",
                level="ERROR",
            )
            return

    def inventory_status(self, obj):
        """Display inventory status for the invoice."""
        if obj.status == "Posted":
            return "✅ Posted"

        try:
            can_post, message = self.can_post_invoice(obj)
            if can_post:
                return "✅ Ready to Post"
            else:
                return "❌ Insufficient Inventory"
        except Exception:
            return "❓ Error Checking"

    inventory_status.short_description = "Inventory Status"

    def can_post_invoice(self, invoice):
        """Check if an invoice can be posted (has sufficient inventory)."""
        try:
            # Create a mock request for inventory checking
            from django.test import RequestFactory
            from authentication.models import CustomUser as User

            # Get a default user for inventory checking
            default_user = User.objects.filter(is_superuser=True).first()
            if not default_user:
                return False, "No system user available for inventory checking"

            # Create a mock request
            factory = RequestFactory()
            mock_request = factory.get("/")
            mock_request.user = default_user

            receipt_no = f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            processor = SalesInvoiceProcessor(invoice, mock_request, receipt_no)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                return (
                    False,
                    f"Validation error: {entries.get('message', 'Unknown error')}",
                )

            # Check for insufficient inventory
            insufficient_items = []
            for item_preview in entries.get("inventory_reduction_preview", []):
                reduction = item_preview.get("reduction_info") or {}
                if not reduction.get("insufficient_inventory"):
                    continue
                shortage = reduction.get("remaining_after_reduction")
                lot = item_preview.get("lot_no") or reduction.get("lot_no") or ""
                serial = (
                    item_preview.get("serial_no") or reduction.get("serial_no") or ""
                )
                label = (
                    f" (serial {serial})"
                    if serial
                    else (f" (lot {lot})" if lot else "")
                )
                insufficient_items.append(
                    {
                        "item": item_preview["item"].item_name,
                        "shortage": shortage,
                        "label": label,
                    }
                )

            if insufficient_items:
                error_message = "Insufficient inventory:\n"
                for item in insufficient_items:
                    error_message += (
                        f"• {item['item']}{item['label']}: "
                        f"Shortage: {item['shortage']:.2f} units\n"
                    )
                return False, error_message

            return True, "OK"
        except Exception as e:
            return False, f"Error checking inventory: {str(e)}"

    def post_invoice(self, request, queryset):
        if len(queryset) != 1:
            if hasattr(self, "message_user"):
                self.message_user(
                    request, "Please select a single invoice to post.", level="ERROR"
                )
            return

        invoice = queryset[0]

        if invoice.status == "Posted":
            if hasattr(self, "message_user"):
                self.message_user(
                    request, "This invoice has already been posted.", level="ERROR"
                )
            return

        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # First, check for insufficient inventory before posting
            processor = SalesInvoiceProcessor(invoice, request, receipt_no)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error posting invoice: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            # Check for insufficient inventory
            insufficient_items = []
            for item_preview in entries.get("inventory_reduction_preview", []):
                reduction = item_preview.get("reduction_info") or {}
                if not reduction.get("insufficient_inventory"):
                    continue
                shortage = reduction.get("remaining_after_reduction")
                lot = item_preview.get("lot_no") or reduction.get("lot_no") or ""
                serial = (
                    item_preview.get("serial_no") or reduction.get("serial_no") or ""
                )
                label = (
                    f" (serial {serial})"
                    if serial
                    else (f" (lot {lot})" if lot else "")
                )
                insufficient_items.append(
                    {
                        "item": item_preview["item"].item_name,
                        "shortage": shortage,
                        "requested": item_preview["quantity_to_reduce"],
                        "label": label,
                    }
                )

            if insufficient_items:
                error_message = "Cannot post invoice due to insufficient inventory:\n"
                for item in insufficient_items:
                    error_message += (
                        f"• {item['item']}{item['label']}: "
                        f"Requested {item['requested']:.2f} units, "
                        f"Shortage: {item['shortage']:.2f} units\n"
                    )

                self.message_user(
                    request,
                    error_message,
                    level="ERROR",
                )
                return

            # If inventory is sufficient, proceed with posting
            posting_processor = SalesInvoicePostingProcessor(
                invoice, request, receipt_no
            )

            with transaction.atomic():
                result = posting_processor.post()

                if result["success"]:
                    if hasattr(self, "message_user"):
                        self.message_user(
                            request,
                            f"Successfully posted invoice {invoice.invoice_no}",
                            level="SUCCESS",
                        )
                else:
                    error_msg = f"Error posting invoice: {result.get('message', 'Unknown error')}"
                    if hasattr(self, "message_user"):
                        self.message_user(request, error_msg, level="ERROR")
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = f"Error posting invoice: {e}"
            if hasattr(self, "message_user"):
                self.message_user(request, error_msg, level="ERROR")
            raise Exception(error_msg)

    def preview_reversal(self, request, queryset):
        """Preview what will happen when reversing a posted sales invoice"""
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single invoice to preview reversal.",
                level=messages.ERROR,
            )
            return

        sales_invoice = queryset[0]

        # Check if invoice is posted
        if sales_invoice.status != "Posted":
            self.message_user(
                request,
                f"Only posted invoices can be reversed. Current status: {sales_invoice.status}",
                level=messages.ERROR,
            )
            return

        # Create a temporary object that looks like PostedSalesInvoice for the processor
        # The reversal processor uses document_no to find entries, which matches SalesInvoice.invoice_no
        class ReversalInvoiceWrapper:
            """Wrapper to make SalesInvoice compatible with reversal processor"""

            def __init__(self, sales_invoice):
                self.no = (
                    sales_invoice.invoice_no
                )  # Use SalesInvoice number for finding entries
                self.customer = sales_invoice.customer
                self.document_date = sales_invoice.document_date
                self.posting_date = sales_invoice.posting_date
                self.vat_date = sales_invoice.vat_date
                self.due_date = sales_invoice.due_date
                self.customer_invoice_no = (
                    sales_invoice.customer_invoice_no
                )  # ✅ For linking to PostedSalesInvoice
                self.status = sales_invoice.status
                self.reversed = False  # SalesInvoice doesn't track reversal, PostedSalesInvoice does
                self.posted_sales_invoice_lines = sales_invoice.lines
                # Add credit_memos as empty queryset (no credit memos exist yet for non-reversed invoices)
                self.credit_memos = SalesCreditMemo.objects.none()

        invoice_wrapper = ReversalInvoiceWrapper(sales_invoice)

        try:
            # Generate preview using wrapper
            processor = SalesInvoiceReversalProcessor(invoice_wrapper, request)
            entries = processor.process()

            if not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing reversal: {entries.get('message', 'Unknown error')}",
                    level=messages.ERROR,
                )
                return

            # Prepare preview data
            preview_data = {
                "invoice": sales_invoice,  # Use original for display
                "steps": [
                    "✅ Create credit memo document",
                    "✅ Reverse GL entries (opposite signs)",
                    "✅ Reverse customer ledger entries",
                    "✅ Reverse item ledger entries",
                    "✅ Restore inventory quantities",
                    "✅ Mark original invoice as reversed",
                ],
                "gl_entries_count": len(entries.get("gl_entries", [])),
                "customer_entries_count": len(entries.get("customer_entries", [])),
                "item_entries_count": len(entries.get("item_entries", [])),
                "value_entries_count": len(entries.get("value_entries", [])),
                "entries": entries,
            }

            # Render beautiful template
            return TemplateResponse(
                request,
                "admin/sales/postedsalesinvoice/preview_reversal.html",
                context={
                    "title": "Preview Reversal",
                    "invoice": sales_invoice,
                    "preview_data": preview_data,
                    "opts": self.model._meta,
                },
            )

        except Exception as e:
            self.message_user(
                request, f"Error previewing reversal: {str(e)}", level=messages.ERROR
            )
            return

    preview_reversal.short_description = "🔍 Preview Reversal (Posted Only)"

    def reverse_invoice(self, request, queryset):
        """Actually reverse the posted sales invoice"""
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single invoice to reverse.",
                level=messages.ERROR,
            )
            return

        sales_invoice = queryset[0]

        # Check if invoice is posted
        if sales_invoice.status != "Posted":
            self.message_user(
                request,
                f"Only posted invoices can be reversed. Current status: {sales_invoice.status}",
                level=messages.ERROR,
            )
            return

        # Create wrapper object for processor
        class ReversalInvoiceWrapper:
            """Wrapper to make SalesInvoice compatible with reversal processor"""

            def __init__(self, sales_invoice):
                self.no = sales_invoice.invoice_no
                self.customer = sales_invoice.customer
                self.document_date = sales_invoice.document_date
                self.posting_date = sales_invoice.posting_date
                self.vat_date = sales_invoice.vat_date
                self.due_date = sales_invoice.due_date
                self.customer_invoice_no = (
                    sales_invoice.customer_invoice_no
                )  # ✅ For linking to PostedSalesInvoice
                self.status = sales_invoice.status
                self.reversed = False
                self.posted_sales_invoice_lines = sales_invoice.lines
                # Add credit_memos as empty queryset
                self.credit_memos = SalesCreditMemo.objects.none()

        invoice_wrapper = ReversalInvoiceWrapper(sales_invoice)

        try:
            # Get reason from POST data (if provided via form)
            reason = request.POST.get(
                "reversal_reason", f"Manual reversal by {request.user.username}"
            )

            # Execute reversal using wrapper
            # All operations wrapped in atomic transaction for complete rollback on failure
            processor = SalesInvoiceReversalPostingProcessor(
                invoice_wrapper, request, reason=reason
            )

            # Outer transaction wraps all operations including SalesInvoice status update
            # If processor.post() fails, everything rolls back including status changes
            with transaction.atomic():
                result = processor.post()

                if not result["success"]:
                    # Processor already rolled back its transaction
                    # Re-raise to trigger outer transaction rollback
                    error_msg = f"❌ Error reversing invoice: {result.get('message', 'Unknown error')}"
                    raise Exception(error_msg)

                # ✅ Reversal successful - continue with status updates
                credit_memo = result.get("credit_memo")
                credit_memo_no = result.get("credit_memo_no")
                transaction_no = result.get("transaction_no", "N/A")
                posted_sales_invoice = result.get(
                    "posted_sales_invoice"
                )  # Already marked as reversed in processor

                # Keep status as "Posted" - the reversed boolean field indicates reversal
                # This matches the purchase invoice reversal pattern
                # PostedSalesInvoice is already marked as reversed in the processor

                # Success messages (only shown if transaction commits successfully)
                self.message_user(
                    request,
                    f"✅ Successfully reversed invoice {sales_invoice.invoice_no}. Credit Memo: {credit_memo_no}",
                    level=messages.SUCCESS,
                )

                # Show details of what was created
                self.message_user(
                    request,
                    f"Created credit memo {credit_memo_no} with {credit_memo.lines.count()} line(s). "
                    f"Invoice {sales_invoice.invoice_no} is now marked as reversed. "
                    f"Transaction: {transaction_no}",
                    level=messages.INFO,
                )

        except Exception as e:
            # ❌ Any exception triggers complete rollback of all operations
            # processor.post() handles its own rollback, outer transaction handles status updates
            error_msg = f"❌ Error reversing invoice: {str(e)}"
            self.message_user(request, error_msg, level=messages.ERROR)
            # Exception propagates, triggering transaction rollback
            # No need to raise again - transaction.atomic() handles it

    reverse_invoice.short_description = "❌ Reverse Invoice (Posted Only)"


class SalesInvoiceProcessor:
    def __init__(self, invoice, request, receipt_no):
        self.invoice = invoice
        if not request:
            raise Exception("Request object is required but was not provided")
        if not hasattr(request, "user"):
            raise Exception("Request object does not have a user attribute")
        if not request.user:
            raise Exception("Request user is not authenticated")

        self.user = request.user
        self.lines = invoice.lines.all()
        self.customer = invoice.customer
        self.genBusinessPostingGroup = invoice.customer.general_business_posting_group
        # Prioritize invoice payment_method - each invoice should use its own payment method
        # Only fall back to customer if invoice doesn't have one (for backward compatibility)
        self.payment_method = invoice.payment_method or invoice.customer.payment_method

        if not self.customer.customer_posting_group:
            raise Exception(
                f"Customer {self.customer.name} does not have a customer posting group assigned"
            )

        self.receivables_account = (
            self.customer.customer_posting_group.receivables_account
        )

        if not self.receivables_account:
            raise Exception(
                f"Customer posting group '{self.customer.customer_posting_group.code}' does not have a receivables account assigned"
            )

        self.receipt_no = receipt_no

        # Prefer invoice dimension so VAT and other document-level entries get correct branch
        # Fallback: user dimension, then first line with dimension (ensures VAT entries get dimension)
        self.global_dimension_1_value = (
            getattr(invoice, "global_dimension_1", None)
            or getattr(request.user, "global_dimension_1", None)
            or next(
                (
                    getattr(ln, "global_dimension_1", None)
                    for ln in self.lines
                    if getattr(ln, "global_dimension_1", None)
                ),
                None,
            )
        )
        self.dimension_set_value = getattr(invoice, "dimension_set", None)

        self.gl_entries = []
        self.customer_entries = []
        self.item_entries = []
        self.resource_ledger_entries = (
            []
        )  # Preview of Resource Ledger Entries (resource lines)
        self.vat_entries = []
        self.detailed_customer_entries = []
        self.bank_account_entries = []  # For bank account ledger entries (preview only)
        self.value_entries = []
        # Invoice discount tracking
        self._invoice_discount_ratio = Decimal("1")
        self._invoice_discount_value = Decimal("0")

    def _effective_line_global_dimension_1(self, line):
        """
        Branch for inventory and G/L on item lines.

        Prefer DimensionValue with the same code as ``SalesInvoiceLine.location_code``
        so posted Item Ledger Entries match the physical location and show under
        the correct branch filter (X-Branch-Id). Avoids stale ``line.global_dimension_1``
        (e.g. CENTRAL) when the line already sells from MWANJARI.
        """
        loc = getattr(line, "location_code", None)
        if loc is not None:
            from dimension.models import DimensionValue

            loc_dim = DimensionValue.objects.filter(code=loc.code).first()
            if loc_dim:
                return loc_dim
        return (
            getattr(line, "global_dimension_1", None)
            or self.global_dimension_1_value
        )

    def _validate_invoice(self):
        if not self.lines.exists():
            raise Exception("Invoice has no lines")

        if not self.customer:
            raise Exception("Invoice has no customer")

        # Validate that payment_method exists (required for processing)
        if not self.payment_method:
            raise Exception(
                f"Invoice {self.invoice.invoice_no or self.invoice.id} does not have a payment method. "
                f"Payment method must be set on the invoice before posting."
            )

        if not self.customer.customer_posting_group:
            raise Exception(
                f"Customer {self.customer.name} does not have a customer posting group assigned"
            )

        if not self.customer.general_business_posting_group:
            raise Exception(
                f"Customer {self.customer.name} does not have a business posting group assigned"
            )

        if not self.customer.customer_posting_group.receivables_account:
            raise Exception(
                f"Customer posting group '{self.customer.customer_posting_group.code}' does not have a receivables account assigned"
            )

        if (
            self.customer.payment_method
            and self.customer.payment_method.is_cash_payment()
        ):
            # Check if payment method has either G/L account or Bank Account configured
            has_gl_account = bool(self.customer.payment_method.bal_account_no)
            has_bank_account = (
                self.customer.payment_method.bal_account_type
                == BalacingAccountType.Bank_Account.name
                and bool(self.customer.payment_method.bal_bank_account_no)
            )
            if not (has_gl_account or has_bank_account):
                raise Exception(
                    f"Payment method '{self.customer.payment_method.code}' does not have a balancing account assigned. "
                    "Please configure either a G/L Account or Bank Account in the payment method."
                )

        for line in self.lines:
            if not line.item:
                continue  # Resource lines: no item tracking
            tracking_requirements = line.item.requires_tracking_line
            if tracking_requirements is False:
                continue

            if isinstance(tracking_requirements, dict):
                tracking_specs = line.tracking_specifications
                # Lot-only POS path: single lot stored on line.tracking_code
                has_lot_on_line = bool(line.tracking_code and str(line.tracking_code).strip())
                uses_specs = tracking_specs.exists()

                if not uses_specs and not has_lot_on_line:
                    raise Exception(
                        f"Item {line.item.item_name} requires tracking specifications"
                    )

                if uses_specs:
                    for spec in tracking_specs:
                        if tracking_requirements.get("serial_no") and not spec.serial_no:
                            raise Exception(
                                f"Serial number required for item {line.item.item_name}"
                            )
                        if tracking_requirements.get("lot_no") and not spec.lot_no:
                            raise Exception(
                                f"Lot number required for item {line.item.item_name}"
                            )
                        if (
                            tracking_requirements.get("expiry_date")
                            and not spec.expiry_date
                        ):
                            raise Exception(
                                f"Expiry date required for item {line.item.item_name}"
                            )
                        if spec.serial_no and int(spec.quantity_base or 0) != 1:
                            raise Exception(
                                f"Quantity (Base) must be 1 when Serial No. is stated "
                                f"for item {line.item.item_name}"
                            )

                    if not line.item_unit_of_measure:
                        raise Exception(
                            f"Unit of measure is required for item {line.item.item_name} "
                            f"in document {self.invoice.invoice_no}"
                        )
                    expected_quantity = int(line.quantity) * int(
                        line.item_unit_of_measure.quantity_per_unit or 1
                    )
                    total_quantity = (
                        tracking_specs.aggregate(total=Sum("quantity_base"))["total"]
                        or 0
                    )
                    if total_quantity != expected_quantity:
                        raise Exception(
                            f"Quantity mismatch for item {line.item.item_name} in document "
                            f"{self.invoice.invoice_no}: Expected {expected_quantity}, "
                            f"but tracking specifications total {total_quantity}."
                        )
                else:
                    # Legacy lot pick on line.tracking_code (no serial worksheet)
                    if tracking_requirements.get("serial_no"):
                        raise Exception(
                            f"Serial number required for item {line.item.item_name}. "
                            f"Open Item Tracking Lines and assign a unique serial per unit."
                        )
                    if tracking_requirements.get("lot_no") and not has_lot_on_line:
                        raise Exception(
                            f"Lot number required for item {line.item.item_name}"
                        )
                    if tracking_requirements.get("expiry_date") and not has_lot_on_line:
                        raise Exception(
                            f"Expiry date required for item {line.item.item_name}"
                        )

                if not line.item_unit_of_measure:
                    raise Exception(
                        f"Unit of measure is required for item {line.item.item_name} "
                        f"in document {self.invoice.invoice_no}"
                    )

        return True

    def _consolidate_gl_entries(self):
        """Consolidate GL entries by grouping them by document_type, gl_account, and other key fields."""
        consolidated = {}
        non_invoice_entries = []

        for entry in self.gl_entries:
            document_type = entry.get("document_type", "")

            # Only consolidate entries with document_type = "Invoice"
            if document_type == "Invoice":
                # Create a key for grouping Invoice entries
                key = (
                    entry.get("gl_account", ""),
                    entry.get("document_no", ""),
                    entry.get("posting_date"),
                    entry.get("department_code"),
                    entry.get("transaction_no", ""),
                )

                if key in consolidated:
                    # Add amounts for the same key
                    consolidated[key]["amount"] += entry.get("amount", 0)
                else:
                    # Create new consolidated entry with all required fields
                    consolidated[key] = {
                        "posting_date": entry.get("posting_date"),
                        "document_type": entry.get("document_type", ""),
                        "document_no": entry.get("document_no", ""),
                        "gl_account": entry.get("gl_account", ""),
                        "description": entry.get("description", ""),
                        "department_code": entry.get("department_code"),
                        "amount": entry.get("amount", 0),
                        "gen_posting_type": entry.get("gen_posting_type", ""),
                        "global_dimension_1": entry.get("global_dimension_1"),
                        "gen_bus_posting_group": entry.get("gen_bus_posting_group"),
                        "gen_prod_posting_group": entry.get("gen_prod_posting_group"),
                        "balance_account_type": entry.get("balance_account_type", ""),
                        "user": entry.get("user"),
                        "transaction_no": entry.get("transaction_no", ""),
                    }
            else:
                # Keep non-Invoice entries as they are
                non_invoice_entries.append(entry)

        # Combine consolidated Invoice entries with non-Invoice entries
        result = list(consolidated.values()) + non_invoice_entries

        # Return the consolidated entries as a list
        return result

    def _calculate_inventory_reduction_preview(
        self,
        item,
        quantity_to_reduce,
        location,
        previous_reductions=None,
        *,
        lot_no=None,
        serial_no=None,
    ):
        """Calculate remaining quantities after reduction (preview).

        When lot_no/serial_no are set, mirrors ``_reduce_inventory_quantities`` so
        Preview Posting catches the same shortages as Post (BC parity).
        """
        from items.models import ItemLedgerEntries

        lot = (lot_no or "").strip() if lot_no else ""
        serial = (serial_no or "").strip() if serial_no else ""
        reduction_key = f"{item.no}|{lot}|{serial}"

        entries = ItemLedgerEntries.objects.filter(
            item=item, remaining_quantity__gt=0, location=location
        )
        if serial:
            entries = entries.filter(serial_no__iexact=serial)
        if lot:
            entries = entries.filter(lot_no=lot)

        # Lot / FEFO when tracking and no specific serial; otherwise FIFO by created_at
        if item.tracking_code and not serial:
            entries = entries.order_by(
                models.F("expiry_date").asc(nulls_last=True),
                "created_at",
            )
        else:
            entries = entries.order_by("created_at")

        simulated_entries = []
        for entry in entries:
            simulated_entries.append(
                {
                    "id": entry.id,
                    "document_no": entry.document_no,
                    "posting_date": entry.posting_date,
                    "remaining_quantity": entry.remaining_quantity,
                    "lot_no": entry.lot_no,
                    "serial_no": entry.serial_no,
                    "expiry_date": entry.expiry_date,
                }
            )

        # Apply prior preview reductions for the same item+lot+serial bucket
        if previous_reductions and reduction_key in previous_reductions:
            for prev_reduction in previous_reductions[reduction_key]:
                remaining_to_apply = prev_reduction
                for sim_entry in simulated_entries:
                    if remaining_to_apply <= 0:
                        break
                    if sim_entry["remaining_quantity"] <= 0:
                        continue
                    reduction = min(sim_entry["remaining_quantity"], remaining_to_apply)
                    sim_entry["remaining_quantity"] -= reduction
                    remaining_to_apply -= reduction

        remaining_to_reduce = quantity_to_reduce
        reduction_details = []

        for sim_entry in simulated_entries:
            if remaining_to_reduce <= 0:
                break

            current_remaining = sim_entry["remaining_quantity"]
            if current_remaining <= 0:
                continue

            reduction = min(current_remaining, remaining_to_reduce)
            new_remaining = current_remaining - reduction

            reduction_details.append(
                {
                    "entry_id": sim_entry["id"],
                    "current_remaining": current_remaining,
                    "reduction": reduction,
                    "new_remaining": new_remaining,
                    "document_no": sim_entry["document_no"],
                    "posting_date": sim_entry["posting_date"],
                    "lot_no": sim_entry["lot_no"],
                    "serial_no": sim_entry.get("serial_no"),
                    "expiry_date": sim_entry["expiry_date"],
                }
            )

            remaining_to_reduce -= reduction

        return {
            "total_reduction": quantity_to_reduce - remaining_to_reduce,
            "remaining_after_reduction": remaining_to_reduce,
            "reduction_details": reduction_details,
            "insufficient_inventory": remaining_to_reduce > 0,
            "lot_no": lot or None,
            "serial_no": serial or None,
        }

    def _calculate_cost_of_goods_sold(self, item, quantity_to_reduce, location):
        """Calculate the actual cost of goods sold based on FIFO method."""
        from items.models import ItemLedgerEntries

        # Get current inventory entries with remaining quantity > 0 and matching location
        # For items with tracking (lot numbers), order by expiry date first (FEFO - First Expired, First Out)
        # For items without tracking, use FIFO (First In, First Out) based on created_at
        if item.tracking_code:
            # Items with tracking: order by expiry_date (earliest first), then by created_at
            entries = ItemLedgerEntries.objects.filter(
                item=item, remaining_quantity__gt=0, location=location
            ).order_by(
                models.F("expiry_date").asc(
                    nulls_last=True
                ),  # Items without expiry date go last
                "created_at",
            )
        else:
            # Items without tracking: use FIFO based on created_at
            entries = ItemLedgerEntries.objects.filter(
                item=item, remaining_quantity__gt=0, location=location
            ).order_by("created_at")

        remaining_to_reduce = quantity_to_reduce
        total_cost = 0.0

        for entry in entries:
            if remaining_to_reduce <= 0:
                break

            current_remaining = entry.remaining_quantity
            if current_remaining <= 0:
                continue

            reduction = min(current_remaining, remaining_to_reduce)

            # Calculate the cost for this reduction
            # We need to get the cost from the ValueEntry associated with this ItemLedgerEntry
            from items.models import ValueEntry

            value_entries = ValueEntry.objects.filter(item_ledger_entry_no=entry.id)

            if value_entries.exists():
                # Calculate average cost per unit for this entry
                total_entry_cost = sum(float(ve.cost_amount) for ve in value_entries)
                total_entry_quantity = abs(
                    sum(float(ve.item_ledger_entry_quantity) for ve in value_entries)
                )

                if total_entry_quantity > 0:
                    cost_per_unit = total_entry_cost / total_entry_quantity
                    cost_for_reduction = cost_per_unit * reduction
                    total_cost += cost_for_reduction
            else:
                # Fallback: use the total cost from the entry if no value entries exist
                cost_per_unit = (
                    entry.total / abs(entry.quantity) if entry.quantity != 0 else 0
                )
                cost_for_reduction = cost_per_unit * reduction
                total_cost += cost_for_reduction

            remaining_to_reduce -= reduction

        return total_cost

    def _reduce_inventory_quantities(
        self, item, quantity_to_reduce, location, *, lot_no=None, serial_no=None
    ):
        """Actually reduce the remaining quantities in the database."""
        from items.models import ItemLedgerEntries

        lot = (lot_no or "").strip() if lot_no else ""
        serial = (serial_no or "").strip() if serial_no else ""

        entries = ItemLedgerEntries.objects.filter(
            item=item, remaining_quantity__gt=0, location=location
        )
        if serial:
            entries = entries.filter(serial_no__iexact=serial)
        if lot:
            entries = entries.filter(lot_no=lot)

        if item.tracking_code and not serial:
            # Lot / FEFO when no specific serial
            entries = entries.order_by(
                models.F("expiry_date").asc(nulls_last=True),
                "created_at",
            )
        else:
            entries = entries.order_by("created_at")

        remaining = quantity_to_reduce

        for entry in entries:
            if remaining <= 0:
                break

            reduction = min(entry.remaining_quantity, remaining)
            entry.remaining_quantity -= reduction
            entry.save()
            remaining -= reduction

        if remaining > 0:
            label = f" (serial {serial})" if serial else (f" (lot {lot})" if lot else "")
            raise Exception(
                f"Insufficient inventory for {item.item_name}{label}. "
                f"Shortage: {remaining} units"
            )

    def process(self):
        try:
            if not self._validate_invoice():
                return {
                    "success": False,
                    "message": "Invoice validation failed",
                    "entries": {},
                }

            transaction_no = f"S{self.invoice.invoice_no}-{self.invoice.posting_date.strftime('%Y%m%d')}-{self.invoice.id}"

            items_lines = []
            resource_lines = []
            for line in self.lines:
                if line.item:
                    genProductPostingGroup = line.item.general_product_posting_group
                    quantity_per_iuom = (
                        line.item_unit_of_measure.quantity_per_unit
                        if line.item_unit_of_measure
                        else 1
                    )
                    items_lines.append(
                        {
                            "item": line.item,
                            "genProductPostingGroup": genProductPostingGroup,
                            "genBusinessPostingGroup": self.genBusinessPostingGroup,
                            "amount": line.total_amount,
                            "gross_amount": line.gross_amount,
                            "discount_amount": line.line_discount_amount or 0,
                            "vat_amount": Decimal(
                                str(getattr(line, "vat_amount", 0) or 0)
                            ),
                            "quantity": line.quantity,
                            "location": line.location_code,
                            "item_unit_of_measure": line.item_unit_of_measure,
                            "sales_invoice_line": line.id,
                            "quantity_per_iuom": quantity_per_iuom,
                            "dimension_set": line.dimension_set,
                            "global_dimension_1": self._effective_line_global_dimension_1(
                                line
                            ),
                        }
                    )
                elif line.resource:
                    qty_per_uom = 1
                    uom_code = (
                        line.unit_of_measure.code if line.unit_of_measure else None
                    )
                    if uom_code and hasattr(line.resource, "get_available_uoms"):
                        uoms = line.resource.get_available_uoms
                        match = next(
                            (u for u in uoms if u.get("code") == uom_code), None
                        )
                        if match:
                            qty_per_uom = match.get("quantity_per_unit") or 1
                    quantity_base = (
                        (Decimal(str(line.quantity)) * qty_per_uom)
                        if qty_per_uom
                        else Decimal(str(line.quantity))
                    )
                    resource_lines.append(
                        {
                            "resource": line.resource,
                            "amount": line.total_amount,
                            "discount_amount": line.line_discount_amount or 0,
                            "vat_amount": Decimal(
                                str(getattr(line, "vat_amount", 0) or 0)
                            ),
                            "quantity": line.quantity,
                            "unit_of_measure": line.unit_of_measure,
                            "unit_price": line.unit_price,
                            "description": line.description
                            or (line.resource.name if line.resource else ""),
                            "qty_per_unit_of_measure": qty_per_uom,
                            "quantity_base": quantity_base,
                            "sales_invoice_line": line.id,
                        }
                    )

            if len(items_lines) > 0 or len(resource_lines) > 0:
                # Calculate subtotal from lines (item + resource, after line discounts)
                subtotal = Decimal(
                    sum(line["amount"] for line in items_lines)
                ) + Decimal(
                    sum(Decimal(str(line["amount"])) for line in resource_lines)
                )

                # Calculate invoice discount value
                invoice_discount_value = Decimal("0")
                if self.invoice.invoice_discount_type:
                    if self.invoice.invoice_discount_type == "amount":
                        invoice_discount_value = Decimal(
                            self.invoice.invoice_discount_amount or 0
                        )
                    elif self.invoice.invoice_discount_type == "percentage":
                        percentage = Decimal(
                            self.invoice.invoice_discount_percentage or 0
                        )
                        invoice_discount_value = (subtotal * percentage) / Decimal(
                            "100"
                        )

                # Final total after invoice discount (net sales excl VAT)
                total_amount = int(subtotal - invoice_discount_value)

                # Customer amount: amounts are always inclusive when VAT enabled - customer pays line total (no add)
                from financials.models import GeneralLedgerSetup

                gl_setup = GeneralLedgerSetup.objects.first()
                total_vat_val = getattr(
                    self.invoice, "total_vat_amount", None
                ) or Decimal("0")
                vat_int = int(Decimal(str(total_vat_val))) if total_vat_val else 0
                vat_enabled = (
                    gl_setup and getattr(gl_setup, "vat_enabled", False) and vat_int > 0
                )
                # When inclusive, total_amount already includes VAT - customer pays that
                customer_amount = total_amount
                self._vat_enabled = vat_enabled

                # Calculate discount ratio to apply proportionally to each line
                # This ensures receivables and sales GL entries match the net total_amount
                discount_ratio = Decimal("1")
                if subtotal > 0 and invoice_discount_value > 0:
                    discount_ratio = (subtotal - invoice_discount_value) / subtotal

                # Store discount ratio for use when creating GL entries
                self._invoice_discount_ratio = discount_ratio
                self._invoice_discount_value = invoice_discount_value

                # Determine cash payment balancing account (applies to all item types)
                bal_account = None
                if self.payment_method and self.payment_method.is_cash_payment():
                    # Check if payment method uses Bank Account
                    if (
                        self.payment_method.bal_account_type
                        == BalacingAccountType.Bank_Account.name
                        and self.payment_method.bal_bank_account_no
                    ):
                        # Use bank account posting logic - get G/L account for preview
                        from bank_account.utils import get_bank_account_gl_account
                        from bank_account.enums import BankAccountDocumentType

                        try:
                            # Get G/L account from bank account posting group (for preview)
                            bal_account = get_bank_account_gl_account(
                                self.payment_method.bal_bank_account_no
                            )

                            # Store bank account entry info for actual posting (not created here, just preview info)
                            self.bank_account_entries.append(
                                {
                                    "bank_account": self.payment_method.bal_bank_account_no,
                                    "posting_date": self.invoice.posting_date,
                                    "document_type": BankAccountDocumentType.Payment.name,
                                    "document_no": self.invoice.invoice_no,
                                    "description": f"Invoice {self.invoice.invoice_no}",
                                    "amount": customer_amount,  # Customer pays sales + VAT when enabled
                                    "bal_account_type": BalacingAccountType.Customer.name,
                                    "bal_account_no": self.customer.no,
                                    "global_dimension_1": self.global_dimension_1_value,
                                    "dimension_set": self.dimension_set_value,
                                    "transaction_no": transaction_no,
                                    "document_date": self.invoice.posting_date,
                                }
                            )
                        except Exception as e:
                            raise Exception(
                                f"Failed to get bank account G/L account: {str(e)}"
                            )
                    elif self.payment_method.bal_account_no:
                        # Use existing G/L Account logic
                        bal_account = self.payment_method.bal_account_no

                for item_line in items_lines:
                    line_dim = item_line.get("global_dimension_1")
                    line_dim_set = item_line.get("dimension_set")
                    general_posting_setup = GeneralPostingSetup.objects.filter(
                        general_product_posting_group=item_line[
                            "genProductPostingGroup"
                        ],
                        general_business_posting_group=self.genBusinessPostingGroup,
                    ).first()

                    if general_posting_setup:
                        # Check item type to determine posting logic
                        item_type = item_line["item"].type

                        # Service and Non-Inventory: Simplified posting (Receivables + Revenue only)
                        if item_type in (
                            InventoryType.Service.value,
                            InventoryType.NonInventory.value,
                        ):
                            sales_account = general_posting_setup.sales_account
                            discount_account = (
                                general_posting_setup.sales_line_discount_account
                            )
                            receivables_account = self.receivables_account

                            if not sales_account:
                                raise Exception(
                                    f"Sales account is not set for general posting setup with business posting group '{self.genBusinessPostingGroup.code}' and product posting group '{item_line['genProductPostingGroup'].code}'"
                                )

                            if (
                                item_line["discount_amount"] > 0
                                and not discount_account
                            ):
                                raise Exception(
                                    f"Sales line discount account is not set for general posting setup with business posting group '{self.genBusinessPostingGroup.code}' and product posting group '{item_line['genProductPostingGroup'].code}'"
                                )

                            if not receivables_account:
                                raise Exception(
                                    f"Receivables account is not set for customer posting group '{self.customer.customer_posting_group.code}'"
                                )

                            # Generate GL entries for Service items (Receivables + Revenue only)
                            # Apply invoice discount ratio to receivables only (net amount)
                            # Sales revenue: when inclusive, use base (amount - vat); else gross
                            net_line_amount = int(
                                Decimal(item_line["amount"])
                                * getattr(self, "_invoice_discount_ratio", Decimal("1"))
                            )
                            line_vat = int(item_line.get("vat_amount", 0) or 0)
                            if getattr(self, "_vat_enabled", False) and line_vat > 0:
                                gross_line_amount = int(
                                    Decimal(item_line["amount"])
                                    - Decimal(str(line_vat))
                                )
                                gross_line_amount = int(
                                    Decimal(gross_line_amount)
                                    * getattr(
                                        self, "_invoice_discount_ratio", Decimal("1")
                                    )
                                )
                            else:
                                gross_line_amount = item_line["gross_amount"]

                            self.gl_entries.extend(
                                [
                                    # Debit receivables account (net after invoice discount)
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": receivables_account,
                                        "description": f"Service Invoice {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": net_line_amount,
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    },
                                    # Credit sales account (Service Revenue) - gross amount before invoice discount
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": sales_account,
                                        "description": f"Service Revenue {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": -gross_line_amount,
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    },
                                ]
                            )

                            # Add discount entry if applicable
                            if item_line["discount_amount"] > 0:
                                self.gl_entries.append(
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": discount_account,
                                        "description": f"Service Line discount {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": item_line["discount_amount"],
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    }
                                )

                            # Service/Non-Inventory: Create Item Ledger + Value Entries with Cost Amount (Non-Invtbl.)
                            # Cost is stored in cost_amount_non_invtbl (not reconciled to G/L), like Business Central
                            quantity = int(
                                item_line["quantity"] * item_line["quantity_per_iuom"]
                            )
                            unit_cost = (
                                getattr(item_line["item"], "unit_cost", None) or 0
                            )
                            if callable(unit_cost):
                                unit_cost = unit_cost()
                            unit_cost = int(unit_cost) if unit_cost else 0
                            service_cost = unit_cost * abs(quantity)
                            net_line_amount = int(
                                Decimal(item_line["amount"])
                                * getattr(self, "_invoice_discount_ratio", Decimal("1"))
                            )
                            line_vat_svc = int(item_line.get("vat_amount", 0) or 0)
                            if (
                                getattr(self, "_vat_enabled", False)
                                and line_vat_svc > 0
                            ):
                                sales_amount_service = int(
                                    (
                                        Decimal(item_line["amount"])
                                        - Decimal(str(line_vat_svc))
                                    )
                                    * getattr(
                                        self, "_invoice_discount_ratio", Decimal("1")
                                    )
                                )
                            else:
                                sales_amount_service = net_line_amount
                            unit_price = net_line_amount / quantity if quantity else 0
                            total = quantity * unit_price

                            self.item_entries.extend(
                                [
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "entry_type": EntryType.Sales.value,
                                        "item": item_line["item"],
                                        "document_no": self.invoice.invoice_no,
                                        "description": f"Invoice {self.invoice.invoice_no}",
                                        "unit_of_measure": item_line[
                                            "item_unit_of_measure"
                                        ],
                                        "unit_price": unit_price,
                                        "date": self.invoice.posting_date,
                                        "user": self.user,
                                        "receipt_no": self.receipt_no,
                                        "location": item_line["location"],
                                        "quantity": -quantity,
                                        "remaining_quantity": 0,
                                        "cost_amount": 0,
                                        "sales_amount": sales_amount_service,
                                        "purchase_amount": 0,
                                        "total": -service_cost,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "document_type": DocumentType.Sales.value,
                                        "transaction_no": transaction_no,
                                    }
                                ]
                            )
                            self.value_entries.extend(
                                [
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "entry_type": EntryType.Sales.value,
                                        "document_no": self.invoice.invoice_no,
                                        "cost_amount": 0,
                                        "cost_amount_non_invtbl": service_cost,
                                        "cost_per_unit": unit_cost,
                                        "item_ledger_entry_quantity": -quantity,
                                        "invoiced_quantity": -quantity,
                                        "valued_quantity": -quantity,
                                        "item": item_line["item"],
                                        "general_product_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "inventory_posting_group": item_line[
                                            "item"
                                        ].inventory_posting_group,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "transaction_no": transaction_no,
                                        "sales_amount": sales_amount_service,
                                        "purchase_amount": 0,
                                    }
                                ]
                            )
                            continue

                        # Inventory items: Full posting logic (existing code)
                        inventory_posting_setup = InventoryPostingSetup.objects.filter(
                            location=item_line["location"],
                            inventory_posting_group=item_line[
                                "item"
                            ].inventory_posting_group,
                        ).first()

                        if inventory_posting_setup:
                            inventory_account = (
                                inventory_posting_setup.inventory_account
                            )
                            direct_cost_applied_account = (
                                general_posting_setup.direct_cost_applied_account
                            )
                            sales_account = general_posting_setup.sales_account
                            discount_account = (
                                general_posting_setup.sales_line_discount_account
                            )
                            receivables_account = self.receivables_account
                            cost_of_goods_sold_account = (
                                general_posting_setup.cogs_account
                            )

                            if not inventory_account:
                                raise Exception(
                                    f"Inventory account is not set for location '{item_line['location'].code}' and inventory posting group '{item_line['item'].inventory_posting_group.code}'"
                                )

                            if not direct_cost_applied_account:
                                raise Exception(
                                    f"Direct cost applied account is not set for general posting setup with business posting group '{self.genBusinessPostingGroup.code}' and product posting group '{item_line['genProductPostingGroup'].code}'"
                                )

                            if not sales_account:
                                raise Exception(
                                    f"Sales account is not set for general posting setup with business posting group '{self.genBusinessPostingGroup.code}' and product posting group '{item_line['genProductPostingGroup'].code}'"
                                )

                            if (
                                item_line["discount_amount"] > 0
                                and not discount_account
                            ):
                                raise Exception(
                                    f"Sales line discount account is not set for general posting setup with business posting group '{self.genBusinessPostingGroup.code}' and product posting group '{item_line['genProductPostingGroup'].code}'"
                                )

                            if not receivables_account:
                                raise Exception(
                                    f"Receivables account is not set for customer posting group '{self.customer.customer_posting_group.code}'"
                                )

                            # Calculate the actual cost of goods sold based on FIFO
                            quantity_to_reduce = (
                                item_line["quantity"] * item_line["quantity_per_iuom"]
                            )
                            actual_cost = self._calculate_cost_of_goods_sold(
                                item_line["item"],
                                quantity_to_reduce,
                                item_line["location"],
                            )

                            # Generate GL entries for sales
                            # Apply invoice discount ratio to receivables only (net amount)
                            # Sales: when inclusive, use base (amount - vat); else gross
                            net_line_amount = int(
                                Decimal(item_line["amount"])
                                * getattr(self, "_invoice_discount_ratio", Decimal("1"))
                            )
                            line_vat_inv = int(item_line.get("vat_amount", 0) or 0)
                            if (
                                getattr(self, "_vat_enabled", False)
                                and line_vat_inv > 0
                            ):
                                gross_line_amount = int(
                                    (
                                        Decimal(item_line["amount"])
                                        - Decimal(str(line_vat_inv))
                                    )
                                    * getattr(
                                        self, "_invoice_discount_ratio", Decimal("1")
                                    )
                                )
                            else:
                                gross_line_amount = item_line["gross_amount"]

                            self.gl_entries.extend(
                                [
                                    # Debit Cost of Goods Sold (actual cost, not sales amount)
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.default.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": cost_of_goods_sold_account,
                                        "description": f"Sales {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": actual_cost,
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    },
                                    # Credit Inventory account (actual cost, not sales amount)
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.default.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": inventory_account,
                                        "description": f"Sales {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": -actual_cost,
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    },
                                    # Debit receivables account (net after invoice discount)
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": receivables_account,
                                        "description": f"Sales {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": net_line_amount,
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    },
                                    # Credit sales account - gross amount before invoice discount
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": sales_account,
                                        "description": f"Sales {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": -gross_line_amount,
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    },
                                ]
                            )

                            if item_line["discount_amount"] > 0:
                                self.gl_entries.append(
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "gl_account": discount_account,
                                        "description": f"Line discount {self.customer.no} on {self.invoice.posting_date}",
                                        "department_code": (
                                            (
                                                line_dim
                                                or self.global_dimension_1_value
                                            ).code
                                            if (
                                                line_dim
                                                or self.global_dimension_1_value
                                            )
                                            else None
                                        ),
                                        "amount": item_line["discount_amount"],
                                        "gen_posting_type": GeneralPostingType.Sales.name,
                                        "dimension_set": line_dim_set,
                                        "global_dimension_1": line_dim
                                        or self.global_dimension_1_value,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "balance_account_type": BalacingAccountType.GLAccount.value,
                                        "user": self.user,
                                        "transaction_no": transaction_no,
                                    }
                                )

                            # Generate Item Ledger Entry
                            sales_line = self.lines.get(
                                id=item_line["sales_invoice_line"]
                            )
                            tracking_specs = TrackingSpecification.objects.filter(
                                sales_invoice_line=sales_line,
                            )
                            quantity = (
                                item_line["quantity"]
                                * item_line["quantity_per_iuom"]
                            )

                            if tracking_specs.exists():
                                total_spec_qty = sum(
                                    spec.quantity_base for spec in tracking_specs
                                ) or quantity
                                for spec in tracking_specs:
                                    spec_qty = int(spec.quantity_base or 0)
                                    if spec_qty <= 0:
                                        continue
                                    unit_price = (
                                        item_line["amount"] / total_spec_qty
                                        if total_spec_qty
                                        else 0
                                    )
                                    cost_share = (
                                        (actual_cost * spec_qty / total_spec_qty)
                                        if total_spec_qty
                                        else 0
                                    )
                                    sales_share = (
                                        (net_line_amount * spec_qty / total_spec_qty)
                                        if total_spec_qty
                                        else 0
                                    )
                                    total = spec_qty * unit_price
                                    self.item_entries.extend(
                                        [
                                            {
                                                "posting_date": self.invoice.posting_date,
                                                "entry_type": EntryType.Sales.value,
                                                "item": item_line["item"],
                                                "document_no": self.invoice.invoice_no,
                                                "description": f"Invoice {self.invoice.invoice_no}",
                                                "unit_of_measure": item_line[
                                                    "item_unit_of_measure"
                                                ],
                                                "unit_price": unit_price,
                                                "date": self.invoice.posting_date,
                                                "user": self.user,
                                                "receipt_no": self.receipt_no,
                                                "lot_no": spec.lot_no,
                                                "expiry_date": spec.expiry_date,
                                                "location": item_line["location"],
                                                "quantity": -spec_qty,
                                                "remaining_quantity": 0,
                                                "cost_amount": cost_share,
                                                "sales_amount": sales_share,
                                                "purchase_amount": 0,
                                                "total": total,
                                                "serial_no": spec.serial_no,
                                                "global_dimension_1": line_dim
                                                or self.global_dimension_1_value,
                                                "document_type": DocumentType.Sales.value,
                                                "transaction_no": transaction_no,
                                            }
                                        ]
                                    )
                                    self.value_entries.extend(
                                        [
                                            {
                                                "posting_date": self.invoice.posting_date,
                                                "entry_type": EntryType.Sales.value,
                                                "document_no": self.invoice.invoice_no,
                                                "cost_amount": cost_share,
                                                "cost_amount_non_invtbl": 0,
                                                "cost_per_unit": (
                                                    cost_share / spec_qty
                                                    if spec_qty > 0
                                                    else 0
                                                ),
                                                "item_ledger_entry_quantity": -spec_qty,
                                                "invoiced_quantity": -spec_qty,
                                                "valued_quantity": -spec_qty,
                                                "item": item_line["item"],
                                                "general_product_posting_group": item_line[
                                                    "genProductPostingGroup"
                                                ],
                                                "inventory_posting_group": item_line[
                                                    "item"
                                                ].inventory_posting_group,
                                                "global_dimension_1": line_dim
                                                or self.global_dimension_1_value,
                                                "transaction_no": transaction_no,
                                                "sales_amount": sales_share,
                                                "purchase_amount": 0,
                                            }
                                        ]
                                    )
                            elif sales_line.tracking_code:
                                # Legacy: lot picked into line.tracking_code
                                unit_price = item_line["amount"] / quantity
                                total = quantity * unit_price

                                self.item_entries.extend(
                                    [
                                        {
                                            "posting_date": self.invoice.posting_date,
                                            "entry_type": EntryType.Sales.value,
                                            "item": item_line["item"],
                                            "document_no": self.invoice.invoice_no,
                                            "description": f"Invoice {self.invoice.invoice_no}",
                                            "unit_of_measure": item_line[
                                                "item_unit_of_measure"
                                            ],
                                            "unit_price": unit_price,
                                            "date": self.invoice.posting_date,
                                            "user": self.user,
                                            "receipt_no": self.receipt_no,
                                            "lot_no": sales_line.tracking_code,
                                            "expiry_date": None,
                                            "location": item_line["location"],
                                            "quantity": -quantity,
                                            "remaining_quantity": 0,
                                            "cost_amount": actual_cost,
                                            "sales_amount": net_line_amount,
                                            "purchase_amount": 0,
                                            "total": total,
                                            "serial_no": None,
                                            "global_dimension_1": line_dim
                                            or self.global_dimension_1_value,
                                            "document_type": DocumentType.Sales.value,
                                            "transaction_no": transaction_no,
                                        }
                                    ]
                                )

                                self.value_entries.extend(
                                    [
                                        {
                                            "posting_date": self.invoice.posting_date,
                                            "entry_type": EntryType.Sales.value,
                                            "document_no": self.invoice.invoice_no,
                                            "cost_amount": actual_cost,
                                            "cost_amount_non_invtbl": 0,
                                            "cost_per_unit": (
                                                actual_cost / quantity
                                                if quantity > 0
                                                else 0
                                            ),
                                            "item_ledger_entry_quantity": -quantity,
                                            "invoiced_quantity": -quantity,
                                            "valued_quantity": -quantity,
                                            "item": item_line["item"],
                                            "general_product_posting_group": item_line[
                                                "genProductPostingGroup"
                                            ],
                                            "inventory_posting_group": item_line[
                                                "item"
                                            ].inventory_posting_group,
                                            "global_dimension_1": line_dim
                                            or self.global_dimension_1_value,
                                            "transaction_no": transaction_no,
                                            "sales_amount": net_line_amount,
                                            "purchase_amount": 0,
                                        }
                                    ]
                                )
                            else:
                                quantity = (
                                    item_line["quantity"]
                                    * item_line["quantity_per_iuom"]
                                )
                                unit_price = item_line["amount"] / quantity
                                total = quantity * unit_price

                                self.item_entries.extend(
                                    [
                                        {
                                            "posting_date": self.invoice.posting_date,
                                            "entry_type": EntryType.Sales.value,
                                            "item": item_line["item"],
                                            "document_no": self.invoice.invoice_no,
                                            "description": f"Invoice {self.invoice.invoice_no}",
                                            "unit_of_measure": item_line[
                                                "item_unit_of_measure"
                                            ],
                                            "unit_price": unit_price,
                                            "date": self.invoice.posting_date,
                                            "user": self.user,
                                            "receipt_no": self.receipt_no,
                                            "location": item_line["location"],
                                            "quantity": -quantity,
                                            "remaining_quantity": 0,
                                            "cost_amount": actual_cost,
                                            "sales_amount": net_line_amount,  # Net amount after invoice discount
                                            "purchase_amount": 0,
                                            "total": total,
                                            "global_dimension_1": line_dim
                                            or self.global_dimension_1_value,
                                            "transaction_no": transaction_no,
                                        }
                                    ]
                                )

                                self.value_entries.extend(
                                    [
                                        {
                                            "posting_date": self.invoice.posting_date,
                                            "entry_type": EntryType.Sales.value,
                                            "document_no": self.invoice.invoice_no,
                                            "cost_amount": actual_cost,
                                            "cost_amount_non_invtbl": 0,
                                            "cost_per_unit": (
                                                actual_cost / quantity
                                                if quantity > 0
                                                else 0
                                            ),
                                            "item_ledger_entry_quantity": -quantity,
                                            "invoiced_quantity": -quantity,
                                            "valued_quantity": -quantity,
                                            "item": item_line["item"],
                                            "general_product_posting_group": item_line[
                                                "genProductPostingGroup"
                                            ],
                                            "inventory_posting_group": item_line[
                                                "item"
                                            ].inventory_posting_group,
                                            "global_dimension_1": line_dim
                                            or self.global_dimension_1_value,
                                            "transaction_no": transaction_no,
                                            "sales_amount": net_line_amount,  # Net amount after invoice discount
                                            "purchase_amount": 0,
                                        }
                                    ]
                                )
                        else:
                            loc = item_line.get("location")
                            ipg = item_line["item"].inventory_posting_group
                            loc_code = getattr(loc, "code", None) or "?"
                            ipg_code = getattr(ipg, "code", None) if ipg else "(none)"
                            raise Exception(
                                "Inventory Posting Setup is not configured for this sale: "
                                f"location '{loc_code}', inventory posting group '{ipg_code}'. "
                                "Add an Inventory Posting Setup for this location and posting group "
                                "before posting inventory sales (Django Admin: Postings / Inventory Posting Setup, "
                                "or run: python manage.py tenant_command seed_inventory_posting_setup --schema=<tenant>)."
                                )
                    else:
                        gppg = item_line.get("genProductPostingGroup")
                        gbpg = self.genBusinessPostingGroup
                        gppg_code = getattr(gppg, "code", None) or "(none)"
                        gbpg_code = getattr(gbpg, "code", None) or "(none)"
                        raise Exception(
                            "General Posting Setup is not configured for this sale line: "
                            f"business posting group '{gbpg_code}', product posting group '{gppg_code}'. "
                            "Add a General Posting Setup row for this combination "
                            "(Django Admin: Postings / General Posting Setup)."
                        )

                # Add invoice discount GL entry if invoice discount exists
                if invoice_discount_value > 0:
                    # Get discount account from first item's posting setup (or use a representative one)
                    representative_prod_posting_group = None
                    if items_lines:
                        representative_prod_posting_group = items_lines[0][
                            "genProductPostingGroup"
                        ]

                    if representative_prod_posting_group:
                        general_posting_setup = GeneralPostingSetup.objects.filter(
                            general_product_posting_group=representative_prod_posting_group,
                            general_business_posting_group=self.genBusinessPostingGroup,
                        ).first()

                        if general_posting_setup:
                            discount_account = (
                                general_posting_setup.sales_line_discount_account
                            )

                            if not discount_account:
                                raise Exception(
                                    f"Sales line discount account is not set for general posting setup with business posting group '{self.genBusinessPostingGroup.code}' and product posting group '{representative_prod_posting_group.code}'. Invoice discount cannot be posted."
                                )

                            self.gl_entries.append(
                                {
                                    "posting_date": self.invoice.posting_date,
                                    "document_type": DocumentType.Invoice.value,
                                    "document_no": self.invoice.invoice_no,
                                    "gl_account": discount_account,
                                    "description": f"Invoice discount {self.customer.no} on {self.invoice.posting_date}",
                                    "department_code": (
                                        self.global_dimension_1_value.code
                                        if self.global_dimension_1_value
                                        else None
                                    ),
                                    "amount": int(invoice_discount_value),
                                    "gen_posting_type": GeneralPostingType.Sales.name,
                                    "global_dimension_1": self.global_dimension_1_value,
                                    "gen_bus_posting_group": self.genBusinessPostingGroup,
                                    "gen_prod_posting_group": representative_prod_posting_group,
                                    "balance_account_type": BalacingAccountType.GLAccount.value,
                                    "user": self.user,
                                    "transaction_no": transaction_no,
                                }
                            )

                # VAT GL entry (when vat_enabled and total_vat_amount > 0)
                try:
                    from financials.models import GeneralLedgerSetup
                    from financials.vat import get_vat_posting_setup

                    gl_setup = GeneralLedgerSetup.objects.first()
                    total_vat = getattr(
                        self.invoice, "total_vat_amount", None
                    ) or Decimal("0")
                    if (
                        gl_setup
                        and getattr(gl_setup, "vat_enabled", False)
                        and total_vat
                        and Decimal(str(total_vat)) > 0
                    ):
                        vat_bus = getattr(
                            self.customer, "vat_business_posting_group", None
                        )
                        sales_vat_account = None
                        for line in self.lines:
                            vat_prod = None
                            if line.item:
                                vat_prod = getattr(
                                    line.item, "vat_product_posting_group", None
                                )
                            elif line.resource:
                                vat_prod = getattr(
                                    line.resource, "vat_product_posting_group", None
                                )
                            setup = get_vat_posting_setup(vat_bus, vat_prod)
                            if (
                                setup
                                and setup.sales_vat_account
                                and getattr(line, "vat_amount", 0)
                            ):
                                sales_vat_account = setup.sales_vat_account
                                break
                        if sales_vat_account:
                            rep_group = None
                            if items_lines:
                                rep_group = items_lines[0].get("genProductPostingGroup")
                            if not rep_group and self.lines.first():
                                ln = self.lines.first()
                                if ln.item:
                                    rep_group = ln.item.general_product_posting_group
                            # No extra VAT Receivable debit - amounts are inclusive, receivables already include VAT
                            self.gl_entries.append(
                                {
                                    "posting_date": self.invoice.posting_date,
                                    "document_type": DocumentType.Invoice.value,
                                    "document_no": self.invoice.invoice_no,
                                    "gl_account": sales_vat_account,
                                    "description": f"VAT Output {self.customer.no} on {self.invoice.posting_date}",
                                    "department_code": (
                                        self.global_dimension_1_value.code
                                        if self.global_dimension_1_value
                                        else None
                                    ),
                                    "amount": -int(Decimal(str(total_vat))),
                                    "gen_posting_type": GeneralPostingType.Sales.name,
                                    "global_dimension_1": self.global_dimension_1_value,
                                    "gen_bus_posting_group": self.genBusinessPostingGroup,
                                    "gen_prod_posting_group": rep_group,
                                    "balance_account_type": BalacingAccountType.GLAccount.value,
                                    "user": self.user,
                                    "transaction_no": transaction_no,
                                }
                            )
                            # Populate vat_entries subledger (BC-style, per-line)
                            # Amounts column is always inclusive of VAT when VAT is enabled
                            prices_incl = True
                            for line in self.lines:
                                line_vat = Decimal(
                                    str(getattr(line, "vat_amount", 0) or 0)
                                )
                                if line_vat <= 0:
                                    continue
                                vat_prod = None
                                if line.item:
                                    vat_prod = getattr(
                                        line.item, "vat_product_posting_group", None
                                    )
                                elif line.resource:
                                    vat_prod = getattr(
                                        line.resource,
                                        "vat_product_posting_group",
                                        None,
                                    )
                                setup = get_vat_posting_setup(vat_bus, vat_prod)
                                if not setup or not setup.sales_vat_account:
                                    continue
                                line_total = Decimal(str(line.total_amount or 0))
                                base = (
                                    line_total - line_vat if prices_incl else line_total
                                )
                                gen_prod = (
                                    line.item.general_product_posting_group
                                    if line.item
                                    else rep_group
                                )
                                # Use line dimension, then invoice, then user (ensure VAT entries get dimension)
                                line_dim1 = getattr(line, "global_dimension_1", None)
                                vat_dim1 = line_dim1 or self.global_dimension_1_value
                                self.vat_entries.append(
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Invoice.value,
                                        "document_no": self.invoice.invoice_no,
                                        "type": "Sale",
                                        "vat_business_posting_group": vat_bus,
                                        "vat_product_posting_group": vat_prod,
                                        "base": int(base),
                                        "amount": int(line_vat),
                                        "vat_percent": setup.vat_percent,
                                        "vat_calculation_type": (
                                            setup.vat_calculation_type or "Normal"
                                        ),
                                        "vat_account": setup.sales_vat_account,
                                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                                        "gen_prod_posting_group": gen_prod,
                                        "global_dimension_1": vat_dim1,
                                        "transaction_no": transaction_no,
                                        "user": self.user,
                                    }
                                )
                except Exception:
                    pass

                # Customer Ledger Entries (use customer_amount = sales + VAT when VAT enabled)
                self.detailed_customer_entries.extend(
                    [
                        {
                            "posting_date": self.invoice.posting_date,
                            "entry_type": "Initial Entry",
                            "document_type": "Invoice",
                            "document_no": self.invoice.invoice_no,
                            "customer_no": self.customer.no,
                            "customer": self.customer,
                            # BC: Invoice Initial Entry is positive (receivable).
                            "amount": customer_amount,
                            "initial_entry_due_date": self.invoice.due_date,
                            "credit_amount": 0,
                            "debit_amount": customer_amount,
                            "transaction_no": transaction_no,
                            "initial_document_type": "Invoice",
                            "customer_ledger_entry": "10001",  # Will be replaced with actual entry ID during posting
                            "applied_customer_ledger_entry_no": 0,
                            "unapplied_by_entry_no": 0,
                            "unapplied": False,
                            "global_dimension_1": self.global_dimension_1_value,
                            "dimension_set": self.dimension_set_value,
                        }
                    ]
                )

                if self.payment_method and self.payment_method.is_cash_payment():
                    self.detailed_customer_entries.extend(
                        [
                            {
                                "posting_date": self.invoice.posting_date,
                                "entry_type": "Initial Entry",
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "customer_no": self.customer.no,
                                "customer": self.customer,
                                "amount": -customer_amount,
                                "initial_entry_due_date": self.invoice.due_date,
                                "transaction_no": transaction_no,
                                "debit_amount": 0,
                                "credit_amount": customer_amount,
                                "initial_document_type": "Payment",
                                "customer_ledger_entry": "10002",  # Will be replaced with actual entry ID during posting
                                "applied_customer_ledger_entry_no": 0,
                                "unapplied_by_entry_no": 0,
                                "unapplied": False,
                                "global_dimension_1": self.global_dimension_1_value,
                                "dimension_set": self.dimension_set_value,
                            },
                            {
                                "posting_date": self.invoice.posting_date,
                                "entry_type": "Application",
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "customer_no": self.customer.no,
                                "customer": self.customer,
                                "amount": -customer_amount,
                                "initial_entry_due_date": self.invoice.due_date,
                                "debit_amount": 0,
                                "credit_amount": customer_amount,
                                "initial_document_type": "Invoice",
                                "customer_ledger_entry": "10001",  # Will be replaced with actual entry ID during posting
                                "applied_customer_ledger_entry_no": 10002,  # Will be replaced with actual entry ID during posting
                                "transaction_no": transaction_no,
                                "unapplied_by_entry_no": 0,
                                "unapplied": False,
                                "global_dimension_1": self.global_dimension_1_value,
                                "dimension_set": self.dimension_set_value,
                            },
                            {
                                "posting_date": self.invoice.posting_date,
                                "entry_type": "Application",
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "customer_no": self.customer.no,
                                "customer": self.customer,
                                "initial_document_type": "Payment",
                                "debit_amount": customer_amount,
                                "credit_amount": 0,
                                "customer_ledger_entry": "10002",  # Will be replaced with actual entry ID during posting
                                "applied_customer_ledger_entry_no": 10002,  # Will be replaced with actual entry ID during posting
                                "amount": customer_amount,
                                "initial_entry_due_date": self.invoice.due_date,
                                "transaction_no": transaction_no,
                                "unapplied_by_entry_no": 0,
                                "unapplied": False,
                                "global_dimension_1": self.global_dimension_1_value,
                                "dimension_set": self.dimension_set_value,
                            },
                        ]
                    )

                self.customer_entries.append(
                    {
                        "posting_date": self.invoice.posting_date,
                        "document_date": self.invoice.document_date,
                        "document_type": DocumentType.Invoice.value,
                        "document_no": self.invoice.invoice_no,
                        "external_document_no": self.invoice.customer_invoice_no,
                        "customer_no": self.customer.no,
                        "customer": self.customer,
                        "description": f"Invoice {self.invoice.invoice_no}",
                        "payment_method": self.payment_method,
                        "original_amount": customer_amount,
                        "amount": customer_amount,
                        "remaining_amount": (
                            0
                            if (
                                self.payment_method
                                and self.payment_method.is_cash_payment()
                            )
                            else customer_amount
                        ),
                        "sales": customer_amount,
                        # BC: cash invoice is closed by the payment application.
                        "open": not (
                            self.payment_method
                            and self.payment_method.is_cash_payment()
                        ),
                        "due_date": self.invoice.due_date,
                        "global_dimension_1": self.global_dimension_1_value,
                        "dimension_set": self.dimension_set_value,
                        "user": self.user,
                        "transaction_no": transaction_no,
                    }
                )

                if self.payment_method and self.payment_method.is_cash_payment():
                    self.customer_entries.append(
                        {
                            "posting_date": self.invoice.posting_date,
                            "document_date": self.invoice.document_date,
                            "document_type": DocumentType.Payment.value,
                            "document_no": self.invoice.invoice_no,
                            "external_document_no": self.invoice.invoice_no,
                            "customer_no": self.customer.no,
                            "customer": self.customer,
                            "description": f"Invoice {self.invoice.invoice_no}",
                            "payment_method": self.payment_method,
                            "original_amount": -customer_amount,
                            "amount": -customer_amount,
                            "remaining_amount": 0,
                            "sales": 0,
                            "open": False,
                            "due_date": self.invoice.due_date,
                            "global_dimension_1": self.global_dimension_1_value,
                            "dimension_set": self.dimension_set_value,
                            "user": self.user,
                            "transaction_no": transaction_no,
                        }
                    )

                # Add payment entries if cash payment (applies to all item types)
                # This is moved outside the item loop so it applies to both Inventory and Service items
                if (
                    self.payment_method
                    and self.payment_method.is_cash_payment()
                    and bal_account
                ):
                    # Get receivables account (same for all items)
                    receivables_account = self.receivables_account

                    # Get a representative product posting group for the payment entry
                    # Use the first item's posting group, or first resource's, or None
                    representative_prod_posting_group = None
                    if items_lines:
                        representative_prod_posting_group = items_lines[0][
                            "genProductPostingGroup"
                        ]
                    elif (
                        resource_lines
                        and resource_lines[0]["resource"].general_product_posting_group
                    ):
                        representative_prod_posting_group = resource_lines[0][
                            "resource"
                        ].general_product_posting_group

                    self.gl_entries.extend(
                        [
                            # debit the cash account
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "gl_account": bal_account,
                                "description": f"Invoice {self.invoice.invoice_no}",
                                "department_code": (
                                    self.global_dimension_1_value.code
                                    if self.global_dimension_1_value
                                    else None
                                ),
                                "amount": customer_amount,
                                "gen_posting_type": GeneralPostingType.Sales.name,
                                "global_dimension_1": self.global_dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": representative_prod_posting_group,
                                "balance_account_type": BalacingAccountType.Customer.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                            # credit the receivables account
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": "Payment",
                                "document_no": self.invoice.invoice_no,
                                "gl_account": receivables_account,
                                "description": f"Invoice {self.invoice.invoice_no}",
                                "department_code": (
                                    self.global_dimension_1_value.code
                                    if self.global_dimension_1_value
                                    else None
                                ),
                                "amount": -customer_amount,
                                "gen_posting_type": GeneralPostingType.Sales.name,
                                "global_dimension_1": self.global_dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": representative_prod_posting_group,
                                "balance_account_type": BalacingAccountType.GLAccount.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                        ]
                    )

            # Resource lines: GL entries (Receivables + Sales) and resource ledger preview
            for resource_line in resource_lines:
                resource = resource_line["resource"]
                gen_product_posting_group = getattr(
                    resource, "general_product_posting_group", None
                )
                if not gen_product_posting_group:
                    raise Exception(
                        f"Resource {resource.code} ({resource.name}) does not have a General Product Posting Group assigned. "
                        "Please set it on the resource card."
                    )
                general_posting_setup = GeneralPostingSetup.objects.filter(
                    general_product_posting_group=gen_product_posting_group,
                    general_business_posting_group=self.genBusinessPostingGroup,
                ).first()
                if not general_posting_setup:
                    raise Exception(
                        f"General posting setup not found for resource posting group '{gen_product_posting_group.code}' "
                        f"and business posting group '{self.genBusinessPostingGroup.code}'"
                    )
                sales_account = general_posting_setup.sales_account
                if not sales_account:
                    raise Exception(
                        f"Sales account is not set for general posting setup (resource: {resource.code})"
                    )
                net_line_amount = int(
                    Decimal(str(resource_line["amount"]))
                    * getattr(self, "_invoice_discount_ratio", Decimal("1"))
                )
                line_vat_res = int(resource_line.get("vat_amount", 0) or 0)
                if getattr(self, "_vat_enabled", False) and line_vat_res > 0:
                    sales_amount = int(
                        (
                            Decimal(str(resource_line["amount"]))
                            - Decimal(str(line_vat_res))
                        )
                        * getattr(self, "_invoice_discount_ratio", Decimal("1"))
                    )
                else:
                    sales_amount = net_line_amount
                self.gl_entries.extend(
                    [
                        {
                            "posting_date": self.invoice.posting_date,
                            "document_type": DocumentType.Invoice.value,
                            "document_no": self.invoice.invoice_no,
                            "gl_account": self.receivables_account,
                            "description": f"Resource Invoice {self.customer.no} on {self.invoice.posting_date}",
                            "department_code": (
                                self.global_dimension_1_value.code
                                if self.global_dimension_1_value
                                else None
                            ),
                            "amount": net_line_amount,
                            "gen_posting_type": GeneralPostingType.Sales.name,
                            "global_dimension_1": self.global_dimension_1_value,
                            "gen_bus_posting_group": self.genBusinessPostingGroup,
                            "gen_prod_posting_group": gen_product_posting_group,
                            "balance_account_type": BalacingAccountType.GLAccount.value,
                            "user": self.user,
                            "transaction_no": transaction_no,
                        },
                        {
                            "posting_date": self.invoice.posting_date,
                            "document_type": DocumentType.Invoice.value,
                            "document_no": self.invoice.invoice_no,
                            "gl_account": sales_account,
                            "description": f"Resource Revenue {self.customer.no} on {self.invoice.posting_date}",
                            "department_code": (
                                self.global_dimension_1_value.code
                                if self.global_dimension_1_value
                                else None
                            ),
                            "amount": -sales_amount,
                            "gen_posting_type": GeneralPostingType.Sales.name,
                            "global_dimension_1": self.global_dimension_1_value,
                            "gen_bus_posting_group": self.genBusinessPostingGroup,
                            "gen_prod_posting_group": gen_product_posting_group,
                            "balance_account_type": BalacingAccountType.GLAccount.value,
                            "user": self.user,
                            "transaction_no": transaction_no,
                        },
                    ]
                )
                unit_cost = getattr(resource, "unit_cost", 0) or 0
                total_cost = float(unit_cost) * float(resource_line["quantity"])
                self.resource_ledger_entries.append(
                    {
                        "entry_type": "Sale",
                        "document_no": self.invoice.invoice_no,
                        "posting_date": self.invoice.posting_date,
                        "resource": resource,
                        "resource_no": resource.code,
                        "description": resource_line["description"],
                        "quantity": resource_line["quantity"],
                        "unit_of_measure": resource_line["unit_of_measure"],
                        "unit_of_measure_code": (
                            resource_line["unit_of_measure"].code
                            if resource_line["unit_of_measure"]
                            else None
                        ),
                        "total_cost": total_cost,
                        "total_price": float(resource_line["amount"]),
                        "unit_price": float(resource_line["unit_price"]),
                        "source_type": "Document",
                        "source_no": self.invoice.invoice_no,
                        "qty_per_unit_of_measure": resource_line[
                            "qty_per_unit_of_measure"
                        ],
                        "quantity_base": resource_line["quantity_base"],
                    }
                )

            # Calculate inventory reduction preview for each item (Inventory items only).
            # Must mirror SalesInvoicePostingProcessor lot/serial reduction so Preview
            # Posting fails for the same shortages as Post (Business Central parity).
            inventory_reduction_preview = []
            previous_reductions = {}  # key: item_no|lot|serial → list of qty

            for line in self.lines:
                if not line.item:
                    continue
                if line.item.type in (
                    InventoryType.Service.value,
                    InventoryType.NonInventory.value,
                ):
                    continue

                quantity_per_iuom = (
                    line.item_unit_of_measure.quantity_per_unit
                    if line.item_unit_of_measure
                    else 1
                )
                quantity_to_reduce = line.quantity * quantity_per_iuom
                location = line.location_code
                tracking_specs = list(line.tracking_specifications)

                def _append_preview(qty, lot_no=None, serial_no=None):
                    lot = (lot_no or "").strip() if lot_no else ""
                    serial = (serial_no or "").strip() if serial_no else ""
                    reduction_key = f"{line.item.no}|{lot}|{serial}"
                    reduction_info = self._calculate_inventory_reduction_preview(
                        line.item,
                        qty,
                        location,
                        previous_reductions,
                        lot_no=lot or None,
                        serial_no=serial or None,
                    )
                    previous_reductions.setdefault(reduction_key, []).append(qty)
                    inventory_reduction_preview.append(
                        {
                            "item": line.item,
                            "quantity_to_reduce": qty,
                            "reduction_info": reduction_info,
                            "lot_no": lot or None,
                            "serial_no": serial or None,
                        }
                    )

                if tracking_specs:
                    for spec in tracking_specs:
                        spec_qty = int(spec.quantity_base or 0)
                        if spec_qty <= 0:
                            continue
                        _append_preview(
                            spec_qty,
                            lot_no=spec.lot_no,
                            serial_no=spec.serial_no,
                        )
                elif line.tracking_code:
                    _append_preview(quantity_to_reduce, lot_no=line.tracking_code)
                else:
                    _append_preview(quantity_to_reduce)

            return {
                "gl_entries": self._consolidate_gl_entries(),
                "customer_entries": self.customer_entries,
                "item_entries": self.item_entries,
                "resource_ledger_entries": self.resource_ledger_entries,
                "vat_entries": self.vat_entries,
                "detailed_customer_entries": self.detailed_customer_entries,
                "value_entries": self.value_entries,
                "bank_account_entries": self.bank_account_entries,
                "inventory_reduction_preview": inventory_reduction_preview,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing invoice: {e}",
                "entries": {},
            }


def resolve_sales_ledger_document_nos(posted_invoice):
    """
    Document numbers used on G/L, customer, item, value, bank, and VAT entries when a
    sale is posted. These are usually SalesInvoice.invoice_no (e.g. SIN-000007), not
    PostedSalesInvoice.no (posted-invoice number series).
    """
    nos = set()
    for attr in ("invoice_no", "no"):
        val = getattr(posted_invoice, attr, None)
        if val:
            nos.add(val)

    customer = getattr(posted_invoice, "customer", None)
    customer_id = getattr(customer, "pk", None)
    customer_invoice_no = getattr(posted_invoice, "customer_invoice_no", None)

    if customer_invoice_no and customer_id:
        sales_invoice_no = (
            SalesInvoice.objects.filter(
                customer_invoice_no=customer_invoice_no,
                customer_id=customer_id,
            )
            .values_list("invoice_no", flat=True)
            .first()
        )
        if sales_invoice_no:
            nos.add(sales_invoice_no)

    posted_no = getattr(posted_invoice, "no", None)
    if posted_no and customer_id:
        psi = PostedSalesInvoice.objects.filter(
            no=posted_no,
            customer_id=customer_id,
        ).first()
        if psi and psi.customer_invoice_no:
            sales_invoice_no = (
                SalesInvoice.objects.filter(
                    customer_invoice_no=psi.customer_invoice_no,
                    customer_id=customer_id,
                )
                .values_list("invoice_no", flat=True)
                .first()
            )
            if sales_invoice_no:
                nos.add(sales_invoice_no)
            nos.add(psi.no)

    nos.discard(None)
    nos.discard("")
    return nos


def sales_ledger_document_filter(posted_invoice):
    return Q(document_no__in=resolve_sales_ledger_document_nos(posted_invoice))


class SalesInvoiceReversalProcessor:
    """
    Preview what will happen when reversing a posted sales invoice.
    This processor calculates opposite entries but does NOT save them.
    """

    def __init__(self, posted_invoice, request):
        self.posted_invoice = posted_invoice
        self.user = request.user
        self.lines = posted_invoice.posted_sales_invoice_lines.all()
        self.customer = posted_invoice.customer

        # Storage for reversal entries
        self.reversal_gl_entries = []
        self.reversal_customer_entries = []
        self.reversal_item_entries = []
        self.reversal_value_entries = []
        self.reversal_detailed_customer_entries = []
        self.reversal_bank_entries = []  # For bank account ledger entries
        self.reversal_vat_entries = []  # For VAT subledger reversal
        self.inventory_restoration_preview = []

    def _ledger_document_filter(self):
        return sales_ledger_document_filter(self.posted_invoice)

    def _validate_reversal(self):
        """Validate that invoice can be reversed"""
        if self.posted_invoice.reversed:
            raise Exception(
                f"Invoice {self.posted_invoice.no} has already been reversed on {self.posted_invoice.reversed_date}"
            )

        if self.posted_invoice.status != "Posted":
            raise Exception(
                f"Only posted invoices can be reversed. Current status: {self.posted_invoice.status}"
            )

        # Check if there are credit memos already
        if self.posted_invoice.credit_memos.filter(status="Posted").exists():
            raise Exception(
                f"Invoice {self.posted_invoice.no} already has credit memos posted against it"
            )

        return True

    def process(self):
        """
        Generate preview of reversal entries.
        Creates OPPOSITE entries to the original posting.
        """
        try:
            self._validate_reversal()

            # Find original entries and create opposite entries
            self._find_and_reverse_gl_entries()
            self._find_and_reverse_customer_entries()
            self._find_and_reverse_item_entries()
            self._find_and_reverse_value_entries()
            self._find_and_reverse_bank_entries()  # Add bank ledger entry reversal
            self._find_and_reverse_vat_entries()  # Add VAT subledger reversal
            self._calculate_inventory_restoration()

            return {
                "success": True,
                "gl_entries": self.reversal_gl_entries,
                "customer_entries": self.reversal_customer_entries,
                "item_entries": self.reversal_item_entries,
                "value_entries": self.reversal_value_entries,
                "detailed_customer_entries": self.reversal_detailed_customer_entries,
                "bank_entries": self.reversal_bank_entries,  # Include bank entries
                "reversal_vat_entries": self.reversal_vat_entries,
                "inventory_restoration_preview": self.inventory_restoration_preview,
            }

        except Exception as e:
            return {"success": False, "message": str(e)}

    def _find_and_reverse_gl_entries(self):
        """Find original GL entries and create opposite entries (includes both Invoice and Payment entries)"""
        from decimal import Decimal

        # Get ALL GL entries for this document (both Invoice and Payment entries)
        original_entries = GeneralLedgerEntry.objects.filter(
            self._ledger_document_filter()
        )

        for entry in original_entries:
            # Convert to Decimal to ensure numeric type
            amount = Decimal(str(entry.amount)) if entry.amount else Decimal("0")

            self.reversal_gl_entries.append(
                {
                    "posting_date": entry.posting_date,  # FIX: Use original entry's posting_date
                    "document_type": "Credit Memo",  # All reversals are Credit Memo type
                    "original_document_type": entry.document_type,  # Preserve original (Invoice or Payment)
                    "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                    "gl_account": entry.gl_account,
                    "description": f"Reversal of {entry.document_type} {entry.document_no}",
                    "amount": -amount,  # OPPOSITE SIGN
                    "gen_posting_type": entry.general_posting_type,
                    "dimension_set": entry.dimension_set,
                    "global_dimension_1": entry.global_dimension_1,
                    "global_dimension_2": entry.global_dimension_2,
                    "gen_bus_posting_group": entry.general_business_posting_group,
                    "gen_prod_posting_group": entry.general_product_posting_group,
                    "balance_account_type": entry.balancing_account_type,
                    "user": self.user,
                    "transaction_no": f"REV-{entry.transaction_no}",
                    "original_amount": amount,  # For preview display
                }
            )

    def _find_and_reverse_customer_entries(self):
        """Find original customer ledger entries and create opposite entries"""
        from decimal import Decimal

        original_entries = CustomerLedgerEntry.objects.filter(
            self._ledger_document_filter()
        )

        for entry in original_entries:
            # Convert to Decimal to ensure numeric type
            original_amount = (
                Decimal(str(entry.original_amount))
                if entry.original_amount
                else Decimal("0")
            )
            amount = Decimal(str(entry.amount)) if entry.amount else Decimal("0")
            sales = Decimal(str(entry.sales)) if entry.sales else Decimal("0")

            self.reversal_customer_entries.append(
                {
                    "posting_date": entry.posting_date,  # FIX: Use original entry's posting_date
                    "document_date": entry.document_date,  # FIX: Use original entry's document_date
                    "document_type": "Credit Memo",
                    "original_document_type": entry.document_type,  # Preserve original type
                    "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                    "customer": entry.customer,
                    "description": f"Reversal of {entry.description}",
                    "payment_method": entry.payment_method,
                    "original_amount": -original_amount,  # OPPOSITE (for posting)
                    "original_amount_before_reversal": original_amount,  # For display
                    "amount": -amount,  # OPPOSITE (for posting)
                    "amount_before_reversal": amount,  # For display
                    "sales": -sales,  # OPPOSITE (for posting)
                    "sales_before_reversal": sales,  # For display
                    "open": False,
                    "due_date": entry.due_date,
                    "global_dimension_1": entry.global_dimension_1,
                    "dimension_set": getattr(entry, "dimension_set", None),
                    "user": self.user,
                    "transaction_no": f"REV-{entry.transaction_no}",
                }
            )

    def _find_and_reverse_item_entries(self):
        """Find original item ledger entries and create opposite entries"""
        from decimal import Decimal

        original_entries = ItemLedgerEntries.objects.filter(
            self._ledger_document_filter()
        )

        for entry in original_entries:
            # Convert to Decimal to ensure numeric type
            quantity = Decimal(str(entry.quantity)) if entry.quantity else Decimal("0")
            total = Decimal(str(entry.total)) if entry.total else Decimal("0")

            self.reversal_item_entries.append(
                {
                    "posting_date": entry.posting_date,  # FIX: Use original entry's posting_date
                    "entry_type": "Positive Adjmt.",
                    "original_entry_type": entry.entry_type,  # Preserve original
                    "item": entry.item,
                    "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                    "description": f"Reversal of {entry.description}",
                    "location": entry.location,
                    "quantity": -quantity,  # OPPOSITE (positive to restore)
                    "quantity_before_reversal": quantity,  # For display
                    "remaining_quantity": -quantity,
                    "total": -total,  # ✅ OPPOSITE total amount
                    "total_before_reversal": total,  # For display
                    "unit_of_measure_code": entry.unit_of_measure_code,
                    "global_dimension_1": entry.global_dimension_1,
                    "global_dimension_2": entry.global_dimension_2,
                    "dimension_set": entry.dimension_set,
                    "user": self.user,
                    "date": entry.posting_date,  # FIX: Use original entry's posting_date
                    "document_type": "Credit Memo",
                    "transaction_no": f"REV-{entry.transaction_no}",
                }
            )

    def _find_and_reverse_value_entries(self):
        """Find original value entries and create opposite entries"""
        from decimal import Decimal

        from dimension.utils import get_first_branch_dimension_value

        original_entries = ValueEntry.objects.filter(self._ledger_document_filter())

        for entry in original_entries:
            # Convert to Decimal to ensure numeric type
            cost_amount = (
                Decimal(str(entry.cost_amount)) if entry.cost_amount else Decimal("0")
            )
            item_ledger_qty = (
                Decimal(str(entry.item_ledger_entry_quantity))
                if entry.item_ledger_entry_quantity
                else Decimal("0")
            )
            invoiced_qty = (
                Decimal(str(entry.invoiced_quantity))
                if entry.invoiced_quantity
                else Decimal("0")
            )
            valued_qty = (
                Decimal(str(entry.valued_quantity))
                if entry.valued_quantity
                else Decimal("0")
            )
            sales_amount = (
                Decimal(str(entry.sales_amount)) if entry.sales_amount else Decimal("0")
            )
            cost_per_unit = (
                Decimal(str(entry.cost_per_unit))
                if entry.cost_per_unit
                else Decimal("0")
            )
            cost_amount_non_invtbl = (
                Decimal(str(entry.cost_amount_non_invtbl))
                if getattr(entry, "cost_amount_non_invtbl", None) is not None
                else Decimal("0")
            )

            self.reversal_value_entries.append(
                {
                    "posting_date": entry.posting_date,  # FIX: Use original entry's posting_date
                    "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                    "item": entry.item,
                    "cost_amount": -cost_amount,  # OPPOSITE (for posting)
                    "cost_amount_non_invtbl": -cost_amount_non_invtbl,  # OPPOSITE for Service/Non-Inv
                    "cost_amount_before_reversal": cost_amount,  # For display
                    "item_ledger_entry_quantity": -item_ledger_qty,
                    "item_ledger_qty_before_reversal": item_ledger_qty,  # For display
                    "invoiced_quantity": -invoiced_qty,
                    "invoiced_qty_before_reversal": invoiced_qty,  # For display
                    "valued_quantity": -valued_qty,
                    "cost_per_unit": cost_per_unit,
                    "general_product_posting_group": entry.general_product_posting_group,
                    "inventory_posting_group": entry.inventory_posting_group,
                    "document_type": "Credit Memo",
                    "entry_type": EntryType.DirectCost.value,
                    "original_entry_type": entry.entry_type,  # Preserve original
                    "sales_amount": -sales_amount,
                    "sales_amount_before_reversal": sales_amount,  # For display
                    "transaction_no": f"REV-{entry.transaction_no}",
                    "global_dimension_1": entry.global_dimension_1,
                    "global_dimension_2": entry.global_dimension_2,
                    "dimension_set": entry.dimension_set,
                }
            )

    def _find_and_reverse_bank_entries(self):
        """
        Find original bank ledger entries and create opposite entries.

        Bank ledger entries are created during invoice posting when:
        - Payment method uses a Bank Account (bal_account_type == "Bank Account")
        - Payment method has bal_bank_account_no configured

        We identify if bank entries should exist by:
        1. Getting the original SalesInvoice (status="Posted") by matching customer_invoice_no
        2. Checking if the payment_method uses a Bank Account
        3. Finding bank ledger entries by document_no matching the invoice number
        """
        from decimal import Decimal
        from bank_account.models import BankAccountLedgerEntry
        from bank_account.enums import BankAccountDocumentType
        from sales.models import SalesInvoice
        from financials.enums import BalacingAccountType

        # Check payment method - prefer PostedSalesInvoice.payment_method if available
        # (for future invoices), otherwise fallback to original SalesInvoice
        payment_method = None
        uses_bank_account = False

        # First, try to get payment_method directly from PostedSalesInvoice (future invoices)
        if (
            hasattr(self.posted_invoice, "payment_method")
            and self.posted_invoice.payment_method
        ):
            payment_method = self.posted_invoice.payment_method
        else:
            # Fallback: Get the original SalesInvoice to check payment method
            # Match by customer_invoice_no (most reliable) or fallback to invoice_no
            original_sales_invoice = None
            customer_invoice_no = getattr(
                self.posted_invoice, "customer_invoice_no", None
            )

            if customer_invoice_no:
                original_sales_invoice = SalesInvoice.objects.filter(
                    customer_invoice_no=customer_invoice_no,
                    status="Posted",
                    customer=self.posted_invoice.customer,
                ).first()

            # Fallback: try to match by invoice_no if customer_invoice_no didn't work
            if not original_sales_invoice:
                # Try to extract invoice_no from posted_invoice.no (format may vary)
                original_sales_invoice = SalesInvoice.objects.filter(
                    invoice_no=self.posted_invoice.no,
                    status="Posted",
                    customer=self.posted_invoice.customer,
                ).first()

            if original_sales_invoice and original_sales_invoice.payment_method:
                payment_method = original_sales_invoice.payment_method

        # Check if payment method uses Bank Account
        if payment_method:
            uses_bank_account = (
                payment_method.bal_account_type == BalacingAccountType.Bank_Account.name
                and bool(payment_method.bal_bank_account_no)
            )

        # Find all bank ledger entries for this invoice
        # Bank entries are created during posting with document_no = SalesInvoice.invoice_no
        # We need to check both PostedSalesInvoice.no and original SalesInvoice.invoice_no
        # because they might be different
        original_entries = BankAccountLedgerEntry.objects.filter(
            self._ledger_document_filter()
        )

        # If payment method doesn't use bank account and no entries exist, skip
        # This is normal for invoices paid with cash or other non-bank payment methods
        if not uses_bank_account and not original_entries.exists():
            return

        # If payment method uses bank account but no entries found, log a warning
        # but continue (entries might have been deleted or there's a data inconsistency)
        if uses_bank_account and not original_entries.exists():
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Expected bank ledger entries for invoice {self.posted_invoice.no} "
                f"(payment method uses bank account) but none found. "
                f"This may indicate a data inconsistency."
            )
            return

        for entry in original_entries:
            # Convert to Decimal to ensure numeric type
            amount = Decimal(str(entry.amount)) if entry.amount else Decimal("0")

            # Determine reversal document type
            if entry.document_type == BankAccountDocumentType.Payment.name:
                reversal_doc_type = BankAccountDocumentType.Refund.name
            else:
                reversal_doc_type = BankAccountDocumentType.Credit_Memo.name

            self.reversal_bank_entries.append(
                {
                    "posting_date": entry.posting_date,
                    "document_type": reversal_doc_type,
                    "original_document_type": entry.document_type,
                    "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                    "bank_account_no": entry.bank_account_no,
                    "description": f"Reversal of {entry.document_type} {entry.document_no}",
                    "amount": -amount,  # OPPOSITE SIGN
                    "bank_account_posting_group": entry.bank_account_posting_group,
                    "bal_account_type": entry.bal_account_type,
                    "bal_account_no": entry.bal_account_no,
                    "global_dimension_1": entry.global_dimension_1,
                    "dimension_set": getattr(entry, "dimension_set", None),
                    "user": self.user,
                    "document_date": entry.document_date,
                    "transaction_no": f"REV-{self.posted_invoice.no}",
                    "original_amount": amount,  # For preview display
                }
            )

    def _find_and_reverse_vat_entries(self):
        """Find original VAT entries and create opposite entries for the subledger."""
        from decimal import Decimal
        from financials.models import VatEntry

        original_entries = VatEntry.objects.filter(self._ledger_document_filter())

        for entry in original_entries:
            base = Decimal(str(entry.base)) if entry.base else Decimal("0")
            amount = Decimal(str(entry.amount)) if entry.amount else Decimal("0")

            self.reversal_vat_entries.append(
                {
                    "posting_date": entry.posting_date,
                    "document_type": "Credit Memo",
                    "document_no": f"CM-PREVIEW-{self.posted_invoice.no}",
                    "type": entry.type,
                    "vat_business_posting_group": entry.vat_business_posting_group,
                    "vat_product_posting_group": entry.vat_product_posting_group,
                    "base": -base,  # OPPOSITE
                    "amount": -amount,  # OPPOSITE
                    "vat_percent": entry.vat_percent,
                    "vat_calculation_type": entry.vat_calculation_type or "Normal",
                    "vat_account": entry.vat_account,
                    "gen_bus_posting_group": entry.general_business_posting_group,
                    "gen_prod_posting_group": entry.general_product_posting_group,
                    "global_dimension_1": entry.global_dimension_1,
                    "transaction_no": f"REV-{entry.transaction_no or self.posted_invoice.no}",
                    "user": self.user,
                }
            )

    def _calculate_inventory_restoration(self):
        """Calculate what inventory quantities will be restored"""
        from decimal import Decimal

        for line in self.lines:
            # Convert to Decimal to ensure numeric type
            quantity_per_unit = (
                Decimal(str(line.item_unit_of_measure.quantity_per_unit))
                if line.item_unit_of_measure
                else Decimal("1")
            )
            line_quantity = (
                Decimal(str(line.quantity)) if line.quantity else Decimal("0")
            )
            quantity_to_restore = line_quantity * quantity_per_unit

            # Get current inventory
            current_inventory_entries = ItemLedgerEntries.objects.filter(
                item=line.item, location=line.location_code
            ).aggregate(total=Sum("remaining_quantity"))

            current_quantity = (
                Decimal(str(current_inventory_entries["total"]))
                if current_inventory_entries["total"]
                else Decimal("0")
            )

            self.inventory_restoration_preview.append(
                {
                    "item": line.item,
                    "location": line.location_code,
                    "quantity_to_restore": quantity_to_restore,
                    "current_quantity": current_quantity,
                    "after_restoration": current_quantity + quantity_to_restore,
                }
            )


class SalesInvoiceReversalPostingProcessor:
    """
    Actually perform the reversal by creating credit memo and opposite entries.
    This processor SAVES all the entries to the database.
    """

    def __init__(self, posted_invoice, request, reason=""):
        self.posted_invoice = posted_invoice
        self.request = request
        self.user = request.user
        self.reason = reason

    def post(self):
        """Execute the reversal in a database transaction

        IMPORTANT: This method FIRST runs the preview processor to generate
        all reversal entries, then creates the actual database entries from
        those preview entries. This ensures consistency between preview and posting.

        Flow:
        1. Run SalesInvoiceReversalProcessor to generate preview entries
        2. Use those preview entries to create actual database entries:
           - GL entries (from reversal_entries["gl_entries"])
           - Customer entries (from reversal_entries["customer_entries"])
           - Item entries (from reversal_entries["item_entries"])
           - Value entries (from reversal_entries["value_entries"])
           - Bank entries (from reversal_entries["bank_entries"])

        All operations are wrapped in an atomic transaction that will rollback
        completely if any step fails. Uses a consistent transaction number
        for all entries in the reversal for proper audit trail.
        """
        with transaction.atomic():
            try:
                # 1. Generate credit memo number FIRST
                from dimension.utils import get_first_branch_dimension_value
                from helpers.helpers import generate_document_number

                credit_memo_no, _ = generate_document_number(
                    SalesReceivable,
                    "credit_memo_no",
                    "credit_memo_no",
                    is_no_series_lines=True,
                )

                if not credit_memo_no:
                    raise Exception("Failed to generate credit memo number")

                # 2. Generate consistent transaction number for ALL reversal entries
                # Format: REV-{credit_memo_no}-{date}-{timestamp}
                import uuid

                transaction_no = (
                    f"REV-{credit_memo_no}-"
                    f"{timezone.now().date().strftime('%Y%m%d')}-"
                    f"{uuid.uuid4().hex[:6].upper()}"
                )

                # 3. Find the PostedSalesInvoice that was created during posting
                # Link via customer_invoice_no (should match between SalesInvoice and PostedSalesInvoice)
                customer_invoice_no = getattr(
                    self.posted_invoice, "customer_invoice_no", None
                )

                # Try to find by customer_invoice_no first (most reliable)
                if customer_invoice_no:
                    posted_sales_invoice = PostedSalesInvoice.objects.filter(
                        customer_invoice_no=customer_invoice_no,
                        customer=self.posted_invoice.customer,
                    ).first()
                else:
                    # Fallback: match by customer and document_date
                    posted_sales_invoice = PostedSalesInvoice.objects.filter(
                        customer=self.posted_invoice.customer,
                        document_date=self.posted_invoice.document_date,
                    ).first()

                # If no PostedSalesInvoice found, the invoice wasn't properly posted
                if not posted_sales_invoice:
                    raise Exception(
                        f"PostedSalesInvoice not found for invoice {self.posted_invoice.no}. "
                        f"The invoice may not have been properly posted through the posting process. "
                        f"Please post the invoice first before attempting to reverse it."
                    )

                # 4. Create Credit Memo document (copy dimensions from original posted invoice)
                credit_memo = SalesCreditMemo.objects.create(
                    credit_memo_no=credit_memo_no,
                    customer=self.posted_invoice.customer,
                    document_date=self.posted_invoice.document_date,
                    posting_date=self.posted_invoice.posting_date,
                    vat_date=self.posted_invoice.vat_date,
                    original_invoice_no=self.posted_invoice.no,
                    original_invoice=posted_sales_invoice,  # Use actual PostedSalesInvoice
                    reason_for_reversal=self.reason,
                    status="Posted",
                    reversed_by_user=self.user,
                    global_dimension_1=posted_sales_invoice.global_dimension_1,
                    global_dimension_2=posted_sales_invoice.global_dimension_2,
                    dimension_set=posted_sales_invoice.dimension_set,
                )

                # 5. Create credit memo lines (copy dimensions from posted lines)
                for line in self.posted_invoice.posted_sales_invoice_lines.all():
                    SalesCreditMemoLine.objects.create(
                        credit_memo=credit_memo,
                        item=line.item,
                        description=line.description,
                        location_code=line.location_code,
                        quantity=line.quantity,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=line.unit_of_measure,
                        unit_price=line.unit_price,
                        amount=line.amount,
                        global_dimension_1=line.global_dimension_1
                        or posted_sales_invoice.global_dimension_1,
                        dimension_set=line.dimension_set,
                    )

                # STEP 1: Get reversal entries from preview processor
                # This generates all reversal entries (GL, Customer, Item, Value, Bank)
                # without saving them - we'll use these entries to create actual DB records
                processor = SalesInvoiceReversalProcessor(
                    self.posted_invoice, self.request
                )
                reversal_entries = processor.process()

                if not reversal_entries.get("success"):
                    raise Exception(reversal_entries.get("message"))

                # STEP 2: Use preview entries to create actual database entries
                # All entries below come from reversal_entries generated by preview processor
                # 7. Create GL entries (with opposite signs) and mark originals as reversed
                # Get ALL GL entries (both Invoice and Payment entries)
                original_gl_entries = list(
                    GeneralLedgerEntry.objects.filter(
                        sales_ledger_document_filter(self.posted_invoice)
                    )
                )

                for idx, gl_entry in enumerate(reversal_entries["gl_entries"]):
                    original_gl = (
                        original_gl_entries[idx]
                        if idx < len(original_gl_entries)
                        else None
                    )

                    # Create reversing GL entry with consistent transaction number
                    reversing_gl = GeneralLedgerEntry.objects.create(
                        posting_date=gl_entry["posting_date"],
                        document_type=gl_entry["document_type"],
                        document_no=credit_memo_no,  # Use actual credit memo number
                        gl_account=gl_entry["gl_account"],
                        description=gl_entry["description"],
                        amount=gl_entry["amount"],
                        general_posting_type=gl_entry["gen_posting_type"],
                        dimension_set=gl_entry.get("dimension_set"),
                        global_dimension_1=gl_entry.get("global_dimension_1"),
                        global_dimension_2=gl_entry.get("global_dimension_2"),
                        general_business_posting_group=gl_entry[
                            "gen_bus_posting_group"
                        ],
                        general_product_posting_group=gl_entry[
                            "gen_prod_posting_group"
                        ],
                        balancing_account_type=gl_entry["balance_account_type"],
                        user=gl_entry["user"],
                        transaction_no=transaction_no,  # ✅ Use consistent transaction number
                        reverses_entry_no=(
                            original_gl.id if original_gl else None
                        ),  # ✅ Link
                    )

                    # Mark original GL entry as reversed
                    if original_gl:
                        original_gl.reversed = True
                        original_gl.reversed_by_document_no = credit_memo_no
                        original_gl.reversed_date = timezone.now().date()
                        original_gl.reversed_by_user = self.user
                        original_gl.save()

                # 7b. Create reversing VAT Entries (BC-style subledger)
                from financials.models import VatEntry

                for vat_entry in reversal_entries.get("reversal_vat_entries", []):
                    VatEntry.objects.create(
                        posting_date=vat_entry["posting_date"],
                        document_type=vat_entry["document_type"],
                        document_no=credit_memo_no,  # Use actual credit memo number
                        type=vat_entry["type"],
                        vat_business_posting_group=vat_entry[
                            "vat_business_posting_group"
                        ],
                        vat_product_posting_group=vat_entry[
                            "vat_product_posting_group"
                        ],
                        base=vat_entry["base"],
                        amount=vat_entry["amount"],
                        vat_percent=vat_entry["vat_percent"],
                        vat_calculation_type=vat_entry["vat_calculation_type"],
                        vat_account=vat_entry["vat_account"],
                        general_business_posting_group=vat_entry[
                            "gen_bus_posting_group"
                        ],
                        general_product_posting_group=vat_entry[
                            "gen_prod_posting_group"
                        ],
                        global_dimension_1=vat_entry.get("global_dimension_1"),
                        transaction_no=transaction_no,
                        user=vat_entry["user"],
                    )

                # 8. Create Customer Ledger entries (with opposite signs) and mark originals
                original_customer_entries = list(
                    CustomerLedgerEntry.objects.filter(
                        sales_ledger_document_filter(self.posted_invoice)
                    )
                )

                for idx, cust_entry in enumerate(reversal_entries["customer_entries"]):
                    original_cust = (
                        original_customer_entries[idx]
                        if idx < len(original_customer_entries)
                        else None
                    )

                    # Create reversing customer entry with consistent transaction number
                    reversing_cust = CustomerLedgerEntry.objects.create(
                        posting_date=cust_entry["posting_date"],
                        document_date=cust_entry["document_date"],
                        document_type=cust_entry["document_type"],
                        document_no=credit_memo_no,
                        customer=cust_entry["customer"],
                        description=cust_entry["description"],
                        payment_method=cust_entry["payment_method"],
                        original_amount=cust_entry["original_amount"],
                        amount=cust_entry["amount"],
                        sales=cust_entry["sales"],
                        open=cust_entry["open"],
                        due_date=cust_entry["due_date"],
                        global_dimension_1=cust_entry["global_dimension_1"],
                        dimension_set=getattr(original_cust, "dimension_set", None)
                        if original_cust
                        else cust_entry.get("dimension_set"),
                        user=cust_entry["user"],
                        transaction_no=transaction_no,  # ✅ Use consistent transaction number
                        reverses_entry_no=(
                            original_cust.id if original_cust else None
                        ),  # ✅ Link
                    )

                    # Mark original customer entry as reversed
                    if original_cust:
                        original_cust.reversed = True
                        original_cust.reversed_by_document_no = credit_memo_no
                        original_cust.reversed_date = timezone.now().date()
                        original_cust.reversed_by_user = self.user
                        original_cust.save()

                # 9. Create Item Ledger entries (with opposite quantities) and mark originals
                original_item_entries = list(
                    ItemLedgerEntries.objects.filter(
                        sales_ledger_document_filter(self.posted_invoice)
                    )
                )

                # Store created reversing entries for linking to ValueEntries
                created_reversing_item_entries = []

                for idx, item_entry in enumerate(reversal_entries["item_entries"]):
                    original_item = (
                        original_item_entries[idx]
                        if idx < len(original_item_entries)
                        else None
                    )

                    # Create reversing item entry with consistent transaction number
                    from dimension.models import get_posting_dimension_payload

                    inv_dim_payload = get_posting_dimension_payload(
                        global_dimension_1=item_entry.get("global_dimension_1"),
                        global_dimension_2=item_entry.get("global_dimension_2"),
                        dimension_set=item_entry.get("dimension_set"),
                    )
                    reversing_item = ItemLedgerEntries.objects.create(
                        posting_date=item_entry["posting_date"],
                        entry_type=item_entry["entry_type"],
                        item=item_entry["item"],
                        document_no=credit_memo_no,
                        description=item_entry["description"],
                        location=item_entry["location"],
                        quantity=item_entry["quantity"],
                        remaining_quantity=item_entry["remaining_quantity"],
                        total=item_entry["total"],  # ✅ Required field
                        unit_of_measure_code=item_entry["unit_of_measure_code"],
                        global_dimension_1=inv_dim_payload.get("global_dimension_1"),
                        global_dimension_2=inv_dim_payload.get("global_dimension_2"),
                        dimension_set=inv_dim_payload.get("dimension_set"),
                        user=item_entry["user"],
                        date=item_entry["date"],
                        document_type=item_entry["document_type"],
                        transaction_no=transaction_no,  # ✅ Use consistent transaction number
                        reverses_entry_no=(
                            original_item.id if original_item else None
                        ),  # ✅ Link
                    )

                    # Store for linking to ValueEntries
                    created_reversing_item_entries.append(reversing_item)

                    # Mark original item entry as reversed
                    if original_item:
                        original_item.reversed = True
                        original_item.reversed_by_document_no = credit_memo_no
                        original_item.reversed_date = timezone.now().date()
                        original_item.reversed_by_user = self.user
                        original_item.save()

                # 10. Create Value entries (with opposite amounts) and mark originals
                # Link each ValueEntry to its corresponding ItemLedgerEntry
                original_value_entries = list(
                    ValueEntry.objects.filter(
                        sales_ledger_document_filter(self.posted_invoice)
                    )
                )

                for idx, value_entry in enumerate(reversal_entries["value_entries"]):
                    original_val = (
                        original_value_entries[idx]
                        if idx < len(original_value_entries)
                        else None
                    )

                    # Get the corresponding reversing ItemLedgerEntry
                    # ValueEntries match ItemLedgerEntries by index (same item/line)
                    reversing_item_entry = (
                        created_reversing_item_entries[idx]
                        if idx < len(created_reversing_item_entries)
                        else None
                    )

                    # Create reversing value entry with consistent transaction number
                    val_dim_payload = get_posting_dimension_payload(
                        global_dimension_1=value_entry.get("global_dimension_1")
                        or (
                            original_val.global_dimension_1 if original_val else None
                        )
                        or (
                            reversing_item_entry.global_dimension_1
                            if reversing_item_entry
                            else None
                        ),
                        global_dimension_2=value_entry.get("global_dimension_2")
                        or (
                            original_val.global_dimension_2 if original_val else None
                        )
                        or (
                            reversing_item_entry.global_dimension_2
                            if reversing_item_entry
                            else None
                        ),
                        dimension_set=value_entry.get("dimension_set")
                        or (original_val.dimension_set if original_val else None)
                        or (
                            reversing_item_entry.dimension_set
                            if reversing_item_entry
                            else None
                        ),
                    )
                    reversing_val = ValueEntry.objects.create(
                        posting_date=value_entry["posting_date"],
                        document_no=credit_memo_no,
                        item=value_entry["item"],
                        cost_amount=value_entry["cost_amount"],
                        cost_amount_non_invtbl=value_entry.get("cost_amount_non_invtbl")
                        or 0,
                        item_ledger_entry_quantity=value_entry[
                            "item_ledger_entry_quantity"
                        ],
                        invoiced_quantity=value_entry["invoiced_quantity"],
                        valued_quantity=value_entry["valued_quantity"],
                        cost_per_unit=value_entry["cost_per_unit"],
                        general_product_posting_group=value_entry[
                            "general_product_posting_group"
                        ],
                        inventory_posting_group=value_entry["inventory_posting_group"],
                        document_type=value_entry["document_type"],
                        entry_type=value_entry["entry_type"],
                        sales_amount=value_entry["sales_amount"],
                        transaction_no=transaction_no,  # ✅ Use consistent transaction number
                        item_ledger_entry_no=reversing_item_entry,  # ✅ Link to reversing ItemLedgerEntry
                        reverses_value_entry_no=(
                            original_val.id if original_val else None
                        ),  # ✅ Link
                        global_dimension_1=val_dim_payload.get("global_dimension_1")
                        or get_first_branch_dimension_value(),
                        global_dimension_2=val_dim_payload.get("global_dimension_2"),
                        dimension_set=val_dim_payload.get("dimension_set"),
                    )

                    # Mark original value entry as reversed
                    if original_val:
                        original_val.reversed = True
                        original_val.reversed_by_document_no = credit_memo_no
                        original_val.reversed_date = timezone.now().date()
                        original_val.reversed_by_user = self.user
                        original_val.save()

                # 11. Create Bank Ledger entries (with opposite amounts) and mark originals
                # Bank ledger entries are identified by:
                # 1. Getting original SalesInvoice (status="Posted") by customer_invoice_no
                # 2. Checking if payment_method uses Bank Account
                # 3. Finding bank ledger entries by document_no matching invoice number
                # If no bank entries exist (e.g., cash payment), reversal_entries["bank_entries"]
                # will be empty and this loop will be skipped.
                from bank_account.models import BankAccountLedgerEntry
                from bank_account.enums import BankAccountDocumentType
                from sales.models import SalesInvoice
                from financials.enums import BalacingAccountType

                # Check payment method - prefer PostedSalesInvoice.payment_method if available
                # (for future invoices), otherwise fallback to original SalesInvoice
                # Note: This is mainly for validation/logging; we still find entries by document_no
                payment_method = None
                if (
                    hasattr(self.posted_invoice, "payment_method")
                    and self.posted_invoice.payment_method
                ):
                    payment_method = self.posted_invoice.payment_method
                else:
                    # Fallback: Get the original SalesInvoice to verify payment method
                    customer_invoice_no = getattr(
                        self.posted_invoice, "customer_invoice_no", None
                    )
                    original_sales_invoice = None

                    if customer_invoice_no:
                        original_sales_invoice = SalesInvoice.objects.filter(
                            customer_invoice_no=customer_invoice_no,
                            status="Posted",
                            customer=self.posted_invoice.customer,
                        ).first()

                    # Fallback: try to match by invoice_no
                    if not original_sales_invoice:
                        original_sales_invoice = SalesInvoice.objects.filter(
                            invoice_no=self.posted_invoice.no,
                            status="Posted",
                            customer=self.posted_invoice.customer,
                        ).first()

                    if original_sales_invoice and original_sales_invoice.payment_method:
                        payment_method = original_sales_invoice.payment_method

                # Get original bank entries for linking reversal entries
                original_bank_entries = list(
                    BankAccountLedgerEntry.objects.filter(
                        sales_ledger_document_filter(self.posted_invoice)
                    )
                )

                # Process bank entry reversals from preview processor
                # (will be empty if invoice wasn't paid with bank account)
                for idx, bank_entry in enumerate(
                    reversal_entries.get("bank_entries", [])
                ):
                    original_bank = (
                        original_bank_entries[idx]
                        if idx < len(original_bank_entries)
                        else None
                    )

                    # Create reversing bank entry with consistent transaction number
                    reversing_bank = BankAccountLedgerEntry.objects.create(
                        bank_account_no=bank_entry["bank_account_no"],
                        posting_date=bank_entry["posting_date"],
                        document_type=bank_entry["document_type"],
                        document_no=credit_memo_no,
                        description=bank_entry["description"],
                        amount=bank_entry[
                            "amount"
                        ],  # Already opposite sign from preview
                        bank_account_posting_group=bank_entry.get(
                            "bank_account_posting_group"
                        ),
                        bal_account_type=bank_entry.get("bal_account_type"),
                        bal_account_no=bank_entry.get("bal_account_no"),
                        global_dimension_1=bank_entry.get("global_dimension_1"),
                        dimension_set=(
                            getattr(original_bank, "dimension_set", None)
                            if original_bank
                            else bank_entry.get("dimension_set")
                        ),
                        user=bank_entry["user"],
                        document_date=bank_entry.get("document_date"),
                        reversed_entry_no=(
                            original_bank.entry_no if original_bank else None
                        ),  # Link to original entry
                    )

                    # Mark original bank entry as reversed
                    if original_bank:
                        original_bank.reversed = True
                        original_bank.reversed_by_entry_no = reversing_bank.entry_no
                        original_bank.reversed_date = timezone.now().date()
                        original_bank.reversed_by_user = self.user
                        original_bank.save()

                # 12. Mark PostedSalesInvoice as reversed
                # Update the actual PostedSalesInvoice object, not the wrapper
                posted_sales_invoice.reversed = True
                posted_sales_invoice.reversed_by = credit_memo_no
                posted_sales_invoice.reversed_date = timezone.now().date()
                posted_sales_invoice.save()

                # ✅ All operations completed successfully
                # Transaction will commit automatically if no exceptions occurred
                return {
                    "success": True,
                    "message": f"Successfully reversed invoice {self.posted_invoice.no}",
                    "credit_memo_no": credit_memo_no,
                    "credit_memo": credit_memo,
                    "transaction_no": transaction_no,  # Return transaction number for audit
                    "posted_sales_invoice": posted_sales_invoice,  # Return for outer transaction
                }

            except Exception as e:
                # ❌ Any exception here will cause automatic rollback of ALL operations
                # This includes: credit memo, all ledger entries, and status updates
                # No partial reversals will remain in the database
                import traceback

                error_details = f"{str(e)}\n\nTransaction Number: {transaction_no if 'transaction_no' in locals() else 'N/A'}"
                return {"success": False, "message": error_details}


class SalesInvoicePostingProcessor:
    def __init__(self, invoice, request, receipt_no):
        self.invoice = invoice
        self.request = request
        if not request:
            raise Exception("Request object is required but was not provided")
        if not hasattr(request, "user"):
            raise Exception("Request object does not have a user attribute")
        if not request.user:
            raise Exception("Request user is not authenticated")

        self.user = request.user
        self.lines = invoice.lines.all()
        self.customer = invoice.customer
        self.genBusinessPostingGroup = invoice.customer.general_business_posting_group
        # IMPORTANT: Use invoice payment_method ONLY - each invoice should have its own payment method
        # This ensures invoices are independent and avoid race conditions with multiple windows
        # Invoice payment_method should be set during invoice creation
        if not invoice.payment_method:
            raise Exception(
                f"Invoice {invoice.invoice_no or invoice.id} does not have a payment method set. "
                f"Payment method must be specified when creating the invoice."
            )
        self.payment_method = invoice.payment_method

        if not self.customer.customer_posting_group:
            raise Exception(
                f"Customer {self.customer.name} does not have a customer posting group assigned"
            )

        self.receivables_account = (
            self.customer.customer_posting_group.receivables_account
        )

        if not self.receivables_account:
            raise Exception(
                f"Customer posting group '{self.customer.customer_posting_group.code}' does not have a receivables account assigned"
            )

        self.receipt_no = receipt_no

    def post(self):
        from django.db import transaction

        processor = SalesInvoiceProcessor(self.invoice, self.request, self.receipt_no)
        entries = processor.process()

        with transaction.atomic():
            # Create Bank Account Ledger Entries (if any)
            from bank_account.utils import create_bank_account_posting_entries

            for bank_entry_info in entries.get("bank_account_entries", []):
                try:
                    result = create_bank_account_posting_entries(
                        bank_account=bank_entry_info["bank_account"],
                        posting_date=bank_entry_info["posting_date"],
                        document_type=bank_entry_info["document_type"],
                        document_no=bank_entry_info["document_no"],
                        description=bank_entry_info["description"],
                        amount=bank_entry_info["amount"],
                        bal_account_type=bank_entry_info["bal_account_type"],
                        bal_account_no=bank_entry_info["bal_account_no"],
                        user=bank_entry_info.get("user", self.user),
                        global_dimension_1=bank_entry_info.get("global_dimension_1"),
                        dimension_set=bank_entry_info.get("dimension_set"),
                        transaction_no=bank_entry_info.get("transaction_no"),
                        document_date=bank_entry_info.get("document_date"),
                    )
                    # Bank account entry is created, G/L account is already in gl_entries
                except Exception as e:
                    raise Exception(
                        f"Failed to create bank account ledger entry: {str(e)}"
                    )

            # Create GL Entries
            from dimension.models import get_posting_dimension_payload
            from dimension.utils import get_first_branch_dimension_value

            for gl_entry in entries["gl_entries"]:
                dim_payload = get_posting_dimension_payload(
                    global_dimension_1=gl_entry.get("global_dimension_1"),
                    dimension_set=gl_entry.get("dimension_set"),
                )
                general_ledger = GeneralLedgerEntry.objects.create(
                    posting_date=gl_entry["posting_date"],
                    document_type=gl_entry["document_type"],
                    document_no=gl_entry["document_no"],
                    gl_account=gl_entry["gl_account"],
                    description=gl_entry["description"],
                    amount=gl_entry["amount"],
                    general_posting_type=gl_entry["gen_posting_type"],
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                    general_business_posting_group=gl_entry["gen_bus_posting_group"],
                    general_product_posting_group=gl_entry["gen_prod_posting_group"],
                    balancing_account_type=(
                        BalacingAccountType.GLAccount.name
                        if gl_entry["balance_account_type"] == "G/L Account"
                        else BalacingAccountType.Customer.value
                    ),
                    user=gl_entry["user"],
                    transaction_no=gl_entry["transaction_no"],
                )
                general_ledger.save()

            # Create VAT Entries (BC-style subledger)
            from financials.models import VatEntry

            for vat_entry in entries.get("vat_entries", []):
                VatEntry.objects.create(
                    posting_date=vat_entry["posting_date"],
                    document_type=vat_entry["document_type"],
                    document_no=vat_entry["document_no"],
                    type=vat_entry["type"],
                    vat_business_posting_group=vat_entry["vat_business_posting_group"],
                    vat_product_posting_group=vat_entry["vat_product_posting_group"],
                    base=vat_entry["base"],
                    amount=vat_entry["amount"],
                    vat_percent=vat_entry["vat_percent"],
                    vat_calculation_type=vat_entry["vat_calculation_type"],
                    vat_account=vat_entry["vat_account"],
                    general_business_posting_group=vat_entry["gen_bus_posting_group"],
                    general_product_posting_group=vat_entry["gen_prod_posting_group"],
                    global_dimension_1=vat_entry.get("global_dimension_1"),
                    transaction_no=vat_entry["transaction_no"],
                    user=vat_entry["user"],
                )

            # Create Customer Ledger Entries
            count = 0
            for customer_entry in entries["customer_entries"]:
                from common.enums import DocumentType

                CustomerLedgerEntry.objects.create(
                    posting_date=customer_entry["posting_date"],
                    document_date=customer_entry["document_date"],
                    document_type=(
                        DocumentType.Invoice.value
                        if customer_entry["document_type"] == "Invoice"
                        else DocumentType.Payment.value
                    ),
                    document_no=customer_entry["document_no"],
                    external_document_no=customer_entry["external_document_no"],
                    customer=customer_entry["customer"],
                    description=customer_entry["description"],
                    payment_method=customer_entry["payment_method"],
                    original_amount=customer_entry["original_amount"],
                    amount=customer_entry["amount"],
                    sales=customer_entry["sales"],
                    open=(
                        False
                        if len(entries["customer_entries"]) == 2
                        else customer_entry["open"]
                    ),
                    due_date=customer_entry["due_date"],
                    global_dimension_1=customer_entry["global_dimension_1"],
                    dimension_set=customer_entry.get("dimension_set"),
                    transaction_no=customer_entry["transaction_no"],
                    user=customer_entry["user"],
                )

            # Create Item Ledger Entries and Value Entries together
            for item_entry, value_entry in zip(
                entries["item_entries"], entries["value_entries"]
            ):
                # Ensure inventory entries carry a valid dimension_set.
                # ItemLedgerEntries.clean() requires global dimensions to be resolvable from either
                # global_dimension_1/global_dimension_2 or a dimension_set (per General Ledger Setup).
                from dimension.models import get_posting_dimension_payload

                inv_dim_payload = get_posting_dimension_payload(
                    global_dimension_1=item_entry.get("global_dimension_1")
                    or getattr(self.invoice, "global_dimension_1", None),
                    global_dimension_2=item_entry.get("global_dimension_2")
                    or getattr(self.invoice, "global_dimension_2", None),
                    dimension_set=item_entry.get("dimension_set")
                    or value_entry.get("dimension_set")
                    or getattr(self.invoice, "dimension_set", None),
                )

                # First create the Item Ledger Entry
                item_ledger = ItemLedgerEntries.objects.create(
                    posting_date=item_entry["posting_date"],
                    entry_type=item_entry["entry_type"],
                    item=item_entry["item"],
                    document_no=item_entry["document_no"],
                    description=item_entry["description"],
                    location=item_entry["location"],
                    quantity=item_entry["quantity"],
                    remaining_quantity=item_entry["remaining_quantity"],
                    total=item_entry["total"],
                    unit_of_measure_code=item_entry["unit_of_measure"],
                    global_dimension_1=inv_dim_payload.get("global_dimension_1")
                    or item_entry.get("global_dimension_1"),
                    global_dimension_2=inv_dim_payload.get("global_dimension_2")
                    or item_entry.get("global_dimension_2"),
                    dimension_set=inv_dim_payload.get("dimension_set"),
                    user=item_entry["user"],
                    receipt_no=item_entry["receipt_no"],
                    date=item_entry["date"],
                    document_type=DocumentType.Sales.value,
                    transaction_no=item_entry["transaction_no"],
                )

                # Handle serial/lot numbers if present
                if "lot_no" in item_entry and item_entry["lot_no"]:
                    item_ledger.lot_no = item_entry["lot_no"]
                if "expiry_date" in item_entry and item_entry["expiry_date"]:
                    item_ledger.expiry_date = item_entry["expiry_date"]
                if "serial_no" in item_entry and item_entry["serial_no"]:
                    item_ledger.serial_no = item_entry["serial_no"]

                item_ledger.save()

                # Then create the Value Entry with reference to the Item Ledger Entry
                ValueEntry.objects.create(
                    posting_date=value_entry["posting_date"],
                    document_no=value_entry["document_no"],
                    item=value_entry["item"],
                    cost_amount=value_entry["cost_amount"],
                    cost_amount_non_invtbl=value_entry.get("cost_amount_non_invtbl")
                    or 0,
                    item_ledger_entry_quantity=value_entry[
                        "item_ledger_entry_quantity"
                    ],
                    invoiced_quantity=value_entry["invoiced_quantity"],
                    valued_quantity=value_entry["valued_quantity"],
                    cost_per_unit=value_entry["cost_per_unit"],
                    general_product_posting_group=value_entry[
                        "general_product_posting_group"
                    ],
                    inventory_posting_group=value_entry["inventory_posting_group"],
                    document_type=DocumentType.Sales.value,
                    entry_type=EntryType.DirectCost.value,
                    sales_amount=value_entry["sales_amount"],
                    item_ledger_entry_no=item_ledger,
                    transaction_no=value_entry["transaction_no"],
                    global_dimension_1=inv_dim_payload.get("global_dimension_1")
                    or value_entry.get("global_dimension_1")
                    or get_first_branch_dimension_value(),  # Fallback to first branch
                    global_dimension_2=inv_dim_payload.get("global_dimension_2")
                    or value_entry.get("global_dimension_2"),
                    dimension_set=inv_dim_payload.get("dimension_set"),
                )

            # Perform actual inventory reduction (Inventory items only; skip resource lines)
            processor = SalesInvoiceProcessor(
                self.invoice, self.request, self.receipt_no
            )
            for line in self.lines:
                if not line.item:
                    continue  # Resource lines: no inventory reduction
                # Skip Service / Non-Inventory — same rule as inventory preview
                if line.item.type in (
                    InventoryType.Service.value,
                    InventoryType.NonInventory.value,
                ):
                    continue

                quantity_to_reduce = (
                    line.quantity * line.item_unit_of_measure.quantity_per_unit
                )
                tracking_specs = list(line.tracking_specifications)
                if tracking_specs:
                    for spec in tracking_specs:
                        spec_qty = int(spec.quantity_base or 0)
                        if spec_qty <= 0:
                            continue
                        processor._reduce_inventory_quantities(
                            line.item,
                            spec_qty,
                            line.location_code,
                            lot_no=spec.lot_no,
                            serial_no=spec.serial_no,
                        )
                elif line.tracking_code:
                    processor._reduce_inventory_quantities(
                        line.item,
                        quantity_to_reduce,
                        line.location_code,
                        lot_no=line.tracking_code,
                    )
                else:
                    processor._reduce_inventory_quantities(
                        line.item, quantity_to_reduce, line.location_code
                    )

            # Create Resource Ledger Entries for resource lines
            for line in self.invoice.lines.all():
                if not line.resource:
                    continue
                qty_per_uom = 1
                if line.unit_of_measure and hasattr(
                    line.resource, "get_available_uoms"
                ):
                    uoms = line.resource.get_available_uoms
                    uom_code = (
                        line.unit_of_measure.code if line.unit_of_measure else None
                    )
                    match = next((u for u in uoms if u.get("code") == uom_code), None)
                    if match:
                        qty_per_uom = match.get("quantity_per_unit") or 1
                quantity_base = (
                    (Decimal(str(line.quantity)) * qty_per_uom)
                    if qty_per_uom
                    else Decimal(str(line.quantity))
                )
                unit_cost = getattr(line.resource, "unit_cost", 0) or 0
                total_cost = Decimal(str(unit_cost)) * Decimal(str(line.quantity))
                ResourceLedgerEntry.objects.create(
                    entry_type="Sale",
                    document_no=self.invoice.invoice_no,
                    posting_date=self.invoice.posting_date,
                    resource=line.resource,
                    description=line.description
                    or (line.resource.name if line.resource else ""),
                    quantity=line.quantity,
                    unit_of_measure=line.unit_of_measure,
                    total_cost=total_cost,
                    total_price=line.total_amount,
                    unit_price=line.unit_price,
                    source_type="Document",
                    source_no=self.invoice.invoice_no,
                    qty_per_unit_of_measure=qty_per_uom,
                    quantity_base=quantity_base,
                )

            # Create Detailed Customer Ledger Entries
            # Get the created customer ledger entries for reference
            created_customer_ledger_entries = CustomerLedgerEntry.objects.filter(
                posting_date=self.invoice.posting_date,
                document_no=self.invoice.invoice_no,
            ).order_by("id")

            count = 0
            for detailed_entry in entries["detailed_customer_entries"]:
                count += 1

                # Determine the correct customer ledger entry based on entry type and count
                if detailed_entry["entry_type"] == "Initial Entry":
                    if detailed_entry["document_type"] == "Invoice":
                        # First entry is always the invoice entry
                        customer_ledger = created_customer_ledger_entries[0]
                    else:  # Payment
                        # Second entry is the payment entry (if cash payment)
                        customer_ledger = (
                            created_customer_ledger_entries[1]
                            if len(created_customer_ledger_entries) > 1
                            else created_customer_ledger_entries[0]
                        )
                else:  # Application entry
                    if detailed_entry["initial_document_type"] == "Invoice":
                        # Application against invoice
                        customer_ledger = created_customer_ledger_entries[0]
                    else:  # Application against payment
                        # Application against payment entry
                        customer_ledger = (
                            created_customer_ledger_entries[1]
                            if len(created_customer_ledger_entries) > 1
                            else created_customer_ledger_entries[0]
                        )

                # Determine applied customer ledger entry number
                applied_customer_ledger_entry_no = 0
                if detailed_entry["entry_type"] == "Application":
                    if detailed_entry["initial_document_type"] == "Invoice":
                        # Application against invoice - reference the payment entry
                        applied_customer_ledger_entry_no = (
                            created_customer_ledger_entries[1].id
                            if len(created_customer_ledger_entries) > 1
                            else 0
                        )
                    else:  # Application against payment - reference the payment entry itself
                        applied_customer_ledger_entry_no = (
                            created_customer_ledger_entries[1].id
                            if len(created_customer_ledger_entries) > 1
                            else 0
                        )

                DetailedCustomerLedgerEntry.objects.create(
                    posting_date=detailed_entry["posting_date"],
                    entry_type=(
                        CommonEntryType.initial.value
                        if detailed_entry["entry_type"] == "Initial Entry"
                        else CommonEntryType.application.value
                    ),
                    document_type=(
                        CommonDocumentType.Invoice.value
                        if detailed_entry["document_type"] == "Invoice"
                        else CommonDocumentType.Payment.value
                    ),
                    document_no=detailed_entry["document_no"],
                    customer=self.invoice.customer,
                    amount=detailed_entry["amount"],
                    debit_amount=detailed_entry["debit_amount"],
                    credit_amount=detailed_entry["credit_amount"],
                    initial_entry_due_date=detailed_entry.get(
                        "initial_entry_due_date", self.invoice.due_date
                    ),
                    initial_document_type=(
                        CommonDocumentType.Invoice.value
                        if detailed_entry["initial_document_type"] == "Invoice"
                        else CommonDocumentType.Payment.value
                    ),
                    customer_ledger_entry=customer_ledger,
                    applied_customer_ledger_entry_no=applied_customer_ledger_entry_no,
                    unapplied_by_entry_no=detailed_entry.get(
                        "unapplied_by_entry_no", 0
                    ),
                    unapplied=detailed_entry.get("unapplied", False),
                    global_dimension_1=detailed_entry.get("global_dimension_1"),
                    dimension_set=detailed_entry.get("dimension_set"),
                    transaction_no=detailed_entry["transaction_no"],
                )

            # Update invoice status
            # Payment method should already be set on invoice from creation
            # We don't modify it here - it was set during invoice creation
            self.invoice.status = "Posted"

            # Ensure invoice payment_method is set (should already be set)
            if not self.invoice.payment_method:
                self.invoice.payment_method = self.payment_method

            # Update customer's payment method as a preference for future invoices only
            # This is optional - customer preference is just a convenience default
            # The actual invoice uses its own payment_method (set above)
            if self.customer.payment_method != self.payment_method:
                self.customer.payment_method = self.payment_method
                self.customer.save(update_fields=["payment_method", "updated_at"])

            self.invoice.save()

            # Create Posted Sales Invoice (copy dimensions from source)
            posted_sales_invoice = PostedSalesInvoice.objects.create(
                customer=self.invoice.customer,
                document_date=self.invoice.document_date,
                posting_date=self.invoice.posting_date,
                due_date=self.invoice.due_date,
                vat_date=self.invoice.vat_date,
                customer_invoice_no=self.invoice.customer_invoice_no,
                payment_method=self.invoice.payment_method,  # Copy payment method from SalesInvoice
                invoice_discount_type=self.invoice.invoice_discount_type,
                invoice_discount_amount=self.invoice.invoice_discount_amount,
                invoice_discount_percentage=self.invoice.invoice_discount_percentage,
                global_dimension_1=self.invoice.global_dimension_1,
                global_dimension_2=self.invoice.global_dimension_2,
                dimension_set=self.invoice.dimension_set,
            )
            posted_sales_invoice.save()

            # Create Posted Sales Invoice Lines (copy type and resource for BC-style lines)
            for line in self.invoice.lines.all():
                description = (line.description or "").strip()
                if not description:
                    if line.item_id and line.item:
                        description = line.item.item_name or ""
                    elif line.resource_id and line.resource:
                        description = line.resource.name or ""
                PostedSalesInvoiceLine.objects.create(
                    posted_sales_invoice=posted_sales_invoice,
                    type=line.type,
                    item=line.item,
                    resource=line.resource,
                    gl_account=line.gl_account,
                    description=description,
                    location_code=line.location_code,
                    quantity=line.quantity,
                    unit_of_measure=line.unit_of_measure,
                    item_unit_of_measure=line.item_unit_of_measure,
                    unit_price=line.unit_price,
                    amount=line.total_amount,
                    dimension_set=line.dimension_set,
                    global_dimension_1=line.global_dimension_1
                    or self.invoice.global_dimension_1,
                )

        return {
            "success": True,
            "message": f"Successfully posted invoice {self.invoice.invoice_no}",
            "entries": entries,
        }


@admin.register(SalesReceivable)
class SalesReceivableAdmin(admin.ModelAdmin):
    list_display = [
        "customer_no",
        "invoice_no",
        "posted_invoice_no",
        "credit_memo_no",
        "posted_credit_memo_no",
        "posted_prepayment_invoice_no",
        "posted_prepayment_credit_memo_no",
        "sales_price_list_no",
        "prevent_price_below_original",
        "disable_price_editing",
        "enable_line_discounts",
        "enable_invoice_discounts",
    ]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (
            "Number Series Configuration",
            {
                "fields": (
                    "customer_no",
                    "sales_no",
                    "invoice_no",
                    "posted_invoice_no",
                    "credit_memo_no",
                    "posted_credit_memo_no",
                    "posted_prepayment_invoice_no",
                    "posted_prepayment_credit_memo_no",
                    "sales_price_list_no",
                )
            },
        ),
        (
            "Price Editing Permissions",
            {
                "fields": (
                    "prevent_price_below_original",
                    "disable_price_editing",
                    "enable_line_discounts",
                    "enable_invoice_discounts",
                ),
                "description": "Configure price editing and discount permissions for sales transactions",
            },
        ),
    ]

    def has_add_permission(self, request):
        return not SalesReceivable.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    actions = ["setup_default_configuration"]

    def setup_default_configuration(self, request, queryset):
        from setup.models import NoSeries, NoSeriesLines

        try:
            # Required series including credit memo series
            required_series = [
                "CUSTOMER",
                "INV",
                "POSTINV",
                "CM",
                "POSTCM",
                "POSTPREPINV",
                "POSTPREPCM",
                "SO",
                "SPL",
            ]
            missing_series = []

            for series_code in required_series:
                if not NoSeries.objects.filter(code=series_code).exists():
                    missing_series.append(series_code)

            if missing_series:
                self.message_user(
                    request,
                    f"Missing required number series: {', '.join(missing_series)}. "
                    f"Please run the setup command or create these series first.",
                    level="ERROR",
                )
                return

            # Get all required number series lines
            try:
                customer_series = NoSeriesLines.objects.get(no_series__code="CUSTOMER")
                invoice_series = NoSeriesLines.objects.get(no_series__code="INV")
                posted_invoice_series = NoSeriesLines.objects.get(
                    no_series__code="POSTINV"
                )
                credit_memo_series = NoSeriesLines.objects.get(no_series__code="CM")
                posted_credit_memo_series = NoSeriesLines.objects.get(
                    no_series__code="POSTCM"
                )
                posted_prepayment_invoice_series = NoSeriesLines.objects.get(
                    no_series__code="POSTPREPINV"
                )
                posted_prepayment_credit_memo_series = NoSeriesLines.objects.get(
                    no_series__code="POSTPREPCM"
                )
                sales_order_series = NoSeriesLines.objects.get(no_series__code="SO")
                sales_price_list_series = NoSeriesLines.objects.get(
                    no_series__code="SPL"
                )
            except NoSeriesLines.DoesNotExist as e:
                self.message_user(
                    request,
                    f"Number series line not found: {str(e)}. Please check your NoSeriesLines setup.",
                    level="ERROR",
                )
                return

            SalesReceivable.objects.create(
                customer_no=customer_series,
                invoice_no=invoice_series,
                posted_invoice_no=posted_invoice_series,
                credit_memo_no=credit_memo_series,
                posted_credit_memo_no=posted_credit_memo_series,
                posted_prepayment_invoice_no=posted_prepayment_invoice_series,
                posted_prepayment_credit_memo_no=posted_prepayment_credit_memo_series,
                sales_order_no=sales_order_series,
                sales_price_list_no=sales_price_list_series,
            )

            self.message_user(
                request,
                "SalesReceivable configuration created successfully! Includes credit memo number series.",
                level="SUCCESS",
            )

        except Exception as e:
            self.message_user(
                request, f"Error setting up configuration: {str(e)}", level="ERROR"
            )

    setup_default_configuration.short_description = (
        "Set up default SalesReceivable configuration"
    )


@admin.register(SalesPriceList)
class SalesPriceListAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "description",
        "assign_to_type",
        "assign_to_no",
        "status",
        "starting_date",
        "ending_date",
    ]
    search_fields = ["code", "description"]
    list_filter = ["status", "assign_to_type", "starting_date"]
    readonly_fields = ["code", "created_at", "updated_at"]
    ordering = ["-starting_date", "code"]
    fieldsets = (
        (
            _("General"),
            {
                "fields": (
                    "code",
                    "description",
                    "status",
                )
            },
        ),
        (
            _("Assignment"),
            {
                "fields": (
                    "assign_to_type",
                    "assign_to_no",
                )
            },
        ),
        (
            _("Validity"),
            {
                "fields": (
                    "starting_date",
                    "ending_date",
                )
            },
        ),
        (
            _("Metadata"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


class PostedSalesInvoiceLineInline(admin.TabularInline):
    model = PostedSalesInvoiceLine
    extra = 1
    fields = [
        "type",
        "item",
        "resource",
        "gl_account",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_price",
        "global_dimension_1",
        "dimension_set",
    ]


@admin.register(PostedSalesInvoice)
class PostedSalesInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "customer",
        "document_date",
        "posting_date",
        "due_date",
        "status",
        "reversal_status_display",
    ]
    search_fields = ["no", "customer__name", "customer__no"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "reversed",
        "reversed_by",
        "reversed_date",
        "invoice_discount_type",
        "invoice_discount_amount",
        "invoice_discount_percentage",
    ]
    list_filter = ["status", "reversed", "posting_date", "document_date"]
    fieldsets = [
        (
            "Document Information",
            {
                "fields": (
                    "no",
                    "customer",
                    "document_date",
                    "posting_date",
                    "vat_date",
                    "due_date",
                    "customer_invoice_no",
                    "status",
                    "payment_method",
                    "global_dimension_1",
                    "global_dimension_2",
                    "dimension_set",
                )
            },
        ),
        (
            "Invoice Discount",
            {
                "fields": (
                    "invoice_discount_type",
                    "invoice_discount_amount",
                    "invoice_discount_percentage",
                ),
                "description": "Invoice-level discount (read-only after posting)",
            },
        ),
        (
            "Reversal Information",
            {
                "fields": (
                    "reversed",
                    "reversed_by",
                    "reversed_date",
                    "reverses_document_no",
                )
            },
        ),
    ]

    inlines = [PostedSalesInvoiceLineInline]

    actions = ["create_credit_memo"]

    def reversal_status_display(self, obj):
        """Display reversal status with visual indicators"""
        if obj.reversed:
            return f"❌ Reversed on {obj.reversed_date} by {obj.reversed_by}"
        return "✅ Active"

    reversal_status_display.short_description = "Reversal Status"

    def get_list_display_links(self, request, list_display):
        """Make the document number clickable"""
        return ["no"]

    def create_credit_memo(self, request, queryset):
        """Create Sales Credit Memo from selected Posted Sales Invoice(s)"""

        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one Posted Sales Invoice to create a credit memo.",
                level=messages.ERROR,
            )
            return

        posted_invoice = queryset.first()

        # Check if already reversed
        if posted_invoice.reversed:
            self.message_user(
                request,
                f"Invoice {posted_invoice.no} has already been reversed on {posted_invoice.reversed_date}.",
                level=messages.ERROR,
            )
            return

        # Check if credit memo already exists
        if posted_invoice.credit_memos.filter(status="Posted").exists():
            self.message_user(
                request,
                f"Invoice {posted_invoice.no} already has credit memos posted against it.",
                level=messages.ERROR,
            )
            return

        try:
            with transaction.atomic():
                # Generate credit memo number
                from helpers.helpers import generate_document_number

                credit_memo_no, _ = generate_document_number(
                    SalesReceivable,
                    "credit_memo_no",
                    "credit_memo_no",
                    is_no_series_lines=True,
                )

                if not credit_memo_no:
                    raise Exception("Failed to generate credit memo number")

                # Create the credit memo with status "Draft" (copy dimensions from posted invoice)
                credit_memo = SalesCreditMemo.objects.create(
                    credit_memo_no=credit_memo_no,
                    customer=posted_invoice.customer,
                    document_date=posted_invoice.document_date,
                    posting_date=posted_invoice.posting_date,
                    vat_date=posted_invoice.vat_date,
                    original_invoice_no=posted_invoice.no,
                    original_invoice=posted_invoice,
                    status="Draft",
                    reversed_by_user=request.user,
                    global_dimension_1=posted_invoice.global_dimension_1,
                    global_dimension_2=posted_invoice.global_dimension_2,
                    dimension_set=posted_invoice.dimension_set,
                )

                # Copy all lines from the posted invoice (including dimensions)
                lines_created = 0
                for line in posted_invoice.posted_sales_invoice_lines.all():
                    SalesCreditMemoLine.objects.create(
                        credit_memo=credit_memo,
                        item=line.item,
                        description=line.description,
                        location_code=line.location_code,
                        quantity=line.quantity,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=line.unit_of_measure,
                        unit_price=line.unit_price,
                        amount=line.amount,
                        global_dimension_1=line.global_dimension_1
                        or posted_invoice.global_dimension_1,
                        dimension_set=line.dimension_set,
                    )
                    lines_created += 1

                self.message_user(
                    request,
                    f"✅ Successfully created Sales Credit Memo from invoice {posted_invoice.no}. "
                    f"Credit Memo {credit_memo_no} has {lines_created} line(s) with status 'Draft'. "
                    f"You can now edit it and post it when ready.",
                    level=messages.SUCCESS,
                )

                # Redirect to the created credit memo
                from django.urls import reverse
                from django.shortcuts import redirect

                url = reverse(
                    "admin:sales_salescreditmemo_change", args=[credit_memo.pk]
                )
                return redirect(url)

        except Exception as e:
            self.message_user(
                request,
                f"Error creating credit memo: {str(e)}",
                level=messages.ERROR,
            )

    create_credit_memo.short_description = "📝 Create Credit Memo"


@admin.register(CustomerPostingGroup)
class CustomerPostingGroupAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "receivables_account")
    search_fields = ("code", "description")
    ordering = ("code",)
    actions = [sync_from_json_file, sync_all_models_from_json]


@admin.register(Customer)
class CustomerAdmin(DefaultDimensionAdminMixin, admin.ModelAdmin):
    related_model = "sales.Customer"
    no_attr = "no"

    list_display = (
        "no",
        "name",
        "city",
        "phone_number",
        "general_business_posting_group",
        "payment_method",
    )
    search_fields = ("name", "phone_number")
    list_filter = (
        "city",
        "customer_posting_group",
        "general_business_posting_group",
        "payment_method",
    )
    readonly_fields = ("no", "created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "no",
                    "name",
                    "address",
                    "address_2",
                    "city",
                )
            },
        ),
        (
            "Contact Information",
            {"fields": ("contact", "phone_number")},
        ),
        (
            "Posting Groups",
            {
                "fields": (
                    "customer_posting_group",
                    "general_business_posting_group",
                    "vat_business_posting_group",
                    "payment_method",
                )
            },
        ),
        ("Financial", {"fields": ("credit_limit",)}),
    )


@admin.register(CustomerLedgerEntry)
class CustomerLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "posting_date",
        "document_type",
        "document_no",
        "customer",
        "get_customer_name",
        "description",
        "amount",
        "get_remaining_amount",
        "sales",
        "payment_method",
        "reversal_status_display",
    )

    list_filter = (
        "posting_date",
        "document_type",
        "customer",
        "payment_method",
        "open",
        "reversed",
    )

    search_fields = (
        "document_no",
        "customer__name",
        "description",
        "external_document_no",
    )

    readonly_fields = (
        "posting_date",
        "document_date",
        "document_type",
        "document_no",
        "customer",
        "amount",
        "get_remaining_amount",
        "sales",
        "reversed",
        "reversed_by_document_no",
        "reversed_date",
        "reverses_entry_no",
        "reversed_by_user",
    )

    date_hierarchy = "posting_date"

    def get_customer_name(self, obj):
        return obj.customer.name

    get_customer_name.short_description = _("Customer Name")
    get_customer_name.admin_order_field = "customer__name"

    def get_remaining_amount(self, obj):
        """Get remaining amount from property"""
        return abs(obj.remaining_amount)

    get_remaining_amount.short_description = _("Remaining Amount")

    def reversal_status_display(self, obj):
        """Display reversal status with visual indicators"""
        if obj.reversed:
            return f"❌ Reversed by {obj.reversed_by_document_no or 'N/A'}"
        elif obj.reverses_entry_no:
            return f"🔄 Reverses Entry #{obj.reverses_entry_no}"
        return "✅ Active"

    reversal_status_display.short_description = _("Reversal Status")

    def has_add_permission(self, request):
        return False  # Entries should only be created through transactions


@admin.register(SalesInvoiceLine)
class SalesInvoiceLineAdmin(admin.ModelAdmin):
    list_display = [
        "sales_invoice",
        "item",
        "gl_account",
        "quantity",
        "unit_price",
        "total_amount",
        "global_dimension_1",
    ]
    list_filter = [
        BranchListFilter,
        "sales_invoice",
        "item",
        "gl_account",
    ]
    list_select_related = (
        "sales_invoice",
        "item",
        "gl_account",
        "global_dimension_1",
    )
    search_fields = [
        "sales_invoice__invoice_no",
        "item__item_name",
        "item__no",
        "global_dimension_1__code",
        "global_dimension_1__description",
    ]
    readonly_fields = ["total_amount", "line_amount"]

    def line_amount(self, obj):
        return obj.total_amount


class SalesCreditMemoLineInline(admin.TabularInline):
    model = SalesCreditMemoLine
    extra = 0
    fields = [
        "item",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_price",
        "amount",
    ]
    readonly_fields = ["amount"]

    def has_add_permission(self, request, obj=None):
        # Don't allow adding lines to posted credit memos
        if obj and obj.status == "Posted":
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Don't allow deleting lines from posted credit memos
        if obj and obj.status == "Posted":
            return False
        return super().has_delete_permission(request, obj)


class SalesCreditMemoPostingProcessor:
    """
    Post an existing Sales Credit Memo by creating reversal entries.
    Similar to SalesInvoiceReversalPostingProcessor but works with existing credit memo.
    """

    def __init__(self, credit_memo, request):
        self.credit_memo = credit_memo
        self.request = request
        self.user = request.user
        self.reason = credit_memo.reason_for_reversal or ""

    def post(self):
        """Execute the posting in a database transaction

        IMPORTANT: This method FIRST runs the preview processor to generate
        all reversal entries, then creates the actual database entries from
        those preview entries. This ensures consistency between preview and posting.

        Flow:
        1. Run SalesInvoiceReversalProcessor to generate preview entries
        2. Use those preview entries to create actual database entries:
           - GL entries (from reversal_entries["gl_entries"])
           - Customer entries (from reversal_entries["customer_entries"])
           - Item entries (from reversal_entries["item_entries"])
           - Value entries (from reversal_entries["value_entries"])
           - Bank entries (from reversal_entries["bank_entries"])

        All operations are wrapped in an atomic transaction that will rollback
        completely if any step fails.
        """
        with transaction.atomic():
            try:
                from dimension.utils import get_first_branch_dimension_value

                # Get the original PostedSalesInvoice
                posted_sales_invoice = self.credit_memo.original_invoice
                if not posted_sales_invoice:
                    raise Exception(
                        "Credit memo is not linked to an original posted invoice."
                    )

                # Find the SalesInvoice to get the invoice_no for finding entries
                customer_invoice_no = getattr(
                    posted_sales_invoice, "customer_invoice_no", None
                )
                sales_invoice = None

                if customer_invoice_no:
                    from .models import SalesInvoice

                    sales_invoice = SalesInvoice.objects.filter(
                        customer_invoice_no=customer_invoice_no,
                        customer=posted_sales_invoice.customer,
                        status="Posted",
                    ).first()

                if not sales_invoice:
                    # Fallback: match by customer and document_date
                    sales_invoice = SalesInvoice.objects.filter(
                        customer=posted_sales_invoice.customer,
                        document_date=posted_sales_invoice.document_date,
                        status="Posted",
                    ).first()

                if not sales_invoice:
                    raise Exception(
                        f"Could not find original Sales Invoice for credit memo {self.credit_memo.credit_memo_no}."
                    )

                # Use the existing credit memo number
                credit_memo_no = self.credit_memo.credit_memo_no

                # Generate consistent transaction number for ALL reversal entries
                import uuid

                transaction_no = (
                    f"REV-{credit_memo_no}-"
                    f"{timezone.now().date().strftime('%Y%m%d')}-"
                    f"{uuid.uuid4().hex[:6].upper()}"
                )

                # Create wrapper for reversal processor
                class ReversalInvoiceWrapper:
                    def __init__(self, sales_invoice):
                        self.no = sales_invoice.invoice_no
                        self.customer = sales_invoice.customer
                        self.document_date = sales_invoice.document_date
                        self.posting_date = sales_invoice.posting_date
                        self.vat_date = getattr(sales_invoice, "vat_date", None)
                        self.due_date = getattr(sales_invoice, "due_date", None)
                        self.customer_invoice_no = getattr(
                            sales_invoice, "customer_invoice_no", None
                        )
                        self.status = sales_invoice.status
                        self.reversed = False
                        self.posted_sales_invoice_lines = sales_invoice.lines
                        self.credit_memos = SalesCreditMemo.objects.none()

                invoice_wrapper = ReversalInvoiceWrapper(sales_invoice)

                # STEP 1: Get reversal entries from preview processor
                # This generates all reversal entries (GL, Customer, Item, Value, Bank)
                # without saving them - we'll use these entries to create actual DB records
                processor = SalesInvoiceReversalProcessor(invoice_wrapper, self.request)
                reversal_entries = processor.process()

                if not reversal_entries.get("success"):
                    raise Exception(reversal_entries.get("message"))

                # Create GL entries (with opposite signs) and mark originals as reversed
                original_gl_entries = list(
                    GeneralLedgerEntry.objects.filter(
                        document_no=sales_invoice.invoice_no
                    )
                )

                for idx, gl_entry in enumerate(reversal_entries["gl_entries"]):
                    original_gl = (
                        original_gl_entries[idx]
                        if idx < len(original_gl_entries)
                        else None
                    )

                    # Create reversing GL entry with consistent transaction number
                    reversing_gl = GeneralLedgerEntry.objects.create(
                        posting_date=gl_entry["posting_date"],
                        document_type=gl_entry["document_type"],
                        document_no=credit_memo_no,  # Use existing credit memo number
                        gl_account=gl_entry["gl_account"],
                        description=gl_entry["description"],
                        amount=gl_entry["amount"],
                        general_posting_type=gl_entry["gen_posting_type"],
                        dimension_set=gl_entry.get("dimension_set"),
                        global_dimension_1=gl_entry.get("global_dimension_1"),
                        global_dimension_2=gl_entry.get("global_dimension_2"),
                        general_business_posting_group=gl_entry[
                            "gen_bus_posting_group"
                        ],
                        general_product_posting_group=gl_entry[
                            "gen_prod_posting_group"
                        ],
                        balancing_account_type=gl_entry["balance_account_type"],
                        user=gl_entry["user"],
                        transaction_no=transaction_no,
                        reverses_entry_no=(original_gl.id if original_gl else None),
                    )

                    # Mark original GL entry as reversed
                    if original_gl:
                        original_gl.reversed = True
                        original_gl.reversed_by_document_no = credit_memo_no
                        original_gl.reversed_date = timezone.now().date()
                        original_gl.reversed_by_user = self.user
                        original_gl.save()

                # Create Customer Ledger entries (with opposite signs) and mark originals
                original_customer_entries = list(
                    CustomerLedgerEntry.objects.filter(
                        document_no=sales_invoice.invoice_no
                    )
                )

                for idx, cust_entry in enumerate(reversal_entries["customer_entries"]):
                    original_cust = (
                        original_customer_entries[idx]
                        if idx < len(original_customer_entries)
                        else None
                    )

                    # Create reversing customer entry
                    reversing_cust = CustomerLedgerEntry.objects.create(
                        posting_date=cust_entry["posting_date"],
                        document_date=cust_entry["document_date"],
                        document_type=cust_entry["document_type"],
                        document_no=credit_memo_no,
                        customer=cust_entry["customer"],
                        description=cust_entry["description"],
                        payment_method=cust_entry["payment_method"],
                        original_amount=cust_entry["original_amount"],
                        amount=cust_entry["amount"],
                        sales=cust_entry["sales"],
                        open=cust_entry["open"],
                        due_date=cust_entry["due_date"],
                        global_dimension_1=cust_entry["global_dimension_1"],
                        dimension_set=(
                            getattr(original_cust, "dimension_set", None)
                            if original_cust
                            else cust_entry.get("dimension_set")
                        ),
                        user=cust_entry["user"],
                        transaction_no=transaction_no,
                        reverses_entry_no=(original_cust.id if original_cust else None),
                    )

                    # Mark original customer entry as reversed
                    if original_cust:
                        original_cust.reversed = True
                        original_cust.reversed_by_document_no = credit_memo_no
                        original_cust.reversed_date = timezone.now().date()
                        original_cust.reversed_by_user = self.user
                        original_cust.save()

                # Create Item Ledger entries (with opposite quantities) and mark originals
                original_item_entries = list(
                    ItemLedgerEntries.objects.filter(
                        document_no=sales_invoice.invoice_no
                    )
                )

                created_reversing_item_entries = []

                for idx, item_entry in enumerate(reversal_entries["item_entries"]):
                    original_item = (
                        original_item_entries[idx]
                        if idx < len(original_item_entries)
                        else None
                    )

                    # Create reversing item entry
                    reversing_item = ItemLedgerEntries.objects.create(
                        posting_date=item_entry["posting_date"],
                        entry_type=item_entry["entry_type"],
                        item=item_entry["item"],
                        document_no=credit_memo_no,
                        description=item_entry["description"],
                        location=item_entry["location"],
                        quantity=item_entry["quantity"],
                        remaining_quantity=item_entry["remaining_quantity"],
                        total=item_entry["total"],
                        unit_of_measure_code=item_entry["unit_of_measure_code"],
                        global_dimension_1=item_entry["global_dimension_1"],
                        user=item_entry["user"],
                        date=item_entry["date"],
                        document_type=item_entry["document_type"],
                        transaction_no=transaction_no,
                        reverses_entry_no=(original_item.id if original_item else None),
                    )

                    created_reversing_item_entries.append(reversing_item)

                    # Mark original item entry as reversed
                    if original_item:
                        original_item.reversed = True
                        original_item.reversed_by_document_no = credit_memo_no
                        original_item.reversed_date = timezone.now().date()
                        original_item.reversed_by_user = self.user
                        original_item.save()

                # Create Value entries (with opposite amounts) and mark originals
                original_value_entries = list(
                    ValueEntry.objects.filter(document_no=sales_invoice.invoice_no)
                )

                for idx, val_entry in enumerate(reversal_entries["value_entries"]):
                    original_val = (
                        original_value_entries[idx]
                        if idx < len(original_value_entries)
                        else None
                    )

                    item_ledger_entry = (
                        created_reversing_item_entries[idx]
                        if idx < len(created_reversing_item_entries)
                        else None
                    )

                    if not item_ledger_entry:
                        continue

                    # Create reversing value entry
                    # Note: ValueEntry doesn't have entry_no field - it uses id (auto-generated)
                    reversing_val = ValueEntry.objects.create(
                        posting_date=val_entry["posting_date"],
                        document_no=credit_memo_no,
                        item=val_entry["item"],
                        cost_amount=val_entry["cost_amount"],
                        cost_amount_non_invtbl=val_entry.get("cost_amount_non_invtbl")
                        or 0,
                        item_ledger_entry_quantity=val_entry[
                            "item_ledger_entry_quantity"
                        ],
                        invoiced_quantity=val_entry["invoiced_quantity"],
                        valued_quantity=val_entry["valued_quantity"],
                        cost_per_unit=val_entry["cost_per_unit"],
                        general_product_posting_group=val_entry.get(
                            "general_product_posting_group"
                        ),
                        inventory_posting_group=val_entry.get(
                            "inventory_posting_group"
                        ),
                        document_type=val_entry.get("document_type", "Credit Memo"),
                        entry_type=val_entry.get(
                            "entry_type", EntryType.DirectCost.value
                        ),
                        sales_amount=val_entry.get("sales_amount", 0),
                        transaction_no=transaction_no,
                        item_ledger_entry_no=item_ledger_entry,  # Link to reversing ItemLedgerEntry
                        global_dimension_1=val_entry.get("global_dimension_1")
                        or get_first_branch_dimension_value(),  # Fallback to first branch
                        reverses_value_entry_no=(
                            original_val.id if original_val else None
                        ),  # Note: field name is reverses_value_entry_no, not reverses_entry_no
                    )

                    # Mark original value entry as reversed
                    if original_val:
                        original_val.reversed = True
                        original_val.reversed_by_document_no = credit_memo_no
                        original_val.reversed_date = timezone.now().date()
                        original_val.reversed_by_user = self.user
                        original_val.save()

                # Create Bank Ledger entries (with opposite amounts) and mark originals
                # Bank ledger entries are identified by:
                # 1. Checking if sales_invoice.payment_method uses Bank Account
                # 2. Finding bank ledger entries by document_no matching invoice number
                # Note: In this processor, we already have the original sales_invoice,
                # so we can check payment_method directly (no need to look it up)
                from bank_account.models import BankAccountLedgerEntry
                from bank_account.enums import BankAccountDocumentType
                from financials.enums import BalacingAccountType

                # Check if payment method uses Bank Account (for validation/logging)
                uses_bank_account = False
                if sales_invoice.payment_method:
                    payment_method = sales_invoice.payment_method
                    uses_bank_account = (
                        payment_method.bal_account_type
                        == BalacingAccountType.Bank_Account.name
                        and bool(payment_method.bal_bank_account_no)
                    )

                original_bank_entries = list(
                    BankAccountLedgerEntry.objects.filter(
                        document_no=sales_invoice.invoice_no
                    )
                )

                for idx, bank_entry in enumerate(
                    reversal_entries.get("bank_entries", [])
                ):
                    original_bank = (
                        original_bank_entries[idx]
                        if idx < len(original_bank_entries)
                        else None
                    )

                    # Create reversing bank entry with consistent transaction number
                    reversing_bank = BankAccountLedgerEntry.objects.create(
                        bank_account_no=bank_entry["bank_account_no"],
                        posting_date=bank_entry["posting_date"],
                        document_type=bank_entry["document_type"],
                        document_no=credit_memo_no,
                        description=bank_entry["description"],
                        amount=bank_entry[
                            "amount"
                        ],  # Already opposite sign from preview
                        bank_account_posting_group=bank_entry.get(
                            "bank_account_posting_group"
                        ),
                        bal_account_type=bank_entry.get("bal_account_type"),
                        bal_account_no=bank_entry.get("bal_account_no"),
                        global_dimension_1=bank_entry.get("global_dimension_1"),
                        dimension_set=(
                            getattr(original_bank, "dimension_set", None)
                            if original_bank
                            else bank_entry.get("dimension_set")
                        ),
                        user=bank_entry["user"],
                        document_date=bank_entry.get("document_date"),
                        reversed_entry_no=(
                            original_bank.entry_no if original_bank else None
                        ),  # Link to original entry
                    )

                    # Mark original bank entry as reversed
                    if original_bank:
                        original_bank.reversed = True
                        original_bank.reversed_by_entry_no = reversing_bank.entry_no
                        original_bank.reversed_date = timezone.now().date()
                        original_bank.reversed_by_user = self.user
                        original_bank.save()

                # Mark PostedSalesInvoice as reversed
                posted_sales_invoice.reversed = True
                posted_sales_invoice.reversed_by = credit_memo_no
                posted_sales_invoice.reversed_date = timezone.now().date()
                posted_sales_invoice.save()

                # Update credit memo status to Posted
                self.credit_memo.status = "Posted"
                self.credit_memo.save()

                # Keep SalesInvoice status as "Posted" - the reversed boolean field indicates reversal
                # This matches the purchase invoice reversal pattern

                return {
                    "success": True,
                    "message": f"Successfully posted credit memo {credit_memo_no}",
                    "credit_memo_no": credit_memo_no,
                    "credit_memo": self.credit_memo,
                    "transaction_no": transaction_no,
                    "posted_sales_invoice": posted_sales_invoice,
                }

            except Exception as e:
                import traceback

                error_details = f"{str(e)}\n\nTransaction Number: {transaction_no if 'transaction_no' in locals() else 'N/A'}"
                return {"success": False, "message": error_details}


@admin.register(SalesCreditMemo)
class SalesCreditMemoAdmin(admin.ModelAdmin):
    list_display = [
        "credit_memo_no",
        "customer",
        "original_invoice_no",
        "document_date",
        "posting_date",
        "status",
        "reversed_by_user",
    ]
    search_fields = [
        "credit_memo_no",
        "customer__name",
        "original_invoice_no",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "credit_memo_no",
        "original_invoice",
        "original_invoice_no",
        "reversed_by_user",
    ]
    list_filter = ["status", "posting_date", "document_date"]

    fieldsets = [
        (
            "Credit Memo Information",
            {
                "fields": (
                    "credit_memo_no",
                    "customer",
                    "document_date",
                    "posting_date",
                    "vat_date",
                    "status",
                )
            },
        ),
        (
            "Original Invoice Reference",
            {
                "fields": (
                    "original_invoice",
                    "original_invoice_no",
                    "reason_for_reversal",
                    "reversed_by_user",
                )
            },
        ),
    ]

    inlines = [SalesCreditMemoLineInline]

    actions = ["preview_posting", "post_credit_memo"]

    def has_add_permission(self, request):
        # Credit memos are created through reversal process, not manually
        return False

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of posted credit memos
        if obj and obj.status == "Posted":
            return False
        return True

    def has_change_permission(self, request, obj=None):
        # Don't allow editing posted credit memos
        if obj and obj.status == "Posted":
            return False
        return True

    def preview_posting(self, request, queryset):
        """Preview posting of Sales Credit Memo by finding and reversing original invoice entries"""

        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one Sales Credit Memo to preview posting.",
                level=messages.ERROR,
            )
            return

        credit_memo = queryset.first()

        # Validate credit memo
        if not credit_memo.original_invoice:
            self.message_user(
                request,
                "This credit memo is not linked to an original posted invoice.",
                level=messages.ERROR,
            )
            return

        if credit_memo.status == "Posted":
            self.message_user(
                request,
                "This credit memo has already been posted.",
                level=messages.ERROR,
            )
            return

        # Get the original PostedSalesInvoice
        posted_invoice = credit_memo.original_invoice

        # Find the SalesInvoice to create wrapper
        # Try to find by customer_invoice_no first
        customer_invoice_no = getattr(posted_invoice, "customer_invoice_no", None)
        sales_invoice = None

        if customer_invoice_no:
            from .models import SalesInvoice

            sales_invoice = SalesInvoice.objects.filter(
                customer_invoice_no=customer_invoice_no,
                customer=posted_invoice.customer,
                status="Posted",
            ).first()

        if not sales_invoice:
            # Fallback: match by customer and document_date
            sales_invoice = SalesInvoice.objects.filter(
                customer=posted_invoice.customer,
                document_date=posted_invoice.document_date,
                status="Posted",
            ).first()

        if not sales_invoice:
            self.message_user(
                request,
                f"Could not find original Sales Invoice for credit memo {credit_memo.credit_memo_no}.",
                level=messages.ERROR,
            )
            return

        # Create wrapper for preview
        class ReversalInvoiceWrapper:
            def __init__(self, sales_invoice):
                self.no = sales_invoice.invoice_no
                self.customer = sales_invoice.customer
                self.document_date = sales_invoice.document_date
                self.posting_date = sales_invoice.posting_date
                self.vat_date = getattr(sales_invoice, "vat_date", None)
                self.due_date = getattr(sales_invoice, "due_date", None)
                self.customer_invoice_no = getattr(
                    sales_invoice, "customer_invoice_no", None
                )
                self.status = sales_invoice.status
                self.reversed = False
                self.posted_sales_invoice_lines = sales_invoice.lines
                self.credit_memos = SalesCreditMemo.objects.none()

        invoice_wrapper = ReversalInvoiceWrapper(sales_invoice)

        try:
            # Generate preview using wrapper
            processor = SalesInvoiceReversalProcessor(invoice_wrapper, request)
            entries = processor.process()

            if not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing posting: {entries.get('message', 'Unknown error')}",
                    level=messages.ERROR,
                )
                return

            # Prepare preview data
            preview_data = {
                "credit_memo": credit_memo,
                "original_invoice": posted_invoice,
                "steps": [
                    "✅ Use existing credit memo document",
                    "✅ Reverse GL entries (opposite signs)",
                    "✅ Reverse customer ledger entries",
                    "✅ Reverse VAT entries (opposite signs)",
                    "✅ Reverse item ledger entries",
                    "✅ Reverse bank ledger entries",
                    "✅ Restore inventory quantities",
                    "✅ Mark original invoice as reversed",
                ],
                "gl_entries_count": len(entries.get("gl_entries", [])),
                "customer_entries_count": len(entries.get("customer_entries", [])),
                "item_entries_count": len(entries.get("item_entries", [])),
                "value_entries_count": len(entries.get("value_entries", [])),
                "bank_entries_count": len(entries.get("bank_entries", [])),
                "vat_entries_count": len(entries.get("reversal_vat_entries", [])),
                "entries": entries,
            }

            # Render preview template (reuse the same template as reversal preview)
            return TemplateResponse(
                request,
                "admin/sales/postedsalesinvoice/preview_reversal.html",
                context={
                    "title": "Preview Credit Memo Posting",
                    "credit_memo": credit_memo,
                    "preview_data": preview_data,
                    "opts": self.model._meta,
                },
            )

        except Exception as e:
            self.message_user(
                request, f"Error previewing posting: {str(e)}", level=messages.ERROR
            )

    preview_posting.short_description = "🔍 Preview Posting"

    def post_credit_memo(self, request, queryset):
        """Post Sales Credit Memo by creating reversal entries"""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one Sales Credit Memo to post.",
                level=messages.ERROR,
            )
            return

        credit_memo = queryset.first()

        # Validate credit memo
        if credit_memo.status == "Posted":
            self.message_user(
                request,
                "This credit memo has already been posted.",
                level=messages.ERROR,
            )
            return

        if not credit_memo.original_invoice:
            self.message_user(
                request,
                "This credit memo is not linked to an original posted invoice.",
                level=messages.ERROR,
            )
            return

        try:
            # Get the original PostedSalesInvoice
            posted_invoice = credit_memo.original_invoice

            # Find the SalesInvoice to create wrapper
            customer_invoice_no = getattr(posted_invoice, "customer_invoice_no", None)
            sales_invoice = None

            if customer_invoice_no:
                from .models import SalesInvoice

                sales_invoice = SalesInvoice.objects.filter(
                    customer_invoice_no=customer_invoice_no,
                    customer=posted_invoice.customer,
                    status="Posted",
                ).first()

            if not sales_invoice:
                # Fallback: match by customer and document_date
                sales_invoice = SalesInvoice.objects.filter(
                    customer=posted_invoice.customer,
                    document_date=posted_invoice.document_date,
                    status="Posted",
                ).first()

            if not sales_invoice:
                raise Exception(
                    f"Could not find original Sales Invoice for credit memo {credit_memo.credit_memo_no}."
                )

            # Create wrapper
            class ReversalInvoiceWrapper:
                def __init__(self, sales_invoice):
                    self.no = sales_invoice.invoice_no
                    self.customer = sales_invoice.customer
                    self.document_date = sales_invoice.document_date
                    self.posting_date = sales_invoice.posting_date
                    self.vat_date = getattr(sales_invoice, "vat_date", None)
                    self.due_date = getattr(sales_invoice, "due_date", None)
                    self.customer_invoice_no = getattr(
                        sales_invoice, "customer_invoice_no", None
                    )
                    self.status = sales_invoice.status
                    self.reversed = False
                    self.posted_sales_invoice_lines = sales_invoice.lines
                    self.credit_memos = SalesCreditMemo.objects.none()

            invoice_wrapper = ReversalInvoiceWrapper(sales_invoice)

            # Use SalesCreditMemoPostingProcessor
            processor = SalesCreditMemoPostingProcessor(credit_memo, request)

            # Start transaction to ensure all entries are created or none are
            with transaction.atomic():
                result = processor.post()

                if result["success"]:
                    self.message_user(
                        request,
                        f"✅ Successfully posted credit memo {credit_memo.credit_memo_no}",
                        level=messages.SUCCESS,
                    )
                else:
                    error_msg = result.get("message", "Unknown error during posting")
                    self.message_user(request, error_msg, level=messages.ERROR)
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = str(e)
            self.message_user(request, error_msg, level=messages.ERROR)

    post_credit_memo.short_description = "📤 Post Credit Memo (Create Reversal Entries)"


@admin.register(DetailedCustomerLedgerEntry)
class DetailedCustomerLedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        "posting_date",
        "entry_type",
        "document_type",
        "document_no",
        "customer",
        "amount",
        "debit_amount",
        "credit_amount",
        "reversal_status_display",
        "customer_ledger_entry",
    )

    list_filter = (
        "posting_date",
        "entry_type",
        "document_type",
        "customer",
        "unapplied",
        "reversed",
    )

    search_fields = (
        "document_no",
        "customer__name",
        "transaction_no",
    )

    readonly_fields = (
        "entry_no",
        "posting_date",
        "entry_type",
        "document_type",
        "document_no",
        "customer",
        "amount",
        "initial_entry_due_date",
        "initial_document_type",
        # "customer_ledger_entry",
        "applied_customer_ledger_entry_no",
        "unapplied_by_entry_no",
        "unapplied",
        "debit_amount",
        "credit_amount",
        "global_dimension_1",
        "transaction_no",
        "reversed",
        "reversed_by_document_no",
        "reversed_date",
        "reverses_entry_no",
        "reversed_by_user",
    )

    def reversal_status_display(self, obj):
        """Display reversal status with visual indicators"""
        if obj.reversed:
            return f"❌ Reversed by {obj.reversed_by_document_no or 'N/A'}"
        elif obj.reverses_entry_no:
            return f"🔄 Reverses Entry #{obj.reverses_entry_no}"
        return "✅ Active"

    reversal_status_display.short_description = _("Reversal Status")

    date_hierarchy = "posting_date"

    ordering = ["-posting_date", "-entry_no"]

    # def has_add_permission(self, request):
    #     return False  # Entries should only be created through transactions

    # def has_delete_permission(self, request, obj=None):
    #     return False  # Prevent deletion of ledger entries

    # def has_change_permission(self, request, obj=None):
    #     return False  # Prevent editing of ledger entries


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1
    fields = [
        "type",
        "item",
        "resource",
        "gl_account",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_price",
    ]
    readonly_fields = ["amount", "total_amount", "line_amount"]


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = [
        "order_no",
        "customer",
        "order_date",
        "expected_delivery_date",
        "status",
        "total_amount",
        "created_at",
    ]
    list_filter = ["status", "order_date"]
    search_fields = ["customer__name", "order_no"]
    readonly_fields = ["created_at", "updated_at", "order_no", "total_amount"]
    inlines = [SalesOrderLineInline]
    fieldsets = [
        ("Customer Information", {"fields": ("customer", "contact_person")}),
        (
            "Document Information",
            {
                "fields": (
                    "order_date",
                    "expected_delivery_date",
                    "status",
                    "notes",
                    "total_amount",
                )
            },
        ),
    ]
