import pandas as pd


from django.contrib import admin
from django.urls import path
from django.db import models
from django.forms import TextInput, Textarea
from django.contrib import messages
from django.shortcuts import render, redirect
from openpyxl import load_workbook
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from django.utils import timezone
from financials.enums import BalacingAccountType

from financials.models import PaymentMethod
from financials.forms import UploadGLAccountsForm
from financials.models import (
    G_LAccount,
    GeneralLedgerEntry,
    GeneralLedgerSetup,
    PaymentBatch,
    Payment,
    VatEntry,
)
from purchases.models import VendorLedger
from purchases.models import DetailedVendorLedgerEntry
from financials.enums import PaymentStatus

# Import sync utilities
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json


from financials.services.chart_of_accounts import indent_chart_of_accounts as run_indent_chart


@admin.action(description="Indent Chart of Accounts")
def indent_chart_of_accounts(modeladmin, request, queryset):
    result = run_indent_chart(queryset)
    if result.errors:
        for message in result.errors:
            messages.error(request, message)
        return
    messages.success(
        request,
        f"Successfully indented the Chart of Accounts ({result.updated} accounts).",
    )


class BaseAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.CharField: {"widget": TextInput(attrs={"size": "40"})},
        models.ForeignKey: {"widget": TextInput(attrs={"size": "40"})},
        models.Choices: {"widget": TextInput(attrs={"size": "40"})},
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "cols": 40})},
    }


class G_LAccountAdmin(BaseAdmin):
    list_display = (
        "no",
        "name",
        "income_balance",
        "accountcategory",
        # "account_subcategory",
        "debit_credit",
        "accounttype",
        "balance",
        "direct_posting",
        "blocked",
        "balance",
        "indentation",
    )
    # actions = [indent_chart_of_accounts]
    search_fields = ["no", "name"]
    actions = [indent_chart_of_accounts, sync_from_json_file, sync_all_models_from_json]

    def upload_excel(self, request):
        form = UploadGLAccountsForm()

        if request.method == "POST":
            try:
                form = UploadGLAccountsForm(request.POST, request.FILES)
                if not form.is_valid():
                    messages.error(request, "Please select a valid Excel file.")
                    return render(
                        request, "admin/upload-chart-of-account.html", {"form": form}
                    )

                upload_file = request.FILES["file"]

                # Validate file type
                if not upload_file.name.endswith(".xlsx"):
                    messages.error(request, "Please upload an Excel file (.xlsx)")
                    return render(
                        request, "admin/upload-chart-of-account.html", {"form": form}
                    )

                # Load workbook and get GL Account sheet
                wb = load_workbook(upload_file)
                ws = wb["GL Account"]

                # Convert to dataframe and skip header rows
                df = pd.DataFrame([row for row in ws.values])
                df = df.iloc[3:]  # Skip first 3 rows

                # Import accounts
                success_count = 0
                for _, row in df.iterrows():
                    try:
                        G_LAccount.objects.create(
                            no=row[0],
                            name=row[1],
                            accounttype=row[2],
                            accountcategory=row[3],
                            income_balance=row[4],
                            debit_credit=row[5],
                            blocked=str(row[6]).lower() == "true",
                            direct_posting=str(row[7]).lower() == "true",
                            indentation=row[8],
                        )
                        success_count += 1
                    except Exception as e:
                        print(e)
                        messages.warning(request, f"Error in row {_+4}: {str(e)}")

                messages.success(
                    request, f"Successfully imported {success_count} accounts"
                )
                return redirect("admin:index")

            except Exception as e:
                print(e)
                messages.error(request, f"Error processing file: {str(e)}")

        return render(request, "admin/upload-chart-of-account.html", {"form": form})

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("upload-excel/", self.upload_excel, name="upload_chart_of_account"),
        ]
        return custom_urls + urls


class ReceiptNoFilter(admin.SimpleListFilter):
    title = "Receipt No."
    parameter_name = "receipt_no"

    def lookups(self, request, model_admin):
        # Get unique receipt numbers
        receipts = (
            GeneralLedgerEntry.objects.exclude(receipt_no__isnull=True)
            .values_list("receipt_no", flat=True)
            .distinct()
        )
        return [(receipt, receipt) for receipt in receipts]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(receipt_no=self.value())
        return queryset


class ReversalStatusFilter(admin.SimpleListFilter):
    title = "Reversal Status"
    parameter_name = "reversal_status"

    def lookups(self, request, model_admin):
        return (
            ("active", "Active (Not Reversed)"),
            ("reversed", "Reversed"),
            ("is_reversal", "Is Reversal Entry"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(reversed=False, reverses_entry_no__isnull=True)
        if self.value() == "reversed":
            return queryset.filter(reversed=True)
        if self.value() == "is_reversal":
            return queryset.filter(reverses_entry_no__isnull=False)


class EmptyDimensionFieldsFilter(admin.SimpleListFilter):
    """Surface G/L rows that still lack dimension set or global dimension FKs."""

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


@admin.register(GeneralLedgerEntry)
class GeneralLedgerEntryAdmin(BaseAdmin):
    list_display = (
        "gl_account",
        "posting_date",
        "document_no",
        "description",
        "document_type",
        "amount",
        "general_posting_type",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
        "reversal_status_display",
        "transaction_no",
    )
    list_select_related = (
        "gl_account",
        "dimension_set",
        "global_dimension_1",
        "global_dimension_2",
    )
    search_fields = [
        "gl_account__no",
        "gl_account__name",
        "document_no",
        "description",
        "transaction_no",
        "receipt_no",
    ]

    list_filter = (
        ReceiptNoFilter,
        ReversalStatusFilter,
        EmptyDimensionFieldsFilter,
        "reversed",
    )

    readonly_fields = [
        "reversed",
        "reversed_by_document_no",
        "reversed_date",
        "reverses_entry_no",
        "reversed_by_user",
    ]

    actions = ["find_related_item_entries"]

    class Media:
        css = {"all": ("admin/css/fix_action_buttons.css",)}

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "view-related-item-entries/",
                self.admin_site.admin_view(self.view_related_item_entries),
                name="financials_generalledgerentry_view_item_entries",
            ),
        ]
        return custom_urls + urls

    def view_related_item_entries(self, request):
        """
        View to display related Item Ledger entries in a table format
        """
        from django.shortcuts import render
        from django.urls import reverse
        from django.http import HttpResponseRedirect
        from items.models import ItemLedgerEntries

        # Get IDs from query string
        gl_entry_ids = request.GET.get("ids", "").split(",")

        if not gl_entry_ids or gl_entry_ids == [""]:
            from django.contrib import messages

            messages.error(request, "No G/L entries selected")
            return HttpResponseRedirect(
                reverse("admin:financials_generalledgerentry_changelist")
            )

        # Get the selected G/L entries
        selected_gl_entries = GeneralLedgerEntry.objects.filter(id__in=gl_entry_ids)

        # Get transaction numbers and document numbers from selected entries
        transaction_nos = list(
            selected_gl_entries.exclude(transaction_no__isnull=True)
            .exclude(transaction_no="")
            .values_list("transaction_no", flat=True)
            .distinct()
        )
        document_nos = list(
            selected_gl_entries.values_list("document_no", flat=True).distinct()
        )

        # Find ALL G/L entries related to the same transaction/document
        # This includes both the selected entries AND their paired entries (debit/credit)
        gl_entries = GeneralLedgerEntry.objects.none()

        # Build query with Q objects to combine transaction_no and document_no
        from django.db.models import Q

        query = Q()
        if transaction_nos:
            query |= Q(transaction_no__in=transaction_nos)
        if document_nos:
            query |= Q(document_no__in=document_nos)

        if query:
            gl_entries = GeneralLedgerEntry.objects.filter(query)

        # Order all G/L entries
        gl_entries = gl_entries.select_related("gl_account", "user").order_by(
            "posting_date", "document_no", "id"
        )

        # Find matching Item Ledger entries
        item_entries = ItemLedgerEntries.objects.none()

        if transaction_nos:
            item_entries = ItemLedgerEntries.objects.filter(
                transaction_no__in=transaction_nos
            )

        # If no transaction_nos, try document_nos
        if not item_entries.exists() and document_nos:
            item_entries = ItemLedgerEntries.objects.filter(
                document_no__in=document_nos
            )

        # Order entries
        item_entries = item_entries.select_related("item", "user", "location").order_by(
            "date", "document_no"
        )

        # Find related Value Entries
        from items.models import ValueEntry

        value_entries = ValueEntry.objects.none()

        # First try by item_ledger_entry_no (most accurate)
        if item_entries.exists():
            value_entries = ValueEntry.objects.filter(
                item_ledger_entry_no__in=item_entries
            )

        # If not found, try by transaction_no
        if not value_entries.exists() and transaction_nos:
            value_entries = ValueEntry.objects.filter(
                transaction_no__in=transaction_nos
            )

        # If still not found, try by document_no
        if not value_entries.exists() and document_nos:
            value_entries = ValueEntry.objects.filter(document_no__in=document_nos)

        value_entries = value_entries.select_related(
            "item", "general_product_posting_group", "inventory_posting_group"
        ).order_by("posting_date", "document_no")

        context = {
            "title": "Related Item Ledger Entries",
            "gl_entries": gl_entries,
            "item_entries": item_entries,
            "value_entries": value_entries,
            "transaction_nos": transaction_nos,
            "document_nos": document_nos,
            "selected_ids": [int(id) for id in gl_entry_ids if id],
            "opts": self.model._meta,
        }

        return render(
            request,
            "admin/financials/generalledgerentry/related_item_entries.html",
            context,
        )

    def reversal_status_display(self, obj):
        """Display reversal status with visual indicators"""
        if obj.reversed:
            return f"❌ Reversed by {obj.reversed_by_document_no or 'N/A'}"
        elif obj.reverses_entry_no:
            return f"🔄 Reverses Entry #{obj.reverses_entry_no}"
        return "✅ Active"

    reversal_status_display.short_description = "Reversal Status"

    @admin.action(description="Find Related Item Ledger Entries")
    def find_related_item_entries(self, request, queryset):
        """
        Find all Item Ledger Entries that were created when these G/L entries were posted.
        Redirects to a dedicated view page showing the entries in table format.
        """
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        # Get IDs of selected entries
        entry_ids = ",".join(str(entry.id) for entry in queryset)

        # Redirect to the view page
        url = reverse("admin:financials_generalledgerentry_view_item_entries")
        return HttpResponseRedirect(f"{url}?ids={entry_ids}")


@admin.register(VatEntry)
class VatEntryAdmin(BaseAdmin):
    list_display = (
        "id",
        "posting_date",
        "document_type",
        "document_no",
        "type",
        "vat_business_posting_group",
        "vat_product_posting_group",
        "base",
        "amount",
        "vat_percent",
    )
    list_filter = ("document_type", "type", "posting_date")
    search_fields = ("document_no",)
    readonly_fields = (
        "posting_date",
        "document_type",
        "document_no",
        "type",
        "vat_business_posting_group",
        "vat_product_posting_group",
        "base",
        "amount",
        "vat_percent",
        "vat_calculation_type",
        "vat_account",
        "general_business_posting_group",
        "general_product_posting_group",
        "global_dimension_1",
        "transaction_no",
        "user",
    )
    ordering = ("-posting_date", "-created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GeneralLedgerSetup)
class GeneralLedgerSetupAdmin(admin.ModelAdmin):
    list_display = (
        "global_dimension_1",
        "global_dimension_2",
        "vat_enabled",
        "enable_multiple_branches",
        "local_currency_code",
        "shortcut_dimension_3",
        "shortcut_dimension_4",
        "shortcut_dimension_5",
        "shortcut_dimension_6",
    )
    search_fields = [
        "global_dimension_1__code",
        "global_dimension_1__description",
        "global_dimension_2__code",
        "global_dimension_2__description",
        "shortcut_dimension_3__code",
        "shortcut_dimension_4__code",
        "shortcut_dimension_5__code",
        "shortcut_dimension_6__code",
    ]
    fieldsets = (
        (
            "Global Dimensions",
            {
                "fields": ("global_dimension_1", "global_dimension_2"),
                "description": "Primary dimensions used for filtering across the system.",
            },
        ),
        (
            "Shortcut Dimensions",
            {
                "fields": (
                    "shortcut_dimension_3",
                    "shortcut_dimension_4",
                    "shortcut_dimension_5",
                    "shortcut_dimension_6",
                ),
                "description": "Additional dimensions shown as quick-entry fields on journal and document lines.",
            },
        ),
        (
            "Regional Settings",
            {
                "fields": ("local_currency_code",),
                "description": "ISO 4217 local currency code (LCY) used for tenant amounts and reports.",
            },
        ),
        (
            "Branch Settings",
            {
                "fields": ("enable_multiple_branches",),
                "description": "When enabled, users must be assigned a branch (Global Dimension 1) and all data is filtered by branch.",
            },
        ),
        (
            "Sales Settings",
            {
                "fields": ("enable_sales_line_type_selection",),
            },
        ),
        (
            "VAT Settings",
            {
                "fields": ("vat_enabled", "default_vat_date"),
                "description": (
                    "Enable VAT calculation and posting. When enabled: (1) Run seed_vat_posting_setup. "
                    "(2) Assign VAT Business Posting Group on Customer/Vendor (not General). "
                    "(3) Assign VAT Product Posting Group on Item (not General). "
                    "Sign out and back in so the frontend shows VAT fields."
                ),
            },
        ),
    )
    autocomplete_fields = [
        "global_dimension_1",
        "global_dimension_2",
        "shortcut_dimension_3",
        "shortcut_dimension_4",
        "shortcut_dimension_5",
        "shortcut_dimension_6",
    ]


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "description",
        "bal_account_type",
        "account_no_display",
        "requires_amount_received",
    )
    search_fields = ("code", "description")
    list_filter = ("bal_account_type", "requires_amount_received")
    ordering = ("code",)
    autocomplete_fields = ["bal_account_no", "bal_bank_account_no"]
    actions = [sync_from_json_file, sync_all_models_from_json]
    fieldsets = (
        ("Basic Information", {"fields": ("code", "description")}),
        (
            "Account Configuration",
            {
                "fields": (
                    "bal_account_type",
                    "bal_account_no",
                    "bal_bank_account_no",
                ),
                "description": "Select account type and corresponding account. Only one account field should be set based on the account type.",
            },
        ),
        (
            "Sales Interface Settings",
            {
                "fields": ("requires_amount_received",),
                "description": "Configure how this payment method behaves in the sales interface",
            },
        ),
    )

    def account_no_display(self, obj):
        """Display the account number based on account type"""
        from financials.enums import BalacingAccountType

        # Django stores enum names, not values, so compare against name
        if obj.bal_account_type == BalacingAccountType.Bank_Account.name:
            if obj.bal_bank_account_no:
                return obj.bal_bank_account_no.no
            return "-"
        elif obj.bal_account_type == BalacingAccountType.GLAccount.name:
            if obj.bal_account_no:
                return obj.bal_account_no.no
            return "-"
        # Fallback: also check values in case some records use values
        elif obj.bal_account_type == BalacingAccountType.Bank_Account.value:
            if obj.bal_bank_account_no:
                return obj.bal_bank_account_no.no
            return "-"
        elif obj.bal_account_type == BalacingAccountType.GLAccount.value:
            if obj.bal_account_no:
                return obj.bal_account_no.no
            return "-"
        return "-"

    account_no_display.short_description = "Account No."


admin.site.register(
    G_LAccount,
    G_LAccountAdmin,
)


@admin.register(PaymentBatch)
class PaymentBatchAdmin(admin.ModelAdmin):
    list_display = ("name", "bal_account_type", "bal_account_no", "no_series")
    search_fields = (
        "name",
        "bal_account_type",
        "bal_account_no__no",
        "bal_account_no__name",
        "no_series__code",
    )
    list_filter = ("bal_account_type",)
    ordering = ("name",)
    autocomplete_fields = [
        "bal_account_no",
    ]


# class InlineVendorLedgerEntry(admin.TabularInline):
#     model = VendorLedger
#     extra = 1
#     fields = [
#         "posting_date",
#         "document_date",
#         "document_type",
#         "document_no",
#         "external_document_no",
#         "vendor",
#         "description",
#         "payment_method",
#         "original_amount",
#         "amount",
#         "remaining_amount",
#         "open",
#         "due_date",
#         "global_dimension_1",
#         "applies_to_id",
#     ]
#     autocomplete_fields = [
#         "payment_method",
#         "vendor",
#         "global_dimension_1",
#         "applies_to_id",
#     ]
#     readonly_fields = [
#         "posting_date",
#         "document_date",
#         "document_type",
#         "document_no",
#         "external_document_no",
#     ]

#     # def get_queryset(self, request):
#     #     # Only show open entries
#     #     return (
#     #         super()
#     #         .get_queryset(request)
#     #         .filter(applies_to_id__isnull=False)
#     #         .distinct()
#     #     )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_batch",
        "payment_method",
        "payment_date",
        "document_no",
        "external_document_no",
        "account_type",
        "message_to_recipient",
        "description",
        "amount",
    )
    search_fields = (
        "payment_batch__name",
        "payment_method__code",
        "payment_method__description",
        "document_no",
        "external_document_no",
        "account_type",
        "message_to_recipient",
        "description",
    )
    list_filter = (
        "payment_batch",
        "payment_method",
        "payment_date",
        "account_type",
        "status",
    )
    ordering = ("payment_date",)
    autocomplete_fields = [
        "payment_batch",
        "payment_method",
        "gl_account",
        "vendor_account",
        "customer_account",
        "gl_balancing_account",
    ]

    actions = ["preview_posting", "post_payment"]

    def post_payment(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single payment to post.",
                level="ERROR",
            )
            return

        payment = queryset[0]

        try:
            # Run validation first
            payment.full_clean()
            payment.clean()  # Custom model validation

            # Create a payment processor and get the entries
            processor = PaymentProcessor(payment, request)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error posting payment: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            # Use transaction.atomic to ensure all database operations succeed or none do
            from django.db import transaction

            next_vendor_entry_id = VendorLedger.objects.aggregate(
                max_id=models.Max("id")
            )["max_id"]
            next_vendor_entry_id = (next_vendor_entry_id or 0) + 1

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
                            transaction_no=bank_entry_info.get("transaction_no"),
                            document_date=bank_entry_info.get("document_date"),
                        )
                        # Bank account entry is created, G/L account is already in gl_entries
                    except Exception as e:
                        raise Exception(
                            f"Failed to create bank account ledger entry: {str(e)}"
                        )

                # Create GL entries (normalize dimension_1/2 -> dimension_set, global_dimension_1/2)
                from dimension.models import normalize_gl_entry_dimensions

                gl_entries = []
                for entry in entries["gl_entries"]:
                    entry_copy = entry.copy()
                    normalize_gl_entry_dimensions(entry_copy)
                    gl_obj = GeneralLedgerEntry(**entry_copy)
                    gl_obj.full_clean()
                    gl_entries.append(gl_obj)
                GeneralLedgerEntry.objects.bulk_create(gl_entries)

                # Create vendor ledger entries
                vendor_entries = []
                for entry in entries["vendor_entries"]:
                    entry_data = (
                        entry.copy()
                    )  # Make a copy to avoid modifying the original
                    entry_data.pop("id", None)  # Remove id if it exists
                    vendor_entries.append(VendorLedger(**entry_data))

                created_vendor_entries = VendorLedger.objects.bulk_create(
                    vendor_entries
                )

                invoice_vendor_ledger = VendorLedger.objects.filter(
                    payment=payment
                ).first()
                if invoice_vendor_ledger and created_vendor_entries:
                    from financials.ledger_application import set_ledger_applies_to

                    payment_vendor_ledger = created_vendor_entries[0]
                    set_ledger_applies_to(payment_vendor_ledger, invoice_vendor_ledger)
                    payment_vendor_ledger.save(
                        update_fields=["applies_to_id", "updated_at"]
                    )

                # Create detailed vendor ledger entries
                detailed_entries = []
                for entry in entries["detailed_vendor_entries"]:
                    entry_data = entry.copy()
                    vendor_ledger_entry_id = entry_data.pop("vendor_ledger_entry")
                    # vendor_ledger_entry_id = entry_data.pop("transaction_no")

                    # Determine the correct vendor ledger entry
                    if vendor_ledger_entry_id == next_vendor_entry_id:
                        vendor_ledger_entry = created_vendor_entries[0]
                    else:
                        vendor_ledger_entry = VendorLedger.objects.get(
                            id=vendor_ledger_entry_id
                        )

                    # Create the detailed entry
                    detailed_entries.append(
                        DetailedVendorLedgerEntry(
                            **entry_data,
                            vendor_ledger_entry=vendor_ledger_entry,
                            unapplied_by_entry_no=0,
                            unapplied=0,
                            # vendor=vendor_ledger_entry.vendor.no,
                        )
                    )

                DetailedVendorLedgerEntry.objects.bulk_create(detailed_entries)

                # Mark payment as posted
                payment.posted = PaymentStatus.Posted
                # update the vendor ledger entry
                vendor_ledger_entry = VendorLedger.objects.get(payment=payment)
                vendor_ledger_entry.payment = None
                vendor_ledger_entry.save()
                if vendor_ledger_entry.remaining_amount == 0:
                    vendor_ledger_entry.open = False
                    vendor_ledger_entry.save()
                payment.posting_date = payment.payment_date
                payment.save()

            self.message_user(
                request,
                f"Successfully posted payment {payment.document_no}",
                level="SUCCESS",
            )

        except ValidationError as e:
            if isinstance(e.message_dict.get("__all__"), list):
                error_message = e.message_dict["__all__"][0]
            else:
                error_message = str(e)
            self.message_user(
                request,
                f"Error posting payment: {error_message}",
                level="ERROR",
            )
            return

        except Exception as e:
            self.message_user(
                request,
                f"Error posting payment: {str(e)}",
                level="ERROR",
            )
            return

    post_payment.short_description = "Post Payment"

    def preview_posting(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single payment to preview posting.",
                level="ERROR",
            )
            return

        payment = queryset[0]

        try:
            # Run validation first
            payment.full_clean()
            payment.clean()  # Custom model validation

            # Create a payment processor and get the entries
            processor = PaymentProcessor(payment, request)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing posting: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            preview_entries = {
                "payment": f"Payment {payment.document_no}",
                "steps": [
                    "Posting payment to vendor/customer account",
                    "Posting to balancing account",
                ],
                "entries": entries,
            }

            return TemplateResponse(
                request,
                "admin/financials/payment/preview_posting.html",
                context={
                    "title": "Preview Posting",
                    "payment": payment,
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

    preview_posting.short_description = "Preview Posting"

    # inlines = [InlineVendorLedgerEntry]


class PaymentProcessor:
    def __init__(self, payment, request):
        self.payment = payment
        self.user = request.user
        self.gl_entries = []
        self.vendor_entries = []
        self.customer_entries = []
        self.detailed_vendor_entries = []
        self.bank_account_entries = []  # For bank account ledger entries (preview only)
        self.vendor = None  # Initialize vendor

        # Get dimension_1 value from payment first, fallback to user's dimension
        self.global_dimension_1_value = getattr(request.user, "global_dimension_1", None)

    def _validate_payment(self):
        # Check if payment has an amount
        if not self.payment.amount:
            raise ValidationError("Payment amount is required")

        # Check if payment has a payment method
        if not self.payment.payment_method:
            raise ValidationError("Payment method is required")

        # Check if payment has the correct account based on account_type
        account_mapping = {
            "G/L Account": self.payment.gl_account,
            "Vendor": self.payment.vendor_account,
            "Customer": self.payment.customer_account,
        }

        if not account_mapping.get(self.payment.account_type):
            raise ValidationError(
                f"Account is required for account type {self.payment.account_type}"
            )

        return True

    def process(self):
        try:
            if not self._validate_payment():
                return {
                    "success": False,
                    "message": "Payment validation failed",
                    "entries": {},
                }

            # Generate entries based on account type
            if self.payment.account_type == "Vendor":
                self._process_vendor_payment()
            elif self.payment.account_type == "Customer":
                self._process_customer_payment()
            elif self.payment.account_type == "G/L Account":
                self._process_gl_payment()

            return {
                "gl_entries": self.gl_entries,
                "vendor_entries": self.vendor_entries,
                "customer_entries": self.customer_entries,
                "detailed_vendor_entries": self.detailed_vendor_entries,
                "bank_account_entries": self.bank_account_entries,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error processing payment: {e}",
                "entries": {},
            }

    def _process_vendor_payment(self):
        self.vendor = self.payment.vendor_account  # Assign to instance variable
        payables_account = self.vendor.vendor_posting_group.payables_account
        transaction_no = f"P{self.payment.document_no}-{self.payment.payment_date.strftime('%Y%m%d')}-{self.payment.id}"

        # Determine balancing account (G/L Account or Bank Account)
        bal_account = None
        if (
            self.payment.payment_method.bal_account_type
            == BalacingAccountType.Bank_Account.name
            and self.payment.payment_method.bal_bank_account_no
        ):
            # Use bank account posting logic - get G/L account for preview
            from bank_account.utils import get_bank_account_gl_account
            from bank_account.enums import BankAccountDocumentType

            try:
                # Get G/L account from bank account posting group (for preview)
                bal_account = get_bank_account_gl_account(
                    self.payment.payment_method.bal_bank_account_no
                )

                # Store bank account entry info for actual posting (not created here, just preview info)
                self.bank_account_entries.append(
                    {
                        "bank_account": self.payment.payment_method.bal_bank_account_no,
                        "posting_date": self.payment.payment_date,
                        "document_type": BankAccountDocumentType.Payment.name,
                        "document_no": self.payment.document_no,
                        "description": self.payment.description
                        or f"Payment {self.payment.document_no}",
                        "amount": -self.payment.amount,  # Negative for vendor payment (money out)
                        "bal_account_type": BalacingAccountType.Vendor.name,
                        "bal_account_no": self.vendor.no,
                        "global_dimension_1": self.global_dimension_1_value,
                        "transaction_no": transaction_no,
                        "document_date": self.payment.payment_date,
                    }
                )
            except Exception as e:
                raise Exception(f"Failed to get bank account G/L account: {str(e)}")
        elif self.payment.payment_method.bal_account_no:
            # Use existing G/L Account logic
            bal_account = self.payment.payment_method.bal_account_no

        # Get the applied vendor ledger entry
        applied_vendor_ledger_entry = VendorLedger.objects.filter(
            payment=self.payment,
        ).first()

        if not applied_vendor_ledger_entry:
            raise ValidationError(
                "No vendor ledger entry found to apply this payment to. Please select an invoice to pay."
            )

        if self.payment.amount > (applied_vendor_ledger_entry.remaining_amount * -1):
            raise ValidationError(
                "Payment amount is greater than the vendor ledger entry remaining amount. Please edit the payment amount."
            )

        # Get the probable next vendor ledger entry ID
        next_vendor_entry_id = VendorLedger.objects.aggregate(max_id=models.Max("id"))[
            "max_id"
        ]
        next_vendor_entry_id = (next_vendor_entry_id or 0) + 1

        # Create GL entries
        self.gl_entries.extend(
            [
                # Debit payables account (reduce vendor liability)
                {
                    "posting_date": self.payment.payment_date,
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "gl_account": payables_account,
                    "description": self.payment.description
                    or f"Payment {self.payment.document_no}",
                    "amount": self.payment.amount,
                    "global_dimension_1": self.global_dimension_1_value,
                    "balancing_account_type": BalacingAccountType.GL_Account.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                },
                # Credit bank/cash account
                {
                    "posting_date": self.payment.payment_date,
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "gl_account": bal_account,
                    "description": self.payment.description
                    or f"Payment {self.payment.document_no}",
                    "amount": -self.payment.amount,
                    "global_dimension_1": self.global_dimension_1_value,
                    "balancing_account_type": BalacingAccountType.Vendor.value,
                    "user": self.user,
                    "transaction_no": transaction_no,
                },
            ]
        )

        # Create vendor ledger entry
        self.vendor_entries.append(
            {
                "id": next_vendor_entry_id,
                "posting_date": self.payment.payment_date,
                "document_date": self.payment.payment_date,
                "document_type": "Payment",
                "document_no": self.payment.document_no,
                "external_document_no": self.payment.external_document_no
                or self.payment.document_no,  # Use document_no as fallback
                "vendor": self.vendor,
                "description": self.payment.description
                or f"Payment {self.payment.document_no}",
                "payment_method": self.payment.payment_method,
                "original_amount": self.payment.amount,
                "amount": self.payment.amount,
                # "total_amount": self.payment.amount,
                "open": False,
                "due_date": self.payment.payment_date,
                "global_dimension_1": self.global_dimension_1_value,
                "transaction_no": transaction_no,
            }
        )

        # Create detailed vendor ledger entries (following purchase invoice pattern)
        self.detailed_vendor_entries.extend(
            [
                # 1. Initial Entry for the payment
                {
                    "posting_date": self.payment.payment_date,
                    "entry_type": "Initial Entry",
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "vendor": self.vendor.no,
                    "vendor": self.vendor,
                    "amount": -self.payment.amount,  # Negative for payment (credit)
                    "initial_entry_due_date": self.payment.payment_date,
                    "transaction_no": transaction_no,
                    "debit_amount": 0,
                    "credit_amount": self.payment.amount,
                    "initial_document_type": "Payment",
                    "vendor_ledger_entry": next_vendor_entry_id,
                    "applied_vendor_ledger_entry_no": 0,
                    "global_dimension_1": self.global_dimension_1_value,
                },
                # 2. Application entry for the payment (against the payment)
                {
                    "posting_date": self.payment.payment_date,
                    "entry_type": "Application",
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "vendor": self.vendor.no,
                    "vendor": self.vendor,
                    "amount": self.payment.amount,  # Positive for application
                    "initial_entry_due_date": self.payment.payment_date,
                    "transaction_no": transaction_no,
                    "debit_amount": self.payment.amount,
                    "credit_amount": 0,
                    "initial_document_type": "Payment",
                    "vendor_ledger_entry": next_vendor_entry_id,
                    "applied_vendor_ledger_entry_no": next_vendor_entry_id,
                    "global_dimension_1": self.global_dimension_1_value,
                },
                # 3. Application entry for the invoice being paid (against the invoice)
                {
                    "posting_date": self.payment.payment_date,
                    "entry_type": "Application",
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "vendor": self.vendor.no,
                    "vendor": self.vendor,
                    "amount": -self.payment.amount,  # Negative for application against invoice
                    "initial_entry_due_date": applied_vendor_ledger_entry.due_date,
                    "transaction_no": transaction_no,
                    "debit_amount": 0,
                    "credit_amount": self.payment.amount,
                    "initial_document_type": "Invoice",
                    "vendor_ledger_entry": applied_vendor_ledger_entry.id,
                    "applied_vendor_ledger_entry_no": next_vendor_entry_id,
                    "global_dimension_1": self.global_dimension_1_value,
                },
            ]
        )

    def _process_customer_payment(self):
        # Similar to vendor payment but for customers
        pass

    def _process_gl_payment(self):
        # Handle direct G/L account payments
        gl_account = self.payment.gl_account
        transaction_no = f"P{self.payment.document_no}-{self.payment.payment_date.strftime('%Y%m%d')}-{self.payment.id}"

        # Determine balancing account (G/L Account or Bank Account)
        bal_account = None
        if (
            self.payment.payment_method.bal_account_type
            == BalacingAccountType.Bank_Account.name
            and self.payment.payment_method.bal_bank_account_no
        ):
            # Use bank account posting logic - get G/L account for preview
            from bank_account.utils import get_bank_account_gl_account
            from bank_account.enums import BankAccountDocumentType

            try:
                # Get G/L account from bank account posting group (for preview)
                bal_account = get_bank_account_gl_account(
                    self.payment.payment_method.bal_bank_account_no
                )

                # Store bank account entry info for actual posting (not created here, just preview info)
                self.bank_account_entries.append(
                    {
                        "bank_account": self.payment.payment_method.bal_bank_account_no,
                        "posting_date": self.payment.payment_date,
                        "document_type": BankAccountDocumentType.Payment.name,
                        "document_no": self.payment.document_no,
                        "description": self.payment.description
                        or f"Payment {self.payment.document_no}",
                        "amount": -self.payment.amount,  # Negative for G/L payment (money out)
                        "bal_account_type": BalacingAccountType.GLAccount.name,
                        "bal_account_no": gl_account.no,
                        "global_dimension_1": self.global_dimension_1_value,
                        "transaction_no": transaction_no,
                        "document_date": self.payment.payment_date,
                    }
                )
            except Exception as e:
                raise Exception(f"Failed to get bank account G/L account: {str(e)}")
        elif self.payment.payment_method.bal_account_no:
            # Use existing G/L Account logic
            bal_account = self.payment.payment_method.bal_account_no

        # Create GL entries
        self.gl_entries.extend(
            [
                # Debit G/L account
                {
                    "posting_date": self.payment.payment_date,
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "gl_account": gl_account,
                    "description": self.payment.description
                    or f"Payment {self.payment.document_no}",
                    "amount": self.payment.amount,
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": "G/L Account",
                    "user": self.user,
                },
                # Credit bank/cash account
                {
                    "posting_date": self.payment.payment_date,
                    "document_type": "Payment",
                    "document_no": self.payment.document_no,
                    "gl_account": bal_account,
                    "description": self.payment.description
                    or f"Payment {self.payment.document_no}",
                    "amount": -self.payment.amount,
                    "global_dimension_1": self.global_dimension_1_value,
                    "balance_account_type": "G/L Account",
                    "user": self.user,
                },
            ]
        )
