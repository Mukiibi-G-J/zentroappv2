from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from django.db import transaction
import uuid

from .models import PaymentJournal

# Register your models here.


@admin.register(PaymentJournal)
class PaymentJournalAdmin(admin.ModelAdmin):
    list_display = [
        "document_no",
        "posting_date",
        "document_type",
        "account_type",
        "account_name_display",
        "amount",
        "bal_account_type",
        "bal_account_name_display",
        "payment_method",
        "status",
        "application_status",
        "external_document_no",
    ]

    list_filter = [
        "posting_date",
        "document_type",
        "account_type",
        "bal_account_type",
        "payment_method",
        "status",
        "application_status",
    ]

    search_fields = [
        "document_no",
        "external_document_no",
        "description",
    ]

    readonly_fields = [
        "account_name",
        "bal_account_name",
        "applies_to_doc_name",
        "created_at",
        "updated_at",
    ]

    actions = ["preview_posting", "post_payment_journal"]

    fieldsets = (
        (
            _("Document Information"),
            {
                "fields": (
                    "posting_date",
                    "document_type",
                    "document_no",
                    "external_document_no",
                    "description",
                )
            },
        ),
        (
            _("Account Information"),
            {
                "fields": (
                    "account_type",
                    "account_content_type",
                    "account_object_id",
                    "account_name",
                )
            },
        ),
        (
            _("Payment Information"),
            {
                "fields": (
                    "payment_method",
                    "amount",
                )
            },
        ),
        (
            _("Balancing Account"),
            {
                "fields": (
                    "bal_account_type",
                    "bal_account_content_type",
                    "bal_account_object_id",
                    "bal_account_name",
                )
            },
        ),
        (
            _("Status and Application"),
            {
                "fields": (
                    "status",
                    "application_status",
                    "applies_to_doc_type",
                    "applies_to_content_type",
                    "applies_to_object_id",
                    "applies_to_doc_name",
                )
            },
        ),
        (
            _("System Information"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def post_payment_journal(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single payment journal entry to post.",
                level="ERROR",
            )
            return

        payment_journal = queryset[0]

        if payment_journal.status == "Posted":
            self.message_user(
                request,
                "This payment journal has already been posted.",
                level="ERROR",
            )
            return

        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Validate tracking specifications for all lines before posting
            payment_journal.full_clean()
            payment_journal.clean()  # Custom model validation

            # Create posting processor and post the payment journal
            processor = PaymentJournalPostingProcessor(
                payment_journal, request, receipt_no
            )

            # Start transaction to ensure all entries are created or none are
            with transaction.atomic():
                result = processor.post()

                if result["success"]:
                    # Update the payment journal status to Posted
                    payment_journal.status = "Posted"
                    payment_journal.save()

                    self.message_user(
                        request,
                        f"Successfully posted payment journal {payment_journal.document_no}",
                        level="SUCCESS",
                    )
                else:
                    error_msg = result.get("message", "Unknown error during posting")
                    self.message_user(request, error_msg, level="ERROR")
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = str(e)
            # Clean up redundant prefixes
            if error_msg.startswith("Error posting payment journal: "):
                error_msg = error_msg.replace("Error posting payment journal: ", "")
            if error_msg.startswith("Error processing payment journal: "):
                error_msg = error_msg.replace("Error processing payment journal: ", "")

            self.message_user(request, error_msg, level="ERROR")
            raise Exception(error_msg)

    post_payment_journal.short_description = "Post Payment Journal"

    def preview_posting(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single payment journal entry to preview posting.",
                level="ERROR",
            )
            return

        payment_journal = queryset[0]
        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Run validation first
            payment_journal.full_clean()
            payment_journal.clean()  # Custom model validation

            # If validation passes, proceed with posting preview
            processor = PaymentJournalProcessor(payment_journal, request, receipt_no)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing posting: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            preview_entries = {
                "payment_journal": f"Payment Journal {payment_journal.id} -> {payment_journal.document_no}",
                "steps": [
                    "Posting payment to account",
                    "Posting to balancing account",
                    "Posting detailed ledger entries",
                ],
                "entries": entries,
            }

            return TemplateResponse(
                request,
                "admin/payments/paymentjournal/preview_posting.html",
                context={
                    "title": "Preview Posting",
                    "payment_journal": payment_journal,
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

    preview_posting.short_description = "Preview Posting"

    def account_name_display(self, obj):
        """Display account name with link if possible"""
        if obj.account_no:
            if hasattr(obj.account_no, "get_absolute_url"):
                return format_html(
                    '<a href="{}">{}</a>',
                    obj.account_no.get_absolute_url(),
                    obj.account_name,
                )
        return obj.account_name

    account_name_display.short_description = _("Account")
    account_name_display.admin_order_field = "account_object_id"

    def bal_account_name_display(self, obj):
        """Display balancing account name with link if possible"""
        if obj.bal_account_no:
            if hasattr(obj.bal_account_no, "get_absolute_url"):
                return format_html(
                    '<a href="{}">{}</a>',
                    obj.bal_account_no.get_absolute_url(),
                    obj.bal_account_name,
                )
        return obj.bal_account_name

    bal_account_name_display.short_description = _("Balancing Account")
    bal_account_name_display.admin_order_field = "bal_account_object_id"

    def get_queryset(self, request):
        """Optimize queryset with select_related for better performance"""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "account_content_type", "bal_account_content_type", "payment_method"
            )
        )

    def save_model(self, request, obj, form, change):
        """Custom save logic if needed"""
        super().save_model(request, obj, form, change)

    class Media:
        css = {"all": ("admin/css/payment_journal.css",)}
        js = ("admin/js/payment_journal.js",)


def _resolve_payment_ledger_dimensions(
    *,
    entry,
    request,
    global_dimension_1_fallback=None,
    applies_to_ledger=None,
):
    """Build dimension_set + global dimensions required by ledger tables."""
    from dimension.branch_filter import get_branch_for_request
    from dimension.models import get_posting_dimension_payload

    dimension_set = entry.get("dimension_set")
    global_dimension_1 = entry.get("global_dimension_1")

    if applies_to_ledger is not None:
        if not dimension_set and getattr(applies_to_ledger, "dimension_set_id", None):
            dimension_set = applies_to_ledger.dimension_set
        if not global_dimension_1 and getattr(applies_to_ledger, "global_dimension_1_id", None):
            global_dimension_1 = applies_to_ledger.global_dimension_1

    if not global_dimension_1 and request is not None:
        global_dimension_1 = get_branch_for_request(request)
    if not global_dimension_1:
        global_dimension_1 = global_dimension_1_fallback

    payload = get_posting_dimension_payload(
        global_dimension_1=global_dimension_1,
        dimension_set=dimension_set,
    )
    if payload["dimension_set"] is None:
        from dimension.utils import resolve_default_branch_for_tenant

        branch, dim_set, _err = resolve_default_branch_for_tenant(
            allow_multiple_branch_values=True
        )
        if dim_set:
            payload = get_posting_dimension_payload(
                global_dimension_1=payload.get("global_dimension_1")
                or global_dimension_1
                or branch,
                dimension_set=dim_set,
            )
    if payload["dimension_set"] is None:
        raise ValueError(
            "Could not resolve posting dimensions for the payment journal. "
            "Configure General Ledger Setup branch dimensions or set the user's branch."
        )
    return payload


class PaymentJournalPostingProcessor:
    def __init__(self, payment_journal, request, receipt_no):
        self.payment_journal = payment_journal
        self.request = request
        self.user = request.user
        self.receipt_no = receipt_no

        # Get dimension_1 value from user's dimension
        self.global_dimension_1_value = getattr(request.user, "global_dimension_1", None)

        self.global_dimension_1 = self.global_dimension_1_value

        self.dimension_set_value = getattr(
            self.payment_journal, "dimension_set", None
        ) or getattr(request.user, "dimension_set", None)

        self.vendor = None
        self.payables_account = None

        if self.payment_journal.account_type == "Vendor":
            self.vendor = self.payment_journal.account_no
            if self.vendor and hasattr(self.vendor, "vendor_posting_group"):
                self.payables_account = (
                    self.vendor.vendor_posting_group.payables_account
                )

    def post(self):
        """Post the payment journal and create actual database entries"""
        try:
            # Process and create entries similar to preview but actually save them
            processor = PaymentJournalProcessor(
                self.payment_journal, self.request, self.receipt_no
            )
            entries = processor.process()

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
                "customer_entries",
                "detailed_vendor_entries",
                "detailed_customer_entries",
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
                    from financials.models import GeneralLedgerEntry
                    from financials.enums import BalacingAccountType

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
                        amount=float(gl_entry["amount"]),
                        general_posting_type=gl_entry["gen_posting_type"],
                        dimension_set=dim_payload["dimension_set"],
                        global_dimension_1=dim_payload["global_dimension_1"],
                        global_dimension_2=dim_payload["global_dimension_2"],
                        balancing_account_type=(
                            BalacingAccountType.GLAccount.name
                            if gl_entry["balance_account_type"] == "G/L Account"
                            else BalacingAccountType.Vendor.value
                        ),
                        user=gl_entry["user"],
                        receipt_no=self.receipt_no,
                        transaction_no=gl_entry["transaction_no"],
                    )

                # Create Vendor Ledger Entries and store them for detailed entries
                vendor_ledger_entries = {}
                applies_to_vendor_ledger = None
                if self.payment_journal.applies_to_object_id:
                    from purchases.models import VendorLedger

                    applies_to_vendor_ledger = VendorLedger.objects.filter(
                        pk=self.payment_journal.applies_to_object_id,
                    ).first()

                for vendor_entry in entries["vendor_entries"]:
                    from purchases.models import VendorLedger
                    from common.enums import DocumentType

                    vendor_dim = _resolve_payment_ledger_dimensions(
                        entry=vendor_entry,
                        request=self.request,
                        global_dimension_1_fallback=self.global_dimension_1_value,
                        applies_to_ledger=applies_to_vendor_ledger,
                    )

                    vendor_ledger = VendorLedger.objects.create(
                        posting_date=vendor_entry["posting_date"],
                        document_date=vendor_entry["document_date"],
                        document_type=(
                            DocumentType.Payment.value
                            if vendor_entry["document_type"] == "Payment"
                            else DocumentType.Invoice.value
                        ),
                        document_no=vendor_entry["document_no"],
                        external_document_no=vendor_entry["external_document_no"]
                        or vendor_entry["document_no"]
                        or "",
                        vendor=vendor_entry["vendor"],
                        description=vendor_entry["description"],
                        payment_method=vendor_entry["payment_method"],
                        original_amount=float(vendor_entry["original_amount"]),
                        amount=float(vendor_entry["amount"]),
                        open=bool(vendor_entry.get("open", not applies_to_vendor_ledger)),
                        due_date=vendor_entry["due_date"],
                        global_dimension_1=vendor_dim["global_dimension_1"],
                        dimension_set=vendor_dim["dimension_set"],
                        transaction_no=vendor_entry["transaction_no"],
                    )
                    # Store the created vendor ledger entry
                    vendor_ledger_entries[vendor_entry["vendor"].id] = vendor_ledger

                # Create Customer Ledger Entries and store them for detailed entries
                customer_ledger_entries = {}
                applies_to_customer_ledger = None
                if self.payment_journal.applies_to_object_id:
                    from sales.models import CustomerLedgerEntry

                    applies_to_customer_ledger = CustomerLedgerEntry.objects.filter(
                        pk=self.payment_journal.applies_to_object_id,
                    ).first()

                for customer_entry in entries["customer_entries"]:
                    from sales.models import CustomerLedgerEntry
                    from common.enums import DocumentType

                    customer_dim = _resolve_payment_ledger_dimensions(
                        entry=customer_entry,
                        request=self.request,
                        global_dimension_1_fallback=self.global_dimension_1_value,
                        applies_to_ledger=applies_to_customer_ledger,
                    )

                    customer_ledger = CustomerLedgerEntry.objects.create(
                        posting_date=customer_entry["posting_date"],
                        document_date=customer_entry["document_date"],
                        document_type=(
                            DocumentType.Payment.value
                            if customer_entry["document_type"] == "Payment"
                            else DocumentType.Invoice.value
                        ),
                        document_no=customer_entry["document_no"],
                        external_document_no=customer_entry["external_document_no"]
                        or customer_entry["document_no"]
                        or "",
                        customer=customer_entry["customer"],
                        description=customer_entry["description"],
                        payment_method=customer_entry["payment_method"],
                        original_amount=customer_entry["original_amount"],
                        amount=customer_entry["amount"],
                        due_date=customer_entry["due_date"],
                        global_dimension_1=customer_dim["global_dimension_1"],
                        dimension_set=customer_dim["dimension_set"],
                        user=customer_entry["user"],
                        transaction_no=customer_entry["transaction_no"],
                        open=bool(customer_entry.get("open", not applies_to_customer_ledger)),
                    )
                    # Store the created customer ledger entry
                    customer_ledger_entries[customer_entry["customer"].id] = (
                        customer_ledger
                    )

                # Create Detailed Vendor Ledger Entries
                for detailed_vendor_entry in entries["detailed_vendor_entries"]:
                    from purchases.models import DetailedVendorLedgerEntry
                    from common.enums import DocumentType, EntryType

                    if (
                        detailed_vendor_entry["entry_type"] == "Application"
                        and not applies_to_vendor_ledger
                    ):
                        continue

                    if (
                        detailed_vendor_entry["entry_type"] == "Application"
                        and detailed_vendor_entry["amount"] > 0
                    ):
                        vendor_ledger_entry = applies_to_vendor_ledger
                        applied_vendor_ledger_entry_no = applies_to_vendor_ledger.id
                    else:
                        vendor_ledger_entry = vendor_ledger_entries.get(
                            detailed_vendor_entry["vendor"].id
                        )
                        applied_vendor_ledger_entry_no = (
                            applies_to_vendor_ledger.id
                            if applies_to_vendor_ledger
                            else 0
                        )

                    if vendor_ledger_entry is None:
                        continue

                    vendor_detail_dim = _resolve_payment_ledger_dimensions(
                        entry=detailed_vendor_entry,
                        request=self.request,
                        global_dimension_1_fallback=self.global_dimension_1_value,
                        applies_to_ledger=(
                            applies_to_vendor_ledger
                            if detailed_vendor_entry["entry_type"] == "Application"
                            else vendor_ledger_entry
                        ),
                    )

                    detailed_vendor = DetailedVendorLedgerEntry.objects.create(
                        posting_date=detailed_vendor_entry["posting_date"],
                        entry_type=(
                            EntryType.initial.value
                            if detailed_vendor_entry["entry_type"] == "Initial Entry"
                            else EntryType.application.value
                        ),
                        document_type=(
                            DocumentType.Payment.value
                            if detailed_vendor_entry["document_type"] == "Payment"
                            else DocumentType.Invoice.value
                        ),
                        document_no=detailed_vendor_entry["document_no"],
                        vendor=detailed_vendor_entry["vendor"],
                        amount=detailed_vendor_entry["amount"],
                        debit_amount=detailed_vendor_entry["debit_amount"],
                        credit_amount=detailed_vendor_entry["credit_amount"],
                        initial_entry_due_date=detailed_vendor_entry[
                            "initial_entry_due_date"
                        ],
                        initial_document_type=(
                            DocumentType.Payment.value
                            if detailed_vendor_entry["initial_document_type"]
                            == "Payment"
                            else DocumentType.Invoice.value
                        ),
                        vendor_ledger_entry=vendor_ledger_entry,
                        applied_vendor_ledger_entry_no=applied_vendor_ledger_entry_no,
                        unapplied_by_entry_no=detailed_vendor_entry[
                            "unapplied_by_entry_no"
                        ],
                        unapplied=detailed_vendor_entry["unapplied"],
                        global_dimension_1=vendor_detail_dim["global_dimension_1"],
                        dimension_set=vendor_detail_dim["dimension_set"],
                        transaction_no=detailed_vendor_entry["transaction_no"],
                    )

                # Create Detailed Customer Ledger Entries
                for detailed_customer_entry in entries["detailed_customer_entries"]:
                    from sales.models import DetailedCustomerLedgerEntry
                    from common.enums import DocumentType, EntryType

                    if (
                        detailed_customer_entry["entry_type"] == "Application"
                        and not applies_to_customer_ledger
                    ):
                        continue

                    if (
                        detailed_customer_entry["entry_type"] == "Application"
                        and detailed_customer_entry["amount"] > 0
                    ):
                        customer_ledger_entry = applies_to_customer_ledger
                        applied_customer_ledger_entry_no = applies_to_customer_ledger.id
                    else:
                        customer_ledger_entry = customer_ledger_entries.get(
                            detailed_customer_entry["customer"].id
                        )
                        applied_customer_ledger_entry_no = (
                            applies_to_customer_ledger.id
                            if applies_to_customer_ledger
                            else 0
                        )

                    if customer_ledger_entry is None:
                        continue

                    customer_detail_dim = _resolve_payment_ledger_dimensions(
                        entry=detailed_customer_entry,
                        request=self.request,
                        global_dimension_1_fallback=self.global_dimension_1_value,
                        applies_to_ledger=(
                            applies_to_customer_ledger
                            if detailed_customer_entry["entry_type"] == "Application"
                            else customer_ledger_entry
                        ),
                    )

                    detailed_customer = DetailedCustomerLedgerEntry.objects.create(
                        posting_date=detailed_customer_entry["posting_date"],
                        entry_type=(
                            EntryType.initial.value
                            if detailed_customer_entry["entry_type"] == "Initial Entry"
                            else EntryType.application.value
                        ),
                        document_type=(
                            DocumentType.Payment.value
                            if detailed_customer_entry["document_type"] == "Payment"
                            else DocumentType.Invoice.value
                        ),
                        document_no=detailed_customer_entry["document_no"],
                        customer=detailed_customer_entry["customer"],
                        amount=detailed_customer_entry["amount"],
                        debit_amount=detailed_customer_entry["debit_amount"],
                        credit_amount=detailed_customer_entry["credit_amount"],
                        initial_entry_due_date=detailed_customer_entry[
                            "initial_entry_due_date"
                        ],
                        initial_document_type=(
                            DocumentType.Payment.value
                            if detailed_customer_entry["initial_document_type"]
                            == "Payment"
                            else DocumentType.Invoice.value
                        ),
                        customer_ledger_entry=customer_ledger_entry,
                        applied_customer_ledger_entry_no=applied_customer_ledger_entry_no,
                        unapplied_by_entry_no=detailed_customer_entry[
                            "unapplied_by_entry_no"
                        ],
                        unapplied=detailed_customer_entry["unapplied"],
                        global_dimension_1=customer_detail_dim["global_dimension_1"],
                        dimension_set=customer_detail_dim["dimension_set"],
                        transaction_no=detailed_customer_entry["transaction_no"],
                    )

            return {
                "success": True,
                "message": f"Successfully posted payment journal {self.payment_journal.document_no}",
                "entries_created": {
                    "gl_entries": len(entries["gl_entries"]),
                    "vendor_entries": len(entries["vendor_entries"]),
                    "customer_entries": len(entries["customer_entries"]),
                    "detailed_vendor_entries": len(entries["detailed_vendor_entries"]),
                    "detailed_customer_entries": len(
                        entries["detailed_customer_entries"]
                    ),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error posting payment journal: {str(e)}",
                "error_type": "PostingError",
                "error_details": str(e),
            }


class PaymentJournalProcessor:
    def __init__(self, payment_journal, request, receipt_no):
        self.payment_journal = payment_journal
        self.user = request.user
        self.receipt_no = receipt_no

        # Get dimension_1 value from user's dimension
        self.global_dimension_1_value = getattr(request.user, "global_dimension_1", None)

        self.global_dimension_1 = self.global_dimension_1_value

        self.dimension_set_value = getattr(
            self.payment_journal, "dimension_set", None
        ) or getattr(request.user, "dimension_set", None)

        self.gl_entries = []
        self.vendor_entries = []
        self.customer_entries = []
        self.detailed_vendor_entries = []
        self.detailed_customer_entries = []
        self.bank_account_entries = []  # For bank account ledger entries (preview only)

        self.vendor = None
        self.payables_account = None

        if self.payment_journal.account_type == "Vendor":
            self.vendor = (
                self.payment_journal.account_no
            )  # or however you get the vendor instance
            if self.vendor and hasattr(self.vendor, "vendor_posting_group"):
                self.payables_account = (
                    self.vendor.vendor_posting_group.payables_account
                )

    def _resolved_external_document_no(self):
        """Customer/vendor ledger tables require a non-null external document no."""
        return (
            (self.payment_journal.external_document_no or "").strip()
            or self.payment_journal.document_no
            or ""
        )

    def _validate_payment_journal(self):
        """Validate the payment journal entry"""
        # Check if payment journal has required fields
        if not self.payment_journal.document_no:
            raise Exception("Payment journal must have a document number")

        if not self.payment_journal.posting_date:
            raise Exception("Payment journal must have a posting date")

        if not self.payment_journal.amount:
            raise Exception("Payment journal must have an amount")

        if not self.payment_journal.account_type:
            raise Exception("Payment journal must have an account type")

        if not self.payment_journal.bal_account_type:
            raise Exception("Payment journal must have a balancing account type")

        # Validate account and balancing account are set
        if not self.payment_journal.account_no:
            raise Exception(
                f"Account is required for account type {self.payment_journal.account_type}"
            )

        if not self.payment_journal.bal_account_no:
            raise Exception(
                f"Balancing account is required for account type {self.payment_journal.bal_account_type}"
            )

        return True

    def process(self):
        """Process the payment journal and generate preview entries"""
        try:
            # Validate the payment journal
            if not self._validate_payment_journal():
                return {
                    "success": False,
                    "message": "Payment journal validation failed",
                    "entries": {},
                }

            # Generate transaction number
            transaction_no = f"PJ{self.payment_journal.document_no}-{self.payment_journal.posting_date.strftime('%Y%m%d')}-{self.payment_journal.id}"

            # Generate GL entries
            self._generate_gl_entries(transaction_no)

            # Generate ledger entries based on account type
            if self.payment_journal.account_type == "Vendor":
                self._generate_vendor_entries(transaction_no)
            elif self.payment_journal.account_type == "Customer":
                self._generate_customer_entries(transaction_no)

            return {
                "gl_entries": self.gl_entries,
                "vendor_entries": self.vendor_entries,
                "customer_entries": self.customer_entries,
                "detailed_vendor_entries": self.detailed_vendor_entries,
                "detailed_customer_entries": self.detailed_customer_entries,
                "bank_account_entries": self.bank_account_entries,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing payment journal: {e}",
                "entries": {},
            }

    def _generate_gl_entries(self, transaction_no):
        """Generate general ledger entries"""
        from financials.enums import BalacingAccountType, GeneralPostingType
        from common.enums import DocumentType

        gen_posting_type = GeneralPostingType.default.name

        # Determine the appropriate GL account based on account type
        if self.payment_journal.account_type == "Vendor":
            # For vendor payments, debit the payables account
            debit_account = self.payables_account
            if not debit_account:
                raise Exception(
                    "Payables account not found for vendor. Please check vendor posting group configuration."
                )
        elif self.payment_journal.account_type == "Customer":
            # For customer payments: Debit Cash, Credit Customer Receivables
            # Validate customer posting group and receivables account
            customer = self.payment_journal.account_no
            if not customer.customer_posting_group:
                raise Exception(
                    f"Customer {customer.name} does not have a customer posting group assigned"
                )
            if not customer.customer_posting_group.receivables_account:
                raise Exception(
                    f"Customer posting group '{customer.customer_posting_group.code}' does not have a receivables account assigned"
                )
            # For customer payments: Debit Cash (balancing account), Credit Receivables
            debit_account = self.payment_journal.bal_account_no  # Cash account
            credit_account = customer.customer_posting_group.receivables_account
        else:
            # For G/L Account payments, use the account directly
            debit_account = self.payment_journal.account_no

        # Validate that we have a valid GL account before creating entries
        if not debit_account:
            raise Exception(
                f"GL account not found for account type {self.payment_journal.account_type}"
            )

        # Debit the account (vendor payables, customer receivables, or G/L account)
        self.gl_entries.append(
            {
                "posting_date": self.payment_journal.posting_date,
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "gl_account": debit_account,
                "description": f"Payment {self.payment_journal.document_no}",
                "department_code": (
                    self.global_dimension_1_value.code if self.global_dimension_1_value else None
                ),
                "amount": self.payment_journal.amount,
                "gen_posting_type": gen_posting_type,
                "global_dimension_1": self.global_dimension_1_value,
                "balance_account_type": BalacingAccountType.GLAccount.value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

        # Handle Bank Account balancing account
        credit_gl_account = None
        if self.payment_journal.bal_account_no:
            # Check if bal_account_no is a BankAccount instance
            from bank_account.models import BankAccount

            if isinstance(self.payment_journal.bal_account_no, BankAccount):
                # Use bank account posting logic - get G/L account for preview
                from bank_account.utils import get_bank_account_gl_account
                from bank_account.enums import BankAccountDocumentType
                from payments.enums import AccountType

                try:
                    # Get G/L account from bank account posting group (for preview)
                    credit_gl_account = get_bank_account_gl_account(
                        self.payment_journal.bal_account_no
                    )

                    # Determine amount sign based on account type
                    # For vendor payments: negative (money out)
                    # For customer payments: positive (money in)
                    # For G/L payments: depends on context
                    if self.payment_journal.account_type == "Vendor":
                        bank_amount = (
                            -self.payment_journal.amount
                        )  # Negative for payment
                        bal_account_type = AccountType.VENDOR.value
                        bal_account_no = self.vendor.no if self.vendor else None
                    elif self.payment_journal.account_type == "Customer":
                        bank_amount = (
                            self.payment_journal.amount
                        )  # Positive for receipt
                        bal_account_type = AccountType.CUSTOMER.value
                        bal_account_no = (
                            self.payment_journal.account_no.no
                            if self.payment_journal.account_no
                            else None
                        )
                    else:  # G/L Account
                        bank_amount = (
                            -self.payment_journal.amount
                        )  # Negative for payment
                        bal_account_type = AccountType.GL.value
                        bal_account_no = debit_account.no if debit_account else None

                    # Store bank account entry info for actual posting (not created here, just preview info)
                    self.bank_account_entries.append(
                        {
                            "bank_account": self.payment_journal.bal_account_no,
                            "posting_date": self.payment_journal.posting_date,
                            "document_type": BankAccountDocumentType.Payment.name,
                            "document_no": self.payment_journal.document_no,
                            "description": f"Payment {self.payment_journal.document_no}",
                            "amount": bank_amount,
                            "bal_account_type": bal_account_type,
                            "bal_account_no": (
                                str(bal_account_no) if bal_account_no else None
                            ),
                            "global_dimension_1": self.global_dimension_1_value,
                            "dimension_set": self.dimension_set_value,
                            "transaction_no": transaction_no,
                            "document_date": self.payment_journal.posting_date,
                        }
                    )
                except Exception as e:
                    raise Exception(f"Failed to get bank account G/L account: {str(e)}")

        # Validate that we have a valid balancing GL account
        if not credit_gl_account and not self.payment_journal.bal_account_no:
            raise Exception("Balancing GL account is required")

        # Credit entry (Customer Receivables for customer payments, Cash for vendor payments)
        if not credit_gl_account:
            credit_gl_account = (
                credit_account
                if self.payment_journal.account_type == "Customer"
                else self.payment_journal.bal_account_no
            )
        self.gl_entries.append(
            {
                "posting_date": self.payment_journal.posting_date,
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "gl_account": credit_gl_account,
                "description": f"Payment {self.payment_journal.document_no}",
                "department_code": (
                    self.global_dimension_1_value.code if self.global_dimension_1_value else None
                ),
                "amount": -self.payment_journal.amount,
                "gen_posting_type": gen_posting_type,
                "global_dimension_1": self.global_dimension_1_value,
                "balance_account_type": BalacingAccountType.GLAccount.value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

    def _is_applied_to_ledger(self) -> bool:
        return bool(getattr(self.payment_journal, "applies_to_object_id", None))

    def _resolve_applies_to_vendor_ledger(self):
        if not self._is_applied_to_ledger():
            return None
        from purchases.models import VendorLedger

        return VendorLedger.objects.filter(
            pk=self.payment_journal.applies_to_object_id,
        ).select_related("vendor").first()

    def _resolve_applies_to_customer_ledger(self):
        if not self._is_applied_to_ledger():
            return None
        from sales.models import CustomerLedgerEntry

        return CustomerLedgerEntry.objects.filter(
            pk=self.payment_journal.applies_to_object_id,
        ).select_related("customer").first()

    def _generate_vendor_entries(self, transaction_no):
        """Generate vendor ledger entries"""
        from common.enums import DocumentType

        amount = self.payment_journal.amount
        posting_date = self.payment_journal.posting_date
        due_date = self.payment_journal.posting_date
        is_applied = self._is_applied_to_ledger()
        applies_to_ledger = self._resolve_applies_to_vendor_ledger() if is_applied else None

        self.vendor_entries.append(
            {
                "posting_date": posting_date,
                "document_date": posting_date,
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "external_document_no": self._resolved_external_document_no(),
                "vendor": self.payment_journal.account_no,
                "description": f"Payment {self.payment_journal.document_no}",
                "payment_method": self.payment_journal.payment_method,
                "original_amount": amount,
                "amount": amount,
                "remaining_amount": 0 if is_applied else amount,
                "open": not is_applied,
                "due_date": posting_date,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

        self.detailed_vendor_entries.append(
            {
                "posting_date": posting_date,
                "entry_type": "Initial Entry",
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "vendor": self.payment_journal.account_no,
                "amount": amount,
                "debit_amount": amount,
                "credit_amount": 0,
                "initial_entry_due_date": due_date,
                "initial_document_type": DocumentType.Payment.value,
                "vendor_ledger_entry": None,
                "applied_vendor_ledger_entry_no": (
                    applies_to_ledger.id if applies_to_ledger else 0
                ),
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "transaction_no": transaction_no,
            }
        )

        if not is_applied or not applies_to_ledger:
            return

        invoice_due_date = applies_to_ledger.due_date or posting_date
        apply_amount = amount

        self.detailed_vendor_entries.append(
            {
                "posting_date": posting_date,
                "entry_type": "Application",
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "vendor": self.payment_journal.account_no,
                "amount": apply_amount,
                "debit_amount": apply_amount,
                "credit_amount": 0,
                "initial_entry_due_date": invoice_due_date,
                "initial_document_type": applies_to_ledger.document_type,
                "vendor_ledger_entry": applies_to_ledger,
                "applied_vendor_ledger_entry_no": applies_to_ledger.id,
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "transaction_no": transaction_no,
            }
        )

        self.detailed_vendor_entries.append(
            {
                "posting_date": posting_date,
                "entry_type": "Application",
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "vendor": self.payment_journal.account_no,
                "amount": -apply_amount,
                "debit_amount": 0,
                "credit_amount": apply_amount,
                "initial_entry_due_date": due_date,
                "initial_document_type": DocumentType.Payment.value,
                "vendor_ledger_entry": None,
                "applied_vendor_ledger_entry_no": applies_to_ledger.id,
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "transaction_no": transaction_no,
            }
        )

    def _generate_customer_entries(self, transaction_no):
        """Generate customer ledger entries"""
        from common.enums import DocumentType

        amount = self.payment_journal.amount
        posting_date = self.payment_journal.posting_date
        due_date = self.payment_journal.posting_date
        is_applied = self._is_applied_to_ledger()
        applies_to_ledger = self._resolve_applies_to_customer_ledger() if is_applied else None

        self.customer_entries.append(
            {
                "posting_date": posting_date,
                "document_date": posting_date,
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "external_document_no": self._resolved_external_document_no(),
                "customer": self.payment_journal.account_no,
                "description": f"Payment {self.payment_journal.document_no}",
                "payment_method": self.payment_journal.payment_method,
                "original_amount": amount,
                "amount": amount,
                "remaining_amount": 0 if is_applied else amount,
                "open": not is_applied,
                "due_date": posting_date,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "user": self.user,
                "transaction_no": transaction_no,
            }
        )

        self.detailed_customer_entries.append(
            {
                "posting_date": posting_date,
                "entry_type": "Initial Entry",
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "customer": self.payment_journal.account_no,
                "amount": amount,
                "debit_amount": amount,
                "credit_amount": 0,
                "initial_entry_due_date": due_date,
                "initial_document_type": DocumentType.Payment.value,
                "customer_ledger_entry": None,
                "applied_customer_ledger_entry_no": (
                    applies_to_ledger.id if applies_to_ledger else 0
                ),
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "transaction_no": transaction_no,
            }
        )

        if not is_applied or not applies_to_ledger:
            return

        invoice_due_date = applies_to_ledger.due_date or posting_date
        apply_amount = amount

        self.detailed_customer_entries.append(
            {
                "posting_date": posting_date,
                "entry_type": "Application",
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "customer": self.payment_journal.account_no,
                "amount": apply_amount,
                "debit_amount": apply_amount,
                "credit_amount": 0,
                "initial_entry_due_date": invoice_due_date,
                "initial_document_type": applies_to_ledger.document_type,
                "customer_ledger_entry": applies_to_ledger,
                "applied_customer_ledger_entry_no": applies_to_ledger.id,
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "transaction_no": transaction_no,
            }
        )

        self.detailed_customer_entries.append(
            {
                "posting_date": posting_date,
                "entry_type": "Application",
                "document_type": DocumentType.Payment.value,
                "document_no": self.payment_journal.document_no,
                "customer": self.payment_journal.account_no,
                "amount": -apply_amount,
                "debit_amount": 0,
                "credit_amount": apply_amount,
                "initial_entry_due_date": due_date,
                "initial_document_type": DocumentType.Payment.value,
                "customer_ledger_entry": None,
                "applied_customer_ledger_entry_no": applies_to_ledger.id,
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": self.global_dimension_1_value,
                "dimension_set": self.dimension_set_value,
                "transaction_no": transaction_no,
            }
        )
