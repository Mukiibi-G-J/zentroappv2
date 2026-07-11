from django.db import models
from django.db.models import Sum, Q
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import datetime

from utils.utils import BaseModel
from setup.models import NoSeriesLines
from items.models import increment_item_number
from financials.enums import BalacingAccountType
from dimension.models import DimensionValue, DimensionSet
from authentication.models import CustomUser as User

from . import enums


class BankAccountPostingGroup(BaseModel):
    """Bank Account Posting Group - defines G/L accounts for bank account transactions"""

    code = models.CharField(
        _("Code"),
        max_length=20,
        unique=True,
        primary_key=True,
        help_text=_("Unique code for the bank account posting group"),
    )
    description = models.CharField(
        _("Description"),
        max_length=100,
        help_text=_("Description of the bank account posting group"),
    )
    bank_account = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name=_("Bank Account"),
        on_delete=models.PROTECT,
        related_name="bank_account_posting_groups",
        help_text=_("General ledger account number for bank account"),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Bank Account Posting Group")
        verbose_name_plural = _("Bank Account Posting Groups")
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"


class BankAccount(BaseModel):
    """Bank Account - tracks bank accounts and their balances"""

    no = models.CharField(
        verbose_name="No.",
        max_length=20,
        primary_key=True,
        unique=True,
        blank=False,
        null=False,
        help_text=_("Bank Account Number"),
    )
    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text=_("Name of the bank account"),
    )
    address = models.TextField(
        _("Address"),
        blank=True,
        null=True,
        help_text=_("Address of the bank"),
    )
    contact = models.TextField(
        _("Contact"),
        blank=True,
        null=True,
        help_text=_("Contact information for the bank"),
    )
    bank_account_no = models.CharField(
        _("Bank Account No."),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Bank account number at the bank"),
    )
    bank_branch_no = models.CharField(
        _("Bank Branch No."),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Bank branch number"),
    )
    min_balance = models.DecimalField(
        _("Min. Balance"),
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text=_("Minimum balance required for this account"),
    )
    bank_account_posting_group = models.ForeignKey(
        BankAccountPostingGroup,
        verbose_name=_("Bank Acc. Posting Group"),
        on_delete=models.SET_NULL,
        related_name="bank_accounts",
        blank=True,
        null=True,
        to_field="code",
        help_text=_("Posting group for this bank account"),
    )

    # FlowFields - calculated from Bank Account Ledger Entries
    @property
    def debit_amount(self):
        """Sum of Debit Amount from Bank Account Ledger Entries"""
        if not self.no:
            return 0.00
        # Sum positive amounts (debits)
        from django.db.models import Case, When, DecimalField, Value

        return (
            BankAccountLedgerEntry.objects.filter(
                bank_account_no=self.no,
                reversed=False,
            ).aggregate(
                total=Sum(
                    Case(
                        When(amount__gt=0, then="amount"),
                        default=Value(0),
                        output_field=DecimalField(max_digits=15, decimal_places=2),
                    )
                )
            )[
                "total"
            ]
            or 0.00
        )

    @property
    def credit_amount(self):
        """Sum of Credit Amount from Bank Account Ledger Entries"""
        if not self.no:
            return 0.00
        # Sum negative amounts as positive (credits)
        from django.db.models import Case, When, DecimalField, Value

        return abs(
            BankAccountLedgerEntry.objects.filter(
                bank_account_no=self.no,
                reversed=False,
            ).aggregate(
                total=Sum(
                    Case(
                        When(amount__lt=0, then="amount"),
                        default=Value(0),
                        output_field=DecimalField(max_digits=15, decimal_places=2),
                    )
                )
            )[
                "total"
            ]
            or 0.00
        )

    @property
    def balance(self):
        """Current balance (debit_amount - credit_amount)"""
        if not self.no:
            return 0.00
        return float(self.debit_amount) - float(self.credit_amount)

    def balance_at_date(self, date):
        """Balance at a specific date - Sum of Amount from Bank Account Ledger Entries filtered by date"""
        if not self.no:
            return 0.00
        return (
            BankAccountLedgerEntry.objects.filter(
                bank_account_no=self.no,
                posting_date__lte=date,
                reversed=False,
            ).aggregate(Sum("amount"))["amount__sum"]
            or 0.00
        )

    def save(self, *args, **kwargs):
        """Auto-generate bank account number using No. Series if not provided"""
        if not self.no:
            try:
                from setup.models import BankAccountSetup

                bank_account_setup = BankAccountSetup.objects.all().first()
                if bank_account_setup and bank_account_setup.bank_account_no_series:
                    bank_account_no_series = NoSeriesLines.objects.filter(
                        no_series=bank_account_setup.bank_account_no_series
                    ).first()

                    if bank_account_no_series:
                        increment_by = bank_account_no_series.increment_by
                        if bank_account_no_series.last_used_number:
                            self.no = increment_item_number(
                                bank_account_no_series.last_used_number, increment_by
                            )
                            bank_account_no_series.last_used_number = self.no
                            bank_account_no_series.last_used_date = (
                                datetime.now().date()
                            )
                            bank_account_no_series.save()
                        else:
                            self.no = bank_account_no_series.start_number
                            bank_account_no_series.last_used_number = self.no
                            bank_account_no_series.last_used_date = (
                                datetime.now().date()
                            )
                            bank_account_no_series.save()
                    else:
                        raise ValidationError(
                            "No number series lines found for bank account numbers. Please configure the number series."
                        )
                else:
                    raise ValidationError(
                        "Bank Account Setup not found or No. Series not configured. Please configure Bank Account Setup first."
                    )
            except Exception as e:
                raise ValidationError(f"Error generating bank account number: {str(e)}")

        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Bank Account")
        verbose_name_plural = _("Bank Accounts")
        ordering = ["no"]
        indexes = [
            models.Index(fields=["no"]),
            models.Index(fields=["bank_account_posting_group"]),
        ]

    def __str__(self):
        return f"{self.no} - {self.name}"


class BankAccountLedgerEntry(BaseModel):
    """Bank Account Ledger Entry - tracks all transactions for bank accounts"""

    entry_no = models.AutoField(
        _("Entry No."),
        primary_key=True,
        help_text=_("Automatic entry number"),
    )
    bank_account_no = models.ForeignKey(
        BankAccount,
        verbose_name=_("Bank Account No."),
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        to_field="no",
        help_text=_("Bank account for this entry"),
    )
    posting_date = models.DateField(
        _("Posting Date"),
        help_text=_("Date when the entry was posted"),
    )
    document_type = models.CharField(
        _("Document Type"),
        max_length=50,
        choices=enums.BankAccountDocumentType.choices(),
        default=enums.BankAccountDocumentType.Payment.name,
        help_text=_("Type of document that created this entry"),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        null=True,
        help_text=_("Description of the transaction"),
    )
    amount = models.DecimalField(
        _("Amount"),
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text=_("Transaction amount (positive for debit, negative for credit)"),
    )
    remaining_amount = models.DecimalField(
        _("Remaining Amount"),
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text=_("Remaining amount to be applied"),
    )
    bank_account_posting_group = models.ForeignKey(
        BankAccountPostingGroup,
        verbose_name=_("Bank Acc. Posting Group"),
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        blank=True,
        null=True,
        to_field="code",
        help_text=_("Posting group from bank account"),
    )
    bal_account_type = models.CharField(
        _("Bal. Account Type"),
        max_length=50,
        choices=BalacingAccountType.choices,
        default=BalacingAccountType.GLAccount.value,
        blank=True,
        null=True,
        help_text=_("Type of balancing account"),
    )
    bal_account_no = models.CharField(
        _("Bal. Account No."),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Balancing account number (based on Bal. Account Type)"),
    )
    statement_status = models.CharField(
        _("Statement Status"),
        max_length=50,
        choices=enums.BankAccountStatementStatus.choices(),
        default=enums.BankAccountStatementStatus.Open.name,
        help_text=_("Status of bank statement reconciliation"),
    )
    statement_no = models.CharField(
        _("Statement No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Bank statement number"),
    )
    statement_line_no = models.IntegerField(
        _("Statement Line No."),
        blank=True,
        null=True,
        help_text=_("Line number on bank statement"),
    )
    document_date = models.DateField(
        _("Document Date"),
        blank=True,
        null=True,
        help_text=_("Date of the source document"),
    )
    document_no = models.CharField(
        _("Document No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Document number that created this entry"),
    )

    # FlowFields for Debit/Credit separation
    @property
    def debit_amount(self):
        """Debit amount (positive amount)"""
        return max(self.amount, 0.00)

    @property
    def credit_amount(self):
        """Credit amount (negative amount as positive)"""
        return abs(min(self.amount, 0.00))

    # Reversal tracking fields
    reversed = models.BooleanField(
        _("Reversed"),
        default=False,
        db_index=True,
        help_text=_("Indicates if this entry has been reversed"),
    )
    reversed_by_entry_no = models.IntegerField(
        _("Reversed By Entry No."),
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Entry number that reversed this entry"),
    )
    reversed_entry_no = models.IntegerField(
        _("Reversed Entry No."),
        blank=True,
        null=True,
        db_index=True,
        help_text=_("If this is a reversing entry, the entry number it reverses"),
    )
    reversed_by_user = models.ForeignKey(
        User,
        verbose_name=_("Reversed By User"),
        on_delete=models.PROTECT,
        related_name="bank_account_ledger_reversals",
        blank=True,
        null=True,
        help_text=_("User who performed the reversal"),
    )
    reversed_date = models.DateField(
        _("Reversal Date"),
        blank=True,
        null=True,
        help_text=_("Date when this entry was reversed"),
    )

    # Dimensions
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        verbose_name=_("Global Dimension 1"),
        on_delete=models.PROTECT,
        related_name="bank_account_ledger_entries",
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="bank_account_ledger_entries",
    )

    # User tracking
    user = models.ForeignKey(
        User,
        verbose_name=_("User"),
        on_delete=models.PROTECT,
        related_name="bank_account_ledger_entries",
        help_text=_("User who created this entry"),
    )

    @property
    def is_reversal_entry(self):
        """Check if this entry is a reversal of another entry"""
        return self.reversed_entry_no is not None

    @property
    def can_be_reversed(self):
        """Check if this entry can be reversed"""
        return not self.reversed

    class Meta:
        verbose_name = _("Bank Account Ledger Entry")
        verbose_name_plural = _("Bank Account Ledger Entries")
        ordering = ["-posting_date", "-entry_no"]
        indexes = [
            models.Index(fields=["bank_account_no", "posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["statement_no", "statement_line_no"]),
            models.Index(fields=["reversed"]),
            models.Index(fields=["reversed_entry_no"]),
        ]

    def __str__(self):
        return (
            f"Entry {self.entry_no} - {self.bank_account_no.no} - {self.posting_date}"
        )
