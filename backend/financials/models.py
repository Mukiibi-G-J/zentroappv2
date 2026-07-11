from django.db import models
from datetime import datetime
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from . import enums
from utils.utils import BaseModel, SingletonSetupModel
from authentication.models import CustomUser as User
from postings.models import (
    GeneralBusinessPostingGroup,
    GeneralProductPostingGroup,
    VATBusinessPostingGroup,
    VATProductPostingGroup,
)
from dimension.models import Dimension, DimensionValue, DimensionSet
from setup.models import NoSeriesLines
from financials.enums import BalacingAccountType
from items.models import increment_item_number


class G_LAccount(BaseModel):
    no = models.CharField(
        verbose_name="No.",
        max_length=255,
        primary_key=True,
        unique=True,
        blank=False,
        null=False,
    )
    name = models.CharField(max_length=255)
    indentation = models.IntegerField(default=0)
    income_balance = models.CharField(
        verbose_name="Income/Balance",
        max_length=255,
        choices=[(tag.value, tag.value) for tag in enums.INCOME_BALANCE],
        blank=True,
        null=True,
    )
    accountcategory = models.CharField(
        verbose_name="Account Category",
        max_length=255,
        choices=[(tag.value, tag.value) for tag in enums.G_L_Account_Category],
        blank=True,
        null=True,
    )
    # account_subcategory = models.ForeignKey(
    #     GLAccountCategories, on_delete=models.CASCADE, blank=True, null=True
    # )
    debit_credit = models.CharField(
        verbose_name="Debit/Credit",
        max_length=10,
        choices=[(tag.value, tag.value) for tag in enums.DEBIT_CREDIT],
        blank=True,
        null=True,
    )
    accounttype = models.CharField(
        verbose_name="Account Type",
        max_length=255,
        choices=[(tag.value, tag.value) for tag in enums.G_L_Account_Type],
        blank=True,
        null=True,
    )
    totaling = models.CharField(
        verbose_name="Totaling", max_length=255, blank=True, null=True
    )
    # balance = models.FloatField(verbose_name="Balance", default=0.00)
    direct_posting = models.BooleanField(verbose_name="Direct Posting", default=False)
    blocked = models.BooleanField(verbose_name="Blocked", default=False)
    general_product_posting_group = models.ForeignKey(
        GeneralProductPostingGroup,
        on_delete=models.SET_NULL,
        related_name="gl_accounts",
        blank=True,
        null=True,
    )

    @property
    def balance(self):
        return (
            GeneralLedgerEntry.objects.filter(gl_account=self.no).aggregate(
                models.Sum("amount")
            )["amount__sum"]
            or 0.00
        )

    def __str__(self):
        return f"{self.name} - {self.no}"

    class Meta:
        verbose_name = "General Ledger Account"
        verbose_name_plural = "General Ledger Accounts"
        ordering = ["name"]


class GeneralLedgerEntry(BaseModel):
    gl_account = models.ForeignKey(
        G_LAccount, on_delete=models.CASCADE, related_name="general_ledger_entries"
    )
    document_type = models.CharField(
        max_length=255,
        verbose_name="Document Type",
        choices=enums.DOCUMENT_TYPE.choices(),
        default=enums.DOCUMENT_TYPE.default.name,
        blank=True,
        null=True,
    )
    posting_date = models.DateField(verbose_name="Posting Date")
    document_no = models.CharField(max_length=255, verbose_name="Document No.")
    description = models.TextField(verbose_name="Description", blank=True, null=True)
    balance_account_no = models.CharField(
        max_length=255, verbose_name="Bal Account No.", blank=True, null=True
    )
    amount = models.FloatField(verbose_name="Amount", default=0.00)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    receipt_no = models.CharField(
        max_length=255, verbose_name="Receipt No.", blank=True, null=True
    )
    balancing_account_type = models.CharField(
        max_length=255,
        verbose_name="Bal. Account Type",
        choices=enums.BalacingAccountType.choices,
        blank=True,
        null=True,
    )
    general_posting_type = models.CharField(
        max_length=255,
        verbose_name="General Posting Type",
        choices=enums.GeneralPostingType.choices,
        blank=True,
        null=True,
        default=enums.GeneralPostingType.default.name,
    )
    general_business_posting_group = models.ForeignKey(
        GeneralBusinessPostingGroup,
        on_delete=models.CASCADE,
        related_name="general_business_posting_group_entries",
        blank=True,
        null=True,
    )
    general_product_posting_group = models.ForeignKey(
        GeneralProductPostingGroup,
        on_delete=models.CASCADE,
        related_name="general_product_posting_group_entries",
        blank=True,
        null=True,
    )
    vat_account = models.ForeignKey(
        G_LAccount,
        on_delete=models.CASCADE,
        related_name="vat_account_entries",
        blank=True,
        null=True,
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="general_ledger_entries",
    )
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="general_ledger_entries_global_dim_1",
        db_index=True,
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="general_ledger_entries_global_dim_2",
        blank=True,
        null=True,
        db_index=True,
    )
    transaction_no = models.CharField(
        max_length=255, verbose_name="Transaction No.", blank=True, null=True
    )
    reversed_by_transaction_no = models.CharField(
        max_length=255, verbose_name="Reversed By", blank=True, null=True
    )

    # Reversal tracking fields
    reversed = models.BooleanField(
        verbose_name="Reversed",
        default=False,
        db_index=True,
        help_text="Indicates if this entry has been reversed",
    )
    reversed_by_document_no = models.CharField(
        verbose_name="Reversed By Document No.",
        max_length=50,
        blank=True,
        null=True,
        help_text="Credit memo or reversing document number",
    )
    reversed_date = models.DateField(
        verbose_name="Reversal Date",
        blank=True,
        null=True,
        help_text="Date when this entry was reversed",
    )
    reverses_entry_no = models.IntegerField(
        verbose_name="Reverses Entry No.",
        blank=True,
        null=True,
        db_index=True,
        help_text="If this is a reversing entry, the ID of the entry it reverses",
    )
    reversed_by_user = models.ForeignKey(
        User,
        verbose_name="Reversed By User",
        on_delete=models.PROTECT,
        related_name="gl_entry_reversals",
        blank=True,
        null=True,
        help_text="User who performed the reversal",
    )

    def clean(self):
        super().clean()
        from dimension.models import get_dimension_value_from_set

        gl_setup = GeneralLedgerSetup.objects.first()
        if not gl_setup:
            return
        ds = self.dimension_set
        if gl_setup.global_dimension_1_id:
            resolved_id = self.global_dimension_1_id
            if not resolved_id and ds:
                v = get_dimension_value_from_set(ds, gl_setup.global_dimension_1)
                resolved_id = v.pk if v else None
            if not resolved_id:
                raise ValidationError(
                    "G/L entries require global dimension 1 (or a dimension set that "
                    "includes it), per General Ledger Setup."
                )
        if gl_setup.global_dimension_2_id:
            resolved_id = self.global_dimension_2_id
            if not resolved_id and ds:
                v = get_dimension_value_from_set(ds, gl_setup.global_dimension_2)
                resolved_id = v.pk if v else None
            if not resolved_id:
                raise ValidationError(
                    "G/L entries require global dimension 2 (or a dimension set that "
                    "includes it), per General Ledger Setup."
                )

    def save(self, *args, **kwargs):
        skip = kwargs.pop("skip_gl_dimension_validation", False)
        if not skip and self._state.adding:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_reversal_entry(self):
        """Check if this entry is a reversal of another entry"""
        return self.reverses_entry_no is not None

    @property
    def can_be_reversed(self):
        """Check if this entry can be reversed"""
        return not self.reversed

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["created_at"],
                name="financials__created_0cbdc3_idx",
            ),
            models.Index(
                fields=["system_id"],
                name="financials__system__718421_idx",
            ),
            models.Index(
                fields=["posting_date", "gl_account"],
                name="fin_gle_date_acct_idx",
            ),
            models.Index(
                fields=["global_dimension_1", "posting_date"],
                name="fin_gle_branch_date_idx",
            ),
            models.Index(fields=["document_no"], name="fin_gle_doc_no_idx"),
        ]


class VatEntry(BaseModel):
    """BC-style VAT Entry subledger. One record per line with VAT during posting."""

    posting_date = models.DateField(verbose_name="Posting Date")
    document_type = models.CharField(
        max_length=255,
        verbose_name="Document Type",
    )
    document_no = models.CharField(max_length=255, verbose_name="Document No.")
    type = models.CharField(
        max_length=20,
        verbose_name="Type",
        choices=[("Sale", "Sale"), ("Purchase", "Purchase")],
    )
    vat_business_posting_group = models.ForeignKey(
        VATBusinessPostingGroup,
        on_delete=models.PROTECT,
        related_name="vat_entries",
        verbose_name="VAT Bus. Posting Group",
        to_field="code",
        blank=True,
        null=True,
    )
    vat_product_posting_group = models.ForeignKey(
        VATProductPostingGroup,
        on_delete=models.PROTECT,
        related_name="vat_entries",
        verbose_name="VAT Prod. Posting Group",
        to_field="code",
        blank=True,
        null=True,
    )
    base = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Base",
        default=0,
        help_text="Taxable base amount (excl. VAT)",
    )
    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Amount",
        default=0,
        help_text="VAT amount",
    )
    vat_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="VAT %",
        default=0,
    )
    vat_calculation_type = models.CharField(
        max_length=20,
        verbose_name="VAT Calculation Type",
        default="Normal",
    )
    vat_account = models.ForeignKey(
        G_LAccount,
        on_delete=models.PROTECT,
        related_name="vat_entries",
        verbose_name="VAT Account",
        blank=True,
        null=True,
        to_field="no",
    )
    general_business_posting_group = models.ForeignKey(
        GeneralBusinessPostingGroup,
        on_delete=models.SET_NULL,
        related_name="vat_entries",
        blank=True,
        null=True,
        to_field="code",
    )
    general_product_posting_group = models.ForeignKey(
        GeneralProductPostingGroup,
        on_delete=models.SET_NULL,
        related_name="vat_entries_prod",
        blank=True,
        null=True,
        to_field="code",
    )
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="vat_entries",
    )
    transaction_no = models.CharField(
        max_length=255, verbose_name="Transaction No.", blank=True, null=True
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="vat_entries"
    )

    class Meta:
        verbose_name = "VAT Entry"
        verbose_name_plural = "VAT Entries"
        ordering = ["-posting_date", "-created_at"]

    def __str__(self):
        return f"VAT Entry {self.document_type} {self.document_no} - {self.amount}"


class GeneralLedgerSetup(SingletonSetupModel):
    global_dimension_1 = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name="global_dimension_1_entries",
        blank=True,
        null=True,
    )
    global_dimension_2 = models.ForeignKey(
        Dimension,
        on_delete=models.CASCADE,
        related_name="global_dimension_2_entries",
        blank=True,
        null=True,
    )
    shortcut_dimension_3 = models.ForeignKey(
        Dimension,
        on_delete=models.SET_NULL,
        related_name="shortcut_dimension_3_setups",
        blank=True,
        null=True,
        verbose_name=_("Shortcut Dimension 3"),
    )
    shortcut_dimension_4 = models.ForeignKey(
        Dimension,
        on_delete=models.SET_NULL,
        related_name="shortcut_dimension_4_setups",
        blank=True,
        null=True,
        verbose_name=_("Shortcut Dimension 4"),
    )
    shortcut_dimension_5 = models.ForeignKey(
        Dimension,
        on_delete=models.SET_NULL,
        related_name="shortcut_dimension_5_setups",
        blank=True,
        null=True,
        verbose_name=_("Shortcut Dimension 5"),
    )
    shortcut_dimension_6 = models.ForeignKey(
        Dimension,
        on_delete=models.SET_NULL,
        related_name="shortcut_dimension_6_setups",
        blank=True,
        null=True,
        verbose_name=_("Shortcut Dimension 6"),
    )
    enable_sales_line_type_selection = models.BooleanField(
        _("Enable Sales Line Type Selection"),
        default=False,
        help_text=_(
            "When enabled, sales and order lines show Type (Item/Resource) as the first field and allow resource lines."
        ),
    )
    enable_multiple_branches = models.BooleanField(
        _("Enable Multiple Branches"),
        default=False,
        help_text=_(
            "When enabled, users must be assigned a branch and data is filtered by branch. "
            "Requires Global Dimension 1 to be configured (e.g. BRANCH)."
        ),
    )
    # VAT settings (BC-style)
    vat_enabled = models.BooleanField(
        _("Enable VAT"),
        default=False,
        help_text=_(
            "When enabled, VAT is calculated and posted on sales and purchase documents. "
            "Requires VAT Posting Setup, and VAT posting groups on customers, vendors, and items."
        ),
    )
    default_vat_date = models.CharField(
        _("Default VAT Date"),
        max_length=20,
        choices=[
            ("posting_date", _("Posting Date")),
            ("document_date", _("Document Date")),
        ],
        default="posting_date",
        blank=True,
        null=True,
        help_text=_("Default source for VAT date on documents."),
    )
    local_currency_code = models.CharField(
        _("Local Currency Code"),
        max_length=3,
        default="UGX",
        help_text=_("ISO 4217 code for local currency (LCY)."),
    )

    def clean(self):
        if self.global_dimension_1_id and self.global_dimension_2_id:
            if self.global_dimension_1_id == self.global_dimension_2_id:
                raise ValidationError(
                    {
                        "global_dimension_2": _(
                            "Global Dimension 2 must be different from Global Dimension 1. "
                            "Each global dimension must reference a distinct dimension (e.g. BRANCH and SHOE_TYPE)."
                        )
                    }
                )
        # Ensure shortcut dimensions are distinct from globals and from each other
        globals_and_shortcuts = [
            (self.global_dimension_1_id, "global_dimension_1"),
            (self.global_dimension_2_id, "global_dimension_2"),
            (self.shortcut_dimension_3_id, "shortcut_dimension_3"),
            (self.shortcut_dimension_4_id, "shortcut_dimension_4"),
            (self.shortcut_dimension_5_id, "shortcut_dimension_5"),
            (self.shortcut_dimension_6_id, "shortcut_dimension_6"),
        ]
        seen = {}
        for dim_id, field_name in globals_and_shortcuts:
            if dim_id:
                if dim_id in seen:
                    raise ValidationError(
                        {
                            field_name: _(
                                "This dimension is already assigned as %(other)s."
                            )
                            % {"other": seen[dim_id]}
                        }
                    )
                seen[dim_id] = field_name.replace("_", " ").title()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class PaymentMethod(BaseModel):
    code = models.CharField(_("Code"), max_length=20, unique=True)
    description = models.CharField(_("Description"), max_length=100)
    bal_account_type = models.CharField(
        _("Bal. Account Type"),
        max_length=20,
        choices=BalacingAccountType.choices,
        default=BalacingAccountType.GLAccount.value,
    )
    bal_account_no = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name=_("G/L Account No."),
        on_delete=models.PROTECT,
        related_name="payment_methods_gl",
        null=True,
        blank=True,
        help_text=_("G/L Account when Bal. Account Type is 'G/L Account'"),
    )
    bal_bank_account_no = models.ForeignKey(
        "bank_account.BankAccount",
        verbose_name=_("Bank Account No."),
        on_delete=models.PROTECT,
        related_name="payment_methods_bank",
        null=True,
        blank=True,
        help_text=_("Bank Account when Bal. Account Type is 'Bank Account'"),
    )
    requires_amount_received = models.BooleanField(
        _("Requires Amount Received"),
        default=True,
        help_text=_(
            "Whether this payment method requires an amount received field in sales interface"
        ),
    )

    class Meta:
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
        ordering = ["code"]
        indexes = [
            models.Index(fields=["updated_at", "id"], name="fin_pm_upd_id_idx"),
            models.Index(fields=["description"], name="fin_pm_desc_idx"),
        ]

    def clean(self):
        """Ensure only the account field matching bal_account_type is set (BC-style)."""
        from financials.enums import BalacingAccountType, coerce_balancing_account_type

        bal_type = coerce_balancing_account_type(self.bal_account_type)
        if bal_type == BalacingAccountType.GLAccount.name:
            if self.bal_bank_account_no:
                raise ValidationError(
                    "Bank Account No. should not be set when Bal. Account Type is 'G/L Account'"
                )
        elif bal_type == BalacingAccountType.Bank_Account.name:
            if self.bal_account_no:
                raise ValidationError(
                    "G/L Account No. should not be set when Bal. Account Type is 'Bank Account'"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.description}"

    @property
    def account_no(self):
        """Get the account number based on the account type"""
        if self.bal_account_type == BalacingAccountType.Bank_Account.value:
            return self.bal_bank_account_no
        return self.bal_account_no

    def is_cash_payment(self):
        """
        Check if this payment method should be treated as a cash payment.
        A payment method is considered cash if it has a balance account number.
        NOT_PAID is explicitly excluded as it represents unpaid invoices.
        """
        has_account = (
            self.bal_account_no is not None or self.bal_bank_account_no is not None
        )
        return has_account and self.code != "NOT_PAID"


class PaymentBatch(BaseModel):
    name = models.CharField(max_length=255, verbose_name="Name")
    bal_account_type = models.CharField(
        max_length=255,
        verbose_name="Bal. Account Type",
        choices=BalacingAccountType.choices,
        default=BalacingAccountType.GLAccount.value,
    )
    bal_account_no = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name=_("Bal. Account No."),
        on_delete=models.PROTECT,
        related_name="payment_batches",
        null=True,
        blank=True,
    )
    no_series = models.ForeignKey(
        "setup.NoSeries",
        verbose_name=_("No. Series"),
        on_delete=models.PROTECT,
        related_name="payment_batches",
        null=True,
        blank=True,
    )


class Payment(BaseModel):
    payment_batch = models.ForeignKey(
        PaymentBatch,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    payment_date = models.DateField(verbose_name="Payment Date")
    document_type = models.CharField(
        max_length=255,
        verbose_name="Document Type",
        choices=enums.DOCUMENT_TYPE.choices(),
        default=enums.DOCUMENT_TYPE.default.name,
    )
    document_no = models.CharField(
        max_length=255, verbose_name="Document No.", blank=True, null=True
    )
    external_document_no = models.CharField(
        max_length=255,
        verbose_name="External Document No.",
        blank=True,
        null=True,
    )
    account_type = models.CharField(
        max_length=255,
        verbose_name="Account Type",
        choices=BalacingAccountType.choices,
        default=BalacingAccountType.GLAccount.value,
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name=_("G/L Account"),
        on_delete=models.PROTECT,
        related_name="payment_entries_gl",
        null=True,
        blank=True,
    )
    vendor_account = models.ForeignKey(
        "purchases.Vendor",
        verbose_name=_("Vendor"),
        on_delete=models.PROTECT,
        related_name="payment_entries_vendor",
        null=True,
        blank=True,
    )
    customer_account = models.ForeignKey(
        "sales.Customer",
        verbose_name=_("Customer"),
        on_delete=models.PROTECT,
        related_name="payment_entries_customer",
        null=True,
        blank=True,
    )
    message_to_recipient = models.TextField(
        verbose_name="Message to Recipient", blank=True, null=True
    )
    description = models.TextField(verbose_name="Description", blank=True, null=True)

    bal_account_type = models.CharField(
        max_length=255,
        verbose_name="Bal. Account Type",
        choices=BalacingAccountType.choices,
        default=BalacingAccountType.GLAccount.value,
    )
    gl_balancing_account = models.ForeignKey(
        "financials.G_LAccount",
        verbose_name=_("G/L Balancing Account"),
        on_delete=models.PROTECT,
        related_name="payment_entries_gl_balancing",
        null=True,
        blank=True,
    )
    amount = models.IntegerField(verbose_name="Amount", default=0)
    status = models.CharField(
        max_length=255,
        verbose_name="Status",
        choices=enums.PaymentStatus.choices(),
        default=enums.PaymentStatus.Open.name,
    )

    def clean(self):
        """Validate that only one account field is set based on account_type"""
        account_fields = {
            BalacingAccountType.GLAccount.value: self.gl_account,
            BalacingAccountType.Vendor.value: self.vendor_account,
            BalacingAccountType.Customer.value: self.customer_account,
        }

        # Check that the selected account type has a value
        if not account_fields.get(self.account_type):
            raise ValidationError(
                f"Account number is required for account type {self.account_type}"
            )

        # Check that only one account field is set
        set_fields = [field for field in account_fields.values() if field is not None]
        if len(set_fields) > 1:
            raise ValidationError("Only one account field should be set")

    def save(self, *args, **kwargs):
        self.clean()
        if not self.pk and not self.document_no:
            try:
                if PaymentBatch.objects.filter(no_series__isnull=False).first():
                    journal_no_series = NoSeriesLines.objects.filter(
                        no_series=PaymentBatch.objects.filter(no_series__isnull=False)
                        .first()
                        .no_series
                    ).first()
                    if journal_no_series:
                        increment_by = journal_no_series.increment_by
                        if journal_no_series.last_used_number:
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

                    print(f"Generated document number: {self.document_no}")

            except ValueError as e:
                print(f"Error parsing document number: {e}")

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def account_no(self):
        """Get the account number based on the account type"""
        account_mapping = {
            BalacingAccountType.GLAccount.value: self.gl_account,
            BalacingAccountType.Vendor.value: self.vendor_account,
            BalacingAccountType.Customer.value: self.customer_account,
        }
        return account_mapping.get(self.account_type)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["payment_date"]
        indexes = [
            models.Index(
                fields=["status", "payment_date"],
                name="fin_pay_status_date_idx",
            ),
        ]

    def __str__(self):
        return f"{self.document_no} - {self.payment_date}"


class GeneralJournalBatch(BaseModel):
    """Named batch for grouping general journal lines (BC Gen. Journal Batch)."""

    name = models.CharField(_("Name"), max_length=50, unique=True)
    description = models.CharField(_("Description"), max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = _("General Journal Batch")
        verbose_name_plural = _("General Journal Batches")
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.upper()
        super().save(*args, **kwargs)


class GeneralJournalLine(BaseModel):
    """Single line on the General Journal worksheet (BC Gen. Journal Line)."""

    batch_name = models.CharField(_("Batch Name"), max_length=50)
    line_no = models.IntegerField(_("Line No."), default=10000)
    posting_date = models.DateField(_("Posting Date"), blank=True, null=True)
    vat_reporting_date = models.DateField(_("VAT Reporting Date"), blank=True, null=True)
    document_type = models.CharField(
        _("Document Type"),
        max_length=30,
        blank=True,
        null=True,
    )
    document_no = models.CharField(_("Document No."), max_length=50, blank=True, null=True)
    external_document_no = models.CharField(
        _("External Document No."), max_length=50, blank=True, null=True,
    )
    account_type = models.CharField(_("Account Type"), max_length=20, blank=True, null=True)
    account_no = models.CharField(_("Account No."), max_length=50, blank=True, null=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    amount = models.IntegerField(_("Amount"), blank=True, null=True, default=0)
    debit_amount = models.IntegerField(_("Debit Amount"), blank=True, null=True, default=0)
    credit_amount = models.IntegerField(_("Credit Amount"), blank=True, null=True, default=0)
    bal_account_type = models.CharField(
        _("Bal. Account Type"), max_length=20, blank=True, null=True,
    )
    bal_account_no = models.CharField(_("Bal. Account No."), max_length=50, blank=True, null=True)
    correction = models.BooleanField(_("Correction"), default=False)
    comment = models.TextField(_("Comment"), blank=True, null=True)
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="general_journal_lines",
        verbose_name=_("Payment Method"),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        default="Open",
        db_index=True,
    )
    application_status = models.CharField(
        _("Application Status"),
        max_length=20,
        blank=True,
        null=True,
    )
    applies_to_doc_type = models.CharField(
        _("Applies To Document Type"), max_length=20, blank=True, null=True,
    )
    applies_to_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="general_journal_line_applies_to",
        verbose_name=_("Applies To Content Type"),
        blank=True,
        null=True,
    )
    applies_to_object_id = models.PositiveIntegerField(
        _("Applies To Object ID"), blank=True, null=True,
    )
    applies_to_doc = GenericForeignKey("applies_to_content_type", "applies_to_object_id")

    class Meta:
        verbose_name = _("General Journal Line")
        verbose_name_plural = _("General Journal Lines")
        ordering = ["batch_name", "line_no"]
        indexes = [
            models.Index(fields=["batch_name", "line_no"]),
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["status"]),
            models.Index(fields=["applies_to_content_type", "applies_to_object_id"]),
        ]

    def __str__(self):
        return f"{self.batch_name} - Line {self.line_no} ({self.document_no or '—'})"

    @staticmethod
    def _resolve_account_name(account_type: str | None, account_no: str | None) -> str:
        if not account_type or not account_no:
            return ""
        try:
            if account_type == "G/L Account":
                acc = G_LAccount.objects.filter(no=account_no).first()
                return acc.name if acc else ""
            if account_type == "Customer":
                from sales.models import Customer
                acc = Customer.objects.filter(no=account_no).first()
                return acc.name if acc else ""
            if account_type == "Vendor":
                from purchases.models import Vendor
                acc = Vendor.objects.filter(no=account_no).first()
                return acc.name if acc else ""
            if account_type == "Bank Account":
                from bank_account.models import BankAccount
                acc = BankAccount.objects.filter(no=account_no).first()
                return acc.name if acc else ""
        except Exception:
            return ""
        return ""

    @property
    def account_name(self) -> str:
        return self._resolve_account_name(self.account_type, self.account_no)

    @property
    def bal_account_name(self) -> str:
        return self._resolve_account_name(self.bal_account_type, self.bal_account_no)

    @property
    def applies_to_doc_name(self) -> str:
        if self.applies_to_doc and hasattr(self.applies_to_doc, "document_no"):
            return self.applies_to_doc.document_no or ""
        return ""

    def effective_amount(self) -> int:
        if self.debit_amount or self.credit_amount:
            return int(self.debit_amount or 0) - int(self.credit_amount or 0)
        return int(self.amount or 0)

    def save(self, *args, **kwargs):
        if self.debit_amount and not self.credit_amount and not self.amount:
            self.amount = self.debit_amount
        elif self.credit_amount and not self.debit_amount and not self.amount:
            self.amount = -abs(int(self.credit_amount))
        elif self.amount and not self.debit_amount and not self.credit_amount:
            amt = int(self.amount)
            if amt >= 0:
                self.debit_amount = amt
                self.credit_amount = 0
            else:
                self.debit_amount = 0
                self.credit_amount = abs(amt)
        if self.posting_date and not self.vat_reporting_date:
            self.vat_reporting_date = self.posting_date
        super().save(*args, **kwargs)


class FinancialReportRowGroup(BaseModel):
    """BC Financial Report Row Group header (row definition name)."""

    name = models.CharField(
        verbose_name="Name",
        max_length=10,
        primary_key=True,
    )
    description = models.CharField(
        verbose_name="Description",
        max_length=100,
        blank=True,
        default="",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Financial Report Row Group"
        verbose_name_plural = "Financial Report Row Groups"
        ordering = ["name"]


class FinancialReportColumnGroup(BaseModel):
    """BC Financial Report Column Group header (column definition name)."""

    name = models.CharField(
        verbose_name="Name",
        max_length=10,
        primary_key=True,
    )
    description = models.CharField(
        verbose_name="Description",
        max_length=100,
        blank=True,
        default="",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Financial Report Column Group"
        verbose_name_plural = "Financial Report Column Groups"
        ordering = ["name"]


class FinancialReportRowLine(BaseModel):
    """BC Financial Report Row Definition line."""

    row_group = models.ForeignKey(
        FinancialReportRowGroup,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Row Group",
    )
    line_no = models.IntegerField(verbose_name="Line No.")
    row_no = models.CharField(
        verbose_name="Row No.",
        max_length=10,
        blank=True,
        default="",
    )
    description = models.CharField(
        verbose_name="Description",
        max_length=250,
        blank=True,
        default="",
    )
    totaling_type = models.CharField(
        verbose_name="Totaling Type",
        max_length=50,
        choices=enums.FinancialReportTotalingType.choices(),
        default=enums.FinancialReportTotalingType.Posting_Accounts.value,
    )
    row_type = models.CharField(
        verbose_name="Line Type",
        max_length=50,
        choices=enums.FinancialReportRowType.choices(),
        default=enums.FinancialReportRowType.Posting.value,
    )
    row_amount_basis = models.CharField(
        verbose_name="Row Type",
        max_length=50,
        choices=enums.FinancialReportColumnType.choices(),
        default=enums.FinancialReportColumnType.Net_Change.value,
    )
    amount_type = models.CharField(
        verbose_name="Amount Type",
        max_length=50,
        choices=enums.FinancialReportAmountType.choices(),
        default=enums.FinancialReportAmountType.Net_Amount.value,
    )
    totaling = models.CharField(
        verbose_name="Totaling",
        max_length=250,
        blank=True,
        null=True,
    )
    show_opposite_sign = models.BooleanField(
        verbose_name="Show Opposite Sign",
        default=False,
    )
    show = models.CharField(
        verbose_name="Show",
        max_length=50,
        choices=enums.FinancialReportShowLine.choices(),
        default=enums.FinancialReportShowLine.Yes.value,
    )
    bold = models.BooleanField(verbose_name="Bold", default=False)
    italic = models.BooleanField(verbose_name="Italic", default=False)
    underline = models.BooleanField(verbose_name="Underline", default=False)
    new_page = models.BooleanField(verbose_name="New Page", default=False)
    indentation = models.PositiveSmallIntegerField(verbose_name="Indentation", default=0)

    def __str__(self):
        return f"{self.row_group_id} / {self.line_no}"

    class Meta:
        verbose_name = "Financial Report Row Line"
        verbose_name_plural = "Financial Report Row Lines"
        ordering = ["line_no"]
        unique_together = ("row_group", "line_no")


class FinancialReportColumnLine(BaseModel):
    """BC Financial Report Column Definition line."""

    column_group = models.ForeignKey(
        FinancialReportColumnGroup,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Column Group",
    )
    line_no = models.IntegerField(verbose_name="Line No.")
    column_no = models.CharField(
        verbose_name="Column No.",
        max_length=10,
        blank=True,
        default="",
    )
    column_header = models.CharField(
        verbose_name="Column Header",
        max_length=250,
        blank=True,
        default="",
    )
    column_type = models.CharField(
        verbose_name="Column Type",
        max_length=50,
        choices=enums.FinancialReportColumnType.choices(),
        default=enums.FinancialReportColumnType.Net_Change.value,
    )
    amount_type = models.CharField(
        verbose_name="Amount Type",
        max_length=50,
        choices=enums.FinancialReportAmountType.choices(),
        blank=True,
        default="",
    )
    formula = models.CharField(
        verbose_name="Formula",
        max_length=80,
        blank=True,
        default="",
    )
    comparison_period_formula = models.CharField(
        verbose_name="Comparison Period Formula",
        max_length=20,
        blank=True,
        default="0M",
        help_text="BC-style period shift, e.g. 0M (this month), -1M (last month), 0Y (this year).",
    )
    show_opposite_sign = models.BooleanField(
        verbose_name="Show Opposite Sign",
        default=False,
    )

    def __str__(self):
        return f"{self.column_group_id} / {self.line_no}"

    class Meta:
        verbose_name = "Financial Report Column Line"
        verbose_name_plural = "Financial Report Column Lines"
        ordering = ["line_no"]
        unique_together = ("column_group", "line_no")


class FinancialReport(BaseModel):
    """BC Table 88 — Financial Report setup."""

    name = models.CharField(
        verbose_name="Name",
        max_length=10,
        primary_key=True,
    )
    description = models.CharField(
        verbose_name="Description",
        max_length=100,
        blank=True,
        default="",
    )
    row_definition = models.ForeignKey(
        FinancialReportRowGroup,
        on_delete=models.PROTECT,
        related_name="financial_reports",
        verbose_name="Financial Report Row Group",
        to_field="name",
        null=True,
        blank=True,
    )
    column_definition = models.ForeignKey(
        FinancialReportColumnGroup,
        on_delete=models.PROTECT,
        related_name="financial_reports",
        verbose_name="Financial Report Column Group",
        to_field="name",
        null=True,
        blank=True,
    )
    period_type = models.CharField(
        verbose_name="Period Type",
        max_length=30,
        choices=enums.FinancialReportPeriodType.choices(),
        default=enums.FinancialReportPeriodType.Month.value,
    )
    start_date = models.DateField(
        verbose_name="Start Date",
        null=True,
        blank=True,
    )
    end_date = models.DateField(
        verbose_name="End Date",
        null=True,
        blank=True,
    )
    show_all_lines = models.BooleanField(
        verbose_name="Show All Lines",
        default=False,
    )
    use_amounts_in_add_currency = models.BooleanField(
        verbose_name="Use Amounts in Add. Reporting Currency",
        default=False,
    )
    dimension_1_filter = models.CharField(
        verbose_name="Dimension 1 Filter",
        max_length=250,
        blank=True,
        default="",
    )
    dimension_2_filter = models.CharField(
        verbose_name="Dimension 2 Filter",
        max_length=250,
        blank=True,
        default="",
    )
    dimension_3_filter = models.CharField(
        verbose_name="Dimension 3 Filter",
        max_length=250,
        blank=True,
        default="",
    )
    dimension_4_filter = models.CharField(
        verbose_name="Dimension 4 Filter",
        max_length=250,
        blank=True,
        default="",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Financial Report"
        verbose_name_plural = "Financial Reports"
        ordering = ["name"]
