from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils.timezone import datetime
from decimal import Decimal

from utils.utils import BaseModel
from authentication.models import CustomUser as User
from setup.models import JournalSetup, NoSeriesLines
from dimension.models import DimensionValue
from setup.enums import JournalType
from financials.models import G_LAccount
from .enums import LoanType, LoanStatus, RepaymentStatus, RepaymentAccountType
from helpers.helpers import increment_item_number


def get_today():
    """Get today's date"""
    return datetime.now().date()


class Loan(BaseModel):
    """
    Loan model for recording loan registrations.
    """

    # Document Information
    loan_no = models.CharField(
        _("Loan No."), max_length=50, unique=True, blank=True, null=True
    )
    loan_type = models.CharField(
        _("Loan Type"),
        max_length=20,
        choices=LoanType.choices(),
        blank=True,
        null=True,
    )
    lender_name = models.CharField(_("Lender Name"), max_length=255)
    loan_amount = models.IntegerField(_("Loan Amount"))
    disbursement_date = models.DateField(
        _("Disbursement Date"), default=get_today, blank=True, null=True
    )
    interest_rate = models.DecimalField(
        _("Interest Rate (%)"),
        max_digits=5,
        decimal_places=2,
        help_text="Annual interest rate as a percentage",
    )
    repayment_period = models.IntegerField(
        _("Repayment Period (Months)"),
        help_text="Number of months for loan repayment",
    )
    repayment_account = models.CharField(
        _("Repayment Account"),
        max_length=20,
        choices=RepaymentAccountType.choices(),
        blank=True,
        null=True,
    )
    bank_account = models.ForeignKey(
        "bank_account.BankAccount",
        on_delete=models.PROTECT,
        verbose_name=_("Bank Account"),
        related_name="loans",
        blank=True,
        null=True,
        help_text=_("Required when Repayment Account is 'Bank/Mobile Money'"),
    )
    purpose = models.TextField(_("Purpose"), blank=True, null=True)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=LoanStatus.choices(),
        default=LoanStatus.OPEN.value,
    )
    posted = models.BooleanField(_("Posted"), default=False)
    posted_date = models.DateField(_("Posted Date"), blank=True, null=True)
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        verbose_name=_("Posted By"),
        blank=True,
        null=True,
        related_name="posted_loans",
    )
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="loans",
        verbose_name=_("Global Dimension 1 (Branch)"),
    )

    class Meta:
        verbose_name = _("Loan")
        verbose_name_plural = _("Loans")
        ordering = ["-disbursement_date", "-loan_no"]
        indexes = [
            models.Index(fields=["loan_no"]),
            models.Index(fields=["disbursement_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["posted"]),
        ]

    def __str__(self):
        return f"{self.loan_no} - {self.lender_name} ({self.loan_amount})"

    def clean(self):
        """Validate the model data"""
        # Only validate if the field is set (allows partial updates for auto-save)
        # Allow 0 values for new loans being created incrementally (will be updated via PATCH)
        if self.loan_amount is not None and self.loan_amount < 0:
            raise ValidationError({"loan_amount": "Loan amount cannot be negative"})
        # Allow 0 for interest_rate during incremental creation
        if self.interest_rate is not None and (
            self.interest_rate < 0 or self.interest_rate > 100
        ):
            raise ValidationError(
                {"interest_rate": "Interest rate must be between 0 and 100"}
            )
        # Allow 0 or 1 for repayment_period during incremental creation
        if self.repayment_period is not None and self.repayment_period < 0:
            raise ValidationError(
                {"repayment_period": "Repayment period cannot be negative"}
            )

        # Only validate repayment_account if it's being set (allows partial updates)
        # The serializer will handle full validation on create/update
        if self.repayment_account:
            # For auto-save (incremental updates), allow "Bank/Mobile Money" without bank_account
            # The bank_account can be selected later. Only validate strictly when:
            # 1. Loan is being posted (posted=True)
            # 2. Loan has been fully created (has PK and all required fields are set)

            # If repayment_account is "Bank/Mobile Money", bank_account is required
            # BUT: Allow it to be None during incremental auto-save (when loan is new or being updated incrementally)
            # Only enforce validation if the loan is posted (final state)
            if self.repayment_account == "Bank/Mobile Money" and not self.bank_account:
                # Only raise error if loan is posted (final validation)
                # For auto-save, allow bank_account to be None - user can select it later
                if self.posted:
                    raise ValidationError(
                        {
                            "bank_account": "Bank account is required when Repayment Account is 'Bank/Mobile Money'"
                        }
                    )
                # For non-posted loans, allow bank_account to be None (auto-save scenario)

            # If repayment_account is "Cash", bank_account should not be set
            if self.repayment_account == "Cash" and self.bank_account:
                raise ValidationError(
                    {
                        "bank_account": "Bank account should not be set when Repayment Account is 'Cash'"
                    }
                )

    def save(self, *args, **kwargs):
        """Override save method to generate loan number if not provided"""
        try:
            # For new loans, ensure required fields have defaults if not set
            # This supports incremental auto-save where fields are added one at a time
            if not self.pk:
                if self.loan_amount is None:
                    self.loan_amount = 0
                if self.interest_rate is None:
                    self.interest_rate = 0
                if self.repayment_period is None:
                    self.repayment_period = 1
                if self.disbursement_date is None:
                    self.disbursement_date = get_today()

            # Handle loan number generation
            if not self.pk and not self.loan_no:
                try:
                    loan_setup = JournalSetup.objects.filter(
                        journal_type=JournalType.LOAN.value
                    ).first()

                    if loan_setup:
                        journal_no_series = NoSeriesLines.objects.filter(
                            no_series=loan_setup.journal_no_series
                        ).first()

                        if journal_no_series:
                            increment_by = journal_no_series.increment_by
                            if journal_no_series.last_used_number:
                                self.loan_no = increment_item_number(
                                    journal_no_series.last_used_number, increment_by
                                )
                                journal_no_series.last_used_number = self.loan_no
                                journal_no_series.last_used_date = datetime.now()
                                journal_no_series.save()
                            else:
                                self.loan_no = journal_no_series.start_number
                                journal_no_series.last_used_number = self.loan_no
                                journal_no_series.last_used_date = datetime.now()
                                journal_no_series.save()
                        else:
                            self.loan_no = (
                                f"LOAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            )
                    else:
                        print("Warning: Loan journal setup not found, using default")
                        self.loan_no = f"LOAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                except Exception as e:
                    print(f"Error generating loan number: {e}")
                    self.loan_no = f"LOAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            self.clean()
            super().save(*args, **kwargs)

        except Exception as e:
            print(f"Error saving Loan: {e}")
            raise

    def is_long_term(self):
        """Returns True if repayment period is greater than 12 months"""
        return self.repayment_period > 12

    def get_loan_payable_account(self):
        """Returns appropriate GL account based on loan term"""
        try:
            if self.is_long_term():
                # Long-term loans use account 5110 (Long-term Bank Loans)
                account = G_LAccount.objects.get(no="5110")
            else:
                # Short-term loans use account 5320 (Loan Payable – Short Term)
                account = G_LAccount.objects.get(no="5320")
            return account
        except G_LAccount.DoesNotExist:
            raise ValidationError(
                "Loan Payable GL account not found. Please run seed_loan_accounts command."
            )

    def calculate_monthly_payment(self):
        """Calculate monthly payment amount using simple interest"""
        if not self.loan_amount or not self.interest_rate or not self.repayment_period:
            return 0

        # Simple interest calculation
        # Monthly payment = (Principal + Total Interest) / Number of months
        principal = Decimal(self.loan_amount)
        rate = Decimal(self.interest_rate) / Decimal(100)
        months = Decimal(self.repayment_period)

        # Total interest = Principal * Rate * (Months / 12)
        total_interest = principal * rate * (months / Decimal(12))

        # Monthly payment
        monthly_payment = (principal + total_interest) / months

        return int(monthly_payment)

    def calculate_total_interest(self):
        """Calculate total interest over loan period"""
        if not self.loan_amount or not self.interest_rate or not self.repayment_period:
            return 0

        principal = Decimal(self.loan_amount)
        rate = Decimal(self.interest_rate) / Decimal(100)
        months = Decimal(self.repayment_period)

        # Total interest = Principal * Rate * (Months / 12)
        total_interest = principal * rate * (months / Decimal(12))

        return int(total_interest)

    def get_remaining_principal(self):
        """Calculate remaining principal after all repayments"""
        total_repaid = (
            self.repayments.filter(posted=True).aggregate(
                total=models.Sum("principal_amount")
            )["total"]
            or 0
        )
        return self.loan_amount - total_repaid


class LoanRepayment(BaseModel):
    """
    Loan Repayment model for recording loan repayments.
    """

    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="repayments",
        verbose_name=_("Loan"),
    )
    repayment_no = models.CharField(
        _("Repayment No."), max_length=50, unique=True, blank=True, null=True
    )
    payment_date = models.DateField(
        _("Payment Date"), default=get_today, blank=True, null=True
    )
    amount_paid = models.IntegerField(_("Amount Paid"), blank=True, null=True)
    principal_amount = models.IntegerField(
        _("Principal Amount"), default=0, help_text="Calculated automatically"
    )
    interest_amount = models.IntegerField(
        _("Interest Amount"), default=0, help_text="Calculated automatically"
    )
    payment_method = models.CharField(
        _("Payment Method"),
        max_length=20,
        choices=RepaymentAccountType.choices(),
        blank=True,
        null=True,
    )
    bank_account = models.ForeignKey(
        "bank_account.BankAccount",
        on_delete=models.PROTECT,
        verbose_name=_("Bank Account"),
        related_name="loan_repayments",
        blank=True,
        null=True,
        help_text=_("Required when Payment Method is 'Bank/Mobile Money'"),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=RepaymentStatus.choices(),
        default=RepaymentStatus.OPEN.value,
    )
    posted = models.BooleanField(_("Posted"), default=False)
    posted_date = models.DateField(_("Posted Date"), blank=True, null=True)
    posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        verbose_name=_("Posted By"),
        blank=True,
        null=True,
        related_name="posted_loan_repayments",
    )
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="loan_repayments",
        verbose_name=_("Global Dimension 1 (Branch)"),
    )

    class Meta:
        verbose_name = _("Loan Repayment")
        verbose_name_plural = _("Loan Repayments")
        ordering = ["-payment_date", "-repayment_no"]
        indexes = [
            models.Index(fields=["repayment_no"]),
            models.Index(fields=["payment_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["posted"]),
            models.Index(fields=["loan"]),
        ]

    def __str__(self):
        return f"{self.repayment_no} - {self.loan.loan_no} ({self.amount_paid})"

    def clean(self):
        """Validate the model data"""
        # Only validate if the field is set (allows partial updates for auto-save)
        # Allow 0 values for new repayments being created incrementally (will be updated via PATCH)
        if self.amount_paid is not None and self.amount_paid < 0:
            raise ValidationError({"amount_paid": "Amount paid cannot be negative"})

        if (
            self.payment_date
            and self.loan
            and self.payment_date < self.loan.disbursement_date
        ):
            raise ValidationError(
                {"payment_date": "Payment date cannot be before loan disbursement date"}
            )

        # Only validate payment_method if it's being set (allows partial updates)
        # The serializer will handle full validation on create/update
        if self.payment_method:
            # For auto-save (incremental updates), allow "Bank/Mobile Money" without bank_account
            # The bank_account can be selected later. Only validate strictly when:
            # 1. Repayment is being posted (posted=True)

            # If payment_method is "Bank/Mobile Money", bank_account is required
            # BUT: Allow it to be None during incremental auto-save (when repayment is new or being updated incrementally)
            # Only enforce validation if the repayment is posted (final state)
            if self.payment_method == "Bank/Mobile Money" and not self.bank_account:
                # Only raise error if repayment is posted (final validation)
                # For auto-save, allow bank_account to be None - user can select it later
                if self.posted:
                    raise ValidationError(
                        {
                            "bank_account": "Bank account is required when Payment Method is 'Bank/Mobile Money'"
                        }
                    )
                # For non-posted repayments, allow bank_account to be None (auto-save scenario)

            # If payment_method is "Cash", bank_account should not be set
            if self.payment_method == "Cash" and self.bank_account:
                raise ValidationError(
                    {
                        "bank_account": "Bank account should not be set when Payment Method is 'Cash'"
                    }
                )

    def save(self, *args, **kwargs):
        """Override save method to generate repayment number and calculate principal/interest"""
        try:
            # For new repayments, ensure required fields have defaults if not set
            # This supports incremental auto-save where fields are added one at a time
            if not self.pk:
                if self.amount_paid is None:
                    self.amount_paid = 0
                if self.payment_date is None:
                    self.payment_date = get_today()

            # Handle repayment number generation
            if not self.pk and not self.repayment_no:
                try:
                    # Try to get LOANREP number series
                    from setup.models import NoSeries

                    loanrep_series = NoSeries.objects.filter(code="LOANREP").first()
                    if loanrep_series:
                        no_series_line = NoSeriesLines.objects.filter(
                            no_series=loanrep_series
                        ).first()

                        if no_series_line:
                            increment_by = no_series_line.increment_by
                            if no_series_line.last_used_number:
                                self.repayment_no = increment_item_number(
                                    no_series_line.last_used_number, increment_by
                                )
                                no_series_line.last_used_number = self.repayment_no
                                no_series_line.last_used_date = datetime.now()
                                no_series_line.save()
                            else:
                                self.repayment_no = no_series_line.start_number
                                no_series_line.last_used_number = self.repayment_no
                                no_series_line.last_used_date = datetime.now()
                                no_series_line.save()
                        else:
                            self.repayment_no = (
                                f"LOANREP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            )
                    else:
                        self.repayment_no = (
                            f"LOANREP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        )

                except Exception as e:
                    print(f"Error generating repayment number: {e}")
                    self.repayment_no = (
                        f"LOANREP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    )

            # Don't calculate principal/interest automatically - will be calculated during posting
            # Set defaults to 0
            if not self.principal_amount:
                self.principal_amount = 0
            if not self.interest_amount:
                self.interest_amount = 0

            self.clean()
            super().save(*args, **kwargs)

        except Exception as e:
            print(f"Error saving LoanRepayment: {e}")
            raise

    def calculate_principal_interest_split(self):
        """Split payment into principal and interest portions"""
        if not self.amount_paid or not self.loan:
            return

        # Get remaining principal
        remaining_principal = self.loan.get_remaining_principal()

        # Calculate interest for this payment period
        # Simple interest: Interest = (Principal * Rate * Days) / (100 * 365)
        # For monthly: Interest = (Principal * Rate) / (100 * 12)
        principal_decimal = Decimal(remaining_principal)
        rate = Decimal(self.loan.interest_rate) / Decimal(100)

        # Calculate monthly interest
        monthly_interest = (principal_decimal * rate) / Decimal(12)

        # If payment is less than interest, all goes to interest
        if self.amount_paid <= int(monthly_interest):
            self.interest_amount = self.amount_paid
            self.principal_amount = 0
        else:
            # Interest portion
            self.interest_amount = int(monthly_interest)
            # Remaining goes to principal
            self.principal_amount = self.amount_paid - self.interest_amount

            # Ensure principal doesn't exceed remaining principal
            if self.principal_amount > remaining_principal:
                self.principal_amount = remaining_principal
                self.interest_amount = self.amount_paid - self.principal_amount
