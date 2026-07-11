from datetime import date
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.timezone import datetime
from django.db import transaction
from django.db.models import Sum, F
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from base.models import BaseModel
from items.models import increment_item_number
from setup.models import NoSeriesLines
from financials.models import PaymentMethod
from dimension.models import DimensionValue, DimensionSet

from postings.models import GeneralBusinessPostingGroup
from helpers.helpers import generate_document_number, ConfigurationError
from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from financials.models import PaymentMethod
from .enums import CustomerType, SalesInvoiceStatus, SalesOrderStatus
from financials.enums import DOCUMENT_TYPE
from utils.utils import BaseModel


class SalesReceivable(BaseModel):
    customer_no = models.ForeignKey(
        "setup.NoSeriesLines", related_name="customer_no", on_delete=models.CASCADE
    )
    sales_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    invoice_no = models.ForeignKey(
        "setup.NoSeriesLines", related_name="sales_invoice_no", on_delete=models.CASCADE
    )
    posted_invoice_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_posted_invoice_no",
        on_delete=models.CASCADE,
    )
    credit_memo_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_credit_memo_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    posted_credit_memo_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_posted_credit_memo_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    posted_prepayment_invoice_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_posted_prepayment_invoice_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_("Number series for posted prepayment invoices"),
    )
    posted_prepayment_credit_memo_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_posted_prepayment_credit_memo_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_("Number series for posted prepayment credit memos"),
    )
    sales_order_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_order_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_("Number series for sales orders"),
    )
    sales_price_list_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="sales_price_list_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        help_text=_("Number series for sales price lists"),
    )

    # Price editing permissions
    prevent_price_below_original = models.BooleanField(
        _("Prevent Price Below Original"),
        default=False,
        help_text=_(
            "Prevent users from editing item prices to values below the original price during sales"
        ),
    )
    disable_price_editing = models.BooleanField(
        _("Disable Price Editing"),
        default=False,
        help_text=_("Completely disable price editing during sales"),
    )
    enable_line_discounts = models.BooleanField(
        _("Enable Line Discounts"),
        default=False,
        help_text=_("Allow users to enter manual discounts on sales lines"),
    )
    enable_invoice_discounts = models.BooleanField(
        _("Enable Invoice Discounts"),
        default=False,
        help_text=_("Allow users to enter invoice-level discounts on sales"),
    )

    class Meta:
        verbose_name = "Sales & Receivables Setup"
        verbose_name_plural = "Sales & Receivables Setup"

    def clean(self):
        """Validate that both price editing options are not enabled simultaneously"""
        if self.prevent_price_below_original and self.disable_price_editing:
            raise ValidationError(
                _(
                    "Cannot prevent price below original and disable price editing at the same time"
                )
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


def get_today():
    return date.today()


class SalesPriceList(BaseModel):
    class AssignToType(models.TextChoices):
        ALL_CUSTOMERS = "all_customers", _("All Customers")
        CUSTOMER = "customer", _("Customer")
        CUSTOMER_PRICE_GROUP = "customer_price_group", _("Customer Price Group")
        CUSTOMER_DISCOUNT_GROUP = (
            "customer_discount_group",
            _("Customer Discount Group"),
        )
        CAMPAIGN = "campaign", _("Campaign")
        CONTRACT = "contract", _("Contract")

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        RELEASED = "released", _("Released")
        CLOSED = "closed", _("Closed")

    code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Auto-generated from Sales Price List No. Series"),
    )
    description = models.CharField(max_length=255)
    assign_to_type = models.CharField(
        max_length=32, choices=AssignToType.choices, default=AssignToType.ALL_CUSTOMERS
    )
    assign_to_no = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_(
            "Customer, price group, or other identifier based on the assign type"
        ),
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN
    )
    starting_date = models.DateField(default=get_today)
    ending_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ["-starting_date", "code"]
        verbose_name = _("Sales Price List")
        verbose_name_plural = _("Sales Price Lists")

    def __str__(self):
        return self.code or self.description

    def clean(self):
        errors = {}
        if (
            self.ending_date
            and self.starting_date
            and self.ending_date < self.starting_date
        ):
            errors["ending_date"] = _(
                "Ending date must be on or after the starting date."
            )
        if self.assign_to_type == self.AssignToType.ALL_CUSTOMERS:
            self.assign_to_no = None
        if errors:
            raise ValidationError(errors)

    def _ensure_code(self):
        if self.code:
            return
        try:
            generated_code, _ = generate_document_number(
                SalesReceivable,
                "sales_price_list_no",
                "code",
                is_no_series_lines=True,
            )
        except ConfigurationError as exc:
            raise ValidationError(str(exc))
        self.code = generated_code

    def save(self, *args, **kwargs):
        self._ensure_code()
        self.full_clean()
        super().save(*args, **kwargs)


class SalesInvoice(BaseModel):

    invoice_no = models.CharField(max_length=255, unique=True, blank=True, null=True)
    customer = models.ForeignKey(
        "Customer", on_delete=models.PROTECT, related_name="sales"
    )
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    document_date = models.DateField(default=get_today, blank=True, null=True)
    posting_date = models.DateField(default=get_today, blank=True, null=True)
    vat_date = models.DateField(default=get_today, blank=True, null=True)
    due_date = models.DateField(default=get_today, blank=True, null=True)
    customer_invoice_no = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )
    status = models.CharField(
        max_length=20, choices=SalesInvoiceStatus.choices, default="Open"
    )

    # Cash and change amounts for receipt
    amount_received = models.IntegerField(
        _("Amount Received"),
        default=0,
        help_text=_("Amount received from customer in cash"),
        blank=True,
        null=True,
    )
    change_amount = models.IntegerField(
        _("Change Amount"),
        default=0,
        help_text=_("Change given back to customer"),
        blank=True,
        null=True,
    )

    # Payment method used for this sale
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        verbose_name=_("Payment Method"),
        on_delete=models.PROTECT,
        related_name="sales_invoices",
        null=True,
        blank=True,
        help_text=_("Payment method used for this sale"),
        default=1,
    )

    # Invoice discount fields
    INVOICE_DISCOUNT_TYPES = (
        ("amount", _("Amount")),
        ("percentage", _("Percentage")),
    )
    invoice_discount_type = models.CharField(
        _("Invoice Discount Type"),
        max_length=20,
        choices=INVOICE_DISCOUNT_TYPES,
        default="amount",
        blank=True,
        null=True,
        help_text=_("Type of invoice discount: fixed amount or percentage"),
    )
    invoice_discount_amount = models.DecimalField(
        _("Invoice Discount Amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Fixed discount amount in UGX"),
    )
    invoice_discount_percentage = models.DecimalField(
        _("Invoice Discount Percentage"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Discount percentage (0-100)"),
    )

    # VAT fields (BC-style, when vat_enabled in General Ledger Setup)
    prices_including_vat = models.BooleanField(
        _("Prices Including VAT"),
        default=False,
        help_text=_("When enabled, unit prices and line amounts include VAT."),
    )
    total_vat_amount = models.DecimalField(
        _("Total VAT Amount"),
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Sum of line VAT amounts (computed)."),
    )

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="sales_invoice_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="sales_invoice_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="sales_invoice_headers",
        verbose_name=_("Dimension Set"),
    )

    def save(self, *args, **kwargs):
        print("being called")
        with transaction.atomic():
            if not self.pk:
                if self.customer:
                    self.customer_name = self.customer.name

                try:
                    # Use the new generic function with is_no_series_lines=True
                    generated_number, _ = generate_document_number(
                        SalesReceivable,
                        "invoice_no",
                        "invoice_no",
                        is_no_series_lines=True,
                    )
                    if generated_number:
                        self.invoice_no = generated_number
                except ConfigurationError as e:
                    # Convert ConfigurationError to ValidationError for better user experience
                    raise ValidationError(str(e))

                if self.invoice_no is None:
                    raise ValidationError("Invoice number is required")

                # Generate customer invoice number if not provided
                if not self.customer_invoice_no:
                    # Generate customer invoice number using the same approach as GenerateInvoiceNoView
                    import random
                    import string
                    from django.utils import timezone

                    today = timezone.now()
                    today_str = today.strftime("%Y%m%d")
                    customer_invoice_no = f"SAL-{today_str}-" + "".join(
                        random.choices(string.digits, k=6)
                    )

                    # Ensure uniqueness
                    while SalesInvoice.objects.filter(
                        customer_invoice_no=customer_invoice_no
                    ).exists():
                        customer_invoice_no = f"SAL-{today_str}-" + "".join(
                            random.choices(string.digits, k=6)
                        )

                    self.customer_invoice_no = customer_invoice_no

            # Ensure status is preserved (don't let default override explicit status)
            print(f"DEBUG: Saving SalesInvoice with status: {self.status}")

            # Validate invoice discount before saving
            self.clean()

            super().save(*args, **kwargs)

    def recalculate_vat(self):
        """Recalculate line VAT amounts and total_vat_amount when VAT is enabled."""
        import logging

        logger = logging.getLogger(__name__)
        try:
            from financials.models import GeneralLedgerSetup
            from financials.vat import get_vat_posting_setup, compute_line_vat

            gl_setup = GeneralLedgerSetup.objects.first()
            if not gl_setup or not getattr(gl_setup, "vat_enabled", False):
                return

            # Amounts column is always inclusive of VAT when VAT is enabled
            prices_incl = True
            total_vat = Decimal("0")

            for line in self.lines.all():
                # VAT uses VAT Business Posting Group (Customer) + VAT Product Posting Group (Item)
                # NOT General Business/Product posting groups
                vat_bus = getattr(self.customer, "vat_business_posting_group", None)
                vat_prod = None
                if line.item:
                    vat_prod = getattr(line.item, "vat_product_posting_group", None)
                elif line.resource:
                    vat_prod = getattr(line.resource, "vat_product_posting_group", None)

                setup = get_vat_posting_setup(vat_bus, vat_prod)
                if not setup or setup.vat_percent <= 0:
                    if not vat_bus or not vat_prod:
                        logger.debug(
                            "VAT skip: Customer %s has vat_business_posting_group=%s, "
                            "Item/Resource has vat_product_posting_group=%s. "
                            "Set these on Customer and Item cards (not General posting groups).",
                            getattr(self.customer, "no", self.customer_id),
                            vat_bus,
                            vat_prod,
                        )
                    SalesInvoiceLine.objects.filter(pk=line.pk).update(
                        vat_percent=Decimal("0"), vat_amount=Decimal("0")
                    )
                    continue

                line_base = Decimal(str(line.total_amount))
                vat_amount, _ = compute_line_vat(
                    line_base, setup.vat_percent, prices_incl
                )
                SalesInvoiceLine.objects.filter(pk=line.pk).update(
                    vat_percent=setup.vat_percent, vat_amount=vat_amount
                )
                total_vat += vat_amount

            self.total_vat_amount = total_vat
            super(SalesInvoice, self).save(
                update_fields=["total_vat_amount", "updated_at"]
            )
        except Exception as e:
            logger.exception(
                "SalesInvoice.recalculate_vat failed for invoice %s: %s", self.id, e
            )

    def __str__(self):
        return f"{self.invoice_no} - {self.customer.name}"

    @property
    def payment_status(self):
        """Get payment status based on CustomerLedgerEntry.open status (primary source of truth)"""
        if self.status != "Posted":
            return "Not Paid Yet"

        # Primary source of truth: Check CustomerLedgerEntry.open status
        # Use filter().first() to handle edge cases where multiple entries might exist
        ledger_entry = CustomerLedgerEntry.objects.filter(
            document_no=self.invoice_no,
            customer=self.customer,
            document_type="Invoice",
        ).first()

        if ledger_entry:
            # Ledger entry exists - use its open status as the source of truth
            if ledger_entry.open:
                return "Not Paid Yet"
            else:
                # Entry is closed - check if it was a cash payment for display purposes
                if (
                    self.payment_method
                    and hasattr(self.payment_method, "is_cash_payment")
                    and self.payment_method.is_cash_payment()
                ):
                    return "Paid"
                else:
                    return "Fully Paid"
        else:
            # No ledger entry found - fall back to payment method check
            if (
                self.payment_method
                and hasattr(self.payment_method, "is_cash_payment")
                and self.payment_method.is_cash_payment()
            ):
                # Cash payment means it was paid immediately
                return "Paid"
            else:
                return "Not Paid Yet"

    @property
    def invoice_discount_value(self):
        """Calculate the actual invoice discount amount based on type"""
        from decimal import Decimal

        if not self.invoice_discount_type:
            return Decimal("0")

        if self.invoice_discount_type == "amount":
            return Decimal(self.invoice_discount_amount or 0)
        elif self.invoice_discount_type == "percentage":
            # Calculate subtotal from lines (after line discounts)
            subtotal = Decimal("0")
            for line in self.lines.all():
                subtotal += Decimal(str(line.total_amount))

            if subtotal > 0:
                percentage = Decimal(self.invoice_discount_percentage or 0)
                return (subtotal * percentage) / Decimal("100")
            else:
                return Decimal("0")
        else:
            return Decimal("0")

    def clean(self):
        """Validate invoice discount"""
        from decimal import Decimal

        # Check if invoice discounts are enabled
        if (
            self.invoice_discount_amount and Decimal(self.invoice_discount_amount) > 0
        ) or (
            self.invoice_discount_percentage
            and Decimal(self.invoice_discount_percentage) > 0
        ):
            sales_setup = SalesReceivable.objects.first()
            if not sales_setup or not sales_setup.enable_invoice_discounts:
                raise ValidationError(
                    _("Invoice discounts are disabled in Sales & Receivables Setup")
                )

        # Validate discount doesn't exceed subtotal
        if self.pk:  # Only validate if invoice has lines
            subtotal = Decimal("0")
            for line in self.lines.all():
                subtotal += Decimal(str(line.total_amount))

            discount_value = self.invoice_discount_value
            if discount_value > subtotal:
                raise ValidationError(
                    _("Invoice discount cannot exceed invoice subtotal")
                )

        # Validate percentage is between 0 and 100
        if self.invoice_discount_percentage:
            percentage = Decimal(self.invoice_discount_percentage)
            if percentage < 0 or percentage > 100:
                raise ValidationError(
                    _("Invoice discount percentage must be between 0 and 100")
                )

        # Validate amount is non-negative
        if self.invoice_discount_amount:
            amount = Decimal(self.invoice_discount_amount)
            if amount < 0:
                raise ValidationError(_("Invoice discount amount cannot be negative"))

    class Meta:
        ordering = ["-document_date"]
        indexes = [
            models.Index(
                fields=["posting_date", "status"], name="sales_inv_report_idx"
            ),
            models.Index(fields=["posting_date"], name="sales_inv_date_idx"),
            models.Index(fields=["customer"], name="sales_inv_customer_idx"),
            models.Index(fields=["status", "document_date"], name="sales_inv_status_doc_idx"),
            models.Index(fields=["created_at"], name="sales_inv_created_idx"),
            models.Index(fields=["payment_method"], name="sales_inv_pay_method_idx"),
        ]


class SalesInvoiceLine(BaseModel):
    LINE_TYPES = (
        ("product", "Product"),
        ("service", "Service"),
    )
    LINE_ENTITY_TYPES = (
        ("item", "Item"),
        ("resource", "Resource"),
    )

    sales_invoice = models.ForeignKey(
        SalesInvoice, related_name="lines", on_delete=models.CASCADE
    )
    type = models.CharField(
        max_length=10,
        choices=LINE_ENTITY_TYPES,
        default="item",
        verbose_name=_("Line Type (Item/Resource)"),
        help_text=_("Whether this line sells an Item or a Resource (BC-style)"),
    )
    item = models.ForeignKey(
        "items.Item",
        related_name="sales_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        "resources.Resource",
        related_name="sales_invoice_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Resource"),
        help_text=_("Resource sold on this line (when type=resource)"),
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        related_name="sales_invoice_lines",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("G/L Account"),
    )
    description = models.TextField(blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_sales_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    quantity = models.IntegerField(default=0)
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_sales_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_sales_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Price",
        help_text="Price per unit",
    )
    line_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Amount deducted from this line before posting"),
    )

    # VAT fields (BC-style, when vat_enabled)
    vat_percent = models.DecimalField(
        _("VAT %"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        null=True,
        blank=True,
        help_text=_("VAT percentage from VAT Posting Setup."),
    )
    vat_amount = models.DecimalField(
        _("VAT Amount"),
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("VAT amount for this line (computed)."),
    )

    # Tracking code field for lot/serial selection
    tracking_code = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Lot number or serial number for tracking",
    )

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="sales_lines",
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="sales_lines",
    )

    # Service sale fields
    line_type = models.CharField(
        max_length=10,
        choices=LINE_TYPES,
        default="product",
        verbose_name="Line Type",
        help_text="Type of sale line: product or service",
    )
    assigned_resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_lines",
        verbose_name="Assigned Resource",
        help_text="Resource assigned to perform this service (e.g., stylist, chef)",
    )
    service_duration = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Service Duration",
        help_text="Actual duration of service performed (in resource's base unit)",
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Cost",
        help_text="Cost per unit (calculated from BOM or set manually)",
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Total Cost",
        help_text="Total cost for this line (unit_cost × quantity)",
    )

    def _get_quantity_per_unit_value(self):
        # Resource lines: quantity is already in resource's base unit (no conversion)
        if self.type == "resource":
            return Decimal("1")
        if (
            self.item_unit_of_measure
            and self.item_unit_of_measure.quantity_per_unit is not None
        ):
            return Decimal(str(self.item_unit_of_measure.quantity_per_unit))
        return Decimal("1")

    def _compute_gross_amount(self):
        quantity = Decimal(self.quantity or 0)
        unit_price = Decimal(self.unit_price or 0)
        return quantity * unit_price * self._get_quantity_per_unit_value()

    @property
    def base_unit_price(self) -> Decimal:
        """Base unit price from item card or resource (price per base UOM)."""
        if self.type == "resource" and self.resource:
            return Decimal(str(self.resource.unit_price))
        if self.item and self.item.unit_price:
            return Decimal(str(self.item.unit_price))
        return Decimal("0.00")

    def _normalize_line_discount(self):
        discount = Decimal(self.line_discount_amount or 0)
        if discount < 0:
            discount = Decimal("0")
        gross = self._compute_gross_amount()
        if discount > gross:
            discount = gross
        self.line_discount_amount = int(discount)

    # Computed field
    @property
    def line_amount(self):
        return self.quantity * self.unit_price

    @property
    def gross_amount(self):
        return int(self._compute_gross_amount())

    @property
    def total_amount(self):
        net = self._compute_gross_amount() - Decimal(self.line_discount_amount or 0)
        return int(net) if net > 0 else 0

    @property
    def tracking_specifications(self):
        """Get tracking specifications for this line"""
        from items.models import TrackingSpecification

        return TrackingSpecification.objects.filter(
            sales_invoice=self.sales_invoice, item=self.item
        )

    @property
    def profit(self):
        """Calculate profit for this line (revenue - cost)"""
        revenue = float(self.line_amount)
        cost = float(self.total_cost)
        return revenue - cost

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        revenue = float(self.line_amount)
        if revenue > 0:
            cost = float(self.total_cost)
            return ((revenue - cost) / revenue) * 100
        return 0

    def is_service_sale(self):
        """Check if this is a service sale (item line with service type, or resource line)."""
        if self.type == "resource":
            return True
        return self.line_type == "service" or (
            self.item and self.item.type == "Service"
        )

    def save(self, *args, **kwargs):
        """Override save to auto-detect line_type, enforce type/item/resource, and calculate costs."""
        # On type change: clear the other FK and item-only fields
        if self.type == "resource":
            self.item_id = None
            self.item_unit_of_measure_id = None
            self.unit_of_measure_id = None
            self.location_code_id = None
            self.tracking_code = None
            if self.resource and not self.unit_price and self.resource.unit_price:
                self.unit_price = self.resource.unit_price
            if self.resource:
                self.unit_cost = getattr(
                    self.resource, "unit_cost", self.resource.direct_unit_cost or 0
                )
                self.total_cost = float(self.unit_cost) * (self.quantity or 0)
        elif self.type == "item":
            self.resource_id = None

        previous_snapshot = None
        if self.pk:
            previous_snapshot = (
                SalesInvoiceLine.objects.filter(pk=self.pk)
                .values("item_unit_of_measure_id", "unit_of_measure_id")
                .first()
            )

        if previous_snapshot and (
            previous_snapshot.get("item_unit_of_measure_id")
            != (self.item_unit_of_measure_id or None)
            or previous_snapshot.get("unit_of_measure_id")
            != (self.unit_of_measure_id or None)
        ):
            self.line_discount_amount = 0

        self._normalize_line_discount()

        # Auto-detect line_type (product/service) for item lines only
        if self.type == "item" and self.item and not self.line_type:
            if self.item.type == "Service":
                self.line_type = "service"
            else:
                self.line_type = "product"

        # For item service sales, calculate costs from BOM if available
        if self.type == "item" and self.line_type == "service" and self.item:
            if hasattr(self.item, "production_bom") and self.item.production_bom:
                bom = self.item.production_bom
                bom_total_cost = bom.calculate_total_cost()
                self.unit_cost = bom_total_cost
                self.total_cost = float(self.unit_cost) * self.quantity

        super().save(*args, **kwargs)

        # Recalculate VAT on invoice when VAT is enabled
        if self.sales_invoice_id:
            self.sales_invoice.recalculate_vat()

    def clean(self):
        # Type/item/resource consistency (BC-style)
        if self.type == "item":
            if not self.item_id:
                raise ValidationError(
                    {"item": _("Item is required when line type is Item.")}
                )
            if self.resource_id:
                raise ValidationError(
                    {"resource": _("Resource must be empty when line type is Item.")}
                )
            if not self.item_unit_of_measure and not self.unit_of_measure:
                raise ValidationError("Unit of Measure is required for item lines.")
        elif self.type == "resource":
            if not self.resource_id:
                raise ValidationError(
                    {"resource": _("Resource is required when line type is Resource.")}
                )
            if self.item_id:
                raise ValidationError(
                    {"item": _("Item must be empty when line type is Resource.")}
                )

        if self.line_discount_amount and self.line_discount_amount > 0:
            sales_setup = SalesReceivable.objects.first()
            if not sales_setup or not sales_setup.enable_line_discounts:
                raise ValidationError(
                    _("Line discounts are disabled in Sales & Receivables Setup")
                )

        # Tracking specs only for item lines
        if (
            self.type == "item"
            and self.item_id
            and self.tracking_specifications.exists()
        ):
            total_quantity = sum(
                spec.quantity_base for spec in self.tracking_specifications
            )
            same_invoice_lines = SalesInvoiceLine.objects.filter(
                sales_invoice=self.sales_invoice, type="item", item_id=self.item_id
            )
            expected_quantity = 0
            for line in same_invoice_lines:
                if (
                    line.item_unit_of_measure
                    and line.item_unit_of_measure.quantity_per_unit
                ):
                    expected_quantity += (
                        line.quantity * line.item_unit_of_measure.quantity_per_unit
                    )
            if total_quantity != expected_quantity:
                raise ValidationError(
                    f"Total quantity in tracking specifications ({total_quantity}) "
                    f"must match sales line quantity ({expected_quantity})"
                )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["item", "sales_invoice"], name="sales_line_prod_idx"),
            models.Index(fields=["item"], name="sales_line_item_idx"),
            models.Index(fields=["type"], name="sales_line_type_idx"),
        ]


class SalesOrder(BaseModel):
    """
    Sales Order header – mirrors SalesInvoice but without posting/accounting behavior.
    """

    order_no = models.CharField(max_length=255, unique=True, blank=True, null=True)
    customer = models.ForeignKey(
        "Customer", on_delete=models.PROTECT, related_name="sales_orders",
        null=True, blank=True,
    )
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    order_date = models.DateField(default=get_today, blank=True, null=True)
    expected_delivery_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=30,
        choices=SalesOrderStatus.choices(),
        default=SalesOrderStatus.OPEN.value,
    )
    total_amount = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        """
        Generate order number on first save using SalesReceivable.sales_order_no series.
        Falls back to SO-{pk} when the series is not yet configured.
        Does NOT post to accounting or touch inventory.
        """
        is_new = not self.pk
        with transaction.atomic():
            if is_new:
                if self.customer:
                    self.customer_name = self.customer.name

                try:
                    generated_number, _ = generate_document_number(
                        SalesReceivable,
                        "sales_order_no",
                        "sales_order_no",
                        is_no_series_lines=True,
                    )
                    if generated_number:
                        self.order_no = generated_number
                except ConfigurationError:
                    pass

            super().save(*args, **kwargs)

            if is_new and not self.order_no:
                fallback = f"SO-{self.pk:06d}"
                SalesOrder.objects.filter(pk=self.pk).update(order_no=fallback)
                self.order_no = fallback

    def __str__(self):
        customer_name = self.customer.name if self.customer_id else '(no customer)'
        return f"{self.order_no} - {customer_name}"

    def recalculate_totals(self):
        """
        Recalculate total_amount from lines.
        Purely numeric; no posting or inventory logic.
        """
        aggregates = self.lines.aggregate(total=models.Sum("amount"))
        self.total_amount = aggregates.get("total") or 0
        super().save(update_fields=["total_amount", "updated_at"])

    class Meta:
        ordering = ["-order_date", "-created_at"]
        indexes = [
            models.Index(
                fields=["order_date", "status"], name="sales_order_date_status_idx"
            ),
            models.Index(fields=["customer"], name="sales_order_customer_idx"),
        ]


class SalesOrderLine(BaseModel):
    """
    Sales Order line – similar to SalesInvoiceLine but with simpler cost fields.
    Supports Item or Resource (BC-style type field).
    """

    LINE_ENTITY_TYPES = (
        ("item", "Item"),
        ("resource", "Resource"),
    )

    sales_order = models.ForeignKey(
        SalesOrder, related_name="lines", on_delete=models.CASCADE
    )
    type = models.CharField(
        max_length=10,
        choices=LINE_ENTITY_TYPES,
        default="item",
        verbose_name=_("Line Type (Item/Resource)"),
        help_text=_("Whether this line sells an Item or a Resource (BC-style)"),
    )
    item = models.ForeignKey(
        "items.Item",
        related_name="sales_order_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        "resources.Resource",
        related_name="sales_order_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Resource"),
        help_text=_("Resource sold on this line (when type=resource)"),
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        related_name="sales_order_lines",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("G/L Account"),
    )
    description = models.TextField(blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_sales_order_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    quantity = models.IntegerField(default=0)
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_sales_order_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_sales_order_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Price",
        help_text="Price per unit",
    )
    line_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_("Amount deducted from this sales order line"),
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Amount",
    )

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="sales_order_lines",
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="sales_order_lines",
    )

    def _get_quantity_per_unit_value(self):
        if self.type == "resource":
            return Decimal("1")
        if (
            self.item_unit_of_measure
            and self.item_unit_of_measure.quantity_per_unit is not None
        ):
            return Decimal(str(self.item_unit_of_measure.quantity_per_unit))
        return Decimal("1")

    def _compute_gross_amount(self):
        quantity = Decimal(self.quantity or 0)
        unit_price = Decimal(self.unit_price or 0)
        return quantity * unit_price * self._get_quantity_per_unit_value()

    def _normalize_line_discount(self):
        discount = Decimal(self.line_discount_amount or 0)
        if discount < 0:
            discount = Decimal("0")
        gross = self._compute_gross_amount()
        if discount > gross:
            discount = gross
        self.line_discount_amount = int(discount)

    @property
    def line_amount(self):
        return self.quantity * self.unit_price

    @property
    def gross_amount(self):
        return int(self._compute_gross_amount())

    @property
    def total_amount(self):
        if not self.quantity or not self.unit_price:
            return 0
        net = self._compute_gross_amount() - Decimal(self.line_discount_amount or 0)
        return int(net) if net > 0 else 0

    def save(self, *args, **kwargs):
        """Compute amount, enforce type/item/resource, trigger header totals."""
        if self.type == "resource":
            self.item_id = None
            self.item_unit_of_measure_id = None
            self.unit_of_measure_id = None
            self.location_code_id = None
            if self.resource and not self.unit_price and self.resource.unit_price:
                self.unit_price = self.resource.unit_price
        elif self.type == "item":
            self.resource_id = None

        previous_snapshot = None
        if self.pk:
            previous_snapshot = (
                SalesOrderLine.objects.filter(pk=self.pk)
                .values("item_unit_of_measure_id", "unit_of_measure_id")
                .first()
            )

        if previous_snapshot and (
            previous_snapshot.get("item_unit_of_measure_id")
            != (self.item_unit_of_measure_id or None)
            or previous_snapshot.get("unit_of_measure_id")
            != (self.unit_of_measure_id or None)
        ):
            self.line_discount_amount = 0

        self._normalize_line_discount()
        net = self._compute_gross_amount() - Decimal(self.line_discount_amount or 0)
        self.amount = int(net) if net > 0 else 0
        super().save(*args, **kwargs)
        self.sales_order.recalculate_totals()

    def clean(self):
        if self.type == "item":
            if not self.item_id:
                raise ValidationError(
                    {"item": _("Item is required when line type is Item.")}
                )
            if self.resource_id:
                raise ValidationError(
                    {"resource": _("Resource must be empty when line type is Item.")}
                )
            if not self.item_unit_of_measure and not self.unit_of_measure:
                raise ValidationError("Unit of Measure is required for item lines.")
        elif self.type == "resource":
            if not self.resource_id:
                raise ValidationError(
                    {"resource": _("Resource is required when line type is Resource.")}
                )
            if self.item_id:
                raise ValidationError(
                    {"item": _("Item must be empty when line type is Resource.")}
                )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["item", "sales_order"], name="sales_order_line_prod_idx"
            ),
            models.Index(fields=["item"], name="sales_order_line_item_idx"),
            models.Index(fields=["type"], name="sales_order_line_type_idx"),
        ]


class PostedSalesInvoice(BaseModel):
    no = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        related_name="posted_sales_invoices",
    )
    preayment = models.ForeignKey(
        "prepayment.Preayment",
        on_delete=models.SET_NULL,
        related_name="posted_sales_invoices",
        null=True,
        blank=True,
    )
    document_date = models.DateField()
    posting_date = models.DateField()
    vat_date = models.DateField()
    due_date = models.DateField()
    customer_invoice_no = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        verbose_name=_("Payment Method"),
        on_delete=models.PROTECT,
        related_name="posted_sales_invoices",
        null=True,
        blank=True,
        help_text=_("Payment method used for this sale"),
    )
    status = models.CharField(
        max_length=20, choices=SalesInvoiceStatus.choices, default="Posted"
    )

    # Reversal tracking fields
    reversed = models.BooleanField(
        _("Reversed"),
        default=False,
        help_text=_("Indicates if this invoice has been reversed"),
    )
    reversed_by = models.CharField(
        _("Reversed By Document No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Document number of the reversing credit memo"),
    )
    reversed_date = models.DateField(_("Reversal Date"), blank=True, null=True)
    reverses_document_no = models.CharField(
        _("Reverses Document No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("If this is a reversal credit memo, the original invoice number"),
    )

    # Invoice discount fields (preserved from SalesInvoice when posting)
    invoice_discount_type = models.CharField(
        _("Invoice Discount Type"),
        max_length=20,
        choices=SalesInvoice.INVOICE_DISCOUNT_TYPES,
        default="amount",
        blank=True,
        null=True,
        help_text=_("Type of invoice discount: fixed amount or percentage"),
    )
    invoice_discount_amount = models.DecimalField(
        _("Invoice Discount Amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Fixed discount amount in UGX"),
    )
    invoice_discount_percentage = models.DecimalField(
        _("Invoice Discount Percentage"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Discount percentage (0-100)"),
    )

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="posted_sales_invoice_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="posted_sales_invoice_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="posted_sales_invoice_headers",
        verbose_name=_("Dimension Set"),
    )

    @property
    def closed(self):
        return self.status == "Closed"

    @property
    def can_be_reversed(self):
        """Check if this invoice can be reversed"""
        return not self.reversed and self.status == "Posted"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.pk:
                if self.customer:
                    self.customer_name = self.customer.name

                try:
                    # Use the new generic function with is_no_series_lines=True
                    generated_number, _ = generate_document_number(
                        SalesReceivable,
                        "posted_invoice_no",
                        "posted_invoice_no",
                        is_no_series_lines=True,
                    )
                    if generated_number:
                        self.no = generated_number
                except ConfigurationError as e:
                    # Convert ConfigurationError to ValidationError for better user experience
                    raise ValidationError(str(e))

                if self.no is None:
                    raise ValidationError("Posted invoice number is required")

            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.no} - {self.customer.name}"

    class Meta:
        ordering = ["-document_date"]
        indexes = [
            models.Index(fields=["posting_date"], name="sales_psi_post_date_idx"),
            models.Index(
                fields=["customer", "posting_date"],
                name="sales_psi_cust_date_idx",
            ),
        ]


class PostedSalesInvoiceLine(BaseModel):
    LINE_ENTITY_TYPES = (
        ("item", "Item"),
        ("resource", "Resource"),
    )

    posted_sales_invoice = models.ForeignKey(
        PostedSalesInvoice,
        related_name="posted_sales_invoice_lines",
        on_delete=models.CASCADE,
    )
    amount = models.IntegerField()

    type = models.CharField(
        max_length=10,
        choices=LINE_ENTITY_TYPES,
        default="item",
        verbose_name=_("Line Type (Item/Resource)"),
        help_text=_("Whether this line is an Item or Resource (BC-style)"),
    )
    item = models.ForeignKey(
        "items.Item",
        related_name="posted_sales_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        "resources.Resource",
        related_name="posted_sales_invoice_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Resource"),
        help_text=_("Resource on this line (when type=resource)"),
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        related_name="posted_sales_invoice_lines",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("G/L Account"),
    )
    description = models.TextField(blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_posted_sales_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    quantity = models.IntegerField()
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_posted_sales_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_posted_sales_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_price = models.IntegerField()

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="posted_sales_lines",
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="posted_sales_lines",
    )

    @property
    def line_amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        if self.type == "resource" and self.resource:
            label = self.resource.name
        elif self.item:
            label = self.item.item_name
        elif self.gl_account:
            label = self.gl_account.name
        else:
            label = ""
        return f"{self.posted_sales_invoice.no} - {label}"

    def clean(self):
        if self.type == "item":
            if self.resource_id:
                raise ValidationError(
                    {"resource": _("Resource must be empty when line type is Item.")}
                )
        elif self.type == "resource":
            if not self.resource_id:
                raise ValidationError(
                    {"resource": _("Resource is required when line type is Resource.")}
                )
            if self.item_id:
                raise ValidationError(
                    {"item": _("Item must be empty when line type is Resource.")}
                )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["type"], name="posted_sales_line_type_idx"),
        ]


class DetailedCustomerLedgerEntry(BaseModel):
    from common.enums import DocumentType, EntryType

    entry_no = models.AutoField(primary_key=True)
    posting_date = models.DateField()
    entry_type = models.CharField(
        max_length=20,
        choices=EntryType.choices,
        help_text=_("Type of customer ledger entry"),
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        help_text=_("Type of document that created this entry"),
    )
    document_no = models.CharField(
        max_length=50, help_text=_("Document number reference")
    )

    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        related_name="sales_detailed_ledger_entries",
        help_text=_("Customer associated with this entry"),
    )
    amount = models.IntegerField(
        help_text=_("Transaction amount in transaction currency"),
    )

    initial_entry_due_date = models.DateField(
        help_text=_("Due date from the initial entry")
    )
    initial_document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        help_text=_("Type of document that created the initial entry"),
        null=True,
        blank=True,
    )
    customer_ledger_entry = models.ForeignKey(
        "CustomerLedgerEntry",
        on_delete=models.CASCADE,
        related_name="sales_detailed_entries",
        help_text=_("Related customer ledger entry"),
    )

    debit_amount = models.IntegerField(
        help_text=_("Debit amount in transaction currency"),
    )
    credit_amount = models.IntegerField(
        help_text=_("Credit amount in transaction currency"),
    )
    applied_customer_ledger_entry_no = models.IntegerField(
        help_text=_("Applied customer ledger entry number"),
    )
    unapplied_by_entry_no = models.IntegerField(
        help_text=_("Unapplied by entry number"),
    )
    unapplied = models.BooleanField(
        help_text=_("Unapplied amount in transaction currency"),
    )
    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        related_name="sales_customer_detailed_entries",
        help_text=_("Global Dimension 1 value"),
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="sales_customer_detailed_entries",
    )

    transaction_no = models.CharField(
        max_length=50,
        help_text=_("Transaction number for grouping related entries"),
    )

    # Reversal tracking fields
    reversed = models.BooleanField(
        _("Reversed"),
        default=False,
        db_index=True,
        help_text=_("Indicates if this entry has been reversed"),
    )
    reversed_by_document_no = models.CharField(
        _("Reversed By Document No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Credit memo or reversing document number"),
    )
    reversed_date = models.DateField(
        _("Reversal Date"),
        blank=True,
        null=True,
        help_text=_("Date when this entry was reversed"),
    )
    reverses_entry_no = models.IntegerField(
        _("Reverses Entry No."),
        blank=True,
        null=True,
        db_index=True,
        help_text=_("If this is a reversing entry, the entry_no it reverses"),
    )
    reversed_by_user = models.ForeignKey(
        "authentication.CustomUser",
        verbose_name=_("Reversed By User"),
        on_delete=models.PROTECT,
        related_name="detailed_customer_ledger_reversals",
        blank=True,
        null=True,
        help_text=_("User who performed the reversal"),
    )

    class Meta:
        ordering = ["posting_date", "entry_no"]
        verbose_name = _("Detailed Customer Ledger Entry")
        verbose_name_plural = _("Detailed Customer Ledger Entries")
        indexes = [
            models.Index(fields=["customer", "posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["transaction_no"]),
        ]

    def __str__(self):
        return f"{self.entry_no} - {self.customer.name} ({self.posting_date})"

    @property
    def is_reversal_entry(self):
        """Check if this entry is a reversal of another entry"""
        return self.reverses_entry_no is not None

    @property
    def can_be_reversed(self):
        """Check if this entry can be reversed"""
        return not self.reversed


class CustomerPostingGroup(BaseModel):
    code = models.CharField(_("Code"), max_length=20, unique=True, primary_key=True)
    description = models.CharField(_("Description"), max_length=100)
    receivables_account = models.ForeignKey(
        "financials.G_LAccount",  # Assuming you have an Account model in financials app
        verbose_name=_("Receivables Account"),
        on_delete=models.PROTECT,
        related_name="sales_customer_posting_groups",
    )

    class Meta:
        verbose_name = _("Customer Posting Group")
        verbose_name_plural = _("Customer Posting Groups")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.description}"


class Customer(BaseModel):
    no = models.CharField(
        verbose_name="NO.", unique=True, editable=False, max_length=20
    )
    name = models.CharField(_("Name"), max_length=100, unique=True)
    address = models.CharField(_("Address"), max_length=100, blank=True)
    address_2 = models.CharField(_("Address 2"), max_length=50, blank=True)
    city = models.CharField(_("City"), max_length=30, blank=True)
    contact = models.CharField(_("Contact"), max_length=100, blank=True)
    phone_number = models.CharField(
        _("Phone No."),
        max_length=30,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9+\-() ]*$", message="Phone number cannot contain letters"
            )
        ],
        null=True,
    )

    credit_limit = models.DecimalField(
        _("Credit Limit (LCY)"),
        max_digits=18,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
    )
    general_business_posting_group = models.ForeignKey(
        "postings.GeneralBusinessPostingGroup",
        verbose_name=_("Gen. Bus. Posting Group"),
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    customer_posting_group = models.ForeignKey(
        CustomerPostingGroup,
        verbose_name=_("Customer Posting Group"),
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    vat_business_posting_group = models.ForeignKey(
        "postings.VATBusinessPostingGroup",
        verbose_name=_("VAT Bus. Posting Group"),
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
        help_text=_("VAT posting group for this customer (when VAT is enabled)."),
    )
    customer_type = models.CharField(
        verbose_name=_("Customer Type"),
        choices=CustomerType.choices,
        default=CustomerType.General,
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        verbose_name=_("Payment Method"),
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        "authentication.CustomUser",
        verbose_name=_("User"),
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Customer")
        verbose_name_plural = _("Customers")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["updated_at", "id"], name="sales_cust_upd_id_idx"),
        ]

    def __str__(self):
        return f"{self.name}"

    @property
    def balance(self):
        """Calculate total balance from open customer ledger entries"""
        # Get all open ledger entries and sum their amounts
        balance = CustomerLedgerEntry.objects.filter(customer=self, open=True)
        total_amount = 0
        for entry in balance:
            total_amount += entry.remaining_amount
        return abs(total_amount)

    def save(self, *args, **kwargs):
        """
        Save method for Customer model that handles automatic customer number generation.

        For new customers (no primary key):
        - Generates customer number using no-series if not provided
        - Uses CUSTOMER no series from SalesReceivable setup
        - Falls back to timestamp-based number if setup is missing
        - Assigns default posting groups if not provided

        For existing customers (updates):
        - Maintains existing customer number
        - Assigns default values for any missing fields
        """
        if not self.no:
            print("no is not set")
            with transaction.atomic():
                try:
                    sales_receivable = SalesReceivable.objects.all().first()
                    if not sales_receivable:
                        print(
                            "Warning: SalesReceivable setup not found, using default customer number"
                        )
                        self.no = f"CUST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    else:
                        customer_no = NoSeriesLines.objects.filter(
                            no_series=sales_receivable.customer_no.no_series
                        ).first()
                        print(customer_no)
                        if customer_no:
                            increment_by = customer_no.increment_by
                            if customer_no.last_used_number:
                                self.no = increment_item_number(
                                    customer_no.last_used_number, increment_by
                                )
                                customer_no.last_used_number = self.no
                                customer_no.last_used_date = datetime.now()
                                customer_no.save()
                            else:
                                self.no = customer_no.start_number
                                customer_no.last_used_number = self.no
                                customer_no.last_used_date = datetime.now()
                                customer_no.save()
                        else:
                            print(
                                "Warning: Customer no series not found, using default customer number"
                            )
                            self.no = f"CUST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                except Exception as e:
                    print(f"Error generating customer number: {e}")
                    self.no = f"CUST-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if not self.customer_posting_group:
            self.customer_posting_group = CustomerPostingGroup.objects.all().first()

        if not self.general_business_posting_group:
            self.general_business_posting_group = (
                GeneralBusinessPostingGroup.objects.all().first()
            )

        super().save(*args, **kwargs)


class SalesCreditMemo(BaseModel):
    """Credit memo created when reversing a posted sales invoice"""

    credit_memo_no = models.CharField(_("Credit Memo No."), max_length=50, unique=True)
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        related_name="sales_credit_memos",
        verbose_name=_("Customer"),
    )
    document_date = models.DateField(_("Document Date"))
    posting_date = models.DateField(_("Posting Date"))
    vat_date = models.DateField(_("VAT Date"), blank=True, null=True)
    original_invoice_no = models.CharField(_("Original Invoice No."), max_length=50)
    original_invoice = models.ForeignKey(
        PostedSalesInvoice,
        on_delete=models.PROTECT,
        related_name="credit_memos",
        verbose_name=_("Original Invoice"),
    )
    reason_for_reversal = models.TextField(
        _("Reason for Reversal"), blank=True, null=True
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=[("Draft", _("Draft")), ("Posted", _("Posted"))],
        default="Draft",
    )

    # User who created the reversal
    reversed_by_user = models.ForeignKey(
        "authentication.CustomUser",
        verbose_name=_("Reversed By"),
        on_delete=models.PROTECT,
        related_name="credit_memos_created",
        null=True,
        blank=True,
    )

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="sales_credit_memo_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="sales_credit_memo_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="sales_credit_memo_headers",
        verbose_name=_("Dimension Set"),
    )

    class Meta:
        verbose_name = _("Sales Credit Memo")
        verbose_name_plural = _("Sales Credit Memos")
        ordering = ["-posting_date", "-credit_memo_no"]

    def __str__(self):
        return f"{self.credit_memo_no} - {self.customer.name}"

    def save(self, *args, **kwargs):
        """Generate credit memo number if not provided"""
        with transaction.atomic():
            if not self.pk and not self.credit_memo_no:
                try:
                    # Use the new generic function with is_no_series_lines=True
                    generated_number, _ = generate_document_number(
                        SalesReceivable,
                        "credit_memo_no",
                        "credit_memo_no",
                        is_no_series_lines=True,
                    )
                    if generated_number:
                        self.credit_memo_no = generated_number
                except ConfigurationError as e:
                    # Convert ConfigurationError to ValidationError for better user experience
                    raise ValidationError(str(e))

                if self.credit_memo_no is None:
                    raise ValidationError("Credit memo number is required")

            super().save(*args, **kwargs)


class SalesCreditMemoLine(BaseModel):
    """Credit memo line items"""

    credit_memo = models.ForeignKey(
        SalesCreditMemo,
        related_name="lines",
        on_delete=models.CASCADE,
        verbose_name=_("Credit Memo"),
    )
    item = models.ForeignKey(
        "items.Item",
        related_name="credit_memo_lines",
        on_delete=models.CASCADE,
        verbose_name=_("Item"),
    )
    description = models.TextField(_("Description"), blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_credit_memo_lines",
        on_delete=models.CASCADE,
        verbose_name=_("Location"),
    )
    quantity = models.IntegerField(_("Quantity"))
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_credit_memo_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Item Unit of Measure"),
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_credit_memo_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Unit of Measure"),
    )
    unit_price = models.IntegerField(_("Unit Price"))
    amount = models.IntegerField(_("Amount"))

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="credit_memo_lines",
        verbose_name=_("Global Dimension 1"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="credit_memo_lines",
    )

    @property
    def line_amount(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.credit_memo.credit_memo_no} - {self.item.item_name}"

    class Meta:
        verbose_name = _("Sales Credit Memo Line")
        verbose_name_plural = _("Sales Credit Memo Lines")
        ordering = ["id"]


class CustomerLedgerEntry(BaseModel):
    posting_date = models.DateField(_("Posting Date"))
    document_date = models.DateField(_("Document Date"))
    document_type = models.CharField(
        _("Document Type"),
        max_length=20,
        choices=DOCUMENT_TYPE.choices,
    )
    document_no = models.CharField(_("Document No."), max_length=20)
    customer = models.ForeignKey(
        "Customer",
        verbose_name=_("Customer No."),
        on_delete=models.PROTECT,
        related_name="sales_ledger_entries",
    )
    description = models.CharField(
        _("Description"), max_length=100, blank=True, null=True
    )
    receipt_no = models.CharField(
        _("Receipt No."), max_length=20, blank=True, null=True
    )

    # Amounts
    amount = models.IntegerField(_("Amount"), default=0)
    # Note: remaining_amount is computed from DetailedCustomerLedgerEntry, not stored
    sales = models.IntegerField(_("Sales"), default=0)
    original_amount = models.IntegerField(_("Original Amount"), default=0)
    payment_method = models.ForeignKey(
        PaymentMethod,
        verbose_name=_("Payment Method Code"),
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    due_date = models.DateField(_("Due Date"), null=True, blank=True)

    # Additional useful fields
    external_document_no = models.CharField(
        _("External Document No."), max_length=35, blank=True
    )
    applies_to_id = models.CharField(
        _("Applies-to ID"),
        max_length=50,
        blank=True,
        default="",
        help_text=_(
            "ID of entries that will be applied when you choose the Apply Entries action"
        ),
    )
    open = models.BooleanField(_("Open"), default=True)
    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        verbose_name=_("Global Dimension 1"),
        on_delete=models.PROTECT,
        related_name="customer_ledger_entries",
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="customer_ledger_entries",
    )
    transaction_no = models.CharField(
        _("Transaction No."), max_length=50, blank=True, null=True
    )
    user = models.ForeignKey(
        "authentication.CustomUser",
        verbose_name=_("User"),
        on_delete=models.PROTECT,
        related_name="customer_ledger_entries",
        default=1,
    )

    # Reversal tracking fields
    reversed = models.BooleanField(
        _("Reversed"),
        default=False,
        db_index=True,
        help_text=_("Indicates if this entry has been reversed"),
    )
    reversed_by_document_no = models.CharField(
        _("Reversed By Document No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Credit memo or reversing document number"),
    )
    reversed_date = models.DateField(
        _("Reversal Date"),
        blank=True,
        null=True,
        help_text=_("Date when this entry was reversed"),
    )
    reverses_entry_no = models.IntegerField(
        _("Reverses Entry No."),
        blank=True,
        null=True,
        db_index=True,
        help_text=_("If this is a reversing entry, the ID of the entry it reverses"),
    )
    reversed_by_user = models.ForeignKey(
        "authentication.CustomUser",
        verbose_name=_("Reversed By User"),
        on_delete=models.PROTECT,
        related_name="customer_ledger_reversals",
        blank=True,
        null=True,
        help_text=_("User who performed the reversal"),
    )

    class Meta:
        verbose_name = _("Customer Ledger Entry")
        verbose_name_plural = _("Customer Ledger Entries")
        ordering = ["-posting_date", "document_no"]
        indexes = [
            models.Index(fields=["customer", "posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["customer", "open"], name="sales_cle_cust_open_idx"),
            models.Index(fields=["open", "posting_date"], name="sales_cle_open_date_idx"),
        ]

    def __str__(self):
        return f"{self.document_type} - {self.document_no} ({self.id})"

    @property
    def remaining_amount(self):
        """Calculate remaining amount from detailed entries"""
        from django.db.models import Sum

        total_amount = DetailedCustomerLedgerEntry.objects.filter(
            customer_ledger_entry=self
        ).aggregate(total_amount=Sum("amount"))["total_amount"]
        return total_amount or 0

    @property
    def is_reversal_entry(self):
        """Check if this entry is a reversal of another entry"""
        return self.reverses_entry_no is not None

    @property
    def can_be_reversed(self):
        """Check if this entry can be reversed"""
        return not self.reversed and self.document_type in ["Invoice", "Payment"]

    def apply_to_entry(self, target_entry: "CustomerLedgerEntry") -> None:
        if not self.open:
            raise ValidationError(_("Applies-to ID can only be set on open entries."))
        from financials.ledger_application import set_ledger_applies_to

        set_ledger_applies_to(self, target_entry)

    def clear_applies_to(self) -> None:
        from financials.ledger_application import clear_ledger_applies_to

        clear_ledger_applies_to(self)


class SalesFavoriteSlot(BaseModel):
    """
    Per-user POS/mobile sales favorites grid slot (tenant-scoped).
    Only occupied slots are stored; empty grid cells have no row.
    """

    user = models.ForeignKey(
        "authentication.CustomUser",
        on_delete=models.CASCADE,
        related_name="sales_favorite_slots",
    )
    position = models.PositiveIntegerField(
        db_index=True,
        help_text=_("0-based row-major index in the favorites grid."),
    )
    item_system_id = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Item.system_id when the slot is occupied."),
    )
    item_no = models.CharField(max_length=225, blank=True, null=True)
    item_name = models.CharField(max_length=225, blank=True, null=True)
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, null=True
    )

    class Meta:
        ordering = ["position"]
        verbose_name = _("Sales favorite slot")
        verbose_name_plural = _("Sales favorite slots")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "position"],
                name="sales_salesfavoriteslot_user_position_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}@{self.position}={self.item_system_id or 'empty'}"
