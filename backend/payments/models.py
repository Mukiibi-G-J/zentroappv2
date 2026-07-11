from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils.timezone import datetime

from utils.utils import BaseModel
from financials.models import PaymentMethod
from setup.models import JournalSetup, NoSeriesLines
from setup.enums import JournalType
from .enums import DocumentType, AccountType, PaymentStatus, ApplicationStatus
from purchases.models import get_today

# Create your models here.


class PaymentJournal(BaseModel):
    """
    Payment Journal model for recording payment transactions.
    Supports generic foreign keys to Customer, Vendor, and GLAccount models.
    """

    # Basic Document Information
    document_no = models.CharField(
        _("Document No."), max_length=50, unique=True, blank=True, null=True
    )
    posting_date = models.DateField(
        _("Posting Date"),
        default=get_today,
        blank=True,
        null=True,
    )
    document_type = models.CharField(
        _("Document Type"),
        max_length=20,
        choices=DocumentType.choices(),
        default=DocumentType.PAYMENT.value,
    )
    external_document_no = models.CharField(
        _("External Document No."), max_length=50, blank=True, null=True
    )

    # Account Information (Generic Foreign Key)
    account_type = models.CharField(
        _("Account Type"),
        max_length=20,
        choices=AccountType.choices(),
        blank=True,
        null=True,
    )
    account_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="payment_journal_accounts",
        verbose_name=_("Account Content Type"),
        blank=True,
        null=True,
    )
    account_object_id = models.PositiveIntegerField(
        _("Account Object ID"), blank=True, null=True
    )
    account_no = GenericForeignKey("account_content_type", "account_object_id")

    # Description and Payment Method
    description = models.TextField(_("Description"), blank=True, null=True)
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        on_delete=models.SET_NULL,
        verbose_name=_("Payment Method"),
        blank=True,
        null=True,
        related_name="payment_journals",
    )

    # Amount
    amount = models.IntegerField(
        _("Amount"),
        # validators=[MinValueValidator(Decimal("1.00"))],
        blank=True,
        null=True,
    )

    # Balancing Account Information (Generic Foreign Key)
    bal_account_type = models.CharField(
        _("Balancing Account Type"),
        max_length=20,
        choices=AccountType.choices(),
        blank=True,
        null=True,
    )
    bal_account_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="payment_journal_balancing_accounts",
        verbose_name=_("Balancing Account Content Type"),
        blank=True,
        null=True,
    )
    bal_account_object_id = models.PositiveIntegerField(
        _("Balancing Account Object ID"), blank=True, null=True
    )
    bal_account_no = GenericForeignKey(
        "bal_account_content_type", "bal_account_object_id"
    )

    # Status and Application Information
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=PaymentStatus.choices(),
        default=PaymentStatus.OPEN.value,
    )
    application_status = models.CharField(
        _("Application Status"),
        max_length=20,
        choices=ApplicationStatus.choices(),
        default=ApplicationStatus.UNAPPLIED.value,
    )

    # Applies To Information (Generic Foreign Key)
    applies_to_doc_type = models.CharField(
        _("Applies To Document Type"), max_length=20, blank=True, null=True
    )
    applies_to_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="payment_journal_applies_to",
        verbose_name=_("Applies To Content Type"),
        blank=True,
        null=True,
    )
    applies_to_object_id = models.PositiveIntegerField(
        _("Applies To Object ID"), blank=True, null=True
    )
    applies_to_doc = GenericForeignKey(
        "applies_to_content_type", "applies_to_object_id"
    )

    class Meta:
        verbose_name = _("Payment Journal Entry")
        verbose_name_plural = _("Payment Journal Entries")
        ordering = ["-posting_date", "-document_no"]
        indexes = [
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["account_type"]),
            models.Index(fields=["bal_account_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["application_status"]),
            models.Index(fields=["account_content_type", "account_object_id"]),
            models.Index(fields=["bal_account_content_type", "bal_account_object_id"]),
            models.Index(fields=["applies_to_content_type", "applies_to_object_id"]),
            models.Index(fields=["payment_method"]),
        ]

    def __str__(self):
        return f"{self.document_no} - {self.posting_date} ({self.amount})"

    def recalculate_amount(self):
        """Set header amount to the sum of line amounts."""
        from django.db.models import Sum

        total = self.lines.aggregate(total=Sum('amount'))['total'] or 0
        if self.amount != total:
            self.amount = total
            super().save(update_fields=['amount', 'updated_at'])

    def clean(self):
        """Validate the model data"""
        from django.core.exceptions import ValidationError

        # Validate that account_no is set based on account_type - only if account_type is provided and not just a default value
        if (
            self.account_type
            and self.account_type.strip()
            and self.account_type
            not in [
                "",
                "Customer",
                "Vendor",
            ]  # Skip validation for empty or default value
            and not self.account_no
        ):
            raise ValidationError(
                {
                    "account_no": f"Account number is required for account type {self.account_type}"
                }
            )

        # Validate that bal_account_no is set based on bal_account_type - only if bal_account_type is provided and not just a default value
        if (
            self.bal_account_type
            and self.bal_account_type.strip()
            and self.bal_account_type
            not in ["", "G/L Account"]  # Skip validation for empty or default value
            and not self.bal_account_no
        ):
            raise ValidationError(
                {
                    "bal_account_no": f"Balancing account number is required for account type {self.bal_account_type}"
                }
            )

        # Validate that applies_to fields are both set or both empty - only if applies_to_doc_type is provided
        # if (
        #     self.applies_to_doc_type
        #     and self.applies_to_doc_type.strip()
        #     and bool(self.applies_to_doc_type) != bool(self.applies_to_doc)
        # ):
        #     raise ValidationError(
        #         {
        #             "applies_to_doc_type": "Both applies to document type and document must be provided together",
        #             "applies_to_doc": "Both applies to document type and document must be provided together",
        #         }
        #     )

    def save(self, *args, **kwargs):
        """Override save method to generate document number if not provided"""
        try:
            # Handle document number generation
            if not self.pk and not self.document_no:
                try:
                    payment_journal_setup = JournalSetup.objects.filter(
                        journal_type=JournalType.PAYMENT.value
                    ).first()

                    if payment_journal_setup:
                        journal_no_series = NoSeriesLines.objects.filter(
                            no_series=payment_journal_setup.journal_no_series
                        ).first()

                        if journal_no_series:
                            increment_by = journal_no_series.increment_by
                            if journal_no_series.last_used_number:
                                # Import the increment function
                                from items.models import increment_item_number

                                self.document_no = increment_item_number(
                                    journal_no_series.last_used_number, increment_by
                                )
                                journal_no_series.last_used_number = self.document_no
                                journal_no_series.last_used_date = datetime.now()
                                journal_no_series.save()
                            else:
                                self.document_no = journal_no_series.start_number
                                journal_no_series.last_used_number = self.document_no
                                journal_no_series.last_used_date = datetime.now()
                                journal_no_series.save()

                        else:

                            self.document_no = (
                                f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            )
                    else:
                        print("Warning: Payment journal setup not found, using default")
                        self.document_no = (
                            f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        )

                except Exception as e:
                    print(f"Error generating payment document number: {e}")
                    self.document_no = f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            if self.account_type and AccountType.VENDOR.value in self.account_type:
                print("Vendor account type found")
                self.applies_to_doc_type = DocumentType.INVOICE.value
                self.bal_account_type = AccountType.GL.value
            if self.account_type and AccountType.CUSTOMER.value in self.account_type:
                print("Customer account type found")
                self.applies_to_doc_type = DocumentType.INVOICE.value
                self.bal_account_type = AccountType.GL.value
            self.clean()
            super().save(*args, **kwargs)

        except Exception as e:
            print(f"Error saving PaymentJournal: {e}")
            raise

    @property
    def account_name(self):
        """Get the name of the account"""
        print(f"Getting account_name for PaymentJournal {self.id}")
        print(f"account_content_type_id: {self.account_content_type_id}")
        print(f"account_object_id: {self.account_object_id}")
        print(f"account_no: {self.account_no}")

        if self.account_no:
            print(f"account_no type: {type(self.account_no)}")
            print(f"account_no attributes: {dir(self.account_no)}")
            if hasattr(self.account_no, "name"):
                name = self.account_no.name
                print(f"Found name attribute: {name}")
                return name
            elif hasattr(self.account_no, "no"):
                name = f"{self.account_no.no} - {getattr(self.account_no, 'name', '')}"
                print(f"Found no attribute: {name}")
                return name
        elif self.account_content_type_id and self.account_object_id:
            # Try to manually resolve the GenericForeignKey
            try:
                content_type = ContentType.objects.get(id=self.account_content_type_id)
                model_class = content_type.model_class()
                if model_class:
                    obj = model_class.objects.get(id=self.account_object_id)
                    if hasattr(obj, "name"):
                        return obj.name
                    elif hasattr(obj, "no"):
                        return f"{obj.no} - {getattr(obj, 'name', '')}"
            except (ContentType.DoesNotExist, Exception):
                print(
                    f"Could not resolve GenericForeignKey for content_type_id={self.account_content_type_id}, object_id={self.account_object_id}"
                )

        print("No account_no found, returning Unknown Account")
        return "Unknown Account"

    @property
    def bal_account_name(self):
        """Get the name of the balancing account"""
        if self.bal_account_no:
            if hasattr(self.bal_account_no, "name"):
                return self.bal_account_no.name
            elif hasattr(self.bal_account_no, "no"):
                return f"{self.bal_account_no.no} - {getattr(self.bal_account_no, 'name', '')}"
        return "Unknown Balancing Account"

    @property
    def payment_method_name(self):
        """Get the name of the payment method"""
        if self.payment_method:
            if hasattr(self.payment_method, "description"):
                return f"{getattr(self.payment_method, 'code', '')} - {self.payment_method.description}"
            elif hasattr(self.payment_method, "name"):
                return self.payment_method.name
            elif hasattr(self.payment_method, "id"):
                return f"Payment Method {self.payment_method.id}"
        return "Not specified"

    @property
    def applies_to_doc_name(self):
        """Get the name of the document this payment applies to"""
        if self.applies_to_doc:
            if hasattr(self.applies_to_doc, "document_no"):
                return self.applies_to_doc.document_no
            elif hasattr(self.applies_to_doc, "name"):
                return self.applies_to_doc.name
            elif hasattr(self.applies_to_doc, "id"):
                return f"Document {self.applies_to_doc.id}"
        return "Unknown Document"


class PaymentLine(BaseModel):
    """
    A single allocation line belonging to a PaymentJournal document.
    Enables one payment header to span multiple account entries.
    """
    payment = models.ForeignKey(
        PaymentJournal,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_("Payment"),
    )
    line_no = models.IntegerField(_("Line No."), default=10000)
    account_type = models.CharField(
        _("Account Type"),
        max_length=20,
        choices=AccountType.choices(),
        blank=True,
        null=True,
    )
    account_no = models.CharField(_("Account No."), max_length=50, blank=True, null=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    amount = models.IntegerField(_("Amount"), blank=True, null=True)
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_lines",
        verbose_name=_("Payment Method"),
    )

    class Meta:
        verbose_name = _("Payment Line")
        verbose_name_plural = _("Payment Lines")
        ordering = ["payment", "line_no"]
        indexes = [
            models.Index(fields=["payment", "line_no"]),
        ]

    def __str__(self):
        return f"{getattr(self.payment, 'document_no', '')} - Line {self.line_no}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.payment_id:
            self.payment.recalculate_amount()

    def delete(self, *args, **kwargs):
        payment = self.payment
        super().delete(*args, **kwargs)
        if payment.pk:
            payment.recalculate_amount()


class CashReceiptJournalBatch(BaseModel):
    """
    Named batch (journal) for grouping Cash Receipt lines.
    Equivalent to a General Journal Batch.
    """
    name = models.CharField(_("Name"), max_length=50, unique=True)
    description = models.CharField(_("Description"), max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = _("Cash Receipt Journal Batch")
        verbose_name_plural = _("Cash Receipt Journal Batches")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super().save(*args, **kwargs)


class CashReceiptJournalLine(BaseModel):
    """
    A single line in a Cash Receipt Journal worksheet.
    Tracks customer payments received and bank/GL allocations.
    """
    batch_name = models.CharField(_("Batch Name"), max_length=50)
    line_no = models.IntegerField(_("Line No."), default=10000)
    posting_date = models.DateField(_("Posting Date"), default=get_today, blank=True, null=True)
    document_no = models.CharField(_("Document No."), max_length=50, blank=True, null=True)
    account_type = models.CharField(
        _("Account Type"),
        max_length=20,
        choices=AccountType.choices(),
        default=AccountType.CUSTOMER.value,
        blank=True,
        null=True,
    )
    account_no = models.CharField(_("Account No."), max_length=50, blank=True, null=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    amount = models.IntegerField(_("Amount"), blank=True, null=True)
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cash_receipt_lines",
        verbose_name=_("Payment Method"),
    )
    bal_account_type = models.CharField(
        _("Bal. Account Type"),
        max_length=20,
        choices=AccountType.choices(),
        blank=True,
        null=True,
    )
    bal_account_no = models.CharField(_("Bal. Account No."), max_length=50, blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=PaymentStatus.choices(),
        default=PaymentStatus.OPEN.value,
    )

    class Meta:
        verbose_name = _("Cash Receipt Journal Line")
        verbose_name_plural = _("Cash Receipt Journal Lines")
        ordering = ["batch_name", "line_no"]
        indexes = [
            models.Index(fields=["batch_name", "line_no"]),
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.batch_name} - Line {self.line_no} ({self.document_no})"
