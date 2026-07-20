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

from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver

from base.models import BaseModel
from items.models import increment_item_number
from setup.models import NoSeriesLines
from financials.models import PaymentMethod
from dimension.models import DimensionValue, DimensionSet
from purchases.enums import PurchaseInvoiceStatus, PurchaseCreditMemoStatus
from postings.models import GeneralBusinessPostingGroup
from helpers.helpers import generate_document_number, ConfigurationError
from authentication.models import CustomUser


class PurchasePayable(BaseModel):
    vendor_no = models.ForeignKey(
        "setup.NoSeriesLines", related_name="vendor_no", on_delete=models.CASCADE
    )
    purchase_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="purchase_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    invoice_no = models.ForeignKey(
        "setup.NoSeriesLines", related_name="invoice_no", on_delete=models.CASCADE
    )
    posted_invoice_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="posted_invoice_no",
        on_delete=models.CASCADE,
    )
    credit_memo_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="credit_memo_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    posted_credit_memo_no = models.ForeignKey(
        "setup.NoSeriesLines",
        related_name="posted_credit_memo_no",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Purchases & Payables Setup"
        verbose_name_plural = "Purchases & Payables Setup"


def get_today():
    return date.today()


class PurchaseInvoice(BaseModel):

    invoice_no = models.CharField(max_length=255, unique=True, blank=True, null=True)
    vendor = models.ForeignKey(
        "purchases.Vendor", on_delete=models.PROTECT, related_name="purchases"
    )
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    document_date = models.DateField(default=get_today, blank=True, null=True)
    posting_date = models.DateField(default=get_today, blank=True, null=True)
    vat_date = models.DateField(default=get_today, blank=True, null=True)
    due_date = models.DateField(default=get_today, blank=True, null=True)
    vendor_invoice_no = models.CharField(
        max_length=100, unique=True, blank=True, null=True
    )
    status = models.CharField(
        max_length=20, choices=PurchaseInvoiceStatus.choices, default="Open"
    )

    # Payment method used for this purchase
    payment_method = models.ForeignKey(
        PaymentMethod,
        verbose_name=_("Payment Method"),
        on_delete=models.PROTECT,
        related_name="purchase_invoices",
        null=True,
        blank=True,
        help_text=_("Payment method used for this purchase"),
        default=1,
    )

    # User who created this purchase invoice
    created_by = models.ForeignKey(
        CustomUser,
        verbose_name=_("Created By"),
        on_delete=models.SET_NULL,
        related_name="created_purchase_invoices",
        null=True,
        blank=True,
        help_text=_("User who created this purchase invoice"),
    )

    # VAT fields (BC-style, when vat_enabled in General Ledger Setup)
    prices_including_vat = models.BooleanField(
        _("Prices Including VAT"),
        default=False,
        help_text=_("When enabled, unit costs and line amounts include VAT."),
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
        related_name="purchase_invoice_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="purchase_invoice_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="purchase_invoice_headers",
        verbose_name=_("Dimension Set"),
    )

    def save(self, *args, **kwargs):
        print("being called")
        with transaction.atomic():
            if not self.pk:
                if self.vendor:
                    self.vendor_name = self.vendor.name

                try:
                    # Use the new generic function with is_no_series_lines=True
                    generated_number, _ = generate_document_number(
                        PurchasePayable,
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

            super().save(*args, **kwargs)

    def recalculate_vat(self):
        """Recalculate line VAT amounts and total_vat_amount when VAT is enabled."""
        try:
            from financials.models import GeneralLedgerSetup
            from financials.vat import get_vat_posting_setup, compute_line_vat

            gl_setup = GeneralLedgerSetup.objects.first()
            if not gl_setup or not getattr(gl_setup, "vat_enabled", False):
                return

            # Document controls whether prices include VAT (BC-style)
            prices_incl = bool(getattr(self, "prices_including_vat", False))
            total_vat = Decimal("0")

            for line in self.lines.all():
                vat_bus = getattr(self.vendor, "vat_business_posting_group", None)
                vat_prod = getattr(line.item, "vat_product_posting_group", None) if line.item else None

                setup = get_vat_posting_setup(vat_bus, vat_prod)
                if not setup or setup.vat_percent <= 0:
                    PurchaseInvoiceLine.objects.filter(pk=line.pk).update(
                        vat_percent=Decimal("0"), vat_amount=Decimal("0")
                    )
                    continue

                line_base = Decimal(str(line.total_amount))
                vat_amount, _ = compute_line_vat(line_base, setup.vat_percent, prices_incl)
                PurchaseInvoiceLine.objects.filter(pk=line.pk).update(
                    vat_percent=setup.vat_percent, vat_amount=vat_amount
                )
                total_vat += vat_amount

            self.total_vat_amount = total_vat
            super(PurchaseInvoice, self).save(update_fields=["total_vat_amount", "updated_at"])
        except Exception:
            pass

    def __str__(self):
        return f"{self.invoice_no} - {self.vendor.name}"

    def validate_all_tracking_specifications(self):
        """Validate tracking specifications for all lines in this invoice"""
        errors = []

        for line in self.lines.all():
            is_valid, error_message = line.validate_tracking_specifications()
            if not is_valid:
                errors.append(error_message)

        return len(errors) == 0, errors

    class Meta:
        ordering = ["-document_date"]
        indexes = [
            models.Index(
                fields=["posting_date", "status"],
                name="purch_pi_date_status_idx",
            ),
            models.Index(fields=["vendor", "status"], name="purch_pi_vend_status_idx"),
        ]


class DocumentAttachment(BaseModel):
    """Attachment (PDF, images, etc.) linked to a purchase invoice. Stored like item images."""

    purchase_invoice = models.ForeignKey(
        PurchaseInvoice,
        on_delete=models.CASCADE,
        related_name="document_attachments",
    )
    file = models.FileField(
        upload_to="document_attachments/%Y/%m/",
        max_length=255,
        verbose_name=_("File"),
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Display name"),
        help_text=_("Optional display name; defaults to filename"),
    )

    def delete(self, *args, **kwargs):
        if self.file and self.file.name and default_storage.exists(self.file.name):
            self.file.delete(save=False)
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.name or (self.file.name if self.file else str(self.pk))

    class Meta:
        verbose_name = "Document Attachment"
        verbose_name_plural = "Document Attachments"
        db_table = "purchases_documentattachment"
        ordering = ("-created_at",)


@receiver(post_delete, sender=DocumentAttachment)
def delete_document_attachment_file(sender, instance, **kwargs):
    if instance.file and instance.file.name and default_storage.exists(instance.file.name):
        instance.file.delete(save=False)


class PurchaseInvoiceLine(BaseModel):
    LINE_ENTITY_TYPES = (
        ("item", "Item"),
        ("resource", "Resource"),
        ("gl_account", "G/L Account"),
    )

    purchase_invoice = models.ForeignKey(
        PurchaseInvoice, related_name="lines", on_delete=models.CASCADE
    )
    type = models.CharField(
        max_length=20,
        choices=LINE_ENTITY_TYPES,
        default="item",
        verbose_name=_("Line Type"),
        help_text=_("Whether this line purchases an Item, Resource, or G/L Account (BC-style)"),
    )
    item = models.ForeignKey(
        "items.Item",
        related_name="purchase_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        "resources.Resource",
        related_name="purchase_invoice_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Resource"),
        help_text=_("Resource purchased on this line (when type=resource)"),
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        related_name="purchase_invoice_lines",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("G/L Account"),
        help_text=_("G/L account debited on this line (when type=gl_account)"),
    )
    description = models.TextField(blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_purchase_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    quantity = models.IntegerField(default=0)
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_purchase_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_purchase_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Cost",
        help_text="Cost per unit",
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

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="purchase_lines",
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="purchase_lines",
    )

    # Computed field
    @property
    def line_amount(self):
        return self.quantity * self.unit_cost

    @property
    def total_amount(self):
        return self.quantity * self.unit_cost if self.quantity and self.unit_cost else 0

    @property
    def base_unit_price(self) -> Decimal:
        """Base unit cost from item card or resource (cost per base UOM)."""
        if self.type == "resource" and self.resource:
            cost = getattr(self.resource, "direct_unit_cost", None) or getattr(
                self.resource, "unit_cost", None
            )
            if cost:
                return Decimal(str(cost))
        if self.item:
            cost = getattr(self.item, 'unit_cost', None) or getattr(self.item, 'unit_price', None)
            if cost:
                return Decimal(str(cost))
        return Decimal("0.00")

    @property
    def tracking_specifications(self):
        """Tracking specs for this line (linked by line FK; item is synced on save)."""
        from items.models import TrackingSpecification

        return TrackingSpecification.objects.filter(
            purchase_invoice_line=self,
        )

    # def __str__(self):
    #     return f"{self.item.item_name} - {self.description[:30]}"

    def save(self, *args, **kwargs):
        if self.type == "resource":
            self.item_id = None
            self.gl_account_id = None
            self.item_unit_of_measure_id = None
            self.unit_of_measure_id = None
            self.location_code_id = None
            if self.resource and not self.unit_cost:
                self.unit_cost = getattr(
                    self.resource, "direct_unit_cost", self.resource.unit_cost or 0
                ) or Decimal("0")
        elif self.type == "gl_account":
            self.item_id = None
            self.resource_id = None
            self.item_unit_of_measure_id = None
            self.unit_of_measure_id = None
            self.location_code_id = None
        elif self.type == "item":
            self.resource_id = None
            self.gl_account_id = None

        super().save(*args, **kwargs)
        if self.purchase_invoice_id:
            self.purchase_invoice.recalculate_vat()

    def clean(self):
        if self.type == "item":
            if not self.item_id:
                raise ValidationError({"item": _("Item is required when line type is Item.")})
            if self.resource_id:
                raise ValidationError({"resource": _("Resource must be empty when line type is Item.")})
            if self.gl_account_id:
                raise ValidationError({"gl_account": _("G/L Account must be empty when line type is Item.")})
            if not self.item_unit_of_measure and not self.unit_of_measure:
                raise ValidationError("Unit of Measure is required for item lines.")
        elif self.type == "resource":
            if not self.resource_id:
                raise ValidationError({"resource": _("Resource is required when line type is Resource.")})
            if self.item_id:
                raise ValidationError({"item": _("Item must be empty when line type is Resource.")})
            if self.gl_account_id:
                raise ValidationError({"gl_account": _("G/L Account must be empty when line type is Resource.")})
        elif self.type == "gl_account":
            if not self.gl_account_id:
                raise ValidationError({"gl_account": _("G/L Account is required when line type is G/L Account.")})
            if self.item_id:
                raise ValidationError({"item": _("Item must be empty when line type is G/L Account.")})
            if self.resource_id:
                raise ValidationError({"resource": _("Resource must be empty when line type is G/L Account.")})

        if (
            self.type == "item"
            and self.item_id
            and self.tracking_specifications.exists()
        ):

            total_quantity = sum(
                spec.quantity_base for spec in self.tracking_specifications
            )

            # Calculate expected quantity for THIS line only
            expected_quantity = (
                self.quantity * self.item_unit_of_measure.quantity_per_unit
            )

            print(
                f"Line {self.id}: Total tracking quantity: {total_quantity}, Expected quantity: {expected_quantity}"
            )

            if total_quantity != expected_quantity:
                raise ValidationError(
                    f"Total quantity in tracking specifications ({total_quantity}) "
                    f"must match purchase line quantity ({expected_quantity}) for item '{self.item.item_name}'"
                )

    def validate_tracking_specifications(self):
        """Validate tracking specifications for this line"""
        if self.type != "item" or not self.item_id:
            return True, None
        if self.tracking_specifications.exists():
            total_quantity = sum(
                spec.quantity_base for spec in self.tracking_specifications
            )
            expected_quantity = (
                self.quantity * self.item_unit_of_measure.quantity_per_unit
            )

            if total_quantity != expected_quantity:
                return (
                    False,
                    f"Item '{self.item.item_name}': Tracking specifications quantity ({total_quantity}) doesn't match line quantity ({expected_quantity})",
                )

        return True, None

    class Meta:
        ordering = ["id"]


class PostedPurchaseInvoice(BaseModel):
    no = models.CharField(max_length=50, unique=True)
    vendor = models.ForeignKey(
        "purchases.Vendor",
        on_delete=models.PROTECT,
        related_name="posted_purchase_invoices",
    )
    document_date = models.DateField()
    posting_date = models.DateField()
    vat_date = models.DateField()
    due_date = models.DateField()
    vendor_invoice_no = models.CharField(max_length=100)

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="posted_purchase_invoice_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="posted_purchase_invoice_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="posted_purchase_invoice_headers",
        verbose_name=_("Dimension Set"),
    )

    @property
    def closed(self):
        # Check if any related vendor ledger entry is closed
        vendor_ledger = VendorLedger.objects.filter(document_no=self.no).first()
        if vendor_ledger:
            return "Yes" if not vendor_ledger.open else "No"
        return "No"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.pk:
                purchase_payable = PurchasePayable.objects.all().first()
                if purchase_payable:
                    posted_invoice_no = NoSeriesLines.objects.filter(
                        no_series=PurchasePayable.objects.all()
                        .first()
                        .posted_invoice_no.no_series
                    ).first()
                    if posted_invoice_no:
                        increment_by = posted_invoice_no.increment_by
                        if posted_invoice_no.last_used_number:
                            # split if were the first number is start number ie wew00001, IJ_t000001
                            self.no = increment_item_number(
                                posted_invoice_no.last_used_number, increment_by
                            )
                            posted_invoice_no.last_used_number = self.no
                            posted_invoice_no.last_used_date = datetime.now()
                            posted_invoice_no.save()
                        else:
                            self.no = posted_invoice_no.start_number
                            posted_invoice_no.last_used_number = self.no
                            posted_invoice_no.last_used_date = datetime.now()
                            posted_invoice_no.save()
            super().save(*args, **kwargs)


class PostedPurchaseInvoiceLine(BaseModel):
    LINE_ENTITY_TYPES = PurchaseInvoiceLine.LINE_ENTITY_TYPES

    posted_purchase_invoice = models.ForeignKey(
        PostedPurchaseInvoice,
        related_name="posted_purchase_invoice_lines",
        on_delete=models.CASCADE,
    )
    amount = models.IntegerField()
    type = models.CharField(
        max_length=20,
        choices=LINE_ENTITY_TYPES,
        default="item",
        verbose_name=_("Line Type"),
    )

    item = models.ForeignKey(
        "items.Item",
        related_name="posted_purchase_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    resource = models.ForeignKey(
        "resources.Resource",
        related_name="posted_purchase_invoice_lines",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("Resource"),
    )
    gl_account = models.ForeignKey(
        "financials.G_LAccount",
        related_name="posted_purchase_invoice_lines",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("G/L Account"),
    )
    description = models.TextField(blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_posted_purchase_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    quantity = models.IntegerField()
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_posted_purchase_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_posted_purchase_invoice_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_cost = models.IntegerField()

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="posted_purchase_invoice_lines",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="posted_purchase_invoice_lines_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="posted_purchase_invoice_lines",
        verbose_name=_("Dimension Set"),
    )

    # total_amount = models.IntegerField()

    class Meta:
        ordering = ["id"]


class VendorLedger(BaseModel):

    from common.enums import DocumentType

    posting_date = models.DateField()
    document_date = models.DateField()
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
    )
    document_no = models.CharField(max_length=50)
    external_document_no = models.CharField(max_length=50, blank=True)
    applies_to_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name=_("Applies-to ID"),
        help_text=_(
            "ID of entries that will be applied when you choose the Apply Entries action"
        ),
    )
    vendor = models.ForeignKey(
        "Vendor", on_delete=models.PROTECT, related_name="ledger_entries"
    )
    description = models.TextField(blank=True)
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_ledger_entries",
    )
    original_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_("Original transaction amount before any modifications"),
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_("Transaction amount in local currency"),
    )
    # remaining_amount = models.DecimalField(
    #     max_digits=15, decimal_places=2, help_text=_("Remaining amount to be settled")
    # )
    open = models.BooleanField(
        default=True, help_text=_("Indicates if the entry is still open/unsettled")
    )
    due_date = models.DateField()

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="vendor_ledger_entries",
        db_column="dimension_1",  # Keep for migration compatibility
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="vendor_ledger_entries",
    )
    payment = models.ForeignKey(
        "financials.Payment",
        on_delete=models.CASCADE,
        related_name="vendor_ledger_entries",
        blank=True,
        null=True,
        help_text=_("Legacy link to financials.Payment (pre–payment journal flow)"),
    )
    transaction_no = models.CharField(
        max_length=255, verbose_name="Transaction No.", blank=True, null=True
    )

    class Meta:
        ordering = ["-posting_date", "-document_no"]
        verbose_name = _("Vendor Ledger Entry")
        verbose_name_plural = _("Vendor Ledger Entries")
        indexes = [
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["vendor"]),
            models.Index(fields=["vendor", "open"], name="purch_vl_vend_open_idx"),
        ]

    def __str__(self):
        return f"{self.document_type} - {self.document_no} ({self.id})"

    @property
    def is_payment_due(self):
        """Check if payment is due"""
        return self.due_date < timezone.now().date() and self.open

    @property
    def days_overdue(self):
        """Calculate number of days payment is overdue"""
        if self.is_payment_due:
            return (timezone.now().date() - self.due_date).days
        return 0

    @property
    def remaining_amount(self):
        """Calculate remaining amount"""
        total_amount = DetailedVendorLedgerEntry.objects.filter(
            vendor_ledger_entry=self
        ).aggregate(total_amount=Sum("amount"))["total_amount"]
        return total_amount

    def apply_to_entry(self, target_entry: "VendorLedger") -> None:
        if not self.open:
            raise ValidationError(_("Applies-to ID can only be set on open entries."))
        from financials.ledger_application import set_ledger_applies_to

        set_ledger_applies_to(self, target_entry)

    def clear_applies_to(self) -> None:
        from financials.ledger_application import clear_ledger_applies_to

        clear_ledger_applies_to(self)


class VendorPostingGroup(BaseModel):
    code = models.CharField(
        max_length=20,
        unique=True,
        validators=[MinLengthValidator(2)],
        help_text=_("Unique code for the vendor posting group"),
    )
    description = models.CharField(
        max_length=100, help_text=_("Description of the vendor posting group")
    )

    payables_account = models.ForeignKey(
        "financials.G_LAccount",
        on_delete=models.PROTECT,
        related_name="vendor_posting_groups",
        help_text=_("General ledger account number for payables"),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["code"]
        verbose_name = _("Vendor Posting Group")
        verbose_name_plural = _("Vendor Posting Groups")
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"


class Vendor(BaseModel):

    # Basic Information
    no = models.CharField(
        verbose_name="Vendor No.",
        max_length=20,
        unique=True,
        editable=False,
        # validators=[MinLengthValidator(5)],
        help_text=_("Unique vendor identification number"),
    )
    name = models.CharField(
        max_length=100, help_text=_("Official business name of the vendor")
    )
    blocked = models.BooleanField(
        default=False,
        help_text=_("Blocking vendor from making new purchases"),
    )

    vendor_posting_group = models.ForeignKey(
        "VendorPostingGroup",
        on_delete=models.PROTECT,
        related_name="vendor_posting_groups",
        help_text=_("Posting group that determines the accounts used for this vendor"),
        null=True,
        blank=True,
    )
    business_posting_group = models.ForeignKey(
        "postings.GeneralBusinessPostingGroup",
        on_delete=models.PROTECT,
        related_name="vendor_business_posting_groups",
        help_text=_("Posting group that determines the accounts used for this vendor"),
        null=True,
        blank=True,
    )
    vat_business_posting_group = models.ForeignKey(
        "postings.VATBusinessPostingGroup",
        verbose_name=_("VAT Bus. Posting Group"),
        on_delete=models.PROTECT,
        related_name="vendors",
        null=True,
        blank=True,
        help_text=_("VAT posting group for this vendor (when VAT is enabled)."),
    )

    # Financial Information
    # balance_lcy = models.In(
    #     max_digits=15,
    #     decimal_places=2,
    #     default=0.00,
    #     help_text=_("Balance in Local Currency"),
    # )

    # Contact Information
    address = models.CharField(max_length=100, blank=True)
    address_2 = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    post_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Payment Information
    payment_method = models.ForeignKey(
        "financials.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendors",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Vendor")
        verbose_name_plural = _("Vendors")
        indexes = [
            models.Index(fields=["no"]),
            models.Index(fields=["name"]),
            models.Index(fields=["updated_at", "id"], name="purch_vend_upd_id_idx"),
        ]

    def __str__(self):
        return f"{self.no} - {self.name}"

    @property
    def full_address(self):
        """Returns the complete address as a formatted string"""
        address_parts = [
            self.address,
            self.address_2,
            self.city,
            self.state.name if self.state else None,
            self.post_code,
            self.country.name if self.country else None,
        ]
        return ", ".join(filter(None, address_parts))

    @property
    def balance(self):
        """Calculate total balance from open vendor ledger entries"""
        # Get all open ledger entries and sum their amounts
        balance = VendorLedger.objects.filter(vendor=self, open=True)
        total_amount = 0
        for entry in balance:
            total_amount += entry.remaining_amount or 0
        return total_amount

    # no series
    def save(self, *args, **kwargs):
        if not self.no:
            print("no is not set")
            with transaction.atomic():
                vendor_no = NoSeriesLines.objects.filter(
                    no_series=PurchasePayable.objects.all().first().vendor_no.no_series
                ).first()
                print(vendor_no)
                if vendor_no:
                    increment_by = vendor_no.increment_by
                    if vendor_no.last_used_number:
                        self.no = increment_item_number(
                            vendor_no.last_used_number, increment_by
                        )
                        vendor_no.last_used_number = self.no
                        vendor_no.last_used_date = datetime.now()
                        vendor_no.save()
                    else:
                        self.no = vendor_no.start_number
                        vendor_no.last_used_number = self.no
                        vendor_no.last_used_date = datetime.now()
                        vendor_no.save()

            if not self.vendor_posting_group:
                self.vendor_posting_group = VendorPostingGroup.objects.all().first()

            if not self.business_posting_group:
                self.business_posting_group = (
                    GeneralBusinessPostingGroup.objects.all().first()
                )
        super().save(**kwargs)


class PurchaseCreditMemo(BaseModel):
    """Purchase Credit Memo - used for returning goods to vendor or correcting purchase invoices"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Unique credit memo number"),
    )
    vendor = models.ForeignKey(
        "purchases.Vendor",
        on_delete=models.PROTECT,
        related_name="purchase_credit_memos",
        verbose_name=_("Vendor"),
        help_text=_("Vendor to whom goods are being returned"),
    )
    vendor_name = models.CharField(
        _("Vendor Name"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Cached vendor name for quick display"),
    )
    contact_person = models.CharField(
        _("Contact"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Contact person at vendor"),
    )
    document_date = models.DateField(
        _("Document Date"),
        default=get_today,
        help_text=_("Date when the credit memo was created"),
    )
    posting_date = models.DateField(
        _("Posting Date"),
        default=get_today,
        help_text=_("Date when the credit memo will be posted to ledgers"),
    )
    due_date = models.DateField(
        _("Due Date"),
        default=get_today,
        help_text=_("Due date for the credit memo"),
    )
    expected_receipt_date = models.DateField(
        _("Expected Receipt Date"),
        blank=True,
        null=True,
        help_text=_("Expected date to receive credit from vendor"),
    )
    vendor_authorization_no = models.CharField(
        _("Vendor Authorization No."),
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Vendor's authorization number for the return"),
    )
    vendor_cr_memo_no = models.CharField(
        _("Vendor Cr. Memo No."),
        max_length=100,
        blank=True,
        null=True,
        help_text=_(
            "Vendor's own credit memo number (not the system-generated number)"
        ),
    )
    original_invoice_no = models.CharField(
        _("Original Invoice No."),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Reference to the original posted invoice if this is a return"),
    )
    original_posted_invoice = models.ForeignKey(
        "PostedPurchaseInvoice",
        on_delete=models.PROTECT,
        related_name="credit_memos",
        verbose_name=_("Original Posted Invoice"),
        blank=True,
        null=True,
        help_text=_("Link to the original posted invoice"),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=PurchaseCreditMemoStatus.choices(),
        default=PurchaseCreditMemoStatus.OPEN.value,
        help_text=_("Current status of the credit memo"),
    )

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="purchase_credit_memo_headers",
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        DimensionValue,
        on_delete=models.SET_NULL,
        related_name="purchase_credit_memo_headers_dim2",
        blank=True,
        null=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="purchase_credit_memo_headers",
        verbose_name=_("Dimension Set"),
    )

    class Meta:
        verbose_name = _("Purchase Credit Memo")
        verbose_name_plural = _("Purchase Credit Memos")
        ordering = ["-document_date", "-no"]

    def __str__(self):
        if self.no:
            return f"{self.no} - {self.vendor_name or self.vendor.name}"
        return f"Draft Credit Memo - {self.vendor_name or self.vendor.name}"

    def save(self, *args, **kwargs):
        """Generate credit memo number and cache vendor name"""
        with transaction.atomic():
            # Cache vendor name for quick display
            if self.vendor and not self.vendor_name:
                self.vendor_name = self.vendor.name

            # Generate credit memo number on creation
            if not self.pk and not self.no:
                try:
                    # Use the generate_document_number function
                    generated_number, _ = generate_document_number(
                        PurchasePayable,
                        "credit_memo_no",
                        "no",
                        is_no_series_lines=True,
                    )
                    if generated_number:
                        self.no = generated_number
                except ConfigurationError as e:
                    # Convert ConfigurationError to ValidationError for better user experience
                    raise ValidationError(str(e))

                if self.no is None:
                    raise ValidationError("Credit memo number is required")

            super().save(*args, **kwargs)


class PurchaseCreditMemoLine(BaseModel):
    """Purchase Credit Memo Line - items being returned to vendor"""

    credit_memo = models.ForeignKey(
        PurchaseCreditMemo,
        related_name="lines",
        on_delete=models.CASCADE,
        verbose_name=_("Credit Memo"),
    )
    item = models.ForeignKey(
        "items.Item",
        related_name="purchase_credit_memo_lines",
        on_delete=models.CASCADE,
        verbose_name=_("Item"),
    )
    description = models.TextField(_("Description"), blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
        verbose_name=_("Location"),
    )
    quantity = models.IntegerField(_("Quantity"), default=0)
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Item Unit of Measure"),
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Unit of Measure"),
    )
    unit_cost = models.IntegerField(_("Unit Cost"), default=0)

    global_dimension_1 = models.ForeignKey(
        DimensionValue,
        on_delete=models.PROTECT,
        related_name="purchase_credit_memo_lines",
        verbose_name=_("Global Dimension 1"),
    )
    dimension_set = models.ForeignKey(
        DimensionSet,
        on_delete=models.PROTECT,
        related_name="purchase_credit_memo_lines",
    )

    # Computed properties
    @property
    def line_amount(self):
        """Calculate line amount"""
        return self.quantity * self.unit_cost

    @property
    def total_amount(self):
        """Calculate total amount"""
        return self.quantity * self.unit_cost if self.quantity and self.unit_cost else 0

    def __str__(self):
        return f"{self.credit_memo.no or 'Draft'} - {self.item.item_name}"

    class Meta:
        verbose_name = _("Purchase Credit Memo Line")
        verbose_name_plural = _("Purchase Credit Memo Lines")
        ordering = ["id"]


class PostedPurchaseCreditMemo(BaseModel):
    no = models.CharField(max_length=50, unique=True)
    vendor = models.ForeignKey(
        "purchases.Vendor",
        on_delete=models.PROTECT,
        related_name="posted_purchase_credit_memos",
    )
    document_date = models.DateField()
    posting_date = models.DateField()
    due_date = models.DateField()
    vendor_cr_memo_no = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Vendor's own credit memo number"),
    )
    original_invoice_no = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Reference to the original posted invoice"),
    )
    original_posted_invoice = models.ForeignKey(
        "PostedPurchaseInvoice",
        on_delete=models.PROTECT,
        related_name="posted_credit_memos",
        blank=True,
        null=True,
        help_text=_("Link to the original posted invoice"),
    )

    @property
    def closed(self):
        # Check if any related vendor ledger entry is closed
        from purchases.models import VendorLedger

        vendor_ledger = VendorLedger.objects.filter(document_no=self.no).first()
        if vendor_ledger:
            return "Yes" if not vendor_ledger.open else "No"
        return "No"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.pk:
                purchase_payable = PurchasePayable.objects.all().first()
                if purchase_payable:
                    posted_credit_memo_no = NoSeriesLines.objects.filter(
                        no_series=PurchasePayable.objects.all()
                        .first()
                        .posted_credit_memo_no.no_series
                    ).first()
                    if posted_credit_memo_no:
                        increment_by = posted_credit_memo_no.increment_by
                        if posted_credit_memo_no.last_used_number:
                            # split if were the first number is start number ie wew00001, IJ_t000001
                            self.no = increment_item_number(
                                posted_credit_memo_no.last_used_number, increment_by
                            )
                            posted_credit_memo_no.last_used_number = self.no
                            posted_credit_memo_no.last_used_date = datetime.now()
                            posted_credit_memo_no.save()
                        else:
                            self.no = posted_credit_memo_no.start_number
                            posted_credit_memo_no.last_used_number = self.no
                            posted_credit_memo_no.last_used_date = datetime.now()
                            posted_credit_memo_no.save()
            super().save(*args, **kwargs)


class PostedPurchaseCreditMemoLine(BaseModel):
    posted_purchase_credit_memo = models.ForeignKey(
        PostedPurchaseCreditMemo,
        related_name="posted_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
    )
    amount = models.IntegerField()

    item = models.ForeignKey(
        "items.Item",
        related_name="posted_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
    )
    description = models.TextField(blank=True)
    location_code = models.ForeignKey(
        "items.Location",
        related_name="location_posted_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
    )
    quantity = models.IntegerField()
    item_unit_of_measure = models.ForeignKey(
        "items.ItemUnitOfMeasure",
        related_name="itemuom_posted_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        related_name="unitofmeasure_posted_purchase_credit_memo_lines",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    unit_cost = models.IntegerField()

    class Meta:
        ordering = ["id"]


class DetailedVendorLedgerEntry(BaseModel):
    from common.enums import DocumentType, EntryType

    entry_no = models.AutoField(primary_key=True)
    posting_date = models.DateField()
    entry_type = models.CharField(
        max_length=20,
        choices=EntryType.choices,
        help_text=_("Type of vendor ledger entry"),
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        help_text=_("Type of document that created this entry"),
    )
    document_no = models.CharField(
        max_length=50, help_text=_("Document number reference")
    )

    vendor = models.ForeignKey(
        "Vendor",
        on_delete=models.PROTECT,
        related_name="detailed_ledger_entries",
        help_text=_("Vendor associated with this entry"),
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
    vendor_ledger_entry = models.ForeignKey(
        "VendorLedger",
        on_delete=models.CASCADE,
        related_name="detailed_entries",
        help_text=_("Related vendor ledger entry"),
    )

    debit_amount = models.IntegerField(
        help_text=_("Debit amount in transaction currency"),
    )
    credit_amount = models.IntegerField(
        help_text=_("Credit amount in transaction currency"),
    )
    applied_vendor_ledger_entry_no = models.IntegerField(
        help_text=_("Applied vendor ledger entry number"),
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
        related_name="vendor_detailed_entries",
        help_text=_("Global Dimension 1 value"),
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="vendor_detailed_entries",
    )

    transaction_no = models.CharField(
        max_length=50,
        help_text=_("Transaction No."),
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["posting_date", "entry_no"]
        verbose_name = _("Detailed Vendor Ledger Entry")
        verbose_name_plural = _("Detailed Vendor Ledger Entries")
        indexes = [
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["vendor"]),
            models.Index(fields=["entry_no"]),
        ]

    def __str__(self):
        return f"{self.entry_no} - {self.document_type} {self.document_no} ({self.vendor.name})"
