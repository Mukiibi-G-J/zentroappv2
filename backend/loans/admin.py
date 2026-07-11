from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.template.response import TemplateResponse
from django.core.exceptions import ValidationError
from django.db import transaction
import uuid

from .models import Loan, LoanRepayment
from .processors import (
    LoanPostingProcessor,
    LoanPostingFinalPoster,
    LoanRepaymentPostingProcessor,
    LoanRepaymentPostingFinalPoster,
)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = [
        "loan_no",
        "lender_name",
        "loan_type",
        "loan_amount",
        "disbursement_date",
        "interest_rate",
        "repayment_period",
        "status",
        "posted",
    ]

    list_filter = [
        "loan_type",
        "status",
        "posted",
        "disbursement_date",
        "repayment_account",
    ]

    search_fields = [
        "loan_no",
        "lender_name",
        "purpose",
    ]

    readonly_fields = [
        "loan_no",
        "posted",
        "posted_date",
        "posted_by",
        "created_at",
        "updated_at",
    ]

    class Media:
        js = ("admin/js/loans.js",)

    fieldsets = (
        (
            _("Document Information"),
            {
                "fields": (
                    "loan_no",
                    "disbursement_date",
                    "status",
                )
            },
        ),
        (
            _("Loan Details"),
            {
                "fields": (
                    "loan_type",
                    "lender_name",
                    "loan_amount",
                    "interest_rate",
                    "repayment_period",
                    "repayment_account",
                    "bank_account",
                    "purpose",
                )
            },
        ),
        (
            _("Posting Information"),
            {
                "fields": (
                    "posted",
                    "posted_date",
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

    actions = ["preview_posting", "post_loan"]

    def preview_posting(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single loan to preview posting.",
                level="ERROR",
            )
            return

        loan = queryset[0]
        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Run validation first
            loan.full_clean()
            loan.clean()

            # If validation passes, proceed with posting preview
            processor = LoanPostingProcessor(loan, request, receipt_no)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing posting: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            preview_entries = {
                "loan": f"Loan {loan.id} -> {loan.loan_no}",
                "steps": [
                    "Posting loan disbursement",
                    "Posting to loan payable account",
                    "Posting to cash/bank account",
                ],
                "entries": entries,
            }

            return TemplateResponse(
                request,
                "admin/loans/loan/preview_posting.html",
                context={
                    "title": "Preview Posting",
                    "loan": loan,
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

    def post_loan(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single loan to post.",
                level="ERROR",
            )
            return

        loan = queryset[0]

        if loan.posted:
            self.message_user(
                request,
                "This loan has already been posted.",
                level="ERROR",
            )
            return

        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Validate tracking specifications for all lines before posting
            loan.full_clean()
            loan.clean()

            # Create posting processor and post the loan
            processor = LoanPostingProcessor(loan, request, receipt_no)
            preview_data = processor.process()

            if isinstance(preview_data, dict) and not preview_data.get("success", True):
                error_msg = preview_data.get("message", "Unknown error during processing")
                self.message_user(request, error_msg, level="ERROR")
                return

            # Check if validation failed (empty preview data)
            if not preview_data or (
                isinstance(preview_data, dict)
                and not preview_data.get("gl_entries")
            ):
                self.message_user(
                    request,
                    "Error: No GL entries generated for posting.",
                    level="ERROR",
                )
                return

            # Start transaction to ensure all entries are created or none are
            with transaction.atomic():
                # Run the final posting logic
                poster = LoanPostingFinalPoster(preview_data, loan, request.user, receipt_no)
                result = poster.post_to_tables()

                if result["success"]:
                    # Update the loan status to Posted
                    loan.posted = True
                    loan.posted_date = timezone.now().date()
                    loan.posted_by = request.user
                    loan.status = "Posted"
                    loan.save()

                    self.message_user(
                        request,
                        f"Successfully posted loan {loan.loan_no}",
                        level="SUCCESS",
                    )
                else:
                    error_msg = result.get("message", "Unknown error during posting")
                    self.message_user(request, error_msg, level="ERROR")
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = str(e)
            if error_msg.startswith("Error posting loan: "):
                error_msg = error_msg.replace("Error posting loan: ", "")
            if error_msg.startswith("Error processing loan: "):
                error_msg = error_msg.replace("Error processing loan: ", "")

            self.message_user(request, error_msg, level="ERROR")
            raise Exception(error_msg)

    post_loan.short_description = "Post Loan"


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = [
        "repayment_no",
        "loan",
        "payment_date",
        "amount_paid",
        "payment_method",
        "status",
        "posted",
    ]

    list_filter = [
        "status",
        "posted",
        "payment_date",
        "payment_method",
    ]

    search_fields = [
        "repayment_no",
        "loan__loan_no",
        "loan__lender_name",
    ]

    readonly_fields = [
        "repayment_no",
        "posted",
        "posted_date",
        "posted_by",
        "created_at",
        "updated_at",
    ]

    class Media:
        js = ("admin/js/loan_repayments.js",)

    fieldsets = (
        (
            _("Document Information"),
            {
                "fields": (
                    "repayment_no",
                    "loan",
                    "payment_date",
                    "status",
                )
            },
        ),
        (
            _("Payment Details"),
            {
                "fields": (
                    "amount_paid",
                    "payment_method",
                    "bank_account",
                )
            },
        ),
        (
            _("Posting Information"),
            {
                "fields": (
                    "posted",
                    "posted_date",
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

    actions = ["preview_posting", "post_repayment"]

    def preview_posting(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single loan repayment to preview posting.",
                level="ERROR",
            )
            return

        repayment = queryset[0]
        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Run validation first
            repayment.full_clean()
            repayment.clean()

            # If validation passes, proceed with posting preview
            processor = LoanRepaymentPostingProcessor(repayment, request, receipt_no)
            entries = processor.process()

            if isinstance(entries, dict) and not entries.get("success", True):
                self.message_user(
                    request,
                    f"Error previewing posting: {entries.get('message', 'Unknown error')}",
                    level="ERROR",
                )
                return

            preview_entries = {
                "repayment": f"Loan Repayment {repayment.id} -> {repayment.repayment_no}",
                "steps": [
                    "Posting loan principal payment",
                    "Posting interest expense",
                    "Posting to cash/bank account",
                ],
                "entries": entries,
            }

            return TemplateResponse(
                request,
                "admin/loans/loanrepayment/preview_posting.html",
                context={
                    "title": "Preview Posting",
                    "repayment": repayment,
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

    def post_repayment(self, request, queryset):
        if len(queryset) != 1:
            self.message_user(
                request,
                "Please select a single loan repayment to post.",
                level="ERROR",
            )
            return

        repayment = queryset[0]

        if repayment.posted:
            self.message_user(
                request,
                "This loan repayment has already been posted.",
                level="ERROR",
            )
            return

        receipt_no = (
            f"RCP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        )

        try:
            # Validate before posting
            repayment.full_clean()
            repayment.clean()

            # Create posting processor and post the repayment
            processor = LoanRepaymentPostingProcessor(repayment, request, receipt_no)
            preview_data = processor.process()

            if isinstance(preview_data, dict) and not preview_data.get("success", True):
                error_msg = preview_data.get("message", "Unknown error during processing")
                self.message_user(request, error_msg, level="ERROR")
                return

            # Check if validation failed (empty preview data)
            if not preview_data or (
                isinstance(preview_data, dict)
                and not preview_data.get("gl_entries")
            ):
                self.message_user(
                    request,
                    "Error: No GL entries generated for posting.",
                    level="ERROR",
                )
                return

            # Start transaction to ensure all entries are created or none are
            with transaction.atomic():
                # Calculate principal and interest before posting (processor calculates this)
                # The processor will calculate and update the repayment object
                # But we need to save it after posting
                
                # Run the final posting logic
                poster = LoanRepaymentPostingFinalPoster(
                    preview_data, repayment, request.user, receipt_no
                )
                result = poster.post_to_tables()

                if result["success"]:
                    # Save the calculated principal and interest amounts
                    repayment.save()
                    
                    # Update the repayment status to Posted
                    repayment.posted = True
                    repayment.posted_date = timezone.now().date()
                    repayment.posted_by = request.user
                    repayment.status = "Posted"
                    repayment.save()

                    self.message_user(
                        request,
                        f"Successfully posted loan repayment {repayment.repayment_no}",
                        level="SUCCESS",
                    )
                else:
                    error_msg = result.get("message", "Unknown error during posting")
                    self.message_user(request, error_msg, level="ERROR")
                    raise Exception(error_msg)

        except Exception as e:
            error_msg = str(e)
            if error_msg.startswith("Error posting loan repayment: "):
                error_msg = error_msg.replace("Error posting loan repayment: ", "")
            if error_msg.startswith("Error processing repayment: "):
                error_msg = error_msg.replace("Error processing repayment: ", "")

            self.message_user(request, error_msg, level="ERROR")
            raise Exception(error_msg)

    post_repayment.short_description = "Post Repayment"

