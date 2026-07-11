from django.contrib import admin, messages
from django.contrib.admin.utils import get_deleted_objects
from django.core.exceptions import ValidationError
from django.db import models, connection
from django.db.utils import ProgrammingError
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.urls import reverse

from prepayment.models import (
    Preayment,
    PreaymentLine,
    PreaymentLineInstallmentHistory,
    PreaymentLineInstallmentDraft,
    PreaymentInstallmentDraft,
    PreaymentInstallmentHistory,
    PrepaymentStatus,
)
from financials.models import PaymentMethod


class PrepaymentLineInline(admin.TabularInline):
    model = PreaymentLine
    extra = 1
    fields = [
        "item",
        "description",
        "quantity",
        "unit_price",
        "amount",
        "deposit_amount",
        "preview_deposit_total",
        "installment_amount",
        "deposit_percent",
        "prepayment_amount_invoiced",
        "prepayment_amount_to_deduct",
        "prepayment_amount_deducted",
        "created_at",
    ]
    readonly_fields = [
        "amount",
        "preview_deposit_total",
        "deposit_percent",
        "prepayment_amount_invoiced",
        "prepayment_amount_deducted",
        "created_at",
        "updated_at",
    ]


class InstallmentDraftInline(admin.StackedInline):
    model = PreaymentLineInstallmentDraft
    extra = 0
    fk_name = "line"
    fields = ["amount", "updated_by", "updated_at"]
    readonly_fields = ["updated_at"]


@admin.register(PreaymentLine)
class PreaymentLineAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document",
        "description",
        "quantity",
        "unit_price",
        "amount",
        "deposit_amount",
        "installment_draft_display",
        "preview_deposit_display",
        "prepayment_amount_invoiced",
    ]
    search_fields = ["document__document_no", "description", "item__item_name", "item__no"]
    inlines = [InstallmentDraftInline]

    @admin.display(description="New Installment (Draft)")
    def installment_draft_display(self, obj):
        return getattr(obj, "installment_draft_amount", 0)

    @admin.display(description="Preview Deposit")
    def preview_deposit_display(self, obj):
        return getattr(obj, "preview_deposit_total", 0)


@admin.register(PreaymentLineInstallmentHistory)
class PreaymentLineInstallmentHistoryAdmin(admin.ModelAdmin):
    list_display = ["id", "line", "amount", "transaction_no", "applied_by", "created_at"]
    search_fields = ["transaction_no", "line__document__document_no"]
    readonly_fields = ["line", "amount", "transaction_no", "applied_by", "created_at", "updated_at"]


@admin.register(PreaymentLineInstallmentDraft)
class PreaymentLineInstallmentDraftAdmin(admin.ModelAdmin):
    list_display = ["id", "line", "amount", "updated_by", "updated_at", "created_at"]
    search_fields = ["line__document__document_no", "line__id"]
    autocomplete_fields = ["line", "updated_by"]


@admin.register(PreaymentInstallmentDraft)
class PreaymentInstallmentDraftAdmin(admin.ModelAdmin):
    list_display = ["id", "document", "amount", "updated_by", "updated_at", "created_at"]
    search_fields = ["document__document_no"]
    autocomplete_fields = ["document", "updated_by"]


@admin.register(PreaymentInstallmentHistory)
class PreaymentInstallmentHistoryAdmin(admin.ModelAdmin):
    list_display = ["id", "document", "amount", "transaction_no", "applied_by", "created_at"]
    search_fields = ["transaction_no", "document__document_no"]
    readonly_fields = ["document", "amount", "transaction_no", "applied_by", "created_at", "updated_at"]


@admin.register(Preayment)
class PreaymentAdmin(admin.ModelAdmin):
    list_display = [
        "document_no",
        "customer",
        "posting_date",
        "status",
        "total_amount",
        "currency",
    ]
    search_fields = ["document_no", "customer__name", "customer__no"]
    list_filter = ["status", "posting_date", "currency"]
    inlines = [PrepaymentLineInline]

    def get_queryset(self, request):
        """Get queryset, deferring new fields until migrations are run."""
        queryset = super().get_queryset(request)
        # Temporarily defer new fields to avoid SELECT errors until migrations are run
        # TODO: Remove this defer after running migrations that add these columns
        queryset = queryset.defer('total_prepayment_to_deduct', 'deposit_percent')
        return queryset

    def get_deleted_objects(self, objs, request):
        """
        Override to ensure queryset defers new fields during deletion.
        This prevents errors when Django's deletion collector queries related objects.
        """
        # Reload objects using the admin's queryset which defers new fields
        # This ensures the deletion collector works with deferred fields
        obj_ids = [obj.pk for obj in objs]
        deferred_objs = list(self.get_queryset(request).filter(pk__in=obj_ids))
        
        try:
            # Call the parent method with the reloaded objects
            return get_deleted_objects(deferred_objs, request, self.admin_site)
        except ProgrammingError:
            # If deletion collector fails due to missing columns, return simplified response
            # This allows deletion to proceed even if related object queries fail
            # TODO: Remove this try/except after running migrations
            deleted_objects = [str(obj) for obj in deferred_objs]
            model_count = {self.model._meta.verbose_name_plural: len(deferred_objs)}
            return (deleted_objects, model_count, set(), [])

    @admin.display(description="Prepmt. Amt. to Deduct")
    def total_prepayment_to_deduct_display(self, obj):
        """Display total_prepayment_to_deduct, handling missing column."""
        try:
            return getattr(obj, 'total_prepayment_to_deduct', 0) or 0
        except Exception:
            return 0

    @admin.display(description="Prepmt. Line Amount %")
    def deposit_percent_display(self, obj):
        """Display deposit_percent, handling missing column."""
        try:
            return getattr(obj, 'deposit_percent', 0) or 0
        except Exception:
            return 0

    readonly_fields = [
        "document_no",
        "total_amount",
        "deposit_percent_display",
        "preview_deposit_total",
        "total_prepayment_to_deduct_display",
        "posted_at",
        "posted_by",
        "posted_transaction_no",
        "created_at",
        "updated_at",
    ]
    fieldsets = [
        (
            "Document",
            {
                "fields": (
                    "document_no",
                    "customer",
                    "contact_person",
                    "description",
                    "status",
                    "currency",
                    "total_amount",
                )
            },
        ),
        (
            "Prepayment Details",
            {
                "fields": (
                    "total_prepayment",
                    "total_prepayment_invoiced",
                    "total_prepayment_deducted",
                    "total_prepayment_to_deduct_display",
                    "deposit_percent_display",
                    "preview_deposit_total",
                )
            },
        ),
        (
            "Dates",
            {"fields": ("document_date", "posting_date", "due_date")},
        ),
        (
            "Posting",
            {"fields": ("posted_at", "posted_by", "posted_transaction_no")},
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at")},
        ),
    ]
    actions = [
        "preview_posting",
        "preview_final_invoice_posting",
        "post_prepayment",
        "post_final_invoice",
        "view_posted_invoices",
        "mark_as_posted",
        "mark_as_cancelled",
    ]

    @admin.action(description="🔍 Preview Posting")
    def preview_posting(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select a single prepayment to preview.",
                level=messages.ERROR,
            )
            return

        preayment = queryset.first()
        try:
            preview_data = preayment.build_posting_preview(request.user)
        except Exception as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return

        steps = [
            "Posting prepayment document",
            "Posting customer ledger entries",
        ]
        if preview_data.get("has_cash_payment"):
            steps.append("Posting balancing account entry")

        preview_entries = {
            "invoice": f"Preayment {preayment.document_no}",
            "steps": steps,
            "entries": preview_data["entries"],
        }

        return TemplateResponse(
            request,
            "admin/prepayment/preayment/preview_posting.html",
            {
                "title": "Preview Preayment Posting",
                "preayment": preayment,
                "preview_entries": preview_entries,
                "opts": self.model._meta,
            },
        )

    @admin.action(description="📋 Preview Final Invoice Posting")
    def preview_final_invoice_posting(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select a single prepayment to preview final invoice posting.",
                level=messages.ERROR,
            )
            return

        preayment = queryset.first()
        
        # Check if payment_method_id is provided (from form submission)
        payment_method_id = request.GET.get("payment_method_id") or request.POST.get("payment_method_id")
        
        # If no payment method selected, show selection form
        if not payment_method_id:
            payment_methods = PaymentMethod.objects.all().order_by("description")
            return TemplateResponse(
                request,
                "admin/prepayment/preayment/select_payment_method.html",
                {
                    "title": "Select Payment Method for Final Invoice Preview",
                    "preayment": preayment,
                    "payment_methods": payment_methods,
                    "opts": self.model._meta,
                    "action": "preview_final_invoice_posting",
                },
            )
        
        # Get payment method and show preview
        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id)
        except PaymentMethod.DoesNotExist:
            self.message_user(
                request,
                f"Payment method with id {payment_method_id} not found.",
                level=messages.ERROR,
            )
            return redirect(
                reverse("admin:prepayment_preayment_changelist")
            )
        
        try:
            preview_data = preayment.build_final_invoice_posting_preview(
                request.user, payment_method=payment_method
            )
        except Exception as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return

        steps = [
            "Posting inventory reduction",
            "Posting cost of goods sold",
            "Posting sales revenue",
            "Posting prepayment deduction",
            "Posting customer receivables",
        ]
        
        # Add payment step if payment method is not NOT_PAID
        if payment_method and payment_method.code != "NOT_PAID":
            steps.append("Posting payment entries")

        preview_entries = {
            "invoice": f"Final Invoice {preayment.document_no}",
            "steps": steps,
            "entries": preview_data["entries"],
            "total_invoice_amount": preview_data["total_invoice_amount"],
            "prepayment_to_deduct": preview_data["prepayment_to_deduct"],
            "net_receivables": preview_data["net_receivables"],
            "posted_invoice_lines": preview_data.get("posted_invoice_lines", []),
            "payment_method": payment_method,
        }

        return TemplateResponse(
            request,
            "admin/prepayment/preayment/preview_posting.html",
            {
                "title": "Preview Final Invoice Posting",
                "preayment": preayment,
                "preview_entries": preview_entries,
                "opts": self.model._meta,
            },
        )

    @admin.action(description="📄 Post Final Invoice")
    def post_final_invoice(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select a single prepayment to post final invoice.",
                level=messages.ERROR,
            )
            return

        preayment = queryset.first()
        
        # Check if payment_method_id is provided (from form submission)
        payment_method_id = request.GET.get("payment_method_id") or request.POST.get("payment_method_id")
        
        # If no payment method selected, show selection form
        if not payment_method_id:
            payment_methods = PaymentMethod.objects.all().order_by("description")
            return TemplateResponse(
                request,
                "admin/prepayment/preayment/select_payment_method.html",
                {
                    "title": "Select Payment Method for Final Invoice Posting",
                    "preayment": preayment,
                    "payment_methods": payment_methods,
                    "opts": self.model._meta,
                    "action": "post_final_invoice",
                },
            )
        
        # Get payment method and post
        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id)
        except PaymentMethod.DoesNotExist:
            self.message_user(
                request,
                f"Payment method with id {payment_method_id} not found.",
                level=messages.ERROR,
            )
            return redirect(
                reverse("admin:prepayment_preayment_changelist")
            )
        
        try:
            result = preayment.post_final_invoice(request.user, payment_method=payment_method)
            posted_invoice = result["posted_invoice"]
            self.message_user(
                request,
                f"Final invoice {posted_invoice.no} posted successfully for prepayment {preayment.document_no}.",
                level=messages.SUCCESS,
            )
        except ValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        except Exception as exc:
            self.message_user(
                request, f"An error occurred while posting: {exc}", level=messages.ERROR
            )

    @admin.action(description="🧾 Post Prepayment Invoice")
    def post_prepayment(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select a single prepayment to post.",
                level=messages.ERROR,
            )
            return

        preayment = queryset.first()
        try:
            result = preayment.post_document(request.user)
            posted_invoice = result["posted_invoice"]
            self.message_user(
                request,
                f"Prepayment {preayment.document_no} posted as invoice {posted_invoice.no}.",
                level=messages.SUCCESS,
            )
        except ValidationError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        except Exception as exc:
            self.message_user(
                request, f"An error occurred while posting: {exc}", level=messages.ERROR
            )

    @admin.action(description="📄 View Posted Prepayment Invoices")
    def view_posted_invoices(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select a single prepayment to view its posted invoices.",
                level=messages.ERROR,
            )
            return

        preayment = queryset.first()
        invoices = preayment.posted_sales_invoices.all()

        return TemplateResponse(
            request,
            "admin/prepayment/preayment/posted_invoices.html",
            {
                "title": f"Posted Invoices for {preayment.document_no}",
                "preayment": preayment,
                "invoices": invoices,
                "opts": self.model._meta,
            },
        )

    @admin.action(description="Mark selected prepayments as posted")
    def mark_as_posted(self, request, queryset):
        updated = queryset.filter(status=PrepaymentStatus.DRAFT).update(
            status=PrepaymentStatus.POSTED
        )
        self.message_user(request, f"{updated} prepayment(s) marked as posted.")

    @admin.action(description="Mark selected prepayments as cancelled")
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.exclude(status=PrepaymentStatus.POSTED).update(
            status=PrepaymentStatus.CANCELLED
        )
        self.message_user(request, f"{updated} prepayment(s) cancelled.")

    def delete_queryset(self, request, queryset):
        """
        Override to handle deletion when new models don't exist in DB yet.
        """
        try:
            # Try normal deletion
            super().delete_queryset(request, queryset)
        except ProgrammingError as e:
            # If deletion fails due to missing tables (new models not migrated yet),
            # use raw SQL to delete directly, bypassing the collector
            # TODO: Remove this try/except after running migrations
            if "does not exist" in str(e):
                # Get object IDs before deletion
                obj_ids = list(queryset.values_list('id', flat=True))
                count = len(obj_ids)
                
                if count > 0:
                    # Use raw SQL to delete directly from the table
                    # This bypasses Django's ORM and the deletion collector
                    table_name = self.model._meta.db_table
                    with connection.cursor() as cursor:
                        placeholders = ','.join(['%s'] * count)
                        cursor.execute(
                            f'DELETE FROM "{table_name}" WHERE "id" IN ({placeholders})',
                            obj_ids
                        )
                    
                    self.message_user(
                        request,
                        f"Successfully deleted {count} prepayment(s). Note: Related objects check was skipped due to pending migrations.",
                        level=messages.WARNING,
                    )
                else:
                    self.message_user(
                        request,
                        "No objects selected for deletion.",
                        level=messages.WARNING,
                    )
            else:
                raise
