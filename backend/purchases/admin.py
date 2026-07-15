from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Max
from django.conf import settings
import uuid

from django.contrib import admin
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from .models import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    PurchasePayable,
    Vendor,
    VendorLedger,
    VendorPostingGroup,
    DetailedVendorLedgerEntry,
    PostedPurchaseInvoice,
    PostedPurchaseInvoiceLine,
    PurchaseCreditMemo,
    PurchaseCreditMemoLine,
    PostedPurchaseCreditMemo,
    PostedPurchaseCreditMemoLine,
    DocumentAttachment,
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

from items.enums import DocumentType, EntryType
from financials.enums import BalacingAccountType
from dimension.models import DimensionValue, Dimension, get_dimension_value_from_set
from dimension.admin_mixin import DefaultDimensionAdminMixin
from common.enums import (
    DocumentType as CommonDocumentType,
    EntryType as CommonEntryType,
)


class DocumentAttachmentInline(admin.TabularInline):
    model = DocumentAttachment
    extra = 0
    fields = ["file", "name", "created_at"]
    readonly_fields = ["created_at"]


class PurchaseInvoiceLineInline(admin.TabularInline):
    model = PurchaseInvoiceLine
    extra = 1
    fields = [
        "item",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_cost",
        "global_dimension_1",
        "dimension_set",
        # "line_amount",
    ]
    readonly_fields = ["total_amount", "line_amount", "global_dimension_1", "dimension_set"]


class TrackingSpecificationInline(admin.TabularInline):
    model = TrackingSpecification
    extra = 1

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Get the parent instance ID from the URL
        if hasattr(request, "resolver_match"):
            instance_id = request.resolver_match.kwargs.get("object_id")
            if instance_id:
                return qs.filter(purchase_invoice_id=instance_id)
        return qs.none()


@admin.register(PurchaseInvoice)
class PurchaseInvoiceAdmin(admin.ModelAdmin):
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
        "vendor",
        "global_dimension_1",
        "global_dimension_2",
        "dimension_set",
        "document_date",
        "vendor_invoice_no",
        "status",
        "created_at",
    ]
    list_filter = ["status", "document_date", EmptyDimensionFieldsFilter]
    search_fields = ["vendor__name", "vendor_invoice_no", "invoice_no"]
    readonly_fields = ["created_at", "updated_at", "invoice_no"]
    list_select_related = (
        "vendor",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
    )
    fieldsets = [
        ("Vendor Information", {"fields": ("vendor", "contact_person")}),
        (
            "Document Information",
            {
                "fields": (
                    "document_date",
                    "posting_date",
                    "vat_date",
                    "due_date",
                    "vendor_invoice_no",
                    "status",
                    "payment_method",
                )
            },
        ),
        (
            "VAT",
            {
                "fields": ("total_vat_amount",),
                "description": "VAT settings (requires VAT enabled in General Ledger Setup). Amounts are always inclusive of VAT.",
            },
        ),
        (
            "Tracking Code (Dimensions)",
            {
                "fields": ("global_dimension_1", "global_dimension_2", "dimension_set"),
                "description": "BC-style dimensions. Global Dimension 1 is typically Branch. Filled from current branch when creating via API.",
            },
        ),
    ]
    inlines = [PurchaseInvoiceLineInline, DocumentAttachmentInline, TrackingSpecificationInline]

    actions = ["preview_posting", "post_invoice"]

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
            # Run validation first
            invoice.full_clean()
            invoice.clean()  # Custom model validation

            # Validate tracking specifications for all lines
            is_valid, errors = invoice.validate_all_tracking_specifications()
            if not is_valid:
                error_message = "; ".join(errors)
                self.message_user(
                    request,
                    f"Error previewing posting: {error_message}",
                    level="ERROR",
                )
                return

            # # Check invoice lines validation
            for line in invoice.lines.all():
                line.full_clean()
                line.clean()  # Custom model validation

            # If validation passes, proceed with posting preview
            processor = PurchaseInvoiceProcessor(invoice, request, receipt_no)
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
                    "Posting purchases and VAT 1",
                    "Posting to vendors 1",
                    "Posting to bal. account 1",
                ],
                "entries": entries,
            }

            return TemplateResponse(
                request,
                "admin/purchases/purchaseinvoice/preview_posting.html",
                context={
                    "title": "Preview Posting",
                    "invoice": invoice,
                    "preview_entries": preview_entries,
                    "opts": self.model._meta,
                },
            )

        except ValidationError as e:
            # Extract just the error message without the dictionary formatting
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
            # Validate tracking specifications for all lines before posting
            is_valid, errors = invoice.validate_all_tracking_specifications()
            if not is_valid:
                error_message = "; ".join(errors)
                if hasattr(self, "message_user"):
                    self.message_user(request, error_message, level="ERROR")
                raise Exception(error_message)

            # Create posting processor and post the invoice
            processor = PurchaseInvoicePostingProcessor(invoice, request, receipt_no)

            # Start transaction to ensure all entries are created or none are
            with transaction.atomic():
                result = processor.post()

                if result["success"]:
                    if hasattr(self, "message_user"):
                        self.message_user(
                            request,
                            f"Successfully posted invoice {invoice.invoice_no}",
                            level="SUCCESS",
                        )
                else:
                    error_msg = result.get("message", "Unknown error during posting")
                    if hasattr(self, "message_user"):
                        self.message_user(request, error_msg, level="ERROR")
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = str(e)
            # Clean up redundant prefixes
            if error_msg.startswith("Error posting purchase: "):
                error_msg = error_msg.replace("Error posting purchase: ", "")
            if error_msg.startswith("Error posting invoice: "):
                error_msg = error_msg.replace("Error posting invoice: ", "")
            if error_msg.startswith("Error processing invoice: "):
                error_msg = error_msg.replace("Error processing invoice: ", "")

            if hasattr(self, "message_user"):
                self.message_user(request, error_msg, level="ERROR")
            raise Exception(error_msg)


class PurchaseInvoiceProcessor:
    def __init__(self, invoice, request, receipt_no):
        self.invoice = invoice
        self.user = request.user
        self.lines = invoice.lines.all()
        self.vendor = invoice.vendor

        # Check if vendor has business posting group
        if not invoice.vendor.business_posting_group:
            raise Exception(
                f"Vendor '{self.vendor.name}' does not have a Business Posting Group assigned. "
                f"Please assign a Business Posting Group to vendor '{self.vendor.name}' before posting invoices."
            )
        self.genBusinessPostingGroup = invoice.vendor.business_posting_group

        # IMPORTANT: Use invoice payment_method ONLY - each invoice should have its own payment method
        # This ensures invoices are independent and avoid race conditions with multiple windows
        # Invoice payment_method should be set during invoice creation or before posting (via modal)
        if not invoice.payment_method:
            raise Exception(
                f"Please choose how this purchase was paid (Pay later, Cash, or Bank) before posting."
            )
        self.payment_method = invoice.payment_method

        # Check if vendor_posting_group exists before accessing payables_account
        if not self.vendor.vendor_posting_group:
            raise Exception(
                f"Vendor '{self.vendor.name}' does not have a Vendor Posting Group assigned. "
                f"Please assign a Vendor Posting Group to vendor '{self.vendor.name}' before posting invoices."
            )

        self.payables_account = self.vendor.vendor_posting_group.payables_account

        # Check if payables_account is set
        if not self.payables_account:
            raise Exception(
                f"Vendor posting group '{self.vendor.vendor_posting_group.code}' does not have a payables account assigned"
            )

        self.receipt_no = receipt_no

        print("payables_account", self.payables_account)
        # Prefer invoice dimension so VAT and other document-level entries get correct branch
        # Fallback: user dimension, then first line with dimension (ensures VAT entries get dimension)
        self.global_dimension_1_value = (
            getattr(invoice, "global_dimension_1", None)
            or getattr(request.user, "global_dimension_1", None)
            or next(
                (getattr(ln, "global_dimension_1", None) for ln in self.lines if getattr(ln, "global_dimension_1", None)),
                None,
            )
        )
        self.dimension_set_value = getattr(invoice, "dimension_set", None)

        self.gl_entries = []
        self.vendor_entries = []
        self.item_entries = []
        self.vat_entries = []
        self.detailed_vendor_entries = []
        self.value_entries = []
        self.bank_account_entries = []  # For bank account ledger entries (preview only)

    @staticmethod
    def _line_type(line):
        return getattr(line, "type", "item") or "item"

    def _vat_product_posting_group_for_line(self, line):
        line_type = self._line_type(line)
        if line_type == "item" and line.item:
            return getattr(line.item, "vat_product_posting_group", None)
        if line_type == "resource" and line.resource:
            return getattr(line.resource, "vat_product_posting_group", None)
        if line_type == "gl_account" and line.gl_account:
            return getattr(line.gl_account, "vat_product_posting_group", None)
        return None

    def _append_gl_account_line_entries(self, line, transaction_no, use_net_for_cost):
        """Debit a G/L Account line directly; payables handled separately for the full invoice."""
        if self._line_type(line) != "gl_account" or not line.gl_account:
            raise Exception("G/L Account is required on G/L Account purchase lines.")
        line_amt = line.line_amount
        cost_amt = (
            line_amt - (getattr(line, "vat_amount", 0) or 0)
            if use_net_for_cost
            else line_amt
        )
        self.gl_entries.append(
            {
                "posting_date": self.invoice.posting_date,
                "document_type": "Invoice",
                "document_no": self.invoice.invoice_no,
                "gl_account": line.gl_account,
                "description": f"Invoice {self.invoice.invoice_no}",
                "department_code": (
                    self.global_dimension_1_value.code
                    if self.global_dimension_1_value
                    else None
                ),
                "amount": cost_amt,
                "gen_posting_type": "Purchase",
                "global_dimension_1": self.global_dimension_1_value,
                "gen_bus_posting_group": self.genBusinessPostingGroup,
                "gen_prod_posting_group": None,
                "balance_account_type": BalacingAccountType.GLAccount.value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

    def _append_resource_line_entries(self, line, transaction_no, use_net_for_cost):
        """Debit purchase account for a resource line via posting setup."""
        if self._line_type(line) != "resource" or not line.resource:
            raise Exception("Resource is required on Resource purchase lines.")
        from postings.models import GeneralPostingSetup

        line_amt = line.line_amount
        cost_amt = (
            line_amt - (getattr(line, "vat_amount", 0) or 0)
            if use_net_for_cost
            else line_amt
        )
        gen_prod = line.resource.general_product_posting_group
        general_posting_setup = GeneralPostingSetup.objects.filter(
            general_product_posting_group=gen_prod,
            general_business_posting_group=self.genBusinessPostingGroup,
        ).first()
        if not general_posting_setup or not general_posting_setup.purchase_account:
            resource_code = getattr(line.resource, "code", "Unknown")
            raise Exception(
                f"Purchase account is not configured for resource '{resource_code}'."
            )
        purchase_account = general_posting_setup.purchase_account
        self.gl_entries.append(
            {
                "posting_date": self.invoice.posting_date,
                "document_type": "Invoice",
                "document_no": self.invoice.invoice_no,
                "gl_account": purchase_account,
                "description": f"Invoice {self.invoice.invoice_no}",
                "department_code": (
                    self.global_dimension_1_value.code
                    if self.global_dimension_1_value
                    else None
                ),
                "amount": cost_amt,
                "gen_posting_type": "Purchase",
                "global_dimension_1": self.global_dimension_1_value,
                "gen_bus_posting_group": self.genBusinessPostingGroup,
                "gen_prod_posting_group": gen_prod,
                "balance_account_type": BalacingAccountType.GLAccount.value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

    def _append_non_item_only_payables(self, line, transaction_no, use_net_for_cost):
        """Credit payables for a non-item line when the invoice has no item lines."""
        line_amt = line.line_amount
        cost_amt = (
            line_amt - (getattr(line, "vat_amount", 0) or 0)
            if use_net_for_cost
            else line_amt
        )
        self.gl_entries.append(
            {
                "posting_date": self.invoice.posting_date,
                "document_type": "Invoice",
                "document_no": self.invoice.invoice_no,
                "gl_account": self.payables_account,
                "description": f"Invoice {self.invoice.invoice_no}",
                "department_code": (
                    self.global_dimension_1_value.code
                    if self.global_dimension_1_value
                    else None
                ),
                "amount": -cost_amt,
                "gen_posting_type": "Purchase",
                "global_dimension_1": self.global_dimension_1_value,
                "gen_bus_posting_group": self.genBusinessPostingGroup,
                "gen_prod_posting_group": None,
                "balance_account_type": BalacingAccountType.GLAccount.value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

    def _append_invoice_settlement_entries(
        self,
        total_amount,
        transaction_no,
        payables_account,
        bal_account,
        gen_prod_posting_group,
    ):
        """Vendor ledger, payables credit, VAT and cash payment GL (once per invoice)."""
        self.detailed_vendor_entries.extend(
            [
                {
                    "posting_date": self.invoice.posting_date,
                    "entry_type": "Initial Entry",
                    "document_type": "Invoice",
                    "document_no": self.invoice.invoice_no,
                    "vendor_no": self.vendor.no,
                    "vendor": self.vendor,
                    "amount": -total_amount,
                    "initial_entry_due_date": self.invoice.due_date,
                    "credit_amount": total_amount,
                    "debit_amount": 0,
                    "transaction_no": transaction_no,
                    "initial_document_type": "Invoice",
                    "vendor_ledger_entry": "10001",
                    "applied_vendor_ledger_entry": "0",
                }
            ]
        )
        if self.payment_method and self.payment_method.is_cash_payment():
            self.detailed_vendor_entries.extend(
                [
                    {
                        "posting_date": self.invoice.posting_date,
                        "entry_type": "Initial Entry",
                        "document_type": "Payment",
                        "document_no": self.invoice.invoice_no,
                        "vendor_no": self.vendor.no,
                        "vendor": self.vendor,
                        "amount": total_amount,
                        "initial_entry_due_date": self.invoice.due_date,
                        "transaction_no": transaction_no,
                        "debit_amount": total_amount,
                        "credit_amount": 0,
                        "initial_document_type": "Payment",
                        "vendor_ledger_entry": "10002",
                        "applied_vendor_ledger_entry": "0",
                    },
                    {
                        "posting_date": self.invoice.posting_date,
                        "entry_type": "Application",
                        "document_type": "Payment",
                        "document_no": self.invoice.invoice_no,
                        "vendor_no": self.vendor.no,
                        "vendor": self.vendor,
                        "amount": total_amount,
                        "initial_entry_due_date": self.invoice.due_date,
                        "debit_amount": total_amount,
                        "credit_amount": 0,
                        "initial_document_type": "Invoice",
                        "vendor_ledger_entry": "10001",
                        "applied_vendor_ledger_entry": "10002",
                        "transaction_no": transaction_no,
                    },
                    {
                        "posting_date": self.invoice.posting_date,
                        "entry_type": "Application",
                        "document_type": "Payment",
                        "document_no": self.invoice.invoice_no,
                        "vendor_no": self.vendor.no,
                        "vendor": self.vendor,
                        "initial_document_type": "Payment",
                        "debit_amount": 0,
                        "credit_amount": total_amount,
                        "vendor_ledger_entry": "10002",
                        "applied_vendor_ledger_entry": "10002",
                        "amount": -total_amount,
                        "initial_entry_due_date": self.invoice.due_date,
                        "transaction_no": transaction_no,
                    },
                ]
            )

        self.vendor_entries.append(
            {
                "posting_date": self.invoice.posting_date,
                "document_date": self.invoice.document_date,
                "document_type": DocumentType.Invoice.value,
                "document_no": self.invoice.invoice_no,
                "external_document_no": self.invoice.vendor_invoice_no,
                "vendor_no": self.vendor.no,
                "vendor": self.vendor,
                "description": f"Invoice {self.invoice.invoice_no}",
                "payment_method": self.payment_method,
                "original_amount": -total_amount,
                "amount": -total_amount,
                "remaining_amount": -total_amount,
                "open": True,
                "due_date": self.invoice.due_date,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )
        if self.payment_method and self.payment_method.is_cash_payment():
            self.vendor_entries.append(
                {
                    "posting_date": self.invoice.posting_date,
                    "document_date": self.invoice.document_date,
                    "document_type": DocumentType.Payment.value,
                    "document_no": self.invoice.invoice_no,
                    "external_document_no": self.invoice.invoice_no,
                    "vendor_no": self.vendor.no,
                    "vendor": self.vendor,
                    "description": f"Invoice {self.invoice.invoice_no}",
                    "payment_method": self.payment_method,
                    "original_amount": total_amount,
                    "amount": total_amount,
                    "remaining_amount": total_amount,
                    "open": False,
                    "due_date": self.invoice.due_date,
                    "global_dimension_1": self.global_dimension_1_value,
                    "dimension_set": self.dimension_set_value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            )

        vat_gl_entries = []
        try:
            from decimal import Decimal
            from financials.models import GeneralLedgerSetup
            from financials.vat import get_vat_posting_setup

            gl_setup = GeneralLedgerSetup.objects.first()
            total_vat = getattr(self.invoice, "total_vat_amount", None) or Decimal("0")
            if (
                gl_setup
                and getattr(gl_setup, "vat_enabled", False)
                and total_vat
                and Decimal(str(total_vat)) > 0
            ):
                vat_bus = getattr(self.vendor, "vat_business_posting_group", None)
                purchase_vat_account = None
                for line in self.lines:
                    vat_prod = self._vat_product_posting_group_for_line(line)
                    setup = get_vat_posting_setup(vat_bus, vat_prod)
                    if setup and setup.purchase_vat_account and getattr(line, "vat_amount", 0):
                        purchase_vat_account = setup.purchase_vat_account
                        break
                if purchase_vat_account:
                    vat_gl_entries.extend(
                        [
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": "Invoice",
                                "document_no": self.invoice.invoice_no,
                                "gl_account": purchase_vat_account,
                                "description": f"VAT Input {self.invoice.invoice_no}",
                                "department_code": (
                                    self.global_dimension_1_value.code
                                    if self.global_dimension_1_value
                                    else None
                                ),
                                "amount": int(Decimal(str(total_vat))),
                                "gen_posting_type": "Purchase",
                                "global_dimension_1": self.global_dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": gen_prod_posting_group,
                                "balance_account_type": BalacingAccountType.GLAccount.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": "Invoice",
                                "document_no": self.invoice.invoice_no,
                                "gl_account": payables_account,
                                "description": f"VAT Input {self.invoice.invoice_no}",
                                "department_code": (
                                    self.global_dimension_1_value.code
                                    if self.global_dimension_1_value
                                    else None
                                ),
                                "amount": -int(Decimal(str(total_vat))),
                                "gen_posting_type": "Purchase",
                                "global_dimension_1": self.global_dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": gen_prod_posting_group,
                                "balance_account_type": BalacingAccountType.GLAccount.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                        ]
                    )
                    if not self.vat_entries:
                        prices_incl = True
                        for pline in self.lines:
                            line_vat = Decimal(str(getattr(pline, "vat_amount", 0) or 0))
                            if line_vat <= 0:
                                continue
                            vat_prod = self._vat_product_posting_group_for_line(pline)
                            setup = get_vat_posting_setup(vat_bus, vat_prod)
                            if not setup or not setup.purchase_vat_account:
                                continue
                            line_total = Decimal(str(pline.total_amount or 0))
                            base = line_total - line_vat if prices_incl else line_total
                            line_dim1 = getattr(pline, "global_dimension_1", None)
                            vat_dim1 = line_dim1 or self.global_dimension_1_value
                            gen_prod = None
                            if pline.item:
                                gen_prod = pline.item.general_product_posting_group
                            elif pline.resource:
                                gen_prod = pline.resource.general_product_posting_group
                            self.vat_entries.append(
                                {
                                    "posting_date": self.invoice.posting_date,
                                    "document_type": "Invoice",
                                    "document_no": self.invoice.invoice_no,
                                    "type": "Purchase",
                                    "vat_business_posting_group": vat_bus,
                                    "vat_product_posting_group": vat_prod,
                                    "base": int(base),
                                    "amount": int(line_vat),
                                    "vat_percent": setup.vat_percent,
                                    "vat_calculation_type": setup.vat_calculation_type or "Normal",
                                    "vat_account": setup.purchase_vat_account,
                                    "gen_bus_posting_group": self.genBusinessPostingGroup,
                                    "gen_prod_posting_group": gen_prod,
                                    "global_dimension_1": vat_dim1,
                                    "transaction_no": transaction_no,
                                    "user": self.user,
                                }
                            )
        except Exception:
            pass

        self.gl_entries.extend(
            [
                {
                    "posting_date": self.invoice.posting_date,
                    "document_type": "Invoice",
                    "document_no": self.invoice.invoice_no,
                    "gl_account": payables_account,
                    "description": f"Invoice {self.invoice.invoice_no}",
                    "department_code": (
                        self.global_dimension_1_value.code
                        if self.global_dimension_1_value
                        else None
                    ),
                    "amount": -total_amount,
                    "gen_posting_type": "Purchase",
                    "global_dimension_1": self.global_dimension_1_value,
                    "gen_bus_posting_group": self.genBusinessPostingGroup,
                    "gen_prod_posting_group": gen_prod_posting_group,
                    "balance_account_type": BalacingAccountType.GLAccount.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                }
            ]
        )
        self.gl_entries.extend(vat_gl_entries)

        if self.payment_method and self.payment_method.is_cash_payment() and bal_account:
            self.gl_entries.extend(
                [
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
                        "amount": -total_amount,
                        "gen_posting_type": "Purchase",
                        "global_dimension_1": self.global_dimension_1_value,
                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                        "gen_prod_posting_group": gen_prod_posting_group,
                        "balance_account_type": BalacingAccountType.Vendor.value,
                        "user": self.user,
                        "transaction_no": transaction_no,
                    },
                    {
                        "posting_date": self.invoice.posting_date,
                        "document_type": "Payment",
                        "document_no": self.invoice.invoice_no,
                        "gl_account": payables_account,
                        "description": f"Invoice {self.invoice.invoice_no}",
                        "department_code": (
                            self.global_dimension_1_value.code
                            if self.global_dimension_1_value
                            else None
                        ),
                        "amount": total_amount,
                        "gen_posting_type": "Purchase",
                        "global_dimension_1": self.global_dimension_1_value,
                        "gen_bus_posting_group": self.genBusinessPostingGroup,
                        "gen_prod_posting_group": gen_prod_posting_group,
                        "balance_account_type": BalacingAccountType.GLAccount.value,
                        "user": self.user,
                        "transaction_no": transaction_no,
                    },
                ]
            )

    def _validate_invoice(self):
        #  check if invoice has lines
        if not self.lines.exists():
            raise Exception("Invoice has no lines")

        # check if invoice has a vendor
        if not self.vendor:
            raise Exception("Invoice has no vendor")

        # check if vendor has required posting groups
        if not self.vendor.vendor_posting_group:
            raise Exception(
                f"Vendor {self.vendor.name} does not have a vendor posting group assigned"
            )

        # Payment method validation is already done in __init__, but double-check for safety
        if not self.payment_method:
            raise Exception(
                "Please choose how this purchase was paid (Pay later, Cash, or Bank) before posting."
            )

        if not self.vendor.business_posting_group:
            raise Exception(
                f"Vendor {self.vendor.name} does not have a business posting group assigned"
            )

        if not self.vendor.vendor_posting_group.payables_account:
            raise Exception(
                f"Vendor posting group '{self.vendor.vendor_posting_group.code}' does not have a payables account assigned"
            )

        # check if vendor has payment method (optional but recommended)
        # if not self.vendor.payment_method:
        #     raise Exception(
        #         f"Vendor {self.vendor.name} does not have a payment method assigned"
        #     )

        # check if payment method has bal_account_no or bal_bank_account_no when it's a cash payment method
        # Use self.payment_method instead of self.vendor.payment_method (we prioritize invoice payment_method)
        if self.payment_method and self.payment_method.is_cash_payment():
            has_gl_account = bool(self.payment_method.bal_account_no)
            has_bank_account = (
                self.payment_method.bal_account_type
                == BalacingAccountType.Bank_Account.name
                and bool(self.payment_method.bal_bank_account_no)
            )
            if not (has_gl_account or has_bank_account):
                payment_method_code = (
                    getattr(self.payment_method, "code", "Unknown")
                    if self.payment_method
                    else "Unknown"
                )
                raise Exception(
                    f"Cash payment is not set up yet. Ask your administrator to configure "
                    f"a cash or bank account on payment method '{payment_method_code}'."
                )

        # check if item requires tracking line (item lines only)
        for line in self.lines:
            if self._line_type(line) != "item" or not line.item:
                continue
            tracking_requirements = line.item.requires_tracking_line
            # Skip validation if tracking is not required (when False is returned)
            if tracking_requirements is False:
                continue

            # Validate tracking requirements if a dict is returned
            if isinstance(tracking_requirements, dict):
                print(tracking_requirements)
                tracking_specs = line.tracking_specifications
                if not tracking_specs.exists():
                    raise Exception(
                        f"Item {line.item.item_name} requires tracking specifications"
                    )

                # Check each tracking spec against requirements
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
                    #  check if lot not exists
                    if ItemLedgerEntries.objects.filter(
                        item=line.item, lot_no=spec.lot_no
                    ).exists():
                        #  expiry date must be the same
                        item_ledger_entry = ItemLedgerEntries.objects.filter(
                            item=line.item, lot_no=spec.lot_no
                        ).first()
                        if item_ledger_entry.expiry_date != spec.expiry_date:
                            raise Exception(
                                f"Lot number {spec.lot_no} already exists for item {line.item.item_name} and expiry date must be the same of date {item_ledger_entry.expiry_date}"
                            )

                # Validate quantity balance for items with tracking specifications
                if tracking_specs.exists():
                    # Get the unit of measure
                    if not line.item_unit_of_measure:
                        raise Exception(
                            f"Unit of measure is required for item {line.item.item_name} in document {self.invoice.invoice_no}"
                        )

                    # Calculate expected quantity
                    expected_quantity = int(line.quantity) * int(
                        line.item_unit_of_measure.quantity_per_unit
                    )

                    # Calculate total quantity from specifications
                    total_quantity = (
                        tracking_specs.aggregate(total=Sum("quantity_base"))["total"]
                        or 0
                    )

                    # Check if quantities match
                    if total_quantity != expected_quantity:
                        raise Exception(
                            f"Quantity mismatch for item {line.item.item_name} in document {self.invoice.invoice_no}: "
                            f"Expected {expected_quantity} (from {line.quantity} × {line.item_unit_of_measure.quantity_per_unit}), "
                            f"but tracking specifications total {total_quantity}. "
                            f"Please ensure all items have proper tracking specifications."
                        )

        return True

    def process(self):
        # validate the invoice
        try:
            if not self._validate_invoice():
                return {
                    "success": False,
                    "message": "Invoice validation failed",
                    "entries": {},
                }

            # Generate transaction number at the beginning
            transaction_no = f"P{self.invoice.invoice_no}-{self.invoice.posting_date.strftime('%Y%m%d')}-{self.invoice.id}"

            # Determine cost amount per line (BC-style): net when VAT enabled and prices incl VAT
            use_net_for_cost = False
            try:
                from financials.models import GeneralLedgerSetup
                gl_setup = GeneralLedgerSetup.objects.first()
                if gl_setup and getattr(gl_setup, "vat_enabled", False) and getattr(self.invoice, "prices_including_vat", False):
                    use_net_for_cost = True
            except Exception:
                pass

            items_lines = []
            for line in self.lines:
                if self._line_type(line) != "item" or not line.item:
                    continue
                genProductPostingGroup = line.item.general_product_posting_group
                quantity_per_iuom = line.item_unit_of_measure.quantity_per_unit
                line_amt = line.line_amount
                cost_amt = (line_amt - (getattr(line, "vat_amount", 0) or 0)) if use_net_for_cost else line_amt
                items_lines.append(
                    {
                        "item": line.item,
                        "genProductPostingGroup": genProductPostingGroup,
                        "genBusinessPostingGroup": self.genBusinessPostingGroup,
                        "amount": cost_amt,  # Cost/inventory posting: net when prices incl VAT
                        "quantity": line.quantity,
                        "location": line.location_code,
                        "item_unit_of_measure": line.item_unit_of_measure,
                        "purchase_invoice_line": line.id,
                        "quantity_per_iuom": quantity_per_iuom,
                    }
                )

            has_item_lines = len(items_lines) > 0
            has_any_lines = self.lines.exists()

            if has_any_lines:
                # Payables = gross (sum of line_amounts); inventory uses net via items_lines["amount"]
                total_amount = sum(l.line_amount for l in self.lines)
                gl_line_total = sum(
                    l.line_amount
                    for l in self.lines
                    if self._line_type(l) == "gl_account"
                )
                purchase_account_total = total_amount - gl_line_total
                print(
                    f"Processing {len(items_lines)} item lines with total amount: {total_amount}"
                )

                # Determine cash payment balancing account (applies to all items)
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
                            # Validate bank account exists before processing
                            if not self.payment_method.bal_bank_account_no:
                                raise Exception(
                                    f"Payment method '{self.payment_method.code}' is configured to use a bank account, "
                                    f"but no bank account is assigned. Please configure the bank account in the payment method settings."
                                )

                            bank_account = self.payment_method.bal_bank_account_no

                            # Get G/L account from bank account posting group (for preview)
                            bal_account = get_bank_account_gl_account(bank_account)

                            # Store bank account entry info for actual posting (not created here, just preview info)
                            self.bank_account_entries.append(
                                {
                                    "bank_account": bank_account,
                                    "posting_date": self.invoice.posting_date,
                                    "document_type": BankAccountDocumentType.Payment.name,
                                    "document_no": self.invoice.invoice_no,
                                    "description": f"Invoice {self.invoice.invoice_no}",
                                    "amount": -total_amount,  # Negative for purchase invoice (money out)
                                    "bal_account_type": BalacingAccountType.Vendor.name,
                                    "bal_account_no": self.vendor.no,
                                    "global_dimension_1": self.global_dimension_1_value,
                                    "dimension_set": self.dimension_set_value,
                                    "transaction_no": transaction_no,
                                    "document_date": self.invoice.posting_date,
                                }
                            )
                        except ValidationError as ve:
                            # Re-raise ValidationError with better context
                            payment_method_name = getattr(
                                self.payment_method, "code", "Unknown"
                            )
                            bank_account_name = (
                                getattr(
                                    self.payment_method.bal_bank_account_no,
                                    "no",
                                    "Unknown",
                                )
                                if self.payment_method.bal_bank_account_no
                                else "Not Set"
                            )
                            raise Exception(
                                f"Payment method '{payment_method_name}' (Bank Account: '{bank_account_name}') configuration error: {str(ve)}"
                            )
                        except Exception as e:
                            payment_method_name = (
                                getattr(self.payment_method, "code", "Unknown")
                                if self.payment_method
                                else "Unknown"
                            )
                            bank_account_name = (
                                getattr(
                                    self.payment_method.bal_bank_account_no,
                                    "no",
                                    "Unknown",
                                )
                                if (
                                    self.payment_method
                                    and self.payment_method.bal_bank_account_no
                                )
                                else "Not Set"
                            )
                            raise Exception(
                                f"Failed to process bank account for payment method '{payment_method_name}' (Bank Account: '{bank_account_name}'): {str(e)}"
                            )
                    elif self.payment_method.bal_account_no:
                        # Use existing G/L Account logic
                        bal_account = self.payment_method.bal_account_no

                for item_idx, item_line in enumerate(items_lines):
                    is_last_item_line = item_idx == len(items_lines) - 1
                    general_posting_setup = GeneralPostingSetup.objects.filter(
                        general_product_posting_group=item_line[
                            "genProductPostingGroup"
                        ],
                        general_business_posting_group=self.genBusinessPostingGroup,
                    ).first()

                    if not general_posting_setup:
                        business_group_code = (
                            getattr(self.genBusinessPostingGroup, "code", "Not Set")
                            if self.genBusinessPostingGroup
                            else "Not Set"
                        )
                        product_group_code = (
                            getattr(
                                item_line.get("genProductPostingGroup"),
                                "code",
                                "Not Set",
                            )
                            if item_line.get("genProductPostingGroup")
                            else "Not Set"
                        )
                        raise Exception(
                            f"General posting setup not found for Business Posting Group '{business_group_code}' and Product Posting Group '{product_group_code}'. "
                            f"Please create a General Posting Setup for this combination."
                        )

                    inventory_posting_setup = InventoryPostingSetup.objects.filter(
                        location=item_line["location"],
                        inventory_posting_group=item_line[
                            "item"
                        ].inventory_posting_group,
                    ).first()

                    if not inventory_posting_setup:
                        location_code = (
                            getattr(item_line.get("location"), "code", "Not Set")
                            if item_line.get("location")
                            else "Not Set"
                        )
                        inventory_group = (
                            getattr(
                                item_line.get("item"), "inventory_posting_group", None
                            )
                            if item_line.get("item")
                            else None
                        )
                        inventory_group_code = (
                            getattr(inventory_group, "code", "Not Set")
                            if inventory_group
                            else "Not Set"
                        )
                        item_name = (
                            getattr(item_line.get("item"), "item_name", "Unknown")
                            if item_line.get("item")
                            else "Unknown"
                        )
                        raise Exception(
                            f"Inventory posting setup not found for Location '{location_code}' and Inventory Posting Group '{inventory_group_code}' (Item: '{item_name}'). "
                            f"Please create an Inventory Posting Setup for this combination."
                        )

                    # Get the actual account objects instead of just the numbers
                    inventory_account = inventory_posting_setup.inventory_account
                    direct_cost_applied_account = (
                        general_posting_setup.direct_cost_applied_account
                    )
                    purchase_account = general_posting_setup.purchase_account
                    payables_account = self.payables_account
                    print("adfadsf", direct_cost_applied_account)
                    # Validate that all required accounts are set
                    if not inventory_account:
                        location_code = (
                            getattr(item_line.get("location"), "code", "Not Set")
                            if item_line.get("location")
                            else "Not Set"
                        )
                        inventory_group = (
                            getattr(
                                item_line.get("item"), "inventory_posting_group", None
                            )
                            if item_line.get("item")
                            else None
                        )
                        inventory_group_code = (
                            getattr(inventory_group, "code", "Not Set")
                            if inventory_group
                            else "Not Set"
                        )
                        raise Exception(
                            f"Inventory account is not set for Location '{location_code}' and Inventory Posting Group '{inventory_group_code}'. "
                            f"Please configure the inventory account in the Inventory Posting Setup."
                        )

                    if not direct_cost_applied_account:
                        business_group_code = (
                            getattr(self.genBusinessPostingGroup, "code", "Not Set")
                            if self.genBusinessPostingGroup
                            else "Not Set"
                        )
                        product_group_code = (
                            getattr(
                                item_line.get("genProductPostingGroup"),
                                "code",
                                "Not Set",
                            )
                            if item_line.get("genProductPostingGroup")
                            else "Not Set"
                        )
                        raise Exception(
                            f"Direct cost applied account is not set for General Posting Setup with Business Posting Group '{business_group_code}' and Product Posting Group '{product_group_code}'. "
                            f"Please configure the direct cost applied account in the General Posting Setup."
                        )

                    if not purchase_account:
                        business_group_code = (
                            getattr(self.genBusinessPostingGroup, "code", "Not Set")
                            if self.genBusinessPostingGroup
                            else "Not Set"
                        )
                        product_group_code = (
                            getattr(
                                item_line.get("genProductPostingGroup"),
                                "code",
                                "Not Set",
                            )
                            if item_line.get("genProductPostingGroup")
                            else "Not Set"
                        )
                        raise Exception(
                            f"Purchase account is not set for General Posting Setup with Business Posting Group '{business_group_code}' and Product Posting Group '{product_group_code}'. "
                            f"Please configure the purchase account in the General Posting Setup."
                        )

                    if not payables_account:
                        raise Exception(
                            f"Payables account is not set for vendor posting group '{self.vendor.vendor_posting_group.code}'"
                        )

                    # Generate GL entries
                    self.gl_entries.extend(
                        [
                            # debit inventory account
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": DocumentType.default.value,
                                "document_no": self.invoice.invoice_no,
                                "gl_account": inventory_account,
                                "description": f"Direct Cost {self.vendor.no} on {self.invoice.posting_date}",
                                "department_code": (
                                    self.global_dimension_1_value.code
                                    if self.global_dimension_1_value
                                    else None
                                ),
                                "amount": item_line["amount"],
                                "gen_posting_type": "Purchase",
                                "global_dimension_1": self.global_dimension_1_value,
                                "gen_bus_posting_group": self.genBusinessPostingGroup,
                                "gen_prod_posting_group": item_line[
                                    "genProductPostingGroup"
                                ],
                                "balance_account_type": BalacingAccountType.GLAccount.value,
                                "user": self.user,
                                "transaction_no": transaction_no,
                            },
                            # credit direct cost applied account
                            {
                                "posting_date": self.invoice.posting_date,
                                "document_type": DocumentType.default.value,
                                "document_no": self.invoice.invoice_no,
                                "gl_account": direct_cost_applied_account,
                                "description": f"Direct Cost {self.vendor.no} on {self.invoice.posting_date}",
                                "department_code": (
                                    self.global_dimension_1_value.code
                                    if self.global_dimension_1_value
                                    else None
                                ),
                                "amount": -item_line["amount"],
                                "gen_posting_type": "Purchase",
                                "global_dimension_1": self.global_dimension_1_value,
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

                    #  Vendor Ledger Entries

                    # Generate Item Ledger Entry
                    tracking_specs = TrackingSpecification.objects.filter(
                        item=item_line["item"],
                        purchase_invoice=self.invoice,
                        purchase_invoice_line=item_line["purchase_invoice_line"],
                    )
                    if tracking_specs.exists():
                        total_quantity = sum(
                            spec.quantity_base for spec in tracking_specs
                        )
                        print(total_quantity)
                        for spec in tracking_specs:
                            # quantity = spec.quantity_base
                            unit_cost = (
                                item_line["amount"] / total_quantity
                            )  # Calculate per unit cost

                            total = spec.quantity_base * unit_cost  # Calculate total

                            item_entry = {
                                "posting_date": self.invoice.posting_date,
                                "entry_type": "Purchase",
                                "item": item_line["item"],
                                "document_no": self.invoice.invoice_no,
                                "description": f"Invoice {self.invoice.invoice_no}",
                                "unit_of_measure": item_line["item_unit_of_measure"],
                                "unit_cost": unit_cost,
                                "date": self.invoice.posting_date,
                                "user": self.user,
                                "receipt_no": self.receipt_no,
                                "lot_no": spec.lot_no,
                                "expiry_date": spec.expiry_date,
                                "location": item_line["location"],
                                "quantity": spec.quantity_base,
                                "remaining_quantity": spec.quantity_base,
                                "cost_amount": unit_cost * spec.quantity_base,
                                "total": total,
                                "serial_no": spec.serial_no,
                                "global_dimension_1": self.global_dimension_1_value,
                                "global_dimension_2": getattr(self.invoice, "global_dimension_2", None),
                                "dimension_set": self.dimension_set_value,
                                "document_type": DocumentType.PurchaseReceipt.value,
                                "transaction_no": transaction_no,
                            }

                            print(
                                f"Generated item entry with lot_no: {item_entry['lot_no']}, expiry_date: {item_entry['expiry_date']}"
                            )

                            self.item_entries.extend([item_entry])
                            self.value_entries.extend(
                                [
                                    {
                                        "posting_date": self.invoice.posting_date,
                                        "document_type": DocumentType.Purchase.value,
                                        "entry_type": EntryType.Purchase.value,
                                        "document_no": self.invoice.invoice_no,
                                        "item_ledger_entry_quantity": spec.quantity_base,
                                        "invoiced_quantity": spec.quantity_base,
                                        "valued_quantity": spec.quantity_base,
                                        "cost_amount": total,
                                        "sales_amount": 0,
                                        "purchase_amount": 0,
                                        "cost_per_unit": unit_cost,
                                        "item": item_line["item"],
                                        "general_product_posting_group": item_line[
                                            "genProductPostingGroup"
                                        ],
                                        "inventory_posting_group": item_line[
                                            "item"
                                        ].inventory_posting_group,
                                        "global_dimension_1": self.global_dimension_1_value,
                                        "global_dimension_2": getattr(self.invoice, "global_dimension_2", None),
                                        "dimension_set": self.dimension_set_value,
                                        "transaction_no": transaction_no,
                                    }
                                ]
                            )

                    else:
                        quantity = (
                            item_line["quantity"] * item_line["quantity_per_iuom"]
                        )
                        unit_cost = (
                            item_line["amount"] / quantity
                        )  # Calculate per unit cost
                        total = quantity * unit_cost  # Calculate total

                        self.item_entries.extend(
                            [
                                {
                                    "posting_date": self.invoice.posting_date,
                                    "entry_type": "Purchase",
                                    "item": item_line["item"],
                                    "document_no": self.invoice.invoice_no,
                                    "description": f"Invoice {self.invoice.invoice_no}",
                                    "unit_of_measure": item_line[
                                        "item_unit_of_measure"
                                    ],
                                    "unit_cost": unit_cost,
                                    "date": self.invoice.posting_date,
                                    "user": self.user,
                                    "receipt_no": self.receipt_no,
                                    "lot_no": None,
                                    "expiry_date": None,
                                    "serial_no": None,
                                    "location": item_line["location"],
                                    "quantity": quantity,
                                    "remaining_quantity": quantity,
                                    "cost_amount": item_line["amount"],
                                    "sales_amount": 0,
                                    "purchase_amount": 0,
                                    "total": total,
                                    "global_dimension_1": self.global_dimension_1_value,
                                    "global_dimension_2": getattr(self.invoice, "global_dimension_2", None),
                                    "dimension_set": self.dimension_set_value,
                                    "transaction_no": transaction_no,
                                }
                            ]
                        )

                        self.value_entries.extend(
                            [
                                {
                                    "posting_date": self.invoice.posting_date,
                                    "entry_type": "Purchase",
                                    "document_no": self.invoice.invoice_no,
                                    "cost_amount": item_line["amount"],
                                    "cost_per_unit": unit_cost,
                                    "item_ledger_entry_quantity": quantity,
                                    "invoiced_quantity": quantity,
                                    "valued_quantity": quantity,
                                    "item": item_line["item"],
                                    "general_product_posting_group": item_line[
                                        "genProductPostingGroup"
                                    ],
                                    "inventory_posting_group": item_line[
                                        "item"
                                    ].inventory_posting_group,
                                    "global_dimension_1": self.global_dimension_1_value,
                                    "global_dimension_2": getattr(self.invoice, "global_dimension_2", None),
                                    "dimension_set": self.dimension_set_value,
                                    "transaction_no": transaction_no,
                                    "sales_amount": 0,
                                    "purchase_amount": 0,
                                    "transaction_no": transaction_no,
                                }
                            ]
                        )
                        # self.detailed_vendor_entries.extend(
                        #     [
                        #         {
                        #             "posting_date": self.invoice.posting_date,
                        #             "entry_type": "Initial Entry",
                        #             "document_type": "Invoice",  # Match with vendor entry
                        #             "document_no": self.invoice.invoice_no,
                        #             "vendor_no": self.vendor.no,
                        #             "amount": -item_line["amount"],
                        #             "initial_entry_due_date": self.invoice.due_date,
                        #             "credit_amount": item_line["amount"],
                        #             "debit_amount": 0,
                        #             "transaction_no": f"P{self.invoice.invoice_no}-{self.invoice.posting_date.strftime('%Y%m%d')}-{self.invoice.id}",
                        #             "initial_document_type": "Invoice",
                        #             "vendor_ledger_entry": "10001",
                        #             "applied_vendor_ledger_entry": "0",
                        #             "transaction_no": transaction_no,
                        #         }
                        #     ]
                        # )

                    # Debit purchase account for this item line (payables/vendor settled once on last line)
                    self.gl_entries.append(
                        {
                            "posting_date": self.invoice.posting_date,
                            "document_type": "Invoice",
                            "document_no": self.invoice.invoice_no,
                            "gl_account": purchase_account,
                            "description": f"Invoice {self.invoice.invoice_no}",
                            "department_code": (
                                self.global_dimension_1_value.code
                                if self.global_dimension_1_value
                                else None
                            ),
                            "amount": item_line["amount"],
                            "gen_posting_type": "Purchase",
                            "global_dimension_1": self.global_dimension_1_value,
                            "gen_bus_posting_group": self.genBusinessPostingGroup,
                            "gen_prod_posting_group": item_line["genProductPostingGroup"],
                            "balance_account_type": BalacingAccountType.GLAccount.value,
                            "user": self.user,
                            "transaction_no": transaction_no,
                        }
                    )

                    if is_last_item_line:
                        self._append_invoice_settlement_entries(
                            total_amount,
                            transaction_no,
                            payables_account,
                            bal_account,
                            item_line["genProductPostingGroup"],
                        )

                if has_item_lines:
                    for line in self.lines:
                        line_type = self._line_type(line)
                        if line_type == "gl_account":
                            self._append_gl_account_line_entries(
                                line, transaction_no, use_net_for_cost
                            )
                        elif line_type == "resource":
                            self._append_resource_line_entries(
                                line, transaction_no, use_net_for_cost
                            )

                if not has_item_lines:
                    payables_account = self.payables_account
                    if not payables_account:
                        raise Exception(
                            f"Payables account is not set for vendor posting group "
                            f"'{self.vendor.vendor_posting_group.code}'"
                        )
                    for line in self.lines:
                        line_type = self._line_type(line)
                        if line_type == "gl_account":
                            self._append_gl_account_line_entries(
                                line, transaction_no, use_net_for_cost
                            )
                        elif line_type == "resource":
                            self._append_resource_line_entries(
                                line, transaction_no, use_net_for_cost
                            )
                    gen_prod = None
                    first_line = self.lines.first()
                    if first_line:
                        gen_prod = self._vat_product_posting_group_for_line(first_line)
                    self._append_invoice_settlement_entries(
                        total_amount,
                        transaction_no,
                        payables_account,
                        bal_account,
                        gen_prod,
                    )

            # Debug: Print what entries were generated
            print(
                f"Generated entries - GL: {len(self.gl_entries)}, Vendor: {len(self.vendor_entries)}, Item: {len(self.item_entries)}, Value: {len(self.value_entries)}"
            )

            return {
                "gl_entries": self.gl_entries,
                "vendor_entries": self.vendor_entries,
                "item_entries": self.item_entries,
                "vat_entries": self.vat_entries,
                "detailed_vendor_entries": self.detailed_vendor_entries,
                "value_entries": self.value_entries,
                "bank_account_entries": self.bank_account_entries,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing invoice: {e}",
                "entries": {},
            }


class PurchaseInvoicePostingProcessor:
    def __init__(self, invoice, request, receipt_no):
        self.invoice = invoice
        self.request = request
        self.user = request.user
        self.lines = invoice.lines.all()
        self.vendor = invoice.vendor

        # Check if vendor has business posting group
        if not invoice.vendor.business_posting_group:
            raise Exception(
                f"Vendor '{self.vendor.name}' does not have a Business Posting Group assigned. "
                f"Please assign a Business Posting Group to vendor '{self.vendor.name}' before posting invoices."
            )
        self.genBusinessPostingGroup = invoice.vendor.business_posting_group

        # IMPORTANT: Use invoice payment_method ONLY - each invoice should have its own payment method
        # This ensures invoices are independent and avoid race conditions with multiple windows
        # Invoice payment_method should be set during invoice creation or before posting
        if not invoice.payment_method:
            raise Exception(
                f"Invoice {invoice.invoice_no or invoice.id} does not have a payment method set. "
                f"Payment method must be specified when creating the invoice or before posting."
            )
        self.payment_method = invoice.payment_method

        # Check if vendor_posting_group exists before accessing payables_account
        if not self.vendor.vendor_posting_group:
            raise Exception(
                f"Vendor {self.vendor.name} does not have a vendor posting group assigned"
            )

        self.payables_account = self.vendor.vendor_posting_group.payables_account

        # Check if payables_account is set
        if not self.payables_account:
            raise Exception(
                f"Vendor posting group '{self.vendor.vendor_posting_group.code}' does not have a payables account assigned"
            )

        self.receipt_no = receipt_no

    def post(self):
        from django.db import transaction
        import traceback
        import logging

        try:
            # Process and create entries similar to preview but actually save them
            processor = PurchaseInvoiceProcessor(
                self.invoice, self.request, self.receipt_no
            )
            entries = processor.process()

            # Debug: Print what was returned from process
            print(f"Process returned: {type(entries)}")
            if isinstance(entries, dict):
                if "success" in entries:
                    print(
                        f"Success: {entries['success']}, Message: {entries.get('message', 'No message')}"
                    )

            # Check if process returned an error response
            if isinstance(entries, dict) and entries.get("success") is False:
                return {
                    "success": False,
                    "message": entries.get(
                        "message", "Unknown error during processing"
                    ),
                    "error_type": "ProcessingError",
                    "error_details": entries.get(
                        "message", "Unknown error during processing"
                    ),
                }

            # Validate that entries contains the expected keys
            required_keys = [
                "gl_entries",
                "vendor_entries",
                "item_entries",
                "value_entries",
                "detailed_vendor_entries",
            ]
            missing_keys = [key for key in required_keys if key not in entries]
            if missing_keys:
                return {
                    "success": False,
                    "message": f"Missing required entry types: {', '.join(missing_keys)}",
                    "error_type": "MissingEntries",
                    "error_details": f"Process method did not return expected entry types: {missing_keys}",
                }

            # Use transaction to ensure all entries are created or none are
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

                for gl_entry in entries["gl_entries"]:
                    # print(gl_entry["document_type"])
                    # print(gl_entry["balance_account_type"])
                    print(
                        (
                            BalacingAccountType.GLAccount.value
                            if gl_entry["balance_account_type"] == "G/L Account"
                            else BalacingAccountType.Vendor.value
                        ),
                    )
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
                        general_business_posting_group=gl_entry[
                            "gen_bus_posting_group"
                        ],
                        general_product_posting_group=gl_entry[
                            "gen_prod_posting_group"
                        ],
                        balancing_account_type=(
                            BalacingAccountType.GLAccount.name
                            if gl_entry["balance_account_type"] == "G/L Account"
                            else BalacingAccountType.Vendor.value
                        ),
                        user=gl_entry["user"],
                        transaction_no=gl_entry["transaction_no"],
                    )
                    general_ledger.save()
                    # print("oooo",general_ledger.balancing_account_type)
                # e
                # Create VAT Entries (BC-style subledger)
                from financials.models import VatEntry

                for vat_entry in entries.get("vat_entries", []):
                    VatEntry.objects.create(
                        posting_date=vat_entry["posting_date"],
                        document_type=vat_entry["document_type"],
                        document_no=vat_entry["document_no"],
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
                        transaction_no=vat_entry["transaction_no"],
                        user=vat_entry["user"],
                    )

                # Create Vendor Ledger Entries
                count = 0
                for vendor_entry in entries["vendor_entries"]:
                    from common.enums import DocumentType

                    # count += 1
                    VendorLedger.objects.create(
                        posting_date=vendor_entry["posting_date"],
                        document_date=vendor_entry["document_date"],
                        document_type=(
                            DocumentType.Invoice.value
                            if vendor_entry["document_type"] == "Invoice"
                            else DocumentType.Payment.value
                        ),
                        document_no=vendor_entry["document_no"],
                        external_document_no=vendor_entry["external_document_no"],
                        vendor=vendor_entry["vendor"],
                        description=vendor_entry["description"],
                        payment_method=vendor_entry["payment_method"],
                        original_amount=vendor_entry["original_amount"],
                        amount=vendor_entry["amount"],
                        # remaining_amount=vendor_entry["remaining_amount"],
                        open=(
                            False
                            if len(entries["vendor_entries"]) == 2
                            else vendor_entry["open"]
                        ),
                        due_date=vendor_entry["due_date"],
                        global_dimension_1=vendor_entry["global_dimension_1"],
                        dimension_set=vendor_entry.get("dimension_set"),
                        transaction_no=vendor_entry["transaction_no"],
                    )

                # Create Item Ledger Entries and Value Entries together
                for item_entry, value_entry in zip(
                    entries["item_entries"], entries["value_entries"]
                ):
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
                        # lot_no=item_entry["lot_no"],
                        # expiry_date=item_entry["expiry_date"],
                        # serial_no=item_entry["serial_no"],
                        global_dimension_1=item_entry["global_dimension_1"],
                        global_dimension_2=item_entry.get("global_dimension_2"),
                        dimension_set=item_entry.get("dimension_set"),
                        user=item_entry["user"],
                        receipt_no=item_entry["receipt_no"],
                        date=item_entry["date"],
                        document_type=DocumentType.PurchaseReceipt.value,
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
                        document_type=DocumentType.Purchase.value,
                        entry_type=EntryType.Purchase.value,
                        sales_amount=value_entry["sales_amount"],
                        item_ledger_entry_no=item_ledger,  # Add reference to the Item Ledger Entry
                        transaction_no=value_entry["transaction_no"],
                        global_dimension_1=value_entry.get("global_dimension_1"),
                        global_dimension_2=value_entry.get("global_dimension_2"),
                        dimension_set=value_entry.get("dimension_set"),
                    )

                # Create Detailed Vendor Ledger Entrie
                count = 0
                for detailed_entry in entries["detailed_vendor_entries"]:
                    count += 1
                    # Find the corresponding VendorLedger entry by matching posting_date, document_no AND document_type
                    if count == 1 or count == 2:
                        vendor_ledger = VendorLedger.objects.get(
                            posting_date=detailed_entry["posting_date"],
                            document_no=detailed_entry["document_no"],
                            document_type=detailed_entry["document_type"],
                        )
                    else:
                        if detailed_entry["entry_type"] == "Application":
                            if count == 3:
                                vendor_ledger = VendorLedger.objects.get(
                                    posting_date=detailed_entry["posting_date"],
                                    document_no=detailed_entry["document_no"],
                                    document_type=CommonDocumentType.Invoice.value,
                                )
                            elif count == 4:
                                vendor_ledger = VendorLedger.objects.get(
                                    posting_date=detailed_entry["posting_date"],
                                    document_no=detailed_entry["document_no"],
                                    document_type=CommonDocumentType.Payment.value,
                                )
                        else:
                            vendor_ledger = VendorLedger.objects.get(
                                posting_date=detailed_entry["posting_date"],
                                document_no=detailed_entry["document_no"],
                                document_type=detailed_entry["document_type"],
                            )

                    DetailedVendorLedgerEntry.objects.create(
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
                        vendor=self.invoice.vendor,
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
                        vendor_ledger_entry=vendor_ledger,
                        applied_vendor_ledger_entry_no=0,
                        unapplied_by_entry_no=0,
                        unapplied=False,
                        global_dimension_1=(
                            self.invoice.global_dimension_1
                            if hasattr(self.invoice, "global_dimension_1")
                            else None
                        ),
                        dimension_set=(
                            self.invoice.dimension_set
                            if hasattr(self.invoice, "dimension_set")
                            else None
                        ),
                        transaction_no=detailed_entry["transaction_no"],
                    )

                # Update invoice status
                # Payment method should already be set on invoice from creation or before posting
                # We don't modify it here - it was set during invoice creation or via API before posting
                self.invoice.status = "Posted"

                # Ensure invoice payment_method is set (should already be set)
                if not self.invoice.payment_method:
                    self.invoice.payment_method = self.payment_method

                # Set created_by if not already set (for existing invoices that were created before this field existed)
                # This captures the user who posted the invoice, which is likely the creator or responsible person
                if not self.invoice.created_by and self.user:
                    self.invoice.created_by = self.user

                # Update vendor's payment method as a preference for future invoices only
                # This is optional - vendor preference is just a convenience default
                # The actual invoice uses its own payment_method (set above)
                if self.vendor.payment_method != self.payment_method:
                    self.vendor.payment_method = self.payment_method
                    self.vendor.save(update_fields=["payment_method", "updated_at"])

                self.invoice.save()
                # Create Posted Purchase Invoice (copy dimensions from source)
                posted_purchase_invoice = PostedPurchaseInvoice.objects.create(
                    vendor=self.invoice.vendor,
                    document_date=self.invoice.document_date,
                    posting_date=self.invoice.posting_date,
                    due_date=self.invoice.due_date,
                    vat_date=self.invoice.vat_date,
                    vendor_invoice_no=self.invoice.vendor_invoice_no,
                    global_dimension_1=self.invoice.global_dimension_1,
                    global_dimension_2=self.invoice.global_dimension_2,
                    dimension_set=self.invoice.dimension_set,
                )
                posted_purchase_invoice.save()
                # Create Posted Purchase Invoice Lines (copy dimensions from source lines)
                # PurchaseInvoiceLine has global_dimension_1 and dimension_set but not global_dimension_2;
                # derive global_dimension_2 from dimension_set when available
                from financials.models import GeneralLedgerSetup
                gl_setup = GeneralLedgerSetup.objects.first()
                for line in self.invoice.lines.all():
                    line_gd2 = None
                    if gl_setup and gl_setup.global_dimension_2_id and line.dimension_set:
                        line_gd2 = get_dimension_value_from_set(
                            line.dimension_set, gl_setup.global_dimension_2
                        )
                    if line_gd2 is None:
                        line_gd2 = self.invoice.global_dimension_2
                    PostedPurchaseInvoiceLine.objects.create(
                        posted_purchase_invoice=posted_purchase_invoice,
                        type=line.type,
                        item=line.item,
                        resource=line.resource,
                        gl_account=line.gl_account,
                        description=line.description,
                        location_code=line.location_code,
                        quantity=line.quantity,
                        unit_of_measure=line.unit_of_measure,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_cost=line.unit_cost,
                        amount=line.total_amount,
                        global_dimension_1=line.global_dimension_1
                        or self.invoice.global_dimension_1,
                        global_dimension_2=line_gd2,
                        dimension_set=line.dimension_set,
                    )
                # posted_purchase_invoice.save()
                # e

            return {
                "success": True,
                "message": f"Successfully posted invoice {self.invoice.invoice_no}",
                "entries": entries,
            }

        except Exception as e:
            # Log the full error for debugging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in PurchaseInvoicePostingProcessor.post(): {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

            return {
                "success": False,
                "message": f"Error posting invoice: {str(e)}",
                "error_type": type(e).__name__,
                "error_details": str(e),
                "traceback": traceback.format_exc() if settings.DEBUG else None,
            }


class PurchaseCreditMemoPostingProcessor:
    def __init__(self, credit_memo, request, receipt_no):
        self.credit_memo = credit_memo
        self.request = request
        self.user = request.user
        self.receipt_no = receipt_no

        # Get the vendor_invoice_no from the posted invoice
        vendor_invoice_no = credit_memo.original_posted_invoice.vendor_invoice_no

        # Find the original PurchaseInvoice using vendor_invoice_no and status "Posted"
        try:
            self.original_purchase_invoice = PurchaseInvoice.objects.get(
                vendor_invoice_no=vendor_invoice_no, status="Posted"
            )
            # Use the invoice_no from the original PurchaseInvoice to query entries
            self.original_doc_no = self.original_purchase_invoice.invoice_no
        except PurchaseInvoice.DoesNotExist:
            raise Exception(
                f"Could not find original Posted Purchase Invoice with vendor_invoice_no: {vendor_invoice_no}"
            )
        except PurchaseInvoice.MultipleObjectsReturned:
            raise Exception(
                f"Multiple Posted Purchase Invoices found with vendor_invoice_no: {vendor_invoice_no}. This should not happen."
            )

    def post(self):
        from django.db import transaction
        import traceback
        import logging
        from decimal import Decimal
        from common.enums import (
            DocumentType as CommonDocumentType,
            EntryType as CommonEntryType,
        )

        try:
            # Find all original entries
            original_gl_entries = GeneralLedgerEntry.objects.filter(
                document_no=self.original_doc_no
            ).order_by("id")

            original_vendor_entries = VendorLedger.objects.filter(
                document_no=self.original_doc_no
            ).order_by("id")

            original_item_entries = ItemLedgerEntries.objects.filter(
                document_no=self.original_doc_no
            ).order_by("id")

            original_value_entries = ValueEntry.objects.filter(
                document_no=self.original_doc_no
            ).order_by("id")

            original_detailed_entries = DetailedVendorLedgerEntry.objects.filter(
                document_no=self.original_doc_no
            ).order_by("entry_no")

            # Get the next vendor ledger entry number that will be created
            try:
                next_vendor_entry_id = (
                    VendorLedger.objects.aggregate(max_id=Max("id"))["max_id"] or 0
                )
                next_vendor_entry_id += 1
            except Exception:
                next_vendor_entry_id = 0

            with transaction.atomic():
                # Create reversal GL entries
                for gl_entry in original_gl_entries:
                    amount = float(gl_entry.amount) if gl_entry.amount else 0

                    if gl_entry.document_type == CommonDocumentType.Payment.value:
                        reversal_doc_type = CommonDocumentType.Refund.value
                    else:
                        reversal_doc_type = "Credit Memo"

                    GeneralLedgerEntry.objects.create(
                        posting_date=self.credit_memo.posting_date,
                        document_type=reversal_doc_type,
                        document_no=self.credit_memo.no,
                        gl_account=gl_entry.gl_account,
                        description=f"Reversal of {gl_entry.document_type} {gl_entry.document_no}",
                        amount=-amount,
                        user=self.user,
                        receipt_no=self.receipt_no,
                        general_posting_type=gl_entry.general_posting_type,
                        dimension_set=gl_entry.dimension_set,
                        global_dimension_1=gl_entry.global_dimension_1,
                        global_dimension_2=gl_entry.global_dimension_2,
                        general_business_posting_group=gl_entry.general_business_posting_group,
                        general_product_posting_group=gl_entry.general_product_posting_group,
                        balancing_account_type=gl_entry.balancing_account_type,
                        transaction_no=f"REV-{self.credit_memo.no}",
                    )

                # Create reversal vendor ledger entries
                reversal_vendor_ledgers = {}
                for vendor_entry in original_vendor_entries:
                    original_amount = (
                        float(vendor_entry.original_amount)
                        if vendor_entry.original_amount
                        else 0
                    )
                    amount = float(vendor_entry.amount) if vendor_entry.amount else 0

                    if vendor_entry.document_type == CommonDocumentType.Payment.value:
                        reversal_doc_type = CommonDocumentType.Refund.value
                    else:
                        reversal_doc_type = "Credit Memo"

                    reversal_vendor_ledger = VendorLedger.objects.create(
                        posting_date=self.credit_memo.posting_date,
                        document_date=self.credit_memo.document_date,
                        document_type=reversal_doc_type,
                        document_no=self.credit_memo.no,
                        external_document_no=self.credit_memo.vendor_cr_memo_no or "",
                        vendor=vendor_entry.vendor,
                        description=f"Reversal of {vendor_entry.document_type} {vendor_entry.document_no}",
                        payment_method=vendor_entry.payment_method,
                        original_amount=-original_amount,
                        amount=-amount,
                        open=True,
                        due_date=self.credit_memo.due_date,
                        global_dimension_1=vendor_entry.global_dimension_1,
                        dimension_set=getattr(vendor_entry, "dimension_set", None),
                        transaction_no=f"REV-{self.credit_memo.no}",
                    )
                    reversal_vendor_ledgers[vendor_entry.vendor.id] = (
                        reversal_vendor_ledger
                    )

                # Create reversal item ledger entries and store them for linking
                created_item_ledgers = []
                for item_entry in original_item_entries:
                    quantity = float(item_entry.quantity) if item_entry.quantity else 0
                    total = float(item_entry.total) if item_entry.total else 0
                    unit_cost = total / quantity if quantity else 0

                    item_ledger = ItemLedgerEntries.objects.create(
                        posting_date=self.credit_memo.posting_date,
                        entry_type="Purchase Return",
                        item=item_entry.item,
                        document_no=self.credit_memo.no,
                        description=f"Reversal of {item_entry.description}",
                        unit_of_measure_code=item_entry.unit_of_measure_code,
                        location=item_entry.location,
                        quantity=-quantity,
                        remaining_quantity=0,  # For returns, nothing remains to return
                        total=-total,
                        user=self.user,
                        receipt_no=self.receipt_no,
                        date=self.credit_memo.posting_date,
                        document_type="Purchase Credit Memo",
                        transaction_no=f"REV-{self.credit_memo.no}",
                        global_dimension_1=item_entry.global_dimension_1,
                    )

                    # Handle serial/lot numbers if present
                    if item_entry.lot_no:
                        item_ledger.lot_no = item_entry.lot_no
                    if item_entry.expiry_date:
                        item_ledger.expiry_date = item_entry.expiry_date
                    if item_entry.serial_no:
                        item_ledger.serial_no = item_entry.serial_no
                    item_ledger.save()
                    created_item_ledgers.append(item_ledger)

                # Create reversal value entries linked to item ledger entries
                for idx, value_entry in enumerate(original_value_entries):
                    item_qty = (
                        float(value_entry.item_ledger_entry_quantity)
                        if value_entry.item_ledger_entry_quantity
                        else 0
                    )
                    invoiced_qty = (
                        float(value_entry.invoiced_quantity)
                        if value_entry.invoiced_quantity
                        else 0
                    )
                    valued_qty = (
                        float(value_entry.valued_quantity)
                        if value_entry.valued_quantity
                        else 0
                    )
                    cost_amount = (
                        float(value_entry.cost_amount) if value_entry.cost_amount else 0
                    )
                    cost_per_unit = (
                        float(value_entry.cost_per_unit)
                        if value_entry.cost_per_unit
                        else 0
                    )

                    # Get the corresponding item ledger entry
                    item_ledger_entry = (
                        created_item_ledgers[idx]
                        if idx < len(created_item_ledgers)
                        else None
                    )

                    if not item_ledger_entry:
                        continue  # Skip if no matching item ledger entry

                    ValueEntry.objects.create(
                        posting_date=self.credit_memo.posting_date,
                        document_type="Purchase Credit Memo",
                        entry_type="Purchase Return",
                        document_no=self.credit_memo.no,
                        item_ledger_entry_no=item_ledger_entry,  # Link to item ledger entry
                        item_ledger_entry_quantity=-item_qty,
                        invoiced_quantity=-invoiced_qty,
                        valued_quantity=-valued_qty,
                        cost_amount=str(-cost_amount),  # Convert to string (CharField)
                        sales_amount="0",  # Convert to string (CharField)
                        cost_per_unit=cost_per_unit,
                        item=value_entry.item,
                        general_product_posting_group=value_entry.general_product_posting_group,
                        inventory_posting_group=value_entry.inventory_posting_group,
                        global_dimension_1=value_entry.global_dimension_1,
                        transaction_no=f"REV-{self.credit_memo.no}",
                    )

                # Create reversal detailed vendor ledger entries
                for detailed_entry in original_detailed_entries:
                    amount = int(detailed_entry.amount) if detailed_entry.amount else 0
                    debit_amount = (
                        int(detailed_entry.debit_amount)
                        if detailed_entry.debit_amount
                        else 0
                    )
                    credit_amount = (
                        int(detailed_entry.credit_amount)
                        if detailed_entry.credit_amount
                        else 0
                    )

                    if detailed_entry.document_type == CommonDocumentType.Payment.value:
                        reversal_doc_type = CommonDocumentType.Refund.value
                    else:
                        reversal_doc_type = "Credit Memo"

                    if (
                        detailed_entry.initial_document_type
                        == CommonDocumentType.Invoice.value
                    ):
                        initial_doc_type = "Credit Memo"
                    elif (
                        detailed_entry.initial_document_type
                        == CommonDocumentType.Payment.value
                    ):
                        initial_doc_type = CommonDocumentType.Refund.value
                    else:
                        initial_doc_type = reversal_doc_type

                    if detailed_entry.entry_type == CommonEntryType.initial.value:
                        applied_vendor_entry_no = 0
                    else:
                        applied_vendor_entry_no = next_vendor_entry_id

                    # Get the reversal vendor ledger entry for this vendor
                    reversal_vendor_ledger = reversal_vendor_ledgers.get(
                        detailed_entry.vendor.id
                    )

                    DetailedVendorLedgerEntry.objects.create(
                        posting_date=self.credit_memo.posting_date,
                        entry_type=detailed_entry.entry_type,
                        document_type=reversal_doc_type,
                        document_no=self.credit_memo.no,
                        vendor=detailed_entry.vendor,
                        amount=-amount,
                        debit_amount=credit_amount,
                        credit_amount=debit_amount,
                        initial_entry_due_date=detailed_entry.initial_entry_due_date,
                        initial_document_type=initial_doc_type,
                        vendor_ledger_entry=reversal_vendor_ledger,
                        applied_vendor_ledger_entry_no=applied_vendor_entry_no,
                        unapplied_by_entry_no=0,
                        unapplied=False,
                        global_dimension_1=detailed_entry.global_dimension_1,
                        dimension_set=getattr(detailed_entry, "dimension_set", None),
                        transaction_no=f"REV-{self.credit_memo.no}",
                    )

                # Update credit memo status
                self.credit_memo.status = "Posted"
                self.credit_memo.save()

                # Create Posted Purchase Credit Memo
                posted_purchase_credit_memo = PostedPurchaseCreditMemo.objects.create(
                    vendor=self.credit_memo.vendor,
                    document_date=self.credit_memo.document_date,
                    posting_date=self.credit_memo.posting_date,
                    due_date=self.credit_memo.due_date,
                    vendor_cr_memo_no=self.credit_memo.vendor_cr_memo_no,
                    original_invoice_no=self.credit_memo.original_invoice_no,
                    original_posted_invoice=self.credit_memo.original_posted_invoice,
                )
                posted_purchase_credit_memo.save()

                # Create Posted Purchase Credit Memo Lines
                for line in self.credit_memo.lines.all():
                    PostedPurchaseCreditMemoLine.objects.create(
                        posted_purchase_credit_memo=posted_purchase_credit_memo,
                        item=line.item,
                        description=line.description,
                        location_code=line.location_code,
                        quantity=line.quantity,
                        unit_of_measure=line.unit_of_measure,
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_cost=line.unit_cost,
                        amount=line.total_amount,
                    )

            return {
                "success": True,
                "message": f"Successfully posted credit memo {self.credit_memo.no}",
            }

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(
                f"Error in PurchaseCreditMemoPostingProcessor.post(): {str(e)}"
            )
            logger.error(f"Full traceback: {traceback.format_exc()}")

            return {
                "success": False,
                "message": f"Error posting credit memo: {str(e)}",
                "error_type": type(e).__name__,
                "error_details": str(e),
                "traceback": traceback.format_exc() if settings.DEBUG else None,
            }


@admin.register(PurchasePayable)
class PurchasePayableAdmin(admin.ModelAdmin):
    list_display = [
        "vendor_no",
        "invoice_no",
        "posted_invoice_no",
        "credit_memo_no",
        "posted_credit_memo_no",
    ]
    readonly_fields = ["created_at", "updated_at"]

    def has_add_permission(self, request):
        # Check if any record exists
        return not PurchasePayable.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the setup record
        return False

    actions = ["setup_default_configuration"]

    def setup_default_configuration(self, request, queryset):
        """Action to help users set up default PurchasePayable configuration"""
        from setup.models import NoSeries, NoSeriesLines

        try:
            # Check if required NoSeries exist
            required_series = ["VENDOR", "INV", "POSTINV", "PURCR", "POSTPURCR"]
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

            # Create PurchasePayable configuration
            PurchasePayable.objects.create(
                vendor_no=NoSeriesLines.objects.get(no_series__code="VENDOR"),
                invoice_no=NoSeriesLines.objects.get(no_series__code="INV"),
                posted_invoice_no=NoSeriesLines.objects.get(no_series__code="POSTINV"),
                credit_memo_no=NoSeriesLines.objects.get(no_series__code="PURCR"),
                posted_credit_memo_no=NoSeriesLines.objects.get(
                    no_series__code="POSTPURCR"
                ),
            )

            self.message_user(
                request,
                "PurchasePayable configuration created successfully! You can now create purchase invoices and credit memos.",
                level="SUCCESS",
            )

        except Exception as e:
            self.message_user(
                request, f"Error setting up configuration: {str(e)}", level="ERROR"
            )

    setup_default_configuration.short_description = (
        "Set up default PurchasePayable configuration"
    )


@admin.register(Vendor)
class VendorAdmin(DefaultDimensionAdminMixin, admin.ModelAdmin):
    related_model = "purchases.Vendor"
    no_attr = "no"

    list_display = [
        "no",
        "name",
        "blocked",
        "balance",
        "city",
        "state",
        "phone",
    ]

    exclude = ("no",)
    # readonly_fields = ("no",)

    fieldsets = [
        (
            "Basic Information",
            {
                "fields": (
                    # "no",
                    "name",
                    "blocked",
                )
            },
        ),
        (
            "Contact Information",
            {
                "fields": (
                    "address",
                    "address_2",
                    "country",
                    "city",
                    "state",
                    "post_code",
                    "phone",
                    "mobile",
                    "email",
                    "website",
                )
            },
        ),
        ("Payment Settings", {"fields": ("payment_method",)}),
        (
            "Posting Groups",
            {
                "fields": ("vendor_posting_group", "business_posting_group", "vat_business_posting_group"),
            },
        ),
    ]

    list_filter = ["blocked", "country", "state"]
    search_fields = ["name", "email", "phone"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(VendorLedger)
class VendorLedgerAdmin(admin.ModelAdmin):
    list_display = [
        "posting_date",
        "document_date",
        "document_type",
        "document_no",
        "external_document_no",
        "vendor",
        "payment_method",
        "original_amount",
        "amount",
        "remaining_amount",
        "open",
        "description",
        "applies_to_id",
    ]

    list_filter = [
        "document_type",
        "posting_date",
        "open",
        "vendor",
        "payment_method",
    ]
    readonly_fields = ["document_no", "remaining_amount"]

    search_fields = [
        "id",
        "document_no",
        "external_document_no",
        "vendor__name",
        "vendor__no",
        "description",
    ]

    readonly_fields = ["remaining_amount", "created_at", "updated_at"]

    fieldsets = [
        (
            "Document Information",
            {
                "fields": (
                    "document_type",
                    "document_no",
                    "external_document_no",
                    "posting_date",
                    "document_date",
                    "due_date",
                )
            },
        ),
        (
            "Transaction Details",
            {
                "fields": (
                    "vendor",
                    "payment_method",
                    "description",
                    "original_amount",
                    "amount",
                    "remaining_amount",
                    "open",
                    "applies_to_id",
                    "payment",
                )
            },
        ),
    ]

    # def has_delete_permission(self, request, obj=None):
    #     # Prevent deletion of ledger entries
    #     return False


@admin.register(DetailedVendorLedgerEntry)
class DetailedVendorLedgerEntryAdmin(admin.ModelAdmin):
    list_display = [
        "posting_date",
        "entry_type",
        "document_type",
        "document_no",
        "vendor",
        "amount",
        "debit_amount",
        "credit_amount",
        "initial_entry_due_date",
        "vendor_ledger_entry",
        "applied_vendor_ledger_entry_no",
        "unapplied_by_entry_no",
        "unapplied",
        "global_dimension_1",
    ]

    search_fields = [
        "document_no",
        "vendor__name",
        "vendor__no",
        "vendor_ledger_entry__document_no",
        "vendor_ledger_entry__id",
    ]


@admin.register(VendorPostingGroup)
class VendorPostingGroupAdmin(admin.ModelAdmin):
    list_display = ["code", "description"]
    search_fields = ["code", "description"]
    readonly_fields = ["created_at", "updated_at"]
    actions = [sync_from_json_file, sync_all_models_from_json]


class PostedPurchaseInvoiceLineInline(admin.TabularInline):
    model = PostedPurchaseInvoiceLine
    extra = 1
    fields = [
        "item",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_cost",
        # "total_amount",
        # "line_amount",
    ]


@admin.register(PostedPurchaseInvoice)
class PostedPurchaseInvoiceAdmin(admin.ModelAdmin):
    list_display = ["no", "vendor", "document_date", "posting_date", "due_date"]
    search_fields = ["no", "vendor__name", "vendor__no"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["create_credit_memo"]

    inlines = [PostedPurchaseInvoiceLineInline]

    def create_credit_memo(self, request, queryset):
        """Create Purchase Credit Memo from selected Posted Purchase Invoice(s)"""

        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one Posted Purchase Invoice to create a credit memo.",
                level="ERROR",
            )
            return

        posted_invoice = queryset.first()

        try:
            with transaction.atomic():
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

                self.message_user(
                    request,
                    f"✅ Successfully created Purchase Credit Memo from invoice {posted_invoice.no}. "
                    f"Credit Memo has {lines_created} line(s) with status 'Open'. "
                    f"You can now edit it and post it when ready.",
                    level="SUCCESS",
                )

                # Redirect to the created credit memo
                from django.shortcuts import redirect
                from django.urls import reverse

                change_url = reverse(
                    "admin:purchases_purchasecreditmemo_change",
                    args=[credit_memo.pk],
                )
                return redirect(change_url)

        except Exception as e:
            self.message_user(
                request,
                f"❌ Error creating credit memo: {str(e)}",
                level="ERROR",
            )

    create_credit_memo.short_description = (
        "Create Purchase Credit Memo from selected invoice"
    )


class PostedPurchaseCreditMemoLineInline(admin.TabularInline):
    model = PostedPurchaseCreditMemoLine
    extra = 0
    readonly_fields = ["created_at", "updated_at"]
    fields = [
        "item",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_cost",
        "amount",
    ]


@admin.register(PostedPurchaseCreditMemo)
class PostedPurchaseCreditMemoAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "vendor",
        "document_date",
        "posting_date",
        "due_date",
        "vendor_cr_memo_no",
    ]
    search_fields = ["no", "vendor__name", "vendor__no", "vendor_cr_memo_no"]
    readonly_fields = ["created_at", "updated_at", "no"]
    inlines = [PostedPurchaseCreditMemoLineInline]

    fieldsets = [
        (
            "Vendor Information",
            {"fields": ("vendor",)},
        ),
        (
            "Document Information",
            {
                "fields": (
                    "no",
                    "vendor_cr_memo_no",
                )
            },
        ),
        (
            "Original Invoice Reference",
            {
                "fields": (
                    "original_invoice_no",
                    "original_posted_invoice",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "document_date",
                    "posting_date",
                    "due_date",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    ]


class PurchaseCreditMemoLineInline(admin.TabularInline):
    model = PurchaseCreditMemoLine
    extra = 1
    fields = [
        "item",
        "description",
        "location_code",
        "quantity",
        "unit_of_measure",
        "item_unit_of_measure",
        "unit_cost",
        "line_amount",
        "global_dimension_1",
    ]
    readonly_fields = ["line_amount"]

    def line_amount(self, obj):
        """Display calculated line amount"""
        if obj.id:
            return obj.line_amount
        return 0

    line_amount.short_description = "Line Amount"

    def has_add_permission(self, request, obj=None):
        """Don't allow adding lines to posted credit memos"""
        if obj and obj.status == "Posted":
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Don't allow deleting lines from posted credit memos"""
        if obj and obj.status == "Posted":
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        """Don't allow editing lines in posted credit memos"""
        if obj and obj.status == "Posted":
            return False
        return super().has_change_permission(request, obj)


@admin.register(PurchaseCreditMemo)
class PurchaseCreditMemoAdmin(admin.ModelAdmin):
    list_display = [
        "no",
        "vendor_name",
        "contact_person",
        "document_date",
        "due_date",
        "status",
    ]
    search_fields = [
        "no",
        "vendor__name",
        "vendor__no",
        "vendor_cr_memo_no",
        "vendor_authorization_no",
    ]
    list_filter = ["status", "document_date", "posting_date"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "no",
        "vendor_name",
        "original_invoice_no",
        "original_posted_invoice",
    ]
    actions = ["preview_posting", "post_credit_memo"]

    inlines = [PurchaseCreditMemoLineInline]

    def preview_posting(self, request, queryset):
        """Preview posting of Purchase Credit Memo by finding and reversing original invoice entries"""

        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one Purchase Credit Memo to preview posting.",
                level="ERROR",
            )
            return

        credit_memo = queryset.first()

        # Validate credit memo
        if not credit_memo.original_posted_invoice:
            self.message_user(
                request,
                "This credit memo is not linked to an original posted invoice.",
                level="ERROR",
            )
            return

        if credit_memo.status == "Posted":
            self.message_user(
                request,
                "This credit memo has already been posted.",
                level="ERROR",
            )
            return

        # Get the vendor_invoice_no from the posted invoice
        vendor_invoice_no = credit_memo.original_posted_invoice.vendor_invoice_no

        # Find the original PurchaseInvoice using vendor_invoice_no and status "Posted"
        try:
            original_purchase_invoice = PurchaseInvoice.objects.get(
                vendor_invoice_no=vendor_invoice_no, status="Posted"
            )
            # Use the invoice_no from the original PurchaseInvoice to query entries
            original_doc_no = original_purchase_invoice.invoice_no
        except PurchaseInvoice.DoesNotExist:
            self.message_user(
                request,
                f"Could not find original Posted Purchase Invoice with vendor_invoice_no: {vendor_invoice_no}",
                level="ERROR",
            )
            return
        except PurchaseInvoice.MultipleObjectsReturned:
            self.message_user(
                request,
                f"Multiple Posted Purchase Invoices found with vendor_invoice_no: {vendor_invoice_no}. This should not happen.",
                level="ERROR",
            )
            return

        try:
            # 1. Find all GL Entries for the original invoice
            original_gl_entries = GeneralLedgerEntry.objects.filter(
                document_no=original_doc_no
            ).order_by("id")

            # 2. Find all Vendor Ledger Entries for the original invoice
            original_vendor_entries = VendorLedger.objects.filter(
                document_no=original_doc_no
            ).order_by("id")

            # 3. Find all Item Ledger Entries for the original invoice
            original_item_entries = ItemLedgerEntries.objects.filter(
                document_no=original_doc_no
            ).order_by("id")

            # 4. Find all Value Entries for the original invoice
            original_value_entries = ValueEntry.objects.filter(
                document_no=original_doc_no
            ).order_by("id")

            # 5. Find all Detailed Vendor Ledger Entries
            original_detailed_entries = DetailedVendorLedgerEntry.objects.filter(
                document_no=original_doc_no
            ).order_by("entry_no")

            # Now create opposite/reversal entries for preview
            from decimal import Decimal
            from common.enums import (
                DocumentType as CommonDocumentType,
                EntryType as CommonEntryType,
            )

            # Get the next vendor ledger entry number that will be created when credit memo is posted
            # This will be used for Application type detailed entries
            try:
                next_vendor_entry_id = (
                    VendorLedger.objects.aggregate(max_id=Max("id"))["max_id"] or 0
                )
                next_vendor_entry_id += 1  # Next entry number
            except Exception:
                next_vendor_entry_id = 0  # Fallback if can't determine

            reversal_gl_entries = []
            for gl_entry in original_gl_entries:
                # Convert amount to Decimal/float to ensure numeric type
                amount = float(gl_entry.amount) if gl_entry.amount else 0

                # Determine document type: REFUND for Payment reversals, Credit Memo for others
                if gl_entry.document_type == CommonDocumentType.Payment.value:
                    reversal_doc_type = CommonDocumentType.Refund.value
                else:
                    reversal_doc_type = "Credit Memo"

                reversal_gl_entries.append(
                    {
                        "posting_date": credit_memo.posting_date,
                        "document_type": reversal_doc_type,
                        "document_no": credit_memo.no,
                        "gl_account": gl_entry.gl_account,
                        "description": f"Reversal of {gl_entry.document_type} {gl_entry.document_no}",
                        "amount": -amount,  # OPPOSITE SIGN
                        "gen_posting_type": gl_entry.general_posting_type,
                        "global_dimension_1": gl_entry.global_dimension_1,
                        "gen_bus_posting_group": gl_entry.general_business_posting_group,
                        "gen_prod_posting_group": gl_entry.general_product_posting_group,
                        "balance_account_type": gl_entry.balancing_account_type,
                        "transaction_no": f"REV-{credit_memo.no}",
                        "original_amount": amount,  # For display
                    }
                )

            reversal_vendor_entries = []
            for vendor_entry in original_vendor_entries:
                # Convert amounts to float to ensure numeric type
                original_amount = (
                    float(vendor_entry.original_amount)
                    if vendor_entry.original_amount
                    else 0
                )
                amount = float(vendor_entry.amount) if vendor_entry.amount else 0

                # Determine document type: REFUND for Payment reversals, Credit Memo for others
                if vendor_entry.document_type == CommonDocumentType.Payment.value:
                    reversal_doc_type = CommonDocumentType.Refund.value
                else:
                    reversal_doc_type = "Credit Memo"

                reversal_vendor_entries.append(
                    {
                        "posting_date": credit_memo.posting_date,
                        "document_date": credit_memo.document_date,
                        "document_type": reversal_doc_type,
                        "document_no": credit_memo.no,
                        "external_document_no": credit_memo.vendor_cr_memo_no or "",
                        "vendor_no": vendor_entry.vendor.no,
                        "vendor": vendor_entry.vendor,
                        "description": f"Reversal of {vendor_entry.document_type} {vendor_entry.document_no}",
                        "payment_method": vendor_entry.payment_method,
                        "original_amount": -original_amount,  # OPPOSITE SIGN
                        "amount": -amount,  # OPPOSITE SIGN
                        "remaining_amount": -amount,  # OPPOSITE SIGN
                        "open": True,
                        "due_date": credit_memo.due_date,
                        "global_dimension_1": vendor_entry.global_dimension_1,
                        "transaction_no": f"REV-{credit_memo.no}",
                    }
                )

            reversal_item_entries = []
            for item_entry in original_item_entries:
                # Convert to numeric types
                quantity = int(item_entry.quantity) if item_entry.quantity else 0
                total = float(item_entry.total) if item_entry.total else 0
                unit_cost = total / quantity if quantity else 0

                reversal_item_entries.append(
                    {
                        "posting_date": credit_memo.posting_date,
                        "entry_type": "Purchase Return",
                        "item": item_entry.item,
                        "document_no": credit_memo.no,
                        "description": f"Reversal of {item_entry.description}",
                        "unit_of_measure": item_entry.unit_of_measure_code,
                        "unit_cost": unit_cost,
                        "location": item_entry.location,
                        "quantity": -quantity,  # OPPOSITE SIGN
                        "remaining_quantity": -quantity,  # OPPOSITE SIGN
                        "cost_amount": -total,  # OPPOSITE SIGN
                        "total": -total,  # OPPOSITE SIGN
                        "lot_no": item_entry.lot_no,
                        "expiry_date": item_entry.expiry_date,
                        "serial_no": item_entry.serial_no,
                        "global_dimension_1": item_entry.global_dimension_1,
                        "global_dimension_2": getattr(item_entry, "global_dimension_2", None),
                        "dimension_set": getattr(item_entry, "dimension_set", None),
                        "document_type": "Purchase Credit Memo",
                        "transaction_no": f"REV-{credit_memo.no}",
                    }
                )

            reversal_value_entries = []
            for value_entry in original_value_entries:
                # Convert to numeric types
                item_qty = (
                    float(value_entry.item_ledger_entry_quantity)
                    if value_entry.item_ledger_entry_quantity
                    else 0
                )
                invoiced_qty = (
                    float(value_entry.invoiced_quantity)
                    if value_entry.invoiced_quantity
                    else 0
                )
                valued_qty = (
                    float(value_entry.valued_quantity)
                    if value_entry.valued_quantity
                    else 0
                )
                cost_amount = (
                    float(value_entry.cost_amount) if value_entry.cost_amount else 0
                )
                cost_per_unit = (
                    float(value_entry.cost_per_unit) if value_entry.cost_per_unit else 0
                )

                reversal_value_entries.append(
                    {
                        "posting_date": credit_memo.posting_date,
                        "document_type": "Purchase Credit Memo",
                        "entry_type": "Purchase Return",
                        "document_no": credit_memo.no,
                        "item_ledger_entry_quantity": -item_qty,  # OPPOSITE
                        "invoiced_quantity": -invoiced_qty,  # OPPOSITE
                        "valued_quantity": -valued_qty,  # OPPOSITE
                        "cost_amount": -cost_amount,  # OPPOSITE SIGN
                        "sales_amount": 0,
                        "purchase_amount": 0,
                        "cost_per_unit": cost_per_unit,
                        "item": value_entry.item,
                        "general_product_posting_group": value_entry.general_product_posting_group,
                        "inventory_posting_group": value_entry.inventory_posting_group,
                        "global_dimension_1": value_entry.global_dimension_1,
                        "global_dimension_2": getattr(value_entry, "global_dimension_2", None),
                        "dimension_set": getattr(value_entry, "dimension_set", None),
                        "transaction_no": f"REV-{credit_memo.no}",
                    }
                )

            reversal_detailed_entries = []
            for detailed_entry in original_detailed_entries:
                # Convert to numeric types
                amount = int(detailed_entry.amount) if detailed_entry.amount else 0
                debit_amount = (
                    int(detailed_entry.debit_amount)
                    if detailed_entry.debit_amount
                    else 0
                )
                credit_amount = (
                    int(detailed_entry.credit_amount)
                    if detailed_entry.credit_amount
                    else 0
                )

                # Determine document type: REFUND for Payment reversals, Credit Memo for others
                if detailed_entry.document_type == CommonDocumentType.Payment.value:
                    reversal_doc_type = CommonDocumentType.Refund.value
                else:
                    reversal_doc_type = "Credit Memo"

                # Determine initial_document_type based on original initial_document_type:
                # - If original was "Invoice" → reversal initial_doc_type = "Credit Memo"
                # - If original was "Payment" → reversal initial_doc_type = "Refund"
                if (
                    detailed_entry.initial_document_type
                    == CommonDocumentType.Invoice.value
                ):
                    initial_doc_type = "Credit Memo"
                elif (
                    detailed_entry.initial_document_type
                    == CommonDocumentType.Payment.value
                ):
                    initial_doc_type = CommonDocumentType.Refund.value
                else:
                    # Fallback: use reversal_doc_type
                    initial_doc_type = reversal_doc_type

                # Determine applied_vendor_ledger_entry_no:
                # - For "Initial Entry" types: 0
                # - For "Application" types: reference the vendor ledger entry that will be created when credit memo is posted
                if detailed_entry.entry_type == CommonEntryType.initial.value:
                    applied_vendor_entry_no = 0
                else:
                    # Application entries reference the vendor ledger entry that will be created from the credit memo
                    applied_vendor_entry_no = next_vendor_entry_id

                reversal_detailed_entries.append(
                    {
                        "posting_date": credit_memo.posting_date,
                        "entry_type": detailed_entry.entry_type,
                        "document_type": reversal_doc_type,
                        "document_no": credit_memo.no,
                        "vendor_no": detailed_entry.vendor.no,
                        "amount": -amount,  # OPPOSITE SIGN
                        "debit_amount": credit_amount,  # SWAP
                        "credit_amount": debit_amount,  # SWAP
                        "initial_entry_due_date": detailed_entry.initial_entry_due_date,
                        "initial_document_type": initial_doc_type,
                        "applied_vendor_ledger_entry_no": applied_vendor_entry_no,
                        "transaction_no": f"REV-{credit_memo.no}",
                    }
                )

            # Prepare preview data
            preview_entries = {
                "credit_memo": f"Credit Memo {credit_memo.no} (reversing {original_doc_no})",
                "original_invoice": original_doc_no,
                "steps": [
                    f"Found {len(original_gl_entries)} GL entries to reverse",
                    f"Found {len(original_vendor_entries)} Vendor entries to reverse",
                    f"Found {len(original_item_entries)} Item entries to reverse",
                    f"Found {len(original_value_entries)} Value entries to reverse",
                    f"Found {len(original_detailed_entries)} Detailed Vendor entries to reverse",
                ],
                "entries": {
                    "gl_entries": reversal_gl_entries,
                    "vendor_entries": reversal_vendor_entries,
                    "item_entries": reversal_item_entries,
                    "value_entries": reversal_value_entries,
                    "detailed_vendor_entries": reversal_detailed_entries,
                },
            }

            return TemplateResponse(
                request,
                "admin/purchases/purchasecreditmemo/preview_posting.html",
                context={
                    "title": "Preview Credit Memo Posting",
                    "credit_memo": credit_memo,
                    "preview_entries": preview_entries,
                    "opts": self.model._meta,
                },
            )

        except Exception as e:
            self.message_user(
                request,
                f"Error previewing credit memo posting: {str(e)}",
                level="ERROR",
            )
            return

    preview_posting.short_description = "Preview posting of credit memo"

    def post_credit_memo(self, request, queryset):
        """Post Purchase Credit Memo by creating reversal entries"""
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly one Purchase Credit Memo to post.",
                level="ERROR",
            )
            return

        credit_memo = queryset.first()

        # Validate credit memo
        if credit_memo.status == "Posted":
            self.message_user(
                request,
                "This credit memo has already been posted.",
                level="ERROR",
            )
            return

        if not credit_memo.original_posted_invoice:
            self.message_user(
                request,
                "This credit memo is not linked to an original posted invoice.",
                level="ERROR",
            )
            return

        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Create posting processor and post the credit memo
            processor = PurchaseCreditMemoPostingProcessor(
                credit_memo, request, receipt_no
            )

            # Start transaction to ensure all entries are created or none are
            with transaction.atomic():
                result = processor.post()

                if result["success"]:
                    self.message_user(
                        request,
                        f"Successfully posted credit memo {credit_memo.no}",
                        level="SUCCESS",
                    )
                else:
                    error_msg = result.get("message", "Unknown error during posting")
                    self.message_user(request, error_msg, level="ERROR")
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = str(e)
            self.message_user(request, error_msg, level="ERROR")

    post_credit_memo.short_description = "Post credit memo (create reversal entries)"

    fieldsets = [
        (
            "Vendor Information",
            {
                "fields": (
                    "vendor",
                    "vendor_name",
                    "contact_person",
                )
            },
        ),
        (
            "Document Information",
            {
                "fields": (
                    "no",
                    "vendor_cr_memo_no",
                    "vendor_authorization_no",
                    "status",
                )
            },
        ),
        (
            "Original Invoice Reference",
            {
                "fields": (
                    "original_invoice_no",
                    "original_posted_invoice",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "document_date",
                    "posting_date",
                    "due_date",
                    "expected_receipt_date",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    ]

    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly when credit memo is posted"""
        readonly = list(self.readonly_fields)
        if obj and obj.status == "Posted":
            # When posted, make all fields readonly except system fields
            readonly.extend(
                [
                    "vendor",
                    "contact_person",
                    "vendor_cr_memo_no",
                    "vendor_authorization_no",
                    "document_date",
                    "posting_date",
                    "due_date",
                    "expected_receipt_date",
                    "status",
                ]
            )
        return readonly

    def has_delete_permission(self, request, obj=None):
        """Don't allow deletion of posted credit memos"""
        if obj and obj.status == "Posted":
            return False
        return super().has_delete_permission(request, obj)
