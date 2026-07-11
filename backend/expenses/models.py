from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils.timezone import datetime

from utils.utils import BaseModel
from financials.models import PaymentMethod, G_LAccount
from setup.models import JournalSetup, NoSeriesLines
from setup.enums import JournalType
from dimension.models import DimensionValue, DimensionSet
from .enums import ExpenseDocumentType, ExpenseStatus
from purchases.models import get_today


class ExpenseCategory(BaseModel):
    """
    High-level accounting category that owns the canonical G/L mapping.
    User-defined expense types inherit their posting details from here.
    """

    code = models.CharField(
        _("Code"),
        max_length=32,
        unique=True,
        help_text=_("Short code for the category (auto-uppercase)"),
    )
    name = models.CharField(
        _("Name"),
        max_length=120,
        help_text=_("Display name shown to users when selecting a category"),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        null=True,
        help_text=_("Optional description surfaced in tooltips/modals"),
    )
    icon = models.CharField(
        _("Icon"),
        max_length=64,
        blank=True,
        null=True,
        help_text=_("Optional icon identifier for frontend cards/chips"),
    )
    default_gl_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.SET_NULL,
        verbose_name=_("Default G/L Account"),
        blank=True,
        null=True,
        related_name="expense_categories",
        help_text=_("Primary G/L account used when expense types do not override"),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_("Whether this category can be selected"),
    )
    is_system = models.BooleanField(
        _("System Category"),
        default=True,
        help_text=_("System categories are seeded and protected from deletion"),
    )

    class Meta:
        verbose_name = _("Expense Category")
        verbose_name_plural = _("Expense Categories")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """Validate expense category data."""
        from django.core.exceptions import ValidationError

        if (
            ExpenseCategory.objects.filter(code=self.code)
            .exclude(id=self.id)
            .exists()
        ):
            raise ValidationError({"code": _("Expense category code must be unique")})

        if not self.name:
            raise ValidationError({"name": _("Expense category name is required")})

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)


class ExpenseType(BaseModel):
    """
    Expense Type model for categorizing different types of expenses.
    Maps to specific G/L accounts for automatic posting.
    """

    code = models.CharField(
        _("Code"),
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Short code for the expense type (auto-uppercase)"),
    )
    name = models.CharField(
        _("Name"), max_length=100, help_text=_("Display name for the expense type")
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        null=True,
        help_text=_("Detailed description of the expense type"),
    )
    category = models.ForeignKey(
        "expenses.ExpenseCategory",
        on_delete=models.PROTECT,
        verbose_name=_("Category"),
        related_name="expense_types",
        help_text=_("Financial category that controls the default G/L account"),
        blank=True,
        null=True,
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.SET_NULL,
        verbose_name=_("Override G/L Account"),
        blank=True,
        null=True,
        related_name="expense_types",
        help_text=_("Optional override G/L account for this expense type"),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_("Whether this expense type is available for use"),
    )
    is_user_defined = models.BooleanField(
        _("User Defined"),
        default=False,
        help_text=_("Indicates whether this type was created by an end user"),
    )

    class Meta:
        verbose_name = _("Expense Type")
        verbose_name_plural = _("Expense Types")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        """Validate the model data"""
        from django.core.exceptions import ValidationError

        if (
            ExpenseType.objects.filter(code=self.code)
            .exclude(id=self.id)
            .exists()
        ):
            raise ValidationError({"code": _("Expense type code must be unique")})

        if not self.name:
            raise ValidationError({"name": _("Expense type name is required")})

    def save(self, *args, **kwargs):
        """Ensure code casing and inherit GL account when needed."""
        if self.code:
            self.code = self.code.upper()
        if self.category and not self.gl_account and self.category.default_gl_account:
            self.gl_account = self.category.default_gl_account
        super().save(*args, **kwargs)

    @property
    def effective_gl_account(self):
        """Return the resolved G/L account for this expense type."""
        if self.gl_account:
            return self.gl_account
        if self.category and self.category.default_gl_account:
            return self.category.default_gl_account
        return None


class Expense(BaseModel):
    """
    Expense model for recording expense transactions.
    Automatically maps expense types to G/L accounts and credits Cash/Bank.
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
        choices=ExpenseDocumentType.choices(),
        default=ExpenseDocumentType.EXPENSE.value,
    )
    external_document_no = models.CharField(
        _("External Document No."), max_length=50, blank=True, null=True
    )

    # Expense Information
    expense_type = models.ForeignKey(
        "expenses.ExpenseType",
        on_delete=models.SET_NULL,
        verbose_name=_("Expense Type"),
        blank=True,
        null=True,
        related_name="expenses",
    )
    description = models.TextField(_("Description"), blank=True, null=True)

    # Amount
    amount = models.IntegerField(
        _("Amount"),
        # validators=[MinValueValidator(1)],
        blank=True,
        null=True,
    )

    # Payment Method (for crediting Cash/Bank)
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        on_delete=models.SET_NULL,
        verbose_name=_("Payment Method"),
        blank=True,
        null=True,
        related_name="expenses",
    )

    # Status
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=ExpenseStatus.choices(),
        default=ExpenseStatus.OPEN.value,
    )

    # G/L Account (automatically determined by expense type)
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.SET_NULL,
        verbose_name=_("G/L Account"),
        blank=True,
        null=True,
        related_name="expenses",
    )

    # Balancing Account (Cash/Bank account)
    balancing_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.SET_NULL,
        verbose_name=_("Balancing Account"),
        blank=True,
        null=True,
        related_name="expense_balancing_entries",
    )

    # Posted Information
    posted_at = models.DateTimeField(_("Posted At"), blank=True, null=True)
    posted_by = models.ForeignKey(
        "authentication.CustomUser",
        on_delete=models.SET_NULL,
        verbose_name=_("Posted By"),
        blank=True,
        null=True,
        related_name="posted_expenses",
    )

    # Transaction Number for grouping related entries
    transaction_no = models.CharField(
        _("Transaction No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Transaction number for grouping related entries"),
    )

    # Dimensions
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="expense_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="expense_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="expense_headers",
        verbose_name=_("Dimension Set"),
    )

    class Meta:
        verbose_name = _("Expense")
        verbose_name_plural = _("Expenses")
        ordering = ["-posting_date", "-document_no"]
        indexes = [
            models.Index(fields=["posting_date", "status"], name="expense_report_idx"),
            models.Index(
                fields=["expense_type", "posting_date"], name="expense_type_date_idx"
            ),
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["expense_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["gl_account"]),
            models.Index(fields=["balancing_account"]),
            models.Index(fields=["payment_method"]),
            models.Index(fields=["posted_at"]),
            models.Index(fields=["transaction_no"]),
        ]

    def __str__(self):
        return f"{self.document_no} - {self.posting_date} ({self.amount})"

    def clean(self):
        """Validate the model data"""
        from django.core.exceptions import ValidationError

        # Validate that expense type is selected
        if not self.expense_type:
            raise ValidationError({"expense_type": "Expense type is required"})

        # Validate that amount is positive
        if self.amount and self.amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero"})

        # Payment method is required only when posting the expense
        # Allow creation without payment method for draft expenses
        if self.status == ExpenseStatus.POSTED.value and not self.payment_method:
            raise ValidationError(
                {"payment_method": "Payment method is required when posting expense"}
            )

    def save(self, *args, **kwargs):
        """Override save to auto-generate document number and set G/L account"""
        try:
            # Handle document number generation
            if not self.pk and not self.document_no:
                self.generate_document_no()

            # Auto-generate external document number if not provided
            if not self.pk and not self.external_document_no:
                self.generate_external_document_no()

            # Auto-set G/L account based on expense type (always re-evaluate to honor overrides)
            if self.expense_type:
                self.gl_account = self.get_gl_account_for_expense_type()

            # Auto-set balancing account based on payment method
            if self.payment_method and not self.balancing_account:
                self.balancing_account = self.get_balancing_account_for_payment_method()

            self.clean()
            super().save(*args, **kwargs)

        except Exception as e:
            print(f"Error saving Expense: {e}")
            raise

    def generate_document_no(self):
        """Generate document number using NoSeries"""
        try:
            # Get the expense journal setup
            expense_journal_setup = JournalSetup.objects.filter(
                journal_type=JournalType.EXPENSE.value
            ).first()

            if expense_journal_setup and expense_journal_setup.journal_no_series:
                journal_no_series = NoSeriesLines.objects.filter(
                    no_series=expense_journal_setup.journal_no_series
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
                    self.document_no = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            else:
                print("Warning: Expense journal setup not found, using default")
                self.document_no = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        except Exception as e:
            print(f"Error generating expense document number: {e}")
            self.document_no = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def generate_external_document_no(self):
        """Generate external document number"""
        try:
            # Generate a unique external document number
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            self.external_document_no = f"EXT-{timestamp}"
        except Exception as e:
            print(f"Error generating external document number: {e}")
            self.external_document_no = f"EXT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_gl_account_for_expense_type(self):
        """Get G/L account based on expense type"""
        if not self.expense_type:
            return None

        return self.expense_type.effective_gl_account

    def get_balancing_account_for_payment_method(self):
        """Get balancing account (Cash/Bank) based on payment method"""
        if not self.payment_method:
            return None

        # Return the balancing account directly from the payment method
        return self.payment_method.bal_account_no

    def get_posting_preview(self):
        """Get preview of journal entries that will be created"""
        if not self.gl_account or not self.balancing_account:
            return None

        # Generate transaction number for grouping related entries
        transaction_no = (
            f"EXP{self.document_no}-{self.posting_date.strftime('%Y%m%d')}-{self.id}"
        )

        entries = [
            {
                "gl_account": self.gl_account,
                "description": f"Expense: {self.description}",
                "amount": self.amount,
                "type": "debit",
                "transaction_no": transaction_no,
            },
            {
                "gl_account": self.balancing_account,
                "description": f"Payment for: {self.description}",
                "amount": self.amount,
                "type": "credit",
                "transaction_no": transaction_no,
            },
        ]

        return entries

    def post_expense(self, user):
        """Post expense to G/L accounts"""
        from financials.models import GeneralLedgerEntry
        from django.utils import timezone

        if not self.gl_account or not self.balancing_account:
            raise ValueError("G/L accounts must be set before posting")

        if self.status == ExpenseStatus.POSTED.value:
            raise ValueError("Expense has already been posted")

        # Generate transaction number for grouping related entries
        transaction_no = (
            f"EXP{self.document_no}-{self.posting_date.strftime('%Y%m%d')}-{self.id}"
        )

        entries = []

        # Create debit entry (expense account)
        from dimension.models import get_posting_dimension_payload
        from financials.enums import DOCUMENT_TYPE as GLDocumentType
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        dim_payload = get_posting_dimension_payload(
            global_dimension_1=self.global_dimension_1
            or getattr(user, "global_dimension_1", None),
            global_dimension_2=self.global_dimension_2
            or getattr(user, "global_dimension_2", None),
            dimension_set=self.dimension_set,
            gl_setup=gl_setup,
        )
        if not dim_payload.get("dimension_set") or not dim_payload.get(
            "global_dimension_1"
        ):
            raise ValueError(
                "Expense is missing branch dimensions. Save the expense again or set Global Dimension 1."
            )
        debit_entry = GeneralLedgerEntry.objects.create(
            gl_account=self.gl_account,
            posting_date=self.posting_date,
            description=f"Expense: {self.description}",
            amount=self.amount,
            transaction_no=transaction_no,
            document_no=self.document_no,
            document_type=GLDocumentType.Expense.name,
            user=user,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )
        entries.append(debit_entry)

        # Create credit entry (balancing account)
        credit_entry = GeneralLedgerEntry.objects.create(
            gl_account=self.balancing_account,
            posting_date=self.posting_date,
            description=f"Payment for: {self.description}",
            amount=-self.amount,  # Negative amount for credit
            transaction_no=transaction_no,
            document_no=self.document_no,
            document_type=GLDocumentType.Expense.name,
            user=user,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )
        entries.append(credit_entry)

        # Update expense status
        self.status = ExpenseStatus.POSTED.value
        self.posted_at = timezone.now()
        self.posted_by = user
        self.transaction_no = transaction_no
        self.save()

        return entries

    def reverse_expense(self, user):
        """Reverse posted expense by creating double entries"""
        from financials.models import GeneralLedgerEntry
        from django.utils import timezone

        if self.status != ExpenseStatus.POSTED.value:
            raise ValueError("Only posted expenses can be reversed")

        if not self.gl_account or not self.balancing_account:
            raise ValueError("Cannot reverse expense - missing G/L accounts")

        # Generate reverse transaction number
        reverse_transaction_no = (
            f"REV{self.document_no}-{self.posting_date.strftime('%Y%m%d')}-{self.id}"
        )

        entries = []

        # Create reverse debit entry (credit the expense account)
        from dimension.models import get_posting_dimension_payload
        from financials.enums import DOCUMENT_TYPE as GLDocumentType
        from financials.models import GeneralLedgerSetup

        gl_setup = GeneralLedgerSetup.objects.first()
        dim_payload = get_posting_dimension_payload(
            global_dimension_1=self.global_dimension_1
            or getattr(user, "global_dimension_1", None),
            global_dimension_2=self.global_dimension_2
            or getattr(user, "global_dimension_2", None),
            dimension_set=self.dimension_set,
            gl_setup=gl_setup,
        )
        reverse_debit_entry = GeneralLedgerEntry.objects.create(
            gl_account=self.gl_account,
            posting_date=self.posting_date,
            description=f"Reverse Expense: {self.description}",
            amount=-self.amount,  # Negative amount to reverse the original debit
            transaction_no=reverse_transaction_no,
            document_no=f"REV-{self.document_no}",
            document_type=GLDocumentType.ExpenseReversal.name,
            user=user,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )
        entries.append(reverse_debit_entry)

        # Create reverse credit entry (debit the balancing account)
        reverse_credit_entry = GeneralLedgerEntry.objects.create(
            gl_account=self.balancing_account,
            posting_date=self.posting_date,
            description=f"Reverse Payment for: {self.description}",
            amount=self.amount,  # Positive amount to reverse the original credit
            transaction_no=reverse_transaction_no,
            document_no=f"REV-{self.document_no}",
            document_type=GLDocumentType.ExpenseReversal.name,
            user=user,
            dimension_set=dim_payload["dimension_set"],
            global_dimension_1=dim_payload["global_dimension_1"],
            global_dimension_2=dim_payload["global_dimension_2"],
        )
        entries.append(reverse_credit_entry)

        # Update expense status to reversed
        self.status = ExpenseStatus.REVERSED.value
        self.save()

        return entries
