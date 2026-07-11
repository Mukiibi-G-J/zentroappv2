from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.utils import ProgrammingError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.enums import (
    DocumentType as CommonDocumentType,
    EntryType as CommonEntryType,
)
from financials.enums import BalacingAccountType, GeneralPostingType, DOCUMENT_TYPE, coerce_balancing_account_type
from financials.models import GeneralLedgerEntry
from items.models import Item
from sales.models import (
    Customer,
    SalesReceivable,
    PostedSalesInvoice,
    PostedSalesInvoiceLine,
    CustomerLedgerEntry,
    DetailedCustomerLedgerEntry,
)
from utils.utils import BaseModel
from helpers.helpers import generate_document_number, ConfigurationError
from postings.models import GeneralPostingSetup
from dimension.models import DimensionValue, DimensionSet


def get_today():
    return timezone.now().date()


class PrepaymentStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    POSTED = "posted", _("Posted")
    CANCELLED = "cancelled", _("Cancelled")


class Preayment(BaseModel):
    document_no = models.CharField(
        max_length=50, unique=True, blank=True, null=True, verbose_name="Document No."
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="prepayment_documents",
        verbose_name=_("Customer"),
    )
    contact_person = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Contact Person")
    )
    document_date = models.DateField(default=get_today)
    posting_date = models.DateField(default=get_today)
    due_date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20, choices=PrepaymentStatus.choices, default=PrepaymentStatus.DRAFT
    )
    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    currency = models.CharField(max_length=3, default="UGX")
    total_prepayment = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Total Prepayment Collected"),
    )
    total_prepayment_invoiced = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Total Prepayment Invoiced"),
    )
    total_prepayment_deducted = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Total Prepayment Deducted"),
    )
    total_prepayment_to_deduct = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt. Amt. to Deduct"),
        help_text=_("Amount of invoiced prepayment to apply next"),
    )
    deposit_percent = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt. Line Amount %"),
        help_text=_("Calculated percentage based on deposit amount vs document total"),
    )
    posted_at = models.DateTimeField(blank=True, null=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="posted_prepayment_documents",
        blank=True,
        null=True,
    )
    posted_transaction_no = models.CharField(max_length=100, blank=True, null=True)
    posted_at = models.DateTimeField(blank=True, null=True)
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="posted_prepayment_documents",
        blank=True,
        null=True,
    )
    posted_transaction_no = models.CharField(max_length=100, blank=True, null=True)

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="preayment_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="preayment_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="preayment_headers",
        verbose_name=_("Dimension Set"),
    )

    class Meta:
        ordering = ["-posting_date", "-id"]
        verbose_name = _("Preayment")
        verbose_name_plural = _("Preayments")

    def __str__(self):
        return self.document_no or f"Preayment {self.pk}"

    def _do_insert(self, manager, using, fields, update_pk, raw):
        """Override to exclude fields that don't exist in DB yet."""
        # Temporarily exclude new fields that don't exist in DB yet
        # TODO: Remove this after running migrations that add these columns
        # Note: deposit_percent and total_prepayment_to_deduct are now included since the columns exist in DB
        fields_to_exclude = []
        # Filter out fields that don't exist in database
        filtered_fields = [f for f in fields if f.name not in fields_to_exclude]
        return super()._do_insert(manager, using, filtered_fields, update_pk, raw)

    def save(self, *args, **kwargs):
        if not self.document_no:
            self.document_no = self._generate_document_no()
        # Validate before saving
        self.clean()
        super().save(*args, **kwargs)

    def _generate_document_no(self):
        try:
            number, _ = generate_document_number(
                SalesReceivable,
                "posted_prepayment_invoice_no",
                "document_no",
                is_no_series_lines=True,
            )
            return number
        except ConfigurationError as exc:
            raise ConfigurationError(
                f"Posted prepayment invoice number series is missing: {exc}"
            )

    def _prepare_line_context(self):
        """
        Prepare line contexts for posting preview/posting.
        Uses document-level deposits and distributes pro-rata across lines.
        For installments (draft exists), posts as a single transaction instead of splitting.
        """
        from postings.models import GeneralPostingSetup

        if not self.customer.general_business_posting_group:
            raise ValidationError(
                "Customer needs a General Business Posting Group to determine prepayment accounts."
            )

        # Get document-level deposit amounts
        draft_amount = Decimal("0.00")
        has_draft = False
        try:
            if hasattr(self, "installment_draft") and self.installment_draft:
                draft_amount = self.installment_draft.amount or Decimal("0.00")
                has_draft = draft_amount > Decimal("0.00")
        except Exception:
            draft_amount = Decimal("0.00")

        collected = (self.total_prepayment or Decimal("0.00")) + draft_amount
        invoiced = self.total_prepayment_invoiced or Decimal("0.00")
        target_total = self.total_amount or Decimal("0.00")

        collectible_remaining = collected - invoiced
        if collectible_remaining < Decimal("0.00"):
            collectible_remaining = Decimal("0.00")

        target_remaining = target_total - invoiced
        if target_remaining < Decimal("0.00"):
            target_remaining = Decimal("0.00")

        amount_to_post = min(collectible_remaining, target_remaining)
        if amount_to_post <= Decimal("0.00"):
            raise ValidationError("No deposit amounts available to process.")

        # For installments (draft exists), post as a single transaction
        if has_draft:
            # Get prepayment account from any posting setup (they should all point to the same account)
            posting_setup = GeneralPostingSetup.objects.filter(
                general_business_posting_group=self.customer.general_business_posting_group,
                prepayment_account__isnull=False,
            ).first()

            if not posting_setup or not posting_setup.prepayment_account:
                raise ValidationError(
                    "Prepayment account is not configured for this customer's posting group."
                )

            # Return single context entry for the full installment amount
            return [
                {
                    "line": None,  # No specific line for installments
                    "amount": amount_to_post,
                    "collected_amount": collected,
                    "invoiced_amount": invoiced,
                    "target_total": target_total,
                    "label": f"Installment {self.document_no}",
                    "prepayment_account": posting_setup.prepayment_account,
                    "product_group": None,  # No product group for installments
                }
            ]

        # Distribute amount pro-rata across lines based on line amounts
        contexts = []
        lines_qs = self.lines.select_related(
            "item", "item__general_product_posting_group"
        ).all()

        if not lines_qs.exists():
            raise ValidationError("Prepayment must have at least one line.")

        total_line_amount = sum((line.amount or Decimal("0.00")) for line in lines_qs)
        if total_line_amount <= Decimal("0.00"):
            raise ValidationError("Total line amount must be greater than zero.")

        # Calculate pro-rata amounts for all lines first
        line_amounts = []
        total_distributed = Decimal("0.00")

        for line in lines_qs:
            if not line.item or not line.item.general_product_posting_group:
                raise ValidationError(
                    "Each prepayment line requires an item with a General Product Posting Group."
                )

            # Calculate pro-rata amount for this line
            line_amount = line.amount or Decimal("0.00")
            line_proportion = (
                line_amount / total_line_amount
                if total_line_amount > 0
                else Decimal("0.00")
            )
            line_post_amount = (amount_to_post * line_proportion).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )

            if line_post_amount > Decimal("0.00"):
                line_amounts.append((line, line_post_amount))
                total_distributed += line_post_amount

        # Adjust the last line to account for rounding differences
        # This ensures the total distributed equals amount_to_post exactly
        if line_amounts:
            rounding_diff = (amount_to_post - total_distributed).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if rounding_diff != Decimal("0.00"):
                # Add rounding difference to the last line
                last_line, last_amount = line_amounts[-1]
                new_last_amount = (last_amount + rounding_diff).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                line_amounts[-1] = (last_line, new_last_amount)

        # Now create contexts with the calculated amounts
        for line, line_post_amount in line_amounts:
            posting_setup_qs = GeneralPostingSetup.objects.filter(
                general_business_posting_group=self.customer.general_business_posting_group,
                prepayment_account__isnull=False,
                general_product_posting_group=line.item.general_product_posting_group,
            )

            posting_setup = posting_setup_qs.first()
            if not posting_setup:
                raise ValidationError(
                    f"Prepayment account is not configured for {self.customer.general_business_posting_group} / "
                    f"{line.item.general_product_posting_group}."
                )

            label = line.description or line.item.item_name or "Prepayment Line"
            contexts.append(
                {
                    "line": line,
                    "amount": line_post_amount,
                    "collected_amount": collected,
                    "invoiced_amount": invoiced,
                    "target_total": target_total,
                    "label": label,
                    "prepayment_account": posting_setup.prepayment_account,
                    "product_group": line.item.general_product_posting_group,
                }
            )

        if not contexts:
            raise ValidationError("No deposit amounts available to process.")

        return contexts

    @transaction.atomic
    def recalculate_totals(self):
        """Recalculate document totals from line amounts and update deposit percent."""
        aggregates = self.lines.aggregate(
            total=models.Sum("amount"),
        )
        self.total_amount = aggregates.get("total") or Decimal("0.00")

        # Calculate deposit percent based on header-level deposit
        deposit_percent_value = Decimal("0.00")
        try:
            if self.total_amount > Decimal("0.00"):
                deposit_percent_value = (
                    (self.total_prepayment / self.total_amount) * Decimal("100")
                ).quantize(Decimal("0.01"))
            else:
                deposit_percent_value = Decimal("0.00")
        except Exception:
            # If calculation fails, keep default of 0.00
            deposit_percent_value = Decimal("0.00")

        # Set deposit_percent value
        self.deposit_percent = deposit_percent_value

        # Validate totals
        self.clean()

        # Build update_fields list
        update_fields = ["total_amount", "deposit_percent", "updated_at"]

        super().save(update_fields=update_fields)

    @property
    def remaining_prepayment(self) -> Decimal:
        """Total prepayment amount still not invoiced."""
        target = self.total_amount or Decimal("0.00")
        invoiced = self.total_prepayment_invoiced or Decimal("0.00")
        return max(target - invoiced, Decimal("0.00"))

    @property
    def preview_deposit_total(self) -> Decimal:
        """
        Read-only preview based on posted portion plus draft installment.
        This shows what the posted exposure would become after applying the draft
        during posting, clamped to document total amount.
        """
        posted = self.total_prepayment_invoiced or Decimal("0.00")
        draft = Decimal("0.00")
        try:
            if hasattr(self, "installment_draft") and self.installment_draft:
                draft = self.installment_draft.amount or Decimal("0.00")
        except Exception:
            draft = Decimal("0.00")
        target = self.total_amount or Decimal("0.00")
        preview = posted + draft
        if preview > target:
            preview = target
        if preview < Decimal("0.00"):
            preview = Decimal("0.00")
        return preview

    def is_fully_posted(self) -> bool:
        """Return True when document total amount has been invoiced."""
        target = self.total_amount or Decimal("0.00")
        invoiced = self.total_prepayment_invoiced or Decimal("0.00")
        return invoiced >= target

    @property
    def is_final_invoiced(self) -> bool:
        """True after the final sales invoice has been posted from this prepayment."""
        return (self.total_prepayment_deducted or Decimal("0.00")) > Decimal("0.00")

    @property
    def collected_prepayment_fully_invoiced(self) -> bool:
        """True when every collected prepayment amount has been prepayment-invoiced."""
        collected = self.total_prepayment or Decimal("0.00")
        invoiced = self.total_prepayment_invoiced or Decimal("0.00")
        return collected > Decimal("0.00") and collected == invoiced

    def assert_open_for_installments(self):
        """Raise when prepayment must not accept further installment collection."""
        if self.status == PrepaymentStatus.CANCELLED:
            raise ValidationError("This prepayment is cancelled.")
        if self.is_final_invoiced:
            raise ValidationError(
                "Final invoice has already been posted for this prepayment. "
                "Collect any remaining balance on the final sales invoice."
            )

    def assert_can_collect_installment(self):
        """Raise when a new installment draft or collection is not allowed."""
        self.assert_open_for_installments()
        if self.is_fully_posted():
            raise ValidationError(
                "This prepayment is fully invoiced. Post the final invoice instead."
            )
        if self.collected_prepayment_fully_invoiced:
            raise ValidationError(
                "All collected prepayments are already invoiced. "
                "Post the final invoice instead of adding more installments."
            )
        if self.remaining_prepayment <= Decimal("0.00"):
            raise ValidationError("No remaining amount to collect on this prepayment.")

    def assert_can_post_final_invoice(self):
        """Raise when final invoice posting is not allowed."""
        self.assert_open_for_installments()
        collected = self.total_prepayment or Decimal("0.00")
        if collected <= Decimal("0.00"):
            raise ValidationError("No prepayment has been collected yet.")
        if not self.collected_prepayment_fully_invoiced:
            invoiced = self.total_prepayment_invoiced or Decimal("0.00")
            balance = collected - invoiced
            raise ValidationError(
                f"Cannot post final invoice. Collected prepayments are not fully invoiced. "
                f"Remaining prepayment balance: {balance:,.2f}. "
                f"Post prepayment invoices first."
            )

    def clean(self):
        """Validate that total_amount cannot be reduced below already posted amount."""
        if self.pk:
            # Get the original instance from database
            try:
                # Defer new fields that don't exist in DB yet
                # TODO: Remove defer after running migrations
                original = Preayment.objects.defer(
                    "total_prepayment_to_deduct", "deposit_percent"
                ).get(pk=self.pk)
                original_invoiced = original.total_prepayment_invoiced or Decimal(
                    "0.00"
                )
                new_total = self.total_amount or Decimal("0.00")
                if new_total < original_invoiced:
                    raise ValidationError(
                        f"Cannot reduce document total below already posted amount of {original_invoiced:,.2f}"
                    )
            except Preayment.DoesNotExist:
                pass
            except ProgrammingError:
                # If database columns don't exist yet, skip validation
                # This allows the code to work before migrations are run
                pass

    def _get_posting_dimension_payload(self, user=None):
        """Resolve dimension_set and global dimensions for ledger/GL posting."""
        from dimension.models import get_posting_dimension_payload

        user_dim_1 = getattr(user, "global_dimension_1", None) if user else None
        return get_posting_dimension_payload(
            global_dimension_1=self.global_dimension_1 or user_dim_1,
            global_dimension_2=self.global_dimension_2,
            dimension_set=self.dimension_set,
        )

    def build_posting_preview(self, user=None, payment_method=None):
        """Return structured preview data similar to sales invoice preview."""
        if not self.customer:
            raise ValidationError("Customer is required for posting preview.")

        receivables_account = None
        if (
            self.customer.customer_posting_group
            and self.customer.customer_posting_group.receivables_account
        ):
            receivables_account = (
                self.customer.customer_posting_group.receivables_account
            )

        if not receivables_account:
            raise ValidationError(
                "Customer posting group must have a receivables account defined."
            )

        dim_payload = self._get_posting_dimension_payload(user)
        global_dimension_1_value = dim_payload["global_dimension_1"]
        dimension_set_value = dim_payload["dimension_set"]
        transaction_no = (
            f"PRE{self.document_no}-{self.posting_date.strftime('%Y%m%d')}-{self.id}"
        )
        entries = {
            "gl_entries": [],
            "customer_entries": [],
            "item_entries": [],
            "value_entries": [],
            "detailed_customer_entries": [],
            "inventory_reduction_preview": [],
        }

        line_context = self._prepare_line_context()
        total_deposit = sum(ctx["amount"] for ctx in line_context)
        general_business_group = self.customer.general_business_posting_group
        due_date = self.due_date or self.posting_date

        for ctx in line_context:
            amount = ctx["amount"]
            line_label = ctx["label"]
            product_group = ctx.get("product_group")  # May be None for installments

            entries["gl_entries"].extend(
                [
                    {
                        "posting_date": self.posting_date,
                        "document_type": "Invoice",
                        "document_no": self.document_no,
                        "gl_account": receivables_account,
                        "description": f"Prepayment for {line_label}",
                        "department_code": (
                            global_dimension_1_value.code if global_dimension_1_value else None
                        ),
                        "amount": amount,
                        "transaction_no": transaction_no,
                        "gen_posting_type": GeneralPostingType.Sales.value,
                        "gen_bus_posting_group": general_business_group,
                        "gen_prod_posting_group": product_group,
                        "global_dimension_1": global_dimension_1_value,
                        "balance_account_type": BalacingAccountType.Customer.value,
                    },
                    {
                        "posting_date": self.posting_date,
                        "document_type": "Invoice",
                        "document_no": self.document_no,
                        "gl_account": ctx["prepayment_account"],
                        "description": f"Prepayment liability ({line_label})",
                        "department_code": (
                            global_dimension_1_value.code if global_dimension_1_value else None
                        ),
                        "amount": -amount,
                        "transaction_no": transaction_no,
                        "gen_posting_type": GeneralPostingType.Sales.value,
                        "gen_bus_posting_group": general_business_group,
                        "gen_prod_posting_group": product_group,
                        "global_dimension_1": global_dimension_1_value,
                        "balance_account_type": BalacingAccountType.GLAccount.name,
                    },
                ]
            )

        # Use provided payment_method or fall back to customer's default
        if payment_method is None:
            payment_method = getattr(self.customer, "payment_method", None)

        entries["customer_entries"].append(
            {
                "posting_date": self.posting_date,
                "document_date": self.document_date,
                "document_type": "Invoice",
                "document_no": self.document_no,
                "external_document_no": None,
                "customer_no": self.customer.no,
                "customer": self.customer,
                "description": f"Prepayment {self.document_no}",
                "payment_method": payment_method,
                "original_amount": total_deposit,
                "amount": total_deposit,
                "remaining_amount": total_deposit,
                "sales": Decimal("0.00"),
                "open": False,  # Closed because payment entry will apply to this invoice
                "due_date": due_date,
                "global_dimension_1": global_dimension_1_value,
                "dimension_set": dimension_set_value,
                "user": user,
                "transaction_no": transaction_no,
            }
        )

        entries["detailed_customer_entries"].append(
            {
                "posting_date": self.posting_date,
                "entry_type": "Initial Entry",
                "document_type": "Invoice",
                "document_no": self.document_no,
                "customer_no": self.customer.no,
                "customer": self.customer,
                "amount": -total_deposit,
                "initial_entry_due_date": due_date,
                "debit_amount": 0,
                "credit_amount": total_deposit,
                "transaction_no": transaction_no,
                "initial_document_type": "Invoice",
                "customer_ledger_entry": "PRE-INVOICE",
                "applied_customer_ledger_entry_no": 0,
                "unapplied_by_entry_no": 0,
                "unapplied": False,
                "global_dimension_1": global_dimension_1_value,
                "dimension_set": dimension_set_value,
            }
        )

        # Create payment entries for ALL prepayments (not just cash)
        # Payment method is required for prepayments (prepayments are payments received)
        import logging
        logger = logging.getLogger(__name__)
        print(f"[build_posting_preview] payment_method parameter: {payment_method} (type: {type(payment_method)})")
        print(f"[build_posting_preview] bool(payment_method): {bool(payment_method)}")
        logger.error(f"[build_posting_preview] payment_method parameter: {payment_method} (type: {type(payment_method)})")
        logger.error(f"[build_posting_preview] bool(payment_method): {bool(payment_method)}")
        if not payment_method:
            print(f"[build_posting_preview] ValidationError: payment_method is None or falsy")
            logger.error(f"[build_posting_preview] ValidationError: payment_method is None or falsy")
            raise ValidationError(
                "Payment method is required for posting prepayments. Please select a payment method."
            )
        print(f"[build_posting_preview] Payment method validation passed: {payment_method.code}")
        logger.error(f"[build_posting_preview] Payment method validation passed: {payment_method.code}")

        is_cash_payment = bool(payment_method and payment_method.is_cash_payment())

        # Determine which account to use for payment
        # For cash: use balancing account (cash account)
        # For non-cash: use receivables account (payment on account)
        if is_cash_payment:
            payment_account = payment_method.bal_account_no
            if not payment_account:
                raise ValidationError(
                    f"Payment method {payment_method.code} is missing a balancing account."
                )
            payment_description = "Cash receipt for prepayment"
            apply_description = "Apply cash receipt to customer"
        else:
            payment_account = receivables_account
            payment_description = "Payment received for prepayment"
            apply_description = "Apply payment to customer"

        # Create G/L entries for payment
        entries["gl_entries"].extend(
            [
                {
                    "posting_date": self.posting_date,
                    "document_type": "Payment",
                    "document_no": self.document_no,
                    "gl_account": payment_account,
                    "description": payment_description,
                    "department_code": (
                        global_dimension_1_value.code if global_dimension_1_value else None
                    ),
                    "amount": total_deposit,
                    "transaction_no": transaction_no,
                    "gen_posting_type": GeneralPostingType.Sales.value,
                    "gen_bus_posting_group": general_business_group,
                    "gen_prod_posting_group": None,
                    "global_dimension_1": global_dimension_1_value,
                    "balance_account_type": (
                        BalacingAccountType.GLAccount.name
                        if is_cash_payment
                        else BalacingAccountType.Customer.value
                    ),
                },
                {
                    "posting_date": self.posting_date,
                    "document_type": "Payment",
                    "document_no": self.document_no,
                    "gl_account": receivables_account,
                    "description": apply_description,
                    "department_code": (
                        global_dimension_1_value.code if global_dimension_1_value else None
                    ),
                    "amount": -total_deposit,
                    "transaction_no": transaction_no,
                    "gen_posting_type": GeneralPostingType.Sales.value,
                    "gen_bus_posting_group": general_business_group,
                    "gen_prod_posting_group": None,
                    "global_dimension_1": global_dimension_1_value,
                    "balance_account_type": BalacingAccountType.Customer.value,
                },
            ]
        )

        # Create Customer Ledger Entry for payment
        entries["customer_entries"].append(
            {
                "posting_date": self.posting_date,
                "document_date": self.document_date,
                "document_type": "Payment",
                "document_no": self.document_no,
                "external_document_no": self.document_no,
                "customer_no": self.customer.no,
                "customer": self.customer,
                "description": f"Prepayment {self.document_no}",
                "payment_method": payment_method,
                "original_amount": -total_deposit,
                "amount": -total_deposit,
                "remaining_amount": -total_deposit,
                "sales": Decimal("0.00"),
                "open": (
                    False if is_cash_payment else False
                ),  # Payment entries are always closed
                "due_date": due_date,
                "global_dimension_1": global_dimension_1_value,
                "dimension_set": dimension_set_value,
                "user": None,
                "transaction_no": transaction_no,
            }
        )

        # Create Detailed Customer Ledger Entries for payment
        entries["detailed_customer_entries"].extend(
            [
                {
                    "posting_date": self.posting_date,
                    "entry_type": "Initial Entry",
                    "document_type": "Payment",
                    "document_no": self.document_no,
                    "customer_no": self.customer.no,
                    "customer": self.customer,
                    "amount": total_deposit,
                    "initial_entry_due_date": due_date,
                    "debit_amount": total_deposit,
                    "credit_amount": 0,
                    "initial_document_type": "Payment",
                    "customer_ledger_entry": "PRE-PAYMENT",
                    "applied_customer_ledger_entry_no": 0,
                    "unapplied_by_entry_no": 0,
                    "unapplied": False,
                    "transaction_no": transaction_no,
                    "global_dimension_1": global_dimension_1_value,
                    "dimension_set": dimension_set_value,
                },
                {
                    "posting_date": self.posting_date,
                    "entry_type": "Application",
                    "document_type": "Payment",
                    "document_no": self.document_no,
                    "customer_no": self.customer.no,
                    "customer": self.customer,
                    "amount": total_deposit,
                    "initial_entry_due_date": due_date,
                    "debit_amount": total_deposit,
                    "credit_amount": 0,
                    "initial_document_type": "Payment",
                    "customer_ledger_entry": "PRE-PAYMENT",
                    "applied_customer_ledger_entry_no": "PRE-PAYMENT",
                    "unapplied_by_entry_no": 0,
                    "unapplied": False,
                    "transaction_no": transaction_no,
                    "global_dimension_1": global_dimension_1_value,
                    "dimension_set": dimension_set_value,
                },
                {
                    "posting_date": self.posting_date,
                    "entry_type": "Application",
                    "document_type": "Payment",
                    "document_no": self.document_no,
                    "customer_no": self.customer.no,
                    "customer": self.customer,
                    "amount": -total_deposit,
                    "initial_entry_due_date": due_date,
                    "debit_amount": 0,
                    "credit_amount": total_deposit,
                    "initial_document_type": "Invoice",
                    "customer_ledger_entry": "PRE-INVOICE",
                    "applied_customer_ledger_entry_no": "PRE-PAYMENT",
                    "unapplied_by_entry_no": 0,
                    "unapplied": False,
                    "transaction_no": transaction_no,
                    "global_dimension_1": global_dimension_1_value,
                    "dimension_set": dimension_set_value,
                },
            ]
        )

        return {
            "entries": entries,
            "total_deposit": total_deposit,
            "has_cash_payment": is_cash_payment,
            "transaction_no": transaction_no,
            "line_context": line_context,
        }

    def build_final_invoice_posting_preview(self, user=None, payment_method=None):
        """
        Build preview for posting final sales invoice from prepayment.
        Shows entries for: Inventory, COGS, Sales, Prepayment deduction, and Customer receivables.

        Can only be done if prepayment has been fully invoiced (no prepayment balance remaining).

        If payment_method is provided and is not NOT_PAID, payment entries will be created.
        If payment_method is NOT_PAID or not provided, no payment entries are created and invoice remains open.
        """
        if not self.customer:
            raise ValidationError("Customer is required for posting preview.")

        if not self.lines.exists():
            raise ValidationError("Prepayment must have at least one line.")

        self.assert_can_post_final_invoice()

        from postings.models import InventoryPostingSetup
        from items.models import ItemLedgerEntries, ValueEntry
        from financials.enums import BalacingAccountType, GeneralPostingType

        receivables_account = None
        if (
            self.customer.customer_posting_group
            and self.customer.customer_posting_group.receivables_account
        ):
            receivables_account = (
                self.customer.customer_posting_group.receivables_account
            )

        if not receivables_account:
            raise ValidationError(
                "Customer posting group must have a receivables account defined."
            )

        dim_payload = self._get_posting_dimension_payload(user)
        global_dimension_1_value = dim_payload["global_dimension_1"]
        dimension_set_value = dim_payload["dimension_set"]
        transaction_no = (
            f"FINV{self.document_no}-{self.posting_date.strftime('%Y%m%d')}-{self.id}"
        )

        entries = {
            "gl_entries": [],
            "customer_entries": [],
            "item_entries": [],
            "value_entries": [],
            "detailed_customer_entries": [],
            "inventory_reduction_preview": [],
        }

        general_business_group = self.customer.general_business_posting_group
        total_invoice_amount = self.total_amount or Decimal("0.00")
        # For final invoice posting, deduct the total prepayment that was invoiced
        # This is the amount that was collected as prepayment and should be deducted from the final invoice
        prepayment_to_deduct = self.total_prepayment_invoiced or Decimal("0.00")
        net_receivables = total_invoice_amount - prepayment_to_deduct

        # Process each line to calculate COGS and inventory reduction
        for line in self.lines.select_related(
            "item",
            "item__general_product_posting_group",
            "item__inventory_posting_group",
        ).all():
            if not line.item or not line.item.general_product_posting_group:
                continue

            # Get posting setups
            general_posting_setup = GeneralPostingSetup.objects.filter(
                general_product_posting_group=line.item.general_product_posting_group,
                general_business_posting_group=general_business_group,
            ).first()

            if not general_posting_setup:
                continue

            # Get location - use user's global_dimension_1 location or first available
            from items.models import Location

            location = None
            if user and hasattr(user, "global_dimension_1") and user.global_dimension_1:
                location = Location.objects.filter(code=user.global_dimension_1.code).first()

            if not location:
                location = Location.objects.first()

            if not location:
                raise ValidationError(
                    "No location found. Please create a location first."
                )

            # Get inventory posting setup
            inventory_posting_setup = InventoryPostingSetup.objects.filter(
                location=location,
                inventory_posting_group=line.item.inventory_posting_group,
            ).first()

            if not inventory_posting_setup:
                continue

            sales_account = general_posting_setup.sales_account
            cogs_account = general_posting_setup.cogs_account
            inventory_account = inventory_posting_setup.inventory_account
            prepayment_account = general_posting_setup.prepayment_account

            if not all(
                [sales_account, cogs_account, inventory_account, prepayment_account]
            ):
                continue

            # Calculate quantity to reduce (convert to base UOM)
            quantity = line.quantity or Decimal("0.00")
            if line.item_unit_of_measure:
                quantity_per_iuom = (
                    line.item_unit_of_measure.quantity_per_unit or Decimal("1.00")
                )
                quantity_to_reduce = quantity * quantity_per_iuom
            else:
                quantity_to_reduce = quantity

            # Get line amount early - needed for item ledger entries
            line_amount = line.amount or Decimal("0.00")
            line_label = line.description or line.item.item_name or "Prepayment Line"

            # Calculate prepayment portion for this line (before the loop)
            line_prepayment_portion = (
                (prepayment_to_deduct * line_amount / total_invoice_amount)
                if total_invoice_amount > 0
                else Decimal("0.00")
            )
            net_line_amount = line_amount - line_prepayment_portion

            # Calculate COGS using FIFO
            # Get inventory entries for this item and location
            item_entries = ItemLedgerEntries.objects.filter(
                item=line.item,
                remaining_quantity__gt=0,
                location=location,
            ).order_by("created_at")

            total_cost = Decimal("0.00")
            remaining_to_reduce = quantity_to_reduce
            item_ledger_preview_entries = []
            value_preview_entries = []

            for entry in item_entries:
                if remaining_to_reduce <= 0:
                    break

                reduction = min(entry.remaining_quantity, remaining_to_reduce)

                # Get cost from value entries
                value_entries = ValueEntry.objects.filter(item_ledger_entry_no=entry.id)
                cost_for_reduction = Decimal("0.00")
                cost_per_unit = Decimal("0.00")

                if value_entries.exists():
                    total_entry_cost = sum(
                        Decimal(str(ve.cost_amount)) for ve in value_entries
                    )
                    total_entry_quantity = abs(
                        sum(
                            Decimal(str(ve.item_ledger_entry_quantity))
                            for ve in value_entries
                        )
                    )
                    if total_entry_quantity > 0:
                        cost_per_unit = total_entry_cost / total_entry_quantity
                        cost_for_reduction = cost_per_unit * reduction
                        total_cost += cost_for_reduction
                else:
                    # Fallback: use entry total
                    if entry.quantity != 0:
                        cost_per_unit = Decimal(str(entry.total)) / abs(
                            Decimal(str(entry.quantity))
                        )
                        cost_for_reduction = cost_per_unit * reduction
                        total_cost += cost_for_reduction

                # Create item ledger entry preview
                unit_price = line.unit_price or Decimal("0.00")
                if quantity_to_reduce > 0:
                    unit_price = line_amount / quantity_to_reduce

                # Calculate sales amount for this reduction
                sales_amount_for_reduction = (
                    (line_amount * reduction / quantity_to_reduce)
                    if quantity_to_reduce > 0
                    else Decimal("0.00")
                )

                item_ledger_preview_entries.append(
                    {
                        "posting_date": self.posting_date,
                        "entry_type": CommonEntryType.Sales.value,
                        "document_type": CommonDocumentType.Sales.value,
                        "document_no": self.document_no,
                        "item": line.item,
                        "location": location,
                        "quantity": -reduction,
                        "unit_of_measure": (
                            line.item_unit_of_measure.unit_of_measure
                            if line.item_unit_of_measure
                            else None
                        ),
                        "cost_amount": cost_for_reduction,
                        "sales_amount": sales_amount_for_reduction,
                        "purchase_amount": Decimal("0.00"),
                        "transaction_no": transaction_no,
                    }
                )

                # Create value entry preview
                value_preview_entries.append(
                    {
                        "posting_date": self.posting_date,
                        "entry_type": CommonEntryType.Sales.value,
                        "document_no": self.document_no,
                        "item": line.item,
                        "cost_amount": cost_for_reduction,
                        "cost_per_unit": cost_per_unit,
                        "item_ledger_entry_quantity": -reduction,
                        "invoiced_quantity": -reduction,
                        "valued_quantity": -reduction,
                        "general_product_posting_group": line.item.general_product_posting_group,
                        "inventory_posting_group": line.item.inventory_posting_group,
                        "transaction_no": transaction_no,
                    }
                )

                remaining_to_reduce -= reduction

            # Add item and value entries to preview
            entries["item_entries"].extend(item_ledger_preview_entries)
            entries["value_entries"].extend(value_preview_entries)

            # Create GL entries for this line
            gl_entries_for_line = [
                # Debit: COGS Account
                {
                    "posting_date": self.posting_date,
                    "document_type": CommonDocumentType.default.value,
                    "document_no": self.document_no,
                    "gl_account": cogs_account,
                    "description": f"COGS for {line_label}",
                    "department_code": (
                        global_dimension_1_value.code if global_dimension_1_value else None
                    ),
                    "amount": total_cost,
                    "gen_posting_type": GeneralPostingType.Sales.value,
                    "global_dimension_1": global_dimension_1_value,
                    "gen_bus_posting_group": general_business_group,
                    "gen_prod_posting_group": line.item.general_product_posting_group,
                    "balance_account_type": BalacingAccountType.GLAccount.name,
                    "transaction_no": transaction_no,
                },
                # Credit: Inventory Account
                {
                    "posting_date": self.posting_date,
                    "document_type": CommonDocumentType.default.value,
                    "document_no": self.document_no,
                    "gl_account": inventory_account,
                    "description": f"Inventory reduction for {line_label}",
                    "department_code": (
                        global_dimension_1_value.code if global_dimension_1_value else None
                    ),
                    "amount": -total_cost,
                    "gen_posting_type": GeneralPostingType.Sales.value,
                    "global_dimension_1": global_dimension_1_value,
                    "gen_bus_posting_group": general_business_group,
                    "gen_prod_posting_group": line.item.general_product_posting_group,
                    "balance_account_type": BalacingAccountType.GLAccount.name,
                    "transaction_no": transaction_no,
                },
            ]

            # Only create receivables and sales entries if there's a net amount after prepayment
            if net_line_amount > Decimal("0.00"):
                gl_entries_for_line.extend(
                    [
                        # Debit: Customer Receivables (net amount = full amount - prepayment portion)
                        {
                            "posting_date": self.posting_date,
                            "document_type": CommonDocumentType.Invoice.value,
                            "document_no": self.document_no,
                            "gl_account": receivables_account,
                            "description": f"Final invoice for {line_label}",
                            "department_code": (
                                global_dimension_1_value.code if global_dimension_1_value else None
                            ),
                            "amount": net_line_amount,
                            "gen_posting_type": GeneralPostingType.Sales.value,
                            "global_dimension_1": global_dimension_1_value,
                            "gen_bus_posting_group": general_business_group,
                            "gen_prod_posting_group": line.item.general_product_posting_group,
                            "balance_account_type": BalacingAccountType.Customer.value,
                            "transaction_no": transaction_no,
                        },
                        # Credit: Sales Account (net amount only - prepayment portion will be credited separately)
                        {
                            "posting_date": self.posting_date,
                            "document_type": CommonDocumentType.Invoice.value,
                            "document_no": self.document_no,
                            "gl_account": sales_account,
                            "description": f"Sales revenue for {line_label}",
                            "department_code": (
                                global_dimension_1_value.code if global_dimension_1_value else None
                            ),
                            "amount": -net_line_amount,
                            "gen_posting_type": GeneralPostingType.Sales.value,
                            "global_dimension_1": global_dimension_1_value,
                            "gen_bus_posting_group": general_business_group,
                            "gen_prod_posting_group": line.item.general_product_posting_group,
                            "balance_account_type": BalacingAccountType.GLAccount.name,
                            "transaction_no": transaction_no,
                        },
                    ]
                )

            entries["gl_entries"].extend(gl_entries_for_line)

        # Add prepayment deduction entry (single entry for the full prepayment amount)
        if prepayment_to_deduct > Decimal("0.00"):
            # Get prepayment account and sales account from posting setup
            posting_setup = GeneralPostingSetup.objects.filter(
                general_business_posting_group=general_business_group,
                prepayment_account__isnull=False,
            ).first()

            if posting_setup and posting_setup.prepayment_account:
                # Get sales account - use the first one from any line's posting setup
                sales_account_for_prepayment = None
                for line in self.lines.select_related(
                    "item", "item__general_product_posting_group"
                ).all():
                    if line.item and line.item.general_product_posting_group:
                        line_posting_setup = GeneralPostingSetup.objects.filter(
                            general_product_posting_group=line.item.general_product_posting_group,
                            general_business_posting_group=general_business_group,
                        ).first()
                        if line_posting_setup and line_posting_setup.sales_account:
                            sales_account_for_prepayment = (
                                line_posting_setup.sales_account
                            )
                            break

                if sales_account_for_prepayment:
                    entries["gl_entries"].extend(
                        [
                            # Debit: Prepayment Account (deducting prepayment)
                            {
                                "posting_date": self.posting_date,
                                "document_type": CommonDocumentType.Invoice.value,
                                "document_no": self.document_no,
                                "gl_account": posting_setup.prepayment_account,
                                "description": f"Prepayment deduction for {self.document_no}",
                                "department_code": (
                                    global_dimension_1_value.code
                                    if global_dimension_1_value
                                    else None
                                ),
                                "amount": prepayment_to_deduct,
                                "gen_posting_type": GeneralPostingType.Sales.value,
                                "global_dimension_1": global_dimension_1_value,
                                "gen_bus_posting_group": general_business_group,
                                "gen_prod_posting_group": None,  # Prepayment deduction is not product-specific
                                "balance_account_type": BalacingAccountType.GLAccount.name,
                                "transaction_no": transaction_no,
                            },
                            # Credit: Sales Account (reducing sales by prepayment amount)
                            {
                                "posting_date": self.posting_date,
                                "document_type": CommonDocumentType.Invoice.value,
                                "document_no": self.document_no,
                                "gl_account": sales_account_for_prepayment,
                                "description": f"Prepayment applied for {self.document_no}",
                                "department_code": (
                                    global_dimension_1_value.code
                                    if global_dimension_1_value
                                    else None
                                ),
                                "amount": -prepayment_to_deduct,
                                "gen_posting_type": GeneralPostingType.Sales.value,
                                "global_dimension_1": global_dimension_1_value,
                                "gen_bus_posting_group": general_business_group,
                                "gen_prod_posting_group": None,
                                "balance_account_type": BalacingAccountType.GLAccount.name,
                                "transaction_no": transaction_no,
                            },
                        ]
                    )

        # Use provided payment_method or fall back to customer's default
        if payment_method is None:
            payment_method = getattr(self.customer, "payment_method", None)

        # Determine if payment entries should be created
        # Only create payment entries if payment_method exists and is not NOT_PAID
        should_create_payment_entries = (
            payment_method is not None and payment_method.code != "NOT_PAID"
        )

        # Customer ledger entry (net amount after prepayment)
        # Only create if there's an actual amount the customer owes (net_receivables > 0)
        if net_receivables > Decimal("0.00"):
            due_date = self.due_date or self.posting_date
            entries["customer_entries"].append(
                {
                    "posting_date": self.posting_date,
                    "document_date": self.document_date,
                    "document_type": CommonDocumentType.Invoice.value,
                    "document_no": self.document_no,
                    "external_document_no": None,
                    "customer_no": self.customer.no,
                    "customer": self.customer,
                    "description": f"Final invoice {self.document_no}",
                    "payment_method": payment_method,
                    "original_amount": net_receivables,
                    "amount": net_receivables,
                    "remaining_amount": net_receivables,
                    "sales": total_invoice_amount,
                    "open": not should_create_payment_entries,  # Closed if payment entries will be created
                    "due_date": due_date,
                    "global_dimension_1": global_dimension_1_value,
                    "dimension_set": dimension_set_value,
                    "user": user,
                    "transaction_no": transaction_no,
                }
            )

            # Add detailed customer ledger entry for the invoice
            entries["detailed_customer_entries"].append(
                {
                    "posting_date": self.posting_date,
                    "entry_type": "Initial Entry",
                    "document_type": "Invoice",
                    "document_no": self.document_no,
                    "customer_no": self.customer.no,
                    "customer": self.customer,
                    "amount": int(net_receivables),
                    "initial_entry_due_date": due_date,
                    "debit_amount": int(net_receivables),
                    "credit_amount": 0,
                    "transaction_no": transaction_no,
                    "initial_document_type": "Invoice",
                    "customer_ledger_entry": "FINAL-INVOICE",  # Placeholder, will be resolved during posting
                    "applied_customer_ledger_entry_no": 0,
                    "unapplied_by_entry_no": 0,
                    "unapplied": False,
                    "global_dimension_1": global_dimension_1_value,
                    "dimension_set": dimension_set_value,
                }
            )

            # Create payment entries only if payment_method is provided and is not NOT_PAID
            if should_create_payment_entries:
                is_cash_payment = bool(
                    payment_method and payment_method.is_cash_payment()
                )

                # Determine which account to use for payment
                if is_cash_payment:
                    payment_account = payment_method.bal_account_no
                    if not payment_account:
                        raise ValidationError(
                            f"Payment method {payment_method.code} is missing a balancing account."
                        )
                    payment_description = "Cash receipt for final invoice"
                    apply_description = "Apply cash receipt to customer"
                else:
                    payment_account = receivables_account
                    payment_description = "Payment received for final invoice"
                    apply_description = "Apply payment to customer"

                # Create G/L entries for payment
                entries["gl_entries"].extend(
                    [
                        {
                            "posting_date": self.posting_date,
                            "document_type": "Payment",
                            "document_no": self.document_no,
                            "gl_account": payment_account,
                            "description": payment_description,
                            "department_code": (
                                global_dimension_1_value.code if global_dimension_1_value else None
                            ),
                            "amount": net_receivables,
                            "transaction_no": transaction_no,
                            "gen_posting_type": GeneralPostingType.Sales.value,
                            "gen_bus_posting_group": general_business_group,
                            "gen_prod_posting_group": None,
                            "global_dimension_1": global_dimension_1_value,
                            "balance_account_type": (
                                BalacingAccountType.GLAccount.name
                                if is_cash_payment
                                else BalacingAccountType.Customer.value
                            ),
                        },
                        {
                            "posting_date": self.posting_date,
                            "document_type": "Payment",
                            "document_no": self.document_no,
                            "gl_account": receivables_account,
                            "description": apply_description,
                            "department_code": (
                                global_dimension_1_value.code if global_dimension_1_value else None
                            ),
                            "amount": -net_receivables,
                            "transaction_no": transaction_no,
                            "gen_posting_type": GeneralPostingType.Sales.value,
                            "gen_bus_posting_group": general_business_group,
                            "gen_prod_posting_group": None,
                            "global_dimension_1": global_dimension_1_value,
                            "balance_account_type": BalacingAccountType.Customer.value,
                        },
                    ]
                )

                # Create Customer Ledger Entry for payment
                entries["customer_entries"].append(
                    {
                        "posting_date": self.posting_date,
                        "document_date": self.document_date,
                        "document_type": "Payment",
                        "document_no": self.document_no,
                        "external_document_no": self.document_no,
                        "customer_no": self.customer.no,
                        "customer": self.customer,
                        "description": f"Final invoice payment {self.document_no}",
                        "payment_method": payment_method,
                        "original_amount": -net_receivables,
                        "amount": -net_receivables,
                        "remaining_amount": -net_receivables,
                        "sales": Decimal("0.00"),
                        "open": False,  # Payment entries are always closed
                        "due_date": due_date,
                        "global_dimension_1": global_dimension_1_value,
                        "dimension_set": dimension_set_value,
                        "user": None,
                        "transaction_no": transaction_no,
                    }
                )

                # Create Detailed Customer Ledger Entries for payment
                entries["detailed_customer_entries"].extend(
                    [
                        {
                            "posting_date": self.posting_date,
                            "entry_type": "Initial Entry",
                            "document_type": "Payment",
                            "document_no": self.document_no,
                            "customer_no": self.customer.no,
                            "customer": self.customer,
                            "amount": net_receivables,
                            "initial_entry_due_date": due_date,
                            "debit_amount": net_receivables,
                            "credit_amount": 0,
                            "initial_document_type": "Payment",
                            "customer_ledger_entry": "FINAL-PAYMENT",
                            "applied_customer_ledger_entry_no": 0,
                            "unapplied_by_entry_no": 0,
                            "unapplied": False,
                            "transaction_no": transaction_no,
                            "global_dimension_1": global_dimension_1_value,
                            "dimension_set": dimension_set_value,
                        },
                        {
                            "posting_date": self.posting_date,
                            "entry_type": "Application",
                            "document_type": "Payment",
                            "document_no": self.document_no,
                            "customer_no": self.customer.no,
                            "customer": self.customer,
                            "amount": net_receivables,
                            "initial_entry_due_date": due_date,
                            "debit_amount": net_receivables,
                            "credit_amount": 0,
                            "initial_document_type": "Payment",
                            "customer_ledger_entry": "FINAL-PAYMENT",
                            "applied_customer_ledger_entry_no": "FINAL-PAYMENT",
                            "unapplied_by_entry_no": 0,
                            "unapplied": False,
                            "transaction_no": transaction_no,
                            "global_dimension_1": global_dimension_1_value,
                            "dimension_set": dimension_set_value,
                        },
                        {
                            "posting_date": self.posting_date,
                            "entry_type": "Application",
                            "document_type": "Payment",
                            "document_no": self.document_no,
                            "customer_no": self.customer.no,
                            "customer": self.customer,
                            "amount": -net_receivables,
                            "initial_entry_due_date": due_date,
                            "debit_amount": 0,
                            "credit_amount": net_receivables,
                            "initial_document_type": "Invoice",
                            "customer_ledger_entry": "FINAL-INVOICE",
                            "applied_customer_ledger_entry_no": "FINAL-PAYMENT",
                            "unapplied_by_entry_no": 0,
                            "unapplied": False,
                            "transaction_no": transaction_no,
                            "global_dimension_1": global_dimension_1_value,
                            "dimension_set": dimension_set_value,
                        },
                    ]
                )

        # Preview PostedSalesInvoice and lines that will be created
        posted_invoice_lines_preview = []

        # Add item lines
        for line in self.lines.select_related(
            "item", "item_unit_of_measure", "item_unit_of_measure__unit_of_measure"
        ).all():
            if not line.item:
                continue

            # Get location for the line
            location = None
            if user and hasattr(user, "global_dimension_1") and user.global_dimension_1:
                from items.models import Location

                location = Location.objects.filter(code=user.global_dimension_1.code).first()
            if not location:
                from items.models import Location

                location = Location.objects.first()

            line_amount = line.amount or Decimal("0.00")
            quantity = line.quantity or Decimal("0.00")
            unit_price = line.unit_price or Decimal("0.00")

            # Calculate prepayment portion for this line
            line_prepayment_portion = (
                (prepayment_to_deduct * line_amount / total_invoice_amount)
                if total_invoice_amount > 0
                else Decimal("0.00")
            )
            net_line_amount = line_amount - line_prepayment_portion

            # Only add line if there's a net amount (or if we want to show all lines)
            if net_line_amount > Decimal("0.00") or line_amount > Decimal("0.00"):
                posted_invoice_lines_preview.append(
                    {
                        "type": "Item",
                        "no": line.item.no if line.item else None,
                        "item_reference_no": None,
                        "description": line.description or line.item.item_name or "",
                        "quantity": int(quantity),
                        "unit_of_measure_code": (
                            line.item_unit_of_measure.unit_of_measure.code
                            if line.item_unit_of_measure
                            and line.item_unit_of_measure.unit_of_measure
                            else None
                        ),
                        "unit_price_incl_vat": float(
                            net_line_amount if net_line_amount > 0 else line_amount
                        ),
                        "item": line.item,
                        "location": location,
                    }
                )

        # Add G/L Account line for prepayment deduction
        if prepayment_to_deduct > Decimal("0.00"):
            posting_setup = GeneralPostingSetup.objects.filter(
                general_business_posting_group=general_business_group,
                prepayment_account__isnull=False,
            ).first()

            if posting_setup and posting_setup.prepayment_account:
                posted_invoice_lines_preview.append(
                    {
                        "type": "G/L Account",
                        "no": posting_setup.prepayment_account.no,
                        "item_reference_no": None,
                        "description": posting_setup.prepayment_account.name,
                        "quantity": -1,  # As shown in the image
                        "unit_of_measure_code": None,
                        "unit_price_incl_vat": float(prepayment_to_deduct),
                        "gl_account": posting_setup.prepayment_account,
                        "item": None,
                        "location": None,
                    }
                )

        return {
            "entries": entries,
            "total_invoice_amount": total_invoice_amount,
            "prepayment_to_deduct": prepayment_to_deduct,
            "net_receivables": net_receivables,
            "transaction_no": transaction_no,
            "posted_invoice_lines": posted_invoice_lines_preview,
        }

    def post_document(self, user, payment_method=None):
        import logging
        logger = logging.getLogger(__name__)
        print(f"[Preayment.post_document] Called with payment_method: {payment_method} (type: {type(payment_method)})")
        logger.error(f"[Preayment.post_document] Called with payment_method: {payment_method} (type: {type(payment_method)})")
        processor = PrepaymentPostingProcessor(
            self, user, payment_method=payment_method
        )
        print(f"[Preayment.post_document] Processor created, calling processor.post()")
        logger.error(f"[Preayment.post_document] Processor created, calling processor.post()")
        return processor.post()

    def post_final_invoice(self, user, payment_method=None):
        """
        Post final sales invoice from prepayment.
        Creates PostedSalesInvoice with item lines and G/L Account line for prepayment deduction.
        """
        processor = FinalInvoicePostingProcessor(
            self, user, payment_method=payment_method
        )
        return processor.post()


class PreaymentLine(BaseModel):
    document = models.ForeignKey(
        Preayment,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("Preayment Document"),
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepayment_lines",
    )
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_prepayment_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_prepayment_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    tracking_code = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        verbose_name=_("Tracking Code"),
        help_text=_(
            "Optional tracking/lot reference associated with this prepayment line."
        ),
    )
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1.00")
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("0.00")
    )
    deposit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt. Line Amount"),
        help_text=_("Amount received from customer for this prepayment line"),
    )
    deposit_percent = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt. Line Amount %"),
        help_text=_("Calculated percentage based on deposit amount vs line total"),
    )
    prepayment_amount_invoiced = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt. Amt. Inv."),
        help_text=_("Portion of the deposit already invoiced"),
    )
    prepayment_amount_to_deduct = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt Amt to Deduct"),
        help_text=_("Amount of invoiced prepayment to apply next"),
    )
    prepayment_amount_deducted = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Prepmt Amt Deducted"),
        help_text=_("Cumulative prepayment applied to final invoices"),
    )
    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="preayment_lines",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="preayment_lines_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="preayment_lines",
        verbose_name=_("Dimension Set"),
    )
    installment_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("New Installment"),
        help_text=_(
            "Enter the additional deposit collected for this line; it will be added to the Prepmt. Line Amount when you save."
        ),
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Preayment Line")
        verbose_name_plural = _("Preayment Lines")

    def __str__(self):
        return f"{self.document.document_no} - {self.description or self.item}"

    @staticmethod
    def _coerce_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
        """JSON/API may send numeric fields as strings; DecimalField accepts them but save() math must use Decimal."""
        if value is None or value == "":
            return default
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value).strip())
        except (ValueError, TypeError, ArithmeticError):
            return default

    def clean(self):
        if self.quantity <= 0:
            raise ValueError("Quantity must be greater than zero")

        line_total = self._line_total
        if self.deposit_amount < Decimal("0.00"):
            raise ValueError("Prepmt. Line Amount cannot be negative")
        if line_total and self.deposit_amount > line_total:
            raise ValueError("Prepmt. Line Amount cannot exceed line total")

        if self.prepayment_amount_invoiced < Decimal("0.00"):
            raise ValueError("Prepmt. Amt. Inv. cannot be negative")
        if self.prepayment_amount_invoiced > self.deposit_amount:
            raise ValueError("Prepmt. Amt. Inv. cannot exceed collected deposit")

        if self.prepayment_amount_deducted < Decimal("0.00"):
            raise ValueError("Prepmt Amt Deducted cannot be negative")
        if self.prepayment_amount_deducted > self.prepayment_amount_invoiced:
            raise ValueError(
                "Prepmt Amt Deducted cannot exceed invoiced prepayment amount"
            )

        remaining_invoiced = (
            self.prepayment_amount_invoiced - self.prepayment_amount_deducted
        )
        if self.prepayment_amount_to_deduct < Decimal("0.00"):
            raise ValueError("Prepmt Amt to Deduct cannot be negative")
        if self.prepayment_amount_to_deduct > remaining_invoiced:
            raise ValueError(
                "Prepmt Amt to Deduct cannot exceed remaining invoiced deposit"
            )

    def save(self, *args, **kwargs):
        if self.item and not self.description:
            self.description = self.item.item_name
        self.quantity = self._coerce_decimal(self.quantity, Decimal("0"))
        self.unit_price = self._coerce_decimal(self.unit_price, Decimal("0"))
        inst = self._coerce_decimal(self.installment_amount, Decimal("0"))
        self.installment_amount = inst
        if inst and inst > Decimal("0.00"):
            current_deposit = self._coerce_decimal(self.deposit_amount, Decimal("0.00"))
            self.deposit_amount = current_deposit + inst
            self.installment_amount = Decimal("0.00")
        quantity = self.quantity
        unit_price = self.unit_price
        # unit_price is already adjusted for the selected UOM (adjusted by frontend)
        self.amount = quantity * unit_price

        self._recalculate_deposit_fields()
        self.clean()

        super().save(*args, **kwargs)
        self.document.recalculate_totals()

    @property
    def _line_total(self) -> Decimal:
        quantity = self._coerce_decimal(self.quantity, Decimal("0"))
        unit_price = self._coerce_decimal(self.unit_price, Decimal("0"))
        # unit_price is already adjusted for the selected UOM
        return quantity * unit_price

    @property
    def base_unit_price(self) -> Decimal:
        """Base unit price from item card (price per base UOM)."""
        if self.item and self.item.unit_price:
            return Decimal(str(self.item.unit_price))
        return Decimal("0.00")

    def _recalculate_deposit_fields(self):
        line_total = self._line_total
        if line_total > Decimal("0.00"):
            self.deposit_percent = (
                (self.deposit_amount / line_total) * Decimal("100")
            ).quantize(Decimal("0.01"))
        else:
            self.deposit_percent = Decimal("0.00")

        remaining_invoiced = (
            self.prepayment_amount_invoiced - self.prepayment_amount_deducted
        )
        if remaining_invoiced < Decimal("0.00"):
            remaining_invoiced = Decimal("0.00")
        if self.prepayment_amount_to_deduct > remaining_invoiced:
            self.prepayment_amount_to_deduct = remaining_invoiced

    @property
    def installment_draft_amount(self) -> Decimal:
        try:
            return self.installment_draft.amount
        except Exception:
            return Decimal("0.00")

    @property
    def preview_deposit_total(self) -> Decimal:
        """
        Read-only preview based on posted portion plus draft installment.
        This intentionally ignores deposit_amount and shows what the posted exposure
        would become after applying the draft during posting, clamped to line amount.
        """
        posted = self.prepayment_amount_invoiced or Decimal("0.00")
        draft = self.installment_draft_amount or Decimal("0.00")
        target = self.amount or Decimal("0.00")
        preview = posted + draft
        if preview > target:
            preview = target
        if preview < Decimal("0.00"):
            preview = Decimal("0.00")
        return preview


class PreaymentLineInstallmentDraft(BaseModel):
    """
    One editable draft installment value per prepayment line.
    This allows operators to adjust the draft amount freely in admin/UI without
    immediately affecting collected deposits. The draft will be applied to the
    line's deposit_amount during posting or an explicit apply action.
    """

    line = models.OneToOneField(
        PreaymentLine,
        on_delete=models.CASCADE,
        related_name="installment_draft",
        verbose_name=_("Prepayment Line"),
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Draft Installment Amount"),
        help_text=_("Editable draft installment not yet collected."),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_prepayment_installment_drafts",
    )

    class Meta:
        verbose_name = _("Preayment Line Installment Draft")
        verbose_name_plural = _("Preayment Line Installment Drafts")

    def __str__(self):
        return f"Draft for Line {self.line_id}: {self.amount}"


class PreaymentLineInstallmentHistory(BaseModel):
    """
    Archive of applied draft installments at posting time.
    DEPRECATED: Use PreaymentInstallmentHistory for new documents.
    Kept for historical data migration.
    """

    line = models.ForeignKey(
        PreaymentLine,
        on_delete=models.CASCADE,
        related_name="installment_history",
        verbose_name=_("Prepayment Line"),
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Applied Installment Amount"),
    )
    transaction_no = models.CharField(max_length=100, blank=True, null=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_prepayment_installment_histories",
    )

    class Meta:
        verbose_name = _("Preayment Line Installment History")
        verbose_name_plural = _("Preayment Line Installment Histories")


class PreaymentInstallmentDraft(BaseModel):
    """
    One editable draft installment value per prepayment document (header-level).
    This allows operators to adjust the draft amount freely in admin/UI without
    immediately affecting collected deposits. The draft will be applied to the
    document's total_prepayment during posting.
    """

    document = models.OneToOneField(
        Preayment,
        on_delete=models.CASCADE,
        related_name="installment_draft",
        verbose_name=_("Prepayment Document"),
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Draft Installment Amount"),
        help_text=_("Editable draft installment not yet collected."),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_prepayment_document_installment_drafts",
    )

    class Meta:
        verbose_name = _("Preayment Installment Draft")
        verbose_name_plural = _("Preayment Installment Drafts")

    def __str__(self):
        return f"Draft for Document {self.document.document_no}: {self.amount}"


class PreaymentInstallmentHistory(BaseModel):
    """
    Archive of applied draft installments at posting time (header-level).
    """

    document = models.ForeignKey(
        Preayment,
        on_delete=models.CASCADE,
        related_name="installment_history",
        verbose_name=_("Prepayment Document"),
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Applied Installment Amount"),
    )
    transaction_no = models.CharField(max_length=100, blank=True, null=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_prepayment_document_installment_histories",
    )

    class Meta:
        verbose_name = _("Preayment Installment History")
        verbose_name_plural = _("Preayment Installment Histories")
        ordering = ["-created_at"]


class PrepaymentPostingProcessor:
    def __init__(self, document: Preayment, user, payment_method=None):
        import logging
        logger = logging.getLogger(__name__)
        print(f"[PrepaymentPostingProcessor.__init__] payment_method received: {payment_method} (type: {type(payment_method)})")
        logger.error(f"[PrepaymentPostingProcessor.__init__] payment_method received: {payment_method} (type: {type(payment_method)})")
        self.document = document
        self.user = user
        self.payment_method = payment_method
        self.global_dimension_1 = getattr(user, "global_dimension_1", None)
        print(f"[PrepaymentPostingProcessor.__init__] self.payment_method set to: {self.payment_method}")
        logger.error(f"[PrepaymentPostingProcessor.__init__] self.payment_method set to: {self.payment_method}")

    def post(self):
        self.document.assert_can_collect_installment()

        # Compute transaction_no same as preview for consistent archiving
        transaction_no = f"PRE{self.document.document_no}-{self.document.posting_date.strftime('%Y%m%d')}-{self.document.id}"

        # Apply document-level draft installment into total_prepayment prior to posting
        # Validate that applying draft won't exceed document target
        from prepayment.models import (
            PreaymentInstallmentDraft,
            PreaymentInstallmentHistory,
        )

        draft = getattr(self.document, "installment_draft", None)
        draft_amount = Decimal("0.00")
        try:
            if draft:
                draft_amount = draft.amount or Decimal("0.00")
        except Exception:
            draft_amount = Decimal("0.00")

        if draft_amount and draft_amount > Decimal("0.00"):
            target = self.document.total_amount or Decimal("0.00")
            invoiced = self.document.total_prepayment_invoiced or Decimal("0.00")
            # Remaining collectible = target - invoiced (don't subtract current_deposit as it includes invoiced amounts)
            # This matches the logic in remaining_prepayment property
            remaining_collectible = target - invoiced
            if remaining_collectible < Decimal("0.00"):
                remaining_collectible = Decimal("0.00")
            if draft_amount > remaining_collectible:
                raise ValidationError(
                    f"Draft installment {draft_amount} exceeds remaining collectible {remaining_collectible} for document {self.document.document_no}."
                )
            # Apply draft into total_prepayment
            current_deposit = self.document.total_prepayment or Decimal("0.00")
            self.document.total_prepayment = current_deposit + draft_amount
            # Reset draft amount
            if draft:
                draft.amount = Decimal("0.00")
                draft.updated_by = self.user
                draft.save(update_fields=["amount", "updated_by", "updated_at"])
            # Persist document
            self.document.save(update_fields=["total_prepayment", "updated_at"])
            # Archive in document-level history
            PreaymentInstallmentHistory.objects.create(
                document=self.document,
                amount=draft_amount,
                transaction_no=transaction_no,
                applied_by=self.user,
            )

        import logging
        logger = logging.getLogger(__name__)
        print(f"[PrepaymentPostingProcessor.post] About to call build_posting_preview with payment_method: {self.payment_method}")
        logger.error(f"[PrepaymentPostingProcessor.post] About to call build_posting_preview with payment_method: {self.payment_method}")
        preview_data = self.document.build_posting_preview(user=self.user, payment_method=self.payment_method)
        entries = preview_data["entries"]
        transaction_no = preview_data["transaction_no"]
        line_context = preview_data["line_context"]
        total_deposit = preview_data["total_deposit"]
        due_date = self.document.due_date or self.document.posting_date

        with transaction.atomic():
            posted_invoice = PostedSalesInvoice.objects.create(
                customer=self.document.customer,
                document_date=self.document.document_date,
                posting_date=self.document.posting_date,
                vat_date=self.document.posting_date,
                due_date=due_date,
                customer_invoice_no=self.document.document_no,
                contact_person=self.document.contact_person,
                preayment=self.document,
                global_dimension_1=getattr(self.document, "global_dimension_1", None)
                or self.global_dimension_1,
                global_dimension_2=getattr(self.document, "global_dimension_2", None),
                dimension_set=getattr(self.document, "dimension_set", None),
            )

            for ctx in line_context:
                line_amount = ctx["amount"]
                # Use Decimal rounding instead of int() to preserve precision
                # Round to 2 decimal places for currency
                rounded_amount = line_amount.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                PostedSalesInvoiceLine.objects.create(
                    posted_sales_invoice=posted_invoice,
                    gl_account=ctx["prepayment_account"],
                    description=ctx["label"],
                    quantity=1,
                    unit_price=rounded_amount,
                    amount=rounded_amount,
                    global_dimension_1=(
                        getattr(self.document, "global_dimension_1", None)
                        or self.global_dimension_1
                    ),
                    dimension_set=getattr(self.document, "dimension_set", None),
                )

                # Update document-level invoiced amounts (not line-level)
                # Lines no longer track deposit amounts individually
                pass

            # Update document-level totals after all lines processed
            total_invoiced = sum(ctx["amount"] for ctx in line_context)
            self.document.total_prepayment_invoiced = (
                self.document.total_prepayment_invoiced or Decimal("0.00")
            ) + total_invoiced
            self.document.total_prepayment_to_deduct = (
                self.document.total_prepayment_to_deduct or Decimal("0.00")
            ) + total_invoiced
            self.document.save(
                update_fields=[
                    "total_prepayment_invoiced",
                    "total_prepayment_to_deduct",
                    "updated_at",
                ]
            )

            from dimension.models import get_posting_dimension_payload

            for gl_entry in entries["gl_entries"]:
                dim_payload = get_posting_dimension_payload(
                    global_dimension_1=gl_entry.get("global_dimension_1"),
                    dimension_set=gl_entry.get("dimension_set"),
                )
                GeneralLedgerEntry.objects.create(
                    gl_account=gl_entry["gl_account"],
                    posting_date=gl_entry["posting_date"],
                    document_type=gl_entry["document_type"],
                    document_no=posted_invoice.no,
                    description=gl_entry["description"],
                    amount=float(gl_entry["amount"]),
                    user=self.user,
                    balancing_account_type=coerce_balancing_account_type(
                        gl_entry.get("balance_account_type")
                    ),
                    general_posting_type=gl_entry.get("gen_posting_type"),
                    general_business_posting_group=gl_entry.get(
                        "gen_bus_posting_group"
                    ),
                    general_product_posting_group=gl_entry.get(
                        "gen_prod_posting_group"
                    ),
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                    transaction_no=transaction_no,
                )

            ledger_invoice = None
            ledger_payment = None
            created_ledgers = []
            is_cash_payment = bool(
                self.document.customer.payment_method
                and self.document.customer.payment_method.is_cash_payment()
            )

            for entry in entries["customer_entries"]:
                document_type = (
                    DOCUMENT_TYPE.Invoice.value
                    if entry["document_type"] == "Invoice"
                    else DOCUMENT_TYPE.Payment.value
                )
                from dimension.models import get_posting_dimension_payload

                cust_dim = get_posting_dimension_payload(
                    global_dimension_1=entry.get("global_dimension_1"),
                    dimension_set=entry.get("dimension_set"),
                )
                ledger = CustomerLedgerEntry.objects.create(
                    posting_date=entry["posting_date"],
                    document_date=entry["document_date"],
                    document_type=document_type,
                    document_no=posted_invoice.no,
                    customer=self.document.customer,
                    description=entry["description"],
                    payment_method=entry["payment_method"],
                    original_amount=int(entry["original_amount"]),
                    amount=int(entry["amount"]),
                    sales=int(entry["sales"]),
                    open=False if is_cash_payment else entry["open"],
                    due_date=entry["due_date"],
                    external_document_no=(
                        entry["external_document_no"] or self.document.document_no
                    ),
                    global_dimension_1=cust_dim["global_dimension_1"],
                    dimension_set=cust_dim["dimension_set"],
                    transaction_no=transaction_no,
                    user=self.user,
                )
                created_ledgers.append(ledger)
                if entry["document_type"] == "Invoice":
                    ledger_invoice = ledger
                else:
                    ledger_payment = ledger

            for detailed in entries["detailed_customer_entries"]:
                if detailed["document_type"] == "Invoice":
                    target_ledger = ledger_invoice
                else:
                    target_ledger = ledger_payment or ledger_invoice

                if target_ledger is None:
                    raise ValidationError(
                        "Unable to resolve customer ledger entry for detailed postings."
                    )

                applied_entry_no = 0
                if detailed["entry_type"] == "Application":
                    if detailed["initial_document_type"] == "Invoice":
                        applied_entry_no = ledger_payment.id if ledger_payment else 0
                    else:
                        applied_entry_no = ledger_invoice.id if ledger_invoice else 0

                det_dim = get_posting_dimension_payload(
                    global_dimension_1=detailed.get("global_dimension_1"),
                    dimension_set=detailed.get("dimension_set"),
                )

                DetailedCustomerLedgerEntry.objects.create(
                    posting_date=detailed["posting_date"],
                    entry_type=(
                        CommonEntryType.initial.value
                        if detailed["entry_type"] == "Initial Entry"
                        else CommonEntryType.application.value
                    ),
                    document_type=(
                        CommonDocumentType.Invoice.value
                        if detailed["document_type"] == "Invoice"
                        else CommonDocumentType.Payment.value
                    ),
                    document_no=posted_invoice.no,
                    customer=self.document.customer,
                    amount=int(detailed["amount"]),
                    debit_amount=int(detailed["debit_amount"]),
                    credit_amount=int(detailed["credit_amount"]),
                    initial_entry_due_date=detailed.get(
                        "initial_entry_due_date", due_date
                    ),
                    initial_document_type=(
                        CommonDocumentType.Invoice.value
                        if detailed["initial_document_type"] == "Invoice"
                        else CommonDocumentType.Payment.value
                    ),
                    customer_ledger_entry=target_ledger,
                    applied_customer_ledger_entry_no=applied_entry_no,
                    unapplied_by_entry_no=detailed.get("unapplied_by_entry_no", 0),
                    unapplied=detailed.get("unapplied", False),
                    global_dimension_1=det_dim["global_dimension_1"],
                    dimension_set=det_dim["dimension_set"],
                    transaction_no=transaction_no,
                )

            self.document.recalculate_totals()
            # Stay draft until final invoice is posted; installment posting only
            # updates prepayment-invoiced totals.
            self.document.save(update_fields=["updated_at"])

        return {
            "posted_invoice": posted_invoice,
            "transaction_no": transaction_no,
            "total_deposit": total_deposit,
        }


class FinalInvoicePostingProcessor:
    """
    Processor for posting final sales invoices from prepayments.
    Creates PostedSalesInvoice with item lines and G/L Account line for prepayment deduction.
    """

    def __init__(self, document: Preayment, user, payment_method=None):
        self.document = document
        self.user = user
        self.payment_method = payment_method
        self.global_dimension_1 = getattr(user, "global_dimension_1", None) if user else None

    def post(self):
        """
        Post the final invoice, creating PostedSalesInvoice and all related entries.
        """
        from django.db import transaction
        from sales.models import PostedSalesInvoice, PostedSalesInvoiceLine
        from items.models import Location
        from helpers.helpers import generate_document_number
        from helpers.helpers import ConfigurationError
        from sales.models import SalesReceivable
        from postings.models import GeneralPostingSetup

        self.document.assert_can_post_final_invoice()

        # Build preview to get all entries - this ensures we post exactly what's in the preview
        preview_data = self.document.build_final_invoice_posting_preview(
            self.user, payment_method=self.payment_method
        )
        entries = preview_data["entries"]
        prepayment_to_deduct = preview_data["prepayment_to_deduct"]
        total_invoice_amount = preview_data["total_invoice_amount"]
        net_receivables = preview_data["net_receivables"]
        transaction_no = preview_data.get("transaction_no")

        # Get location
        location = None
        if self.user and hasattr(self.user, "global_dimension_1") and self.user.global_dimension_1:
            location = Location.objects.filter(code=self.user.global_dimension_1.code).first()
        if not location:
            location = Location.objects.first()
        if not location:
            raise ValidationError("No location found. Please create a location first.")

        due_date = self.document.due_date or self.document.posting_date

        with transaction.atomic():
            header_dim = self.document._get_posting_dimension_payload(self.user)

            # Create PostedSalesInvoice (copy dimensions from prepayment document)
            posted_invoice = PostedSalesInvoice.objects.create(
                customer=self.document.customer,
                document_date=self.document.document_date,
                posting_date=self.document.posting_date,
                vat_date=self.document.posting_date,
                due_date=due_date,
                customer_invoice_no=self.document.document_no,
                contact_person=self.document.contact_person,
                preayment=self.document,
                global_dimension_1=header_dim["global_dimension_1"],
                global_dimension_2=header_dim["global_dimension_2"],
                dimension_set=header_dim["dimension_set"],
            )

            from dimension.models import get_posting_dimension_payload

            # Create PostedSalesInvoiceLines for each item
            for line in self.document.lines.select_related(
                "item", "item_unit_of_measure", "item_unit_of_measure__unit_of_measure"
            ).all():
                if not line.item:
                    continue

                line_amount = line.amount or Decimal("0.00")
                quantity = line.quantity or Decimal("0.00")

                # Calculate prepayment portion for this line
                line_prepayment_portion = (
                    (prepayment_to_deduct * line_amount / total_invoice_amount)
                    if total_invoice_amount > 0
                    else Decimal("0.00")
                )
                net_line_amount = line_amount - line_prepayment_portion

                # Only create line if there's a net amount
                if net_line_amount > Decimal("0.00"):
                    unit_price = (
                        int(net_line_amount / quantity)
                        if quantity > 0
                        else int(net_line_amount)
                    )
                    amount = int(net_line_amount)

                    line_dim = get_posting_dimension_payload(
                        global_dimension_1=getattr(line, "global_dimension_1", None)
                        or getattr(self.document, "global_dimension_1", None)
                        or self.global_dimension_1,
                        global_dimension_2=getattr(line, "global_dimension_2", None)
                        or getattr(self.document, "global_dimension_2", None),
                        dimension_set=getattr(line, "dimension_set", None)
                        or getattr(self.document, "dimension_set", None),
                    )

                    PostedSalesInvoiceLine.objects.create(
                        posted_sales_invoice=posted_invoice,
                        item=line.item,
                        description=line.description or line.item.item_name or "",
                        location_code=location,
                        quantity=int(quantity),
                        item_unit_of_measure=line.item_unit_of_measure,
                        unit_of_measure=(
                            line.item_unit_of_measure.unit_of_measure
                            if line.item_unit_of_measure
                            else None
                        ),
                        unit_price=unit_price,
                        amount=amount,
                        global_dimension_1=line_dim["global_dimension_1"],
                        dimension_set=line_dim["dimension_set"],
                    )

            # Create G/L Account line for prepayment deduction
            if prepayment_to_deduct > Decimal("0.00"):
                posting_setup = GeneralPostingSetup.objects.filter(
                    general_business_posting_group=self.document.customer.general_business_posting_group,
                    prepayment_account__isnull=False,
                ).first()

                if posting_setup and posting_setup.prepayment_account:
                    gl_line_dim = get_posting_dimension_payload(
                        global_dimension_1=header_dim["global_dimension_1"],
                        global_dimension_2=header_dim["global_dimension_2"],
                        dimension_set=header_dim["dimension_set"],
                    )
                    PostedSalesInvoiceLine.objects.create(
                        posted_sales_invoice=posted_invoice,
                        item=None,
                        gl_account=posting_setup.prepayment_account,
                        description=posting_setup.prepayment_account.name,
                        location_code=None,
                        quantity=-1,  # As shown in the image
                        item_unit_of_measure=None,
                        unit_of_measure=None,
                        unit_price=int(prepayment_to_deduct),
                        amount=int(prepayment_to_deduct),
                        global_dimension_1=gl_line_dim["global_dimension_1"],
                        dimension_set=gl_line_dim["dimension_set"],
                    )

            # Create General Ledger Entries - use ALL entries from preview
            from financials.models import GeneralLedgerEntry
            from financials.enums import BalacingAccountType
            from common.enums import DocumentType as CommonDocumentType

            # Post ALL GL entries from preview (including prepayment deduction entries)
            # The preview method creates all entries including:
            # - COGS (debit) and Inventory (credit) for each line
            # - Customer Receivables (debit) and Sales (credit) for net amounts
            # - Prepayment Account (debit) and Sales Account (credit) for prepayment deduction
            # We post ALL of them exactly as shown in the preview
            # Use the prepayment document number (from preview) for all entries to match the preview
            prepayment_document_no = self.document.document_no
            for gl_entry in entries["gl_entries"]:
                # Ensure all required fields are present
                if not gl_entry.get("gl_account"):
                    continue  # Skip entries without GL account

                from dimension.models import get_posting_dimension_payload

                dim_payload = get_posting_dimension_payload(
                    global_dimension_1=gl_entry.get("global_dimension_1"),
                    dimension_set=gl_entry.get("dimension_set"),
                )
                GeneralLedgerEntry.objects.create(
                    gl_account=gl_entry["gl_account"],
                    posting_date=gl_entry["posting_date"],
                    document_type=gl_entry["document_type"],
                    document_no=prepayment_document_no,  # Use prepayment document number to match preview
                    description=gl_entry["description"],
                    amount=float(gl_entry["amount"]),
                    user=self.user,
                    balancing_account_type=coerce_balancing_account_type(
                        gl_entry.get("balance_account_type")
                    ),
                    general_posting_type=gl_entry.get("gen_posting_type"),
                    general_business_posting_group=gl_entry.get(
                        "gen_bus_posting_group"
                    ),
                    general_product_posting_group=gl_entry.get(
                        "gen_prod_posting_group"
                    ),
                    dimension_set=dim_payload["dimension_set"],
                    global_dimension_1=dim_payload["global_dimension_1"],
                    global_dimension_2=dim_payload["global_dimension_2"],
                    transaction_no=transaction_no,
                )

            # Create Customer Ledger Entries
            from sales.models import CustomerLedgerEntry
            from common.enums import DocumentType as DOCUMENT_TYPE

            ledger_invoice = None
            is_cash_payment = bool(
                self.document.customer.payment_method
                and self.document.customer.payment_method.is_cash_payment()
            )

            for entry in entries["customer_entries"]:
                document_type = (
                    DOCUMENT_TYPE.Invoice.value
                    if entry["document_type"] == "Invoice"
                    else DOCUMENT_TYPE.Payment.value
                )
                from dimension.models import get_posting_dimension_payload

                cust_dim = get_posting_dimension_payload(
                    global_dimension_1=entry.get("global_dimension_1"),
                    dimension_set=entry.get("dimension_set"),
                )
                ledger = CustomerLedgerEntry.objects.create(
                    posting_date=entry["posting_date"],
                    document_date=entry["document_date"],
                    document_type=document_type,
                    document_no=posted_invoice.no,
                    customer=self.document.customer,
                    description=entry["description"],
                    payment_method=entry.get("payment_method"),
                    original_amount=int(entry["original_amount"]),
                    amount=int(entry["amount"]),
                    sales=int(entry["sales"]),
                    open=False if is_cash_payment else entry["open"],
                    due_date=entry["due_date"],
                    external_document_no=entry.get("external_document_no")
                    or self.document.document_no,
                    global_dimension_1=cust_dim["global_dimension_1"],
                    dimension_set=cust_dim["dimension_set"],
                    transaction_no=transaction_no,
                    user=self.user,
                )
                if entry["document_type"] == "Invoice":
                    ledger_invoice = ledger

            # Create Detailed Customer Ledger Entries
            for detailed in entries["detailed_customer_entries"]:
                # Determine target ledger entry
                if detailed["document_type"] == "Invoice":
                    target_ledger = ledger_invoice
                else:
                    target_ledger = (
                        ledger_invoice  # For final invoice, only invoice entry exists
                    )

                if target_ledger is None:
                    raise ValidationError(
                        "Unable to resolve customer ledger entry for detailed postings."
                    )

                # Determine applied entry number (for final invoice, typically 0 as it's initial)
                applied_entry_no = 0
                if detailed["entry_type"] == "Application":
                    # For applications, we'd reference other entries, but for final invoice
                    # it's typically an initial entry
                    applied_entry_no = 0

                from dimension.models import get_posting_dimension_payload

                det_dim = get_posting_dimension_payload(
                    global_dimension_1=detailed.get("global_dimension_1"),
                    dimension_set=detailed.get("dimension_set"),
                )

                DetailedCustomerLedgerEntry.objects.create(
                    posting_date=detailed["posting_date"],
                    entry_type=(
                        CommonEntryType.initial.value
                        if detailed["entry_type"] == "Initial Entry"
                        else CommonEntryType.application.value
                    ),
                    document_type=(
                        CommonDocumentType.Invoice.value
                        if detailed["document_type"] == "Invoice"
                        else CommonDocumentType.Payment.value
                    ),
                    document_no=posted_invoice.no,
                    customer=self.document.customer,
                    amount=int(detailed["amount"]),
                    debit_amount=int(detailed["debit_amount"]),
                    credit_amount=int(detailed["credit_amount"]),
                    initial_entry_due_date=detailed.get(
                        "initial_entry_due_date", due_date
                    ),
                    initial_document_type=(
                        CommonDocumentType.Invoice.value
                        if detailed["initial_document_type"] == "Invoice"
                        else CommonDocumentType.Payment.value
                    ),
                    customer_ledger_entry=target_ledger,
                    applied_customer_ledger_entry_no=applied_entry_no,
                    unapplied_by_entry_no=detailed.get("unapplied_by_entry_no", 0),
                    unapplied=detailed.get("unapplied", False),
                    global_dimension_1=det_dim["global_dimension_1"],
                    dimension_set=det_dim["dimension_set"],
                    transaction_no=transaction_no,
                )

            # Create Item Ledger Entries and Value Entries
            from items.models import ItemLedgerEntries, ValueEntry
            from items.enums import EntryType, DocumentType

            # First, reduce inventory quantities in existing ItemLedgerEntries (FIFO)
            # Group item entries by item and location to reduce quantities
            item_reductions = {}
            for item_entry in entries["item_entries"]:
                item = item_entry["item"]
                location = item_entry["location"]
                quantity_to_reduce = abs(
                    int(item_entry["quantity"])
                )  # Quantity is negative for sales

                # Item uses 'no' as primary key, not 'id'
                key = (
                    item.no if hasattr(item, "no") else item.pk,
                    location.pk if location else None,
                )
                if key not in item_reductions:
                    item_reductions[key] = {
                        "item": item,
                        "location": location,
                        "quantity": 0,
                    }
                item_reductions[key]["quantity"] += quantity_to_reduce

            # Actually reduce inventory quantities
            for key, reduction_info in item_reductions.items():
                item = reduction_info["item"]
                location = reduction_info["location"]
                quantity_to_reduce = reduction_info["quantity"]

                # Get entries to reduce (FIFO)
                if item.tracking_code:
                    # Items with tracking: order by expiry_date (FEFO)
                    inventory_entries = ItemLedgerEntries.objects.filter(
                        item=item,
                        remaining_quantity__gt=0,
                        location=location,
                    ).order_by("expiry_date", "created_at")
                else:
                    # Items without tracking: use FIFO
                    inventory_entries = ItemLedgerEntries.objects.filter(
                        item=item,
                        remaining_quantity__gt=0,
                        location=location,
                    ).order_by("created_at")

                remaining_to_reduce = quantity_to_reduce
                for entry in inventory_entries:
                    if remaining_to_reduce <= 0:
                        break
                    reduction = min(entry.remaining_quantity, remaining_to_reduce)
                    entry.remaining_quantity -= reduction
                    entry.save(update_fields=["remaining_quantity"])
                    remaining_to_reduce -= reduction

                if remaining_to_reduce > 0:
                    raise ValidationError(
                        f"Insufficient inventory for {item.item_name} at location {location.code if location else 'N/A'}. "
                        f"Shortage: {remaining_to_reduce} units"
                    )

            # Now create new Item Ledger Entries and Value Entries for the sales transaction
            # Map prepayment lines to item entries to get ItemUnitOfMeasure
            line_map = {
                line.item.no: line
                for line in self.document.lines.select_related(
                    "item", "item_unit_of_measure"
                ).all()
                if line.item
            }

            for item_entry, value_entry in zip(
                entries["item_entries"], entries["value_entries"]
            ):
                item = item_entry["item"]
                # Get ItemUnitOfMeasure from the prepayment line
                prepayment_line = line_map.get(
                    item.no if hasattr(item, "no") else item.pk
                )
                item_unit_of_measure = None
                if prepayment_line and prepayment_line.item_unit_of_measure:
                    item_unit_of_measure = prepayment_line.item_unit_of_measure
                else:
                    # Fallback: try to get default ItemUnitOfMeasure for this item
                    from items.models import ItemUnitOfMeasure

                    item_unit_of_measure = ItemUnitOfMeasure.objects.filter(
                        item=item, default=True
                    ).first()
                    if not item_unit_of_measure:
                        # Get any ItemUnitOfMeasure for this item
                        item_unit_of_measure = ItemUnitOfMeasure.objects.filter(
                            item=item
                        ).first()

                # Get unit_of_measure string for the unit_of_measure field
                unit_of_measure_str = "PCS"  # Default
                if item_unit_of_measure and item_unit_of_measure.unit_of_measure:
                    unit_of_measure_str = item_unit_of_measure.unit_of_measure.code
                elif item_entry.get("unit_of_measure"):
                    # Fallback to what's in the preview
                    unit_of_measure_obj = item_entry.get("unit_of_measure")
                    if hasattr(unit_of_measure_obj, "code"):
                        unit_of_measure_str = unit_of_measure_obj.code
                    elif isinstance(unit_of_measure_obj, str):
                        unit_of_measure_str = unit_of_measure_obj

                inv_dim = get_posting_dimension_payload(
                    global_dimension_1=item_entry.get("global_dimension_1")
                    or header_dim.get("global_dimension_1"),
                    global_dimension_2=header_dim.get("global_dimension_2"),
                    dimension_set=item_entry.get("dimension_set")
                    or header_dim.get("dimension_set"),
                )

                # Create Item Ledger Entry (sales entry with negative quantity)
                item_ledger = ItemLedgerEntries.objects.create(
                    posting_date=item_entry["posting_date"],
                    entry_type=item_entry["entry_type"],
                    item=item,
                    document_no=posted_invoice.no,
                    description=item_entry.get("description", ""),
                    location=item_entry["location"],
                    quantity=int(item_entry["quantity"]),  # Negative for sales
                    remaining_quantity=0,  # Sales entries have no remaining quantity
                    total=int(item_entry["cost_amount"]),
                    unit_of_measure=unit_of_measure_str,
                    unit_of_measure_code=item_unit_of_measure,  # Must be ItemUnitOfMeasure instance
                    global_dimension_1=inv_dim["global_dimension_1"],
                    global_dimension_2=inv_dim.get("global_dimension_2"),
                    dimension_set=inv_dim["dimension_set"],
                    user=self.user,
                    date=item_entry["posting_date"],
                    document_type=DocumentType.Sales.value,
                    transaction_no=transaction_no,
                )

                # Create Value Entry linked to Item Ledger Entry
                ValueEntry.objects.create(
                    posting_date=value_entry["posting_date"],
                    document_no=posted_invoice.no,
                    item=value_entry["item"],
                    cost_amount=str(int(value_entry["cost_amount"])),
                    item_ledger_entry_quantity=int(
                        value_entry["item_ledger_entry_quantity"]
                    ),
                    invoiced_quantity=int(value_entry["invoiced_quantity"]),
                    valued_quantity=int(value_entry["valued_quantity"]),
                    cost_per_unit=round(float(value_entry["cost_per_unit"]), 2),
                    general_product_posting_group=value_entry[
                        "general_product_posting_group"
                    ],
                    inventory_posting_group=value_entry["inventory_posting_group"],
                    document_type=DocumentType.Sales.value,
                    entry_type=EntryType.DirectCost.value,
                    item_ledger_entry_no=item_ledger,
                    transaction_no=transaction_no,
                    global_dimension_1=value_entry.get("global_dimension_1"),
                )

            # Clear any leftover installment draft; final invoice closes collection.
            try:
                draft = getattr(self.document, "installment_draft", None)
                if draft and (draft.amount or Decimal("0.00")) > Decimal("0.00"):
                    draft.amount = Decimal("0.00")
                    draft.updated_by = self.user
                    draft.save(update_fields=["amount", "updated_by", "updated_at"])
            except Exception:
                pass

            # Update prepayment document
            self.document.total_prepayment_deducted = (
                self.document.total_prepayment_deducted or Decimal("0.00")
            ) + prepayment_to_deduct
            self.document.total_prepayment_to_deduct = Decimal(
                "0.00"
            )  # Reset after deduction
            self.document.status = PrepaymentStatus.POSTED
            self.document.posted_at = timezone.now()
            self.document.posted_by = self.user
            self.document.posted_transaction_no = transaction_no
            self.document.save()

        return {
            "success": True,
            "message": f"Successfully posted final invoice {posted_invoice.no}",
            "posted_invoice": posted_invoice,
            "entries": entries,
        }
