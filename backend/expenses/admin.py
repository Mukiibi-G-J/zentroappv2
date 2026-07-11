from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from django.db import transaction
import uuid

from .models import Expense, ExpenseType, ExpenseCategory
from .enums import ExpenseStatus


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "default_gl_account_display",
        "is_active",
        "is_system",
    ]
    list_filter = ["is_active", "is_system"]
    search_fields = ["code", "name", "description"]
    ordering = ["name"]
    readonly_fields = ["is_system", "created_at", "updated_at", "system_id"]

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "code",
                    "name",
                    "description",
                    "icon",
                )
            },
        ),
        (
            _("Accounting"),
            {"fields": ("default_gl_account",)},
        ),
        (
            _("Status"),
            {"fields": ("is_active", "is_system")},
        ),
        (
            _("System"),
            {"fields": ("created_at", "updated_at", "system_id"), "classes": ("collapse",)},
        ),
    )

    def default_gl_account_display(self, obj):
        if obj.default_gl_account:
            return f"{obj.default_gl_account.no} - {obj.default_gl_account.name}"
        return "-"

    default_gl_account_display.short_description = "Default G/L Account"


@admin.register(ExpenseType)
class ExpenseTypeAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "category",
        "gl_account_display",
        "is_active",
    ]

    list_filter = [
        "is_active",
        "gl_account",
    ]

    search_fields = [
        "code",
        "name",
        "description",
        "gl_account__name",
        "gl_account__no",
    ]

    list_editable = [
        "is_active",
    ]

    ordering = ["name"]

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "code",
                    "name",
                    "description",
                    "category",
                )
            },
        ),
        (
            _("G/L Account"),
            {
                "fields": ("gl_account",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Settings"),
            {
                "fields": ("is_active",),
            },
        ),
    )

    def gl_account_display(self, obj):
        """Display G/L account with link"""
        if obj.gl_account:
            return format_html(
                '<a href="{}">{}</a>',
                reverse("admin:financials_g_laccount_change", args=[obj.gl_account.no]),
                f"{obj.gl_account.no} - {obj.gl_account.name}",
            )
        return "-"

    gl_account_display.short_description = "G/L Account"


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "document_no",
        "posting_date",
        "expense_type",
        "description",
        "amount_display",
        "payment_method",
        "status_display",
        "gl_account_display",
        "balancing_account_display",
        "external_document_no",
        "transaction_no",
        "global_dimension_1",   
        "global_dimension_2",
        "dimension_set",
    ]

    list_filter = [
        "status",
        "expense_type",
        "posting_date",
        "payment_method",
        "created_at",
    ]

    search_fields = [
        "document_no",
        "description",
        "external_document_no",
        "expense_type__name",
        "expense_type__code",
        "gl_account__name",
        "balancing_account__name",
    ]

    readonly_fields = [
        "document_no",
        "gl_account",
        "balancing_account",
        "transaction_no",
        "posted_at",
        "posted_by",
        "created_at",
        "updated_at",
    ]

    actions = ["preview_posting", "post_expense", "post_expenses", "reverse_expense"]

    date_hierarchy = "posting_date"
    ordering = ["-posting_date", "-document_no"]

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
                    "global_dimension_1",
                    "global_dimension_2",
                    "dimension_set",
                )
            },
        ),
        (
            _("Expense Information"),
            {
                "fields": (
                    "expense_type",
                    "amount",
                    "payment_method",
                )
            },
        ),
        (
            _("Status"),
            {"fields": ("status",)},
        ),
        (
            _("G/L Accounts"),
            {
                "fields": (
                    "gl_account",
                    "balancing_account",
                    "transaction_no",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Posting Information"),
            {
                "fields": (
                    "posted_at",
                    "posted_by",
                ),
                "classes": ("collapse",),
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

    def get_queryset(self, request):
        """Filter by company - in tenant context, all data belongs to current tenant"""
        qs = super().get_queryset(request)
        # In tenant context, all data is already filtered by company
        return qs

    def has_add_permission(self, request):
        """Only superusers can add expenses"""
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        """Only superusers can change expenses"""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete expenses"""
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on status"""
        readonly_fields = list(super().get_readonly_fields(request, obj))

        if obj and obj.status == ExpenseStatus.POSTED.value:
            readonly_fields.extend(
                ["expense_type", "description", "amount", "payment_method"]
            )

        return readonly_fields

    def get_actions(self, request):
        """Custom actions for expense management"""
        actions = super().get_actions(request)

        if request.user.is_superuser:
            actions["post_expenses"] = (
                self.post_expenses,
                "post_expenses",
                "Post selected expenses",
            )

        return actions

    def post_expenses(self, request, queryset):
        """Post selected expenses"""
        success_count = 0
        error_count = 0

        for expense in queryset:
            try:
                if expense.status == ExpenseStatus.OPEN.value:
                    expense.post_expense(request.user)
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1

        if success_count > 0:
            self.message_user(
                request,
                f"Successfully posted {success_count} expense(s). {error_count} failed.",
            )
        else:
            self.message_user(
                request,
                f"Failed to post expenses. {error_count} errors occurred.",
                level="ERROR",
            )

    post_expenses.short_description = "Post selected expenses"

    def reverse_expense(self, request, queryset):
        """Reverse posted expense by creating double entries"""
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single expense to reverse.",
                level="ERROR",
            )
            return

        expense = queryset[0]

        if expense.status != ExpenseStatus.POSTED.value:
            self.message_user(
                request,
                "Only posted expenses can be reversed.",
                level="ERROR",
            )
            return

        if not expense.gl_account or not expense.balancing_account:
            self.message_user(
                request,
                "Cannot reverse expense - missing G/L accounts.",
                level="ERROR",
            )
            return

        try:
            with transaction.atomic():
                # Create reverse entries
                reverse_entries = expense.reverse_expense(request.user)

                self.message_user(
                    request,
                    f"Expense {expense.document_no} reversed successfully. {len(reverse_entries)} reverse G/L entries created.",
                    level="SUCCESS",
                )

        except Exception as e:
            self.message_user(
                request,
                f"Failed to reverse expense: {str(e)}",
                level="ERROR",
            )

    reverse_expense.short_description = "Reverse posted expense"

    def preview_posting(self, request, queryset):
        """Preview posting for selected expense"""
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single expense to preview posting.",
                level="ERROR",
            )
            return

        expense = queryset[0]

        if expense.status == ExpenseStatus.POSTED.value:
            self.message_user(
                request,
                "This expense has already been posted.",
                level="ERROR",
            )
            return

        if not expense.gl_account or not expense.balancing_account:
            self.message_user(
                request,
                "G/L accounts must be set before previewing posting.",
                level="ERROR",
            )
            return

        try:
            preview_entries = expense.get_posting_preview()

            if not preview_entries:
                self.message_user(
                    request,
                    "Cannot generate preview - missing G/L accounts.",
                    level="ERROR",
                )
                return

            context = {
                "expense": expense,
                "preview_entries": preview_entries,
                "title": f"Preview Posting for {expense.document_no}",
            }

            return TemplateResponse(
                request,
                "admin/expenses/expense/preview_posting.html",
                context,
            )

        except Exception as e:
            self.message_user(
                request,
                f"Error generating preview: {str(e)}",
                level="ERROR",
            )

    def post_expense(self, request, queryset):
        """Post selected expense"""
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single expense to post.",
                level="ERROR",
            )
            return

        expense = queryset[0]

        if expense.status == ExpenseStatus.POSTED.value:
            self.message_user(
                request,
                "This expense has already been posted.",
                level="ERROR",
            )
            return

        if not expense.gl_account or not expense.balancing_account:
            self.message_user(
                request,
                "G/L accounts must be set before posting.",
                level="ERROR",
            )
            return

        try:
            with transaction.atomic():
                posted_entries = expense.post_expense(request.user)

                self.message_user(
                    request,
                    f"Expense {expense.document_no} posted successfully. {len(posted_entries)} G/L entries created.",
                    level="SUCCESS",
                )

        except Exception as e:
            self.message_user(
                request,
                f"Failed to post expense: {str(e)}",
                level="ERROR",
            )

    def amount_display(self, obj):
        """Format amount display"""
        if obj.amount:
            formatted_amount = "{:,}".format(obj.amount)
            return format_html(
                '<span style="color: red;">UGX {}</span>', formatted_amount
            )
        return "-"

    amount_display.short_description = "Amount"

    def status_display(self, obj):
        """Format status display with colors"""
        status_colors = {
            ExpenseStatus.OPEN.value: "orange",
            ExpenseStatus.POSTED.value: "green",
            ExpenseStatus.REVERSED.value: "red",
        }

        color = status_colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = "Status"

    def gl_account_display(self, obj):
        """Display G/L account with link"""
        if obj.gl_account:
            return format_html(
                '<a href="{}">{}</a>',
                reverse("admin:financials_g_laccount_change", args=[obj.gl_account.no]),
                f"{obj.gl_account.no} - {obj.gl_account.name}",
            )
        return "-"

    gl_account_display.short_description = "G/L Account"

    def balancing_account_display(self, obj):
        """Display balancing account with link"""
        if obj.balancing_account:
            return format_html(
                '<a href="{}">{}</a>',
                reverse(
                    "admin:financials_g_laccount_change",
                    args=[obj.balancing_account.no],
                ),
                f"{obj.balancing_account.no} - {obj.balancing_account.name}",
            )
        return "-"

    balancing_account_display.short_description = "Balancing Account"
