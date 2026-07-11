from django.contrib import admin
from django.db import models
from django.forms import TextInput, Textarea
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

from .models import (
    BankAccount,
    BankAccountLedgerEntry,
    BankAccountPostingGroup,
)
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json


class BaseAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.CharField: {"widget": TextInput(attrs={"size": "40"})},
        models.ForeignKey: {"widget": TextInput(attrs={"size": "40"})},
        models.Choices: {"widget": TextInput(attrs={"size": "40"})},
        models.TextField: {"widget": Textarea(attrs={"rows": 4, "cols": 40})},
    }


@admin.register(BankAccountPostingGroup)
class BankAccountPostingGroupAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "gl_account_no",
    )
    search_fields = ("code", "bank_account__no", "bank_account__name")
    ordering = ("code",)
    autocomplete_fields = ["bank_account"]
    actions = [sync_from_json_file, sync_all_models_from_json]

    def gl_account_no(self, obj):
        """Display G/L Account No."""
        if obj.bank_account:
            return f"{obj.bank_account.no} - {obj.bank_account.name}"
        return "-"

    gl_account_no.short_description = _("G/L Account No.")


class BankAccountLedgerEntryInline(admin.TabularInline):
    model = BankAccountLedgerEntry
    extra = 0
    fields = [
        "entry_no",
        "posting_date",
        "document_type",
        "document_no",
        "description",
        "amount",
        "remaining_amount",
        "statement_status",
        "reversed",
        "global_dimension_1",
        "dimension_set",
    ]
    readonly_fields = [
        "entry_no",
        "posting_date",
        "document_type",
        "document_no",
        "description",
        "amount",
        "remaining_amount",
        "statement_status",
        "reversed",
    ]
    can_delete = False
    show_change_link = True


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = (
        "no",
        "name",
        "bank_account_no",
        "bank_account_posting_group",
        "min_balance",
        "debit_amount",
        "credit_amount",
        "balance",
    )
    search_fields = (
        "no",
        "name",
        "bank_account_no",
        "bank_branch_no",
        "bank_account_posting_group__code",
        "address",
        "contact",
    )
    list_filter = ("bank_account_posting_group",)
    ordering = ("no",)
    autocomplete_fields = ["bank_account_posting_group"]
    readonly_fields = [
        "no",
        "debit_amount",
        "credit_amount",
        "balance",
        "created_at",
        "updated_at",
    ]
    inlines = [BankAccountLedgerEntryInline]
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "no",
                    "name",
                    "address",
                    "contact",
                    "bank_account_no",
                    "bank_branch_no",
                    "min_balance",
                )
            },
        ),
        (
            "Posting",
            {
                "fields": ("bank_account_posting_group",),
            },
        ),
        (
            "Balance Information",
            {
                "fields": (
                    "debit_amount",
                    "credit_amount",
                    "balance",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    actions = [sync_from_json_file, sync_all_models_from_json]

    def debit_amount(self, obj):
        """Display debit amount"""
        return f"{obj.debit_amount:,.2f}"

    debit_amount.short_description = _("Debit Amount")

    def credit_amount(self, obj):
        """Display credit amount"""
        return f"{obj.credit_amount:,.2f}"

    credit_amount.short_description = _("Credit Amount")

    def balance(self, obj):
        """Display balance"""
        return f"{obj.balance:,.2f}"

    balance.short_description = _("Balance")


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
            return queryset.filter(reversed=False, reversed_entry_no__isnull=True)
        if self.value() == "reversed":
            return queryset.filter(reversed=True)
        if self.value() == "is_reversal":
            return queryset.filter(reversed_entry_no__isnull=False)


@admin.register(BankAccountLedgerEntry)
class BankAccountLedgerEntryAdmin(BaseAdmin):
    list_display = (
        "entry_no",
        "bank_account_no",
        "posting_date",
        "document_type",
        "document_no",
        "description",
        "amount",
        "debit_amount",
        "credit_amount",
        "remaining_amount",
        "statement_status",
        "reversal_status_display",
    )
    search_fields = [
        "entry_no",
        "bank_account_no__no",
        "bank_account_no__name",
        "document_no",
        "description",
        "statement_no",
    ]
    list_filter = (
        ReversalStatusFilter,
        "reversed",
        "posting_date",
        "document_type",
        "statement_status",
        "bank_account_no",
    )
    readonly_fields = [
        "entry_no",
        "debit_amount",
        "credit_amount",
        "reversed",
        "reversed_by_entry_no",
        "reversed_entry_no",
        "reversed_by_user",
        "reversed_date",
    ]
    autocomplete_fields = [
        "bank_account_no",
        "bank_account_posting_group",
        "global_dimension_1",
        "user",
    ]
    ordering = ["-posting_date", "-entry_no"]
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "entry_no",
                    "bank_account_no",
                    "posting_date",
                    "document_date",
                    "document_type",
                    "document_no",
                    "description",
                )
            },
        ),
        (
            "Amounts",
            {
                "fields": (
                    "amount",
                    "remaining_amount",
                    "debit_amount",
                    "credit_amount",
                )
            },
        ),
        (
            "Posting",
            {
                "fields": (
                    "bank_account_posting_group",
                    "bal_account_type",
                    "bal_account_no",
                )
            },
        ),
        (
            "Statement",
            {
                "fields": (
                    "statement_status",
                    "statement_no",
                    "statement_line_no",
                )
            },
        ),
        (
            "Dimensions",
            {
                "fields": ("global_dimension_1",),
            },
        ),
        (
            "Reversal",
            {
                "fields": (
                    "reversed",
                    "reversed_by_entry_no",
                    "reversed_entry_no",
                    "reversed_by_user",
                    "reversed_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "System",
            {
                "fields": ("user",),
                "classes": ("collapse",),
            },
        ),
    )

    def debit_amount(self, obj):
        """Display debit amount"""
        return f"{obj.debit_amount:,.2f}"

    debit_amount.short_description = _("Debit Amount")

    def credit_amount(self, obj):
        """Display credit amount"""
        return f"{obj.credit_amount:,.2f}"

    credit_amount.short_description = _("Credit Amount")

    def reversal_status_display(self, obj):
        """Display reversal status with visual indicators"""
        if obj.reversed:
            return f"❌ Reversed by Entry #{obj.reversed_by_entry_no or 'N/A'}"
        elif obj.reversed_entry_no:
            return f"🔄 Reverses Entry #{obj.reversed_entry_no}"
        return "✅ Active"

    reversal_status_display.short_description = "Reversal Status"
