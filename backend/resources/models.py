from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime

from utils.utils import BaseModel
from base.models import Objects
from dimension.models import DefaultDimension, DimensionValue
from setup.models import NoSeriesLines, ResourceSetup
from helpers.helpers import increment_item_number


class Resource(BaseModel):
    """
    Resource model for managing service providers (people, equipment, spaces).
    Used in Production BOM for service-based businesses.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    RESOURCE_TYPES = (
        ("person", "Person"),
        ("equipment", "Equipment"),
        ("space", "Space"),
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="Code",
        help_text="Auto-generated resource code (e.g., RES-XXX-0001)",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Name",
        help_text="Name of the resource (e.g., Jane Doe - Master Stylist)",
    )
    resource_type = models.CharField(
        max_length=10,
        choices=RESOURCE_TYPES,
        verbose_name="Resource Type",
        help_text="Type of resource: person, equipment, or space",
    )
    base_unit = models.ForeignKey(
        "items.UnitOfMeasure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Base Unit",
        help_text="Unit of measurement for this resource (same model as items)",
        related_name="resources_using_as_base",
        to_field="code",
    )

    # Cost Structure (Business Central approach)
    direct_unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Direct Unit Cost",
        help_text="Pure direct cost (e.g., labor rate, machine cost per unit)",
    )
    indirect_cost_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Indirect Cost %",
        help_text="Overhead percentage (rent, utilities, admin, etc.)",
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Unit Cost",
        help_text="Auto-calculated: Direct Unit Cost + (Direct Unit Cost × Indirect Cost %)",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Price",
        help_text="Price per unit (what customer pays)",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Whether this resource is currently active",
    )
    blocked = models.BooleanField(
        default=False,
        verbose_name="Blocked",
        help_text="Whether this resource is blocked from use",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Additional details about this resource",
    )
    general_product_posting_group = models.ForeignKey(
        "postings.GeneralProductPostingGroup",
        on_delete=models.SET_NULL,
        verbose_name="General Product Posting Group",
        null=True,
        blank=True,
        help_text="General product posting group for accounting",
    )
    photo = models.ImageField(
        upload_to="resources/photos/",
        blank=True,
        null=True,
        verbose_name="Photo",
        help_text="Photo of the resource",
    )

    class Meta:
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["resource_type"]),
            models.Index(fields=["is_active"]),
        ]

    @staticmethod
    def _get_resource_table_object():
        """
        Resolve the Objects entry representing the Resources table.

        Uses the related_model pointer so we don't hard-code table IDs.
        """
        try:
            return Objects.objects.get(
                object_type="Table",
                related_model="resources.Resource",
            )
        except Objects.DoesNotExist:
            return None

    @property
    def global_dimension_1(self):
        """
        Branch / Location dimension for this resource.

        NOTE:
        - This is no longer stored directly on the Resource record.
        - It is now resolved via the DefaultDimension table using:
          * table  -> Resources table ID (Objects.object_id)
          * no     -> this resource's code
        - Returns the first matching DimensionValue (or None).
        """
        table_obj = self._get_resource_table_object()
        if not table_obj:
            return None

        default_dim = (
            DefaultDimension.objects.filter(
                table=table_obj,
                no=self.code,
            )
            .select_related("dimension_value")
            .first()
        )

        return default_dim.dimension_value if default_dim else None

    def clean(self):
        """Validate the model fields"""
        super().clean()

        # Validate direct_unit_cost
        if self.direct_unit_cost < 0:
            raise ValidationError(
                {"direct_unit_cost": "Direct unit cost cannot be negative"}
            )

        # Validate indirect_cost_pct
        if self.indirect_cost_pct < 0:
            raise ValidationError(
                {"indirect_cost_pct": "Indirect cost percentage cannot be negative"}
            )
        if self.indirect_cost_pct > 100:
            raise ValidationError(
                {"indirect_cost_pct": "Indirect cost percentage cannot exceed 100%"}
            )

        # Validate unit_price
        if self.unit_price < 0:
            raise ValidationError({"unit_price": "Unit price cannot be negative"})

        # Calculate unit_cost for validation (with proper rounding)
        from decimal import Decimal, ROUND_HALF_UP

        calculated_unit_cost = self.direct_unit_cost * (
            1 + (self.indirect_cost_pct / 100)
        )
        calculated_unit_cost = calculated_unit_cost.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Validate unit_price >= calculated unit_cost
        if self.unit_price < calculated_unit_cost:
            raise ValidationError(
                {
                    "unit_price": f"Unit price must be greater than or equal to unit cost ({calculated_unit_cost:.2f})"
                }
            )

    def save(self, *args, **kwargs):
        """Override save to auto-generate code and calculate unit_cost"""
        # Auto-generate code using Resource number series setup
        if not self.code:
            try:
                resource_setup = ResourceSetup.objects.all().first()
                if resource_setup and resource_setup.resource_no_series:
                    resource_no_series = NoSeriesLines.objects.filter(
                        no_series=resource_setup.resource_no_series
                    ).first()

                    if resource_no_series:
                        increment_by = resource_no_series.increment_by
                        if resource_no_series.last_used_number:
                            # Generate new number using existing logic
                            self.code = increment_item_number(
                                resource_no_series.last_used_number, increment_by
                            )
                        else:
                            # Use start number if no previous number exists
                            self.code = resource_no_series.start_number

                        # Update the NoSeriesLines object
                        resource_no_series.last_used_number = self.code
                        resource_no_series.last_used_date = datetime.now().date()
                        resource_no_series.save()
                    else:
                        # Fallback if no series lines configured
                        import random
                        import string

                        self.code = (
                            f"RES-TMP-{''.join(random.choices(string.digits, k=4))}"
                        )
                else:
                    # Fallback if no ResourceSetup configured
                    import random
                    import string

                    self.code = f"RES-TMP-{''.join(random.choices(string.digits, k=4))}"
            except Exception as e:
                # Fallback on any error
                import random
                import string

                self.code = f"RES-TMP-{''.join(random.choices(string.digits, k=4))}"

        # Auto-calculate unit_cost based on direct cost + indirect cost %
        # Formula: Unit Cost = Direct Unit Cost + (Direct Unit Cost × Indirect Cost %)
        # Round to 2 decimal places to match field definition
        from decimal import Decimal, ROUND_HALF_UP

        calculated_cost = self.direct_unit_cost * (1 + (self.indirect_cost_pct / 100))
        self.unit_cost = calculated_cost.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Run validation
        self.full_clean()

        # Default base_unit to HOUR if not set (same UnitOfMeasure model as items)
        if self.base_unit_id is None:
            from items.models import UnitOfMeasure

            uom, _ = UnitOfMeasure.objects.get_or_create(
                code="HOUR",
                defaults={"description": "Hour"},
            )
            self.base_unit = uom

        super().save(*args, **kwargs)

        # Sync ResourceUnitOfMeasure: ensure base_unit has a row with quantity_per_unit=1, default=True
        self._sync_resource_unit_of_measure()

    def _sync_resource_unit_of_measure(self):
        """Create or update ResourceUnitOfMeasure for this resource's base_unit (quantity=1, default=True)."""
        if not self.base_unit:
            return
        uom = self.base_unit
        # Ensure exactly one ResourceUnitOfMeasure for this resource+base_unit with default=True, quantity_per_unit=1
        ResourceUnitOfMeasure.objects.filter(resource=self).update(default=False)
        ResourceUnitOfMeasure.objects.update_or_create(
            resource=self,
            unit_of_measure=uom,
            defaults={
                "quantity_per_unit": 1,
                "default": True,
            },
        )

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def indirect_cost_amount(self):
        """Calculate the actual indirect cost amount"""
        from decimal import Decimal, ROUND_HALF_UP

        amount = self.direct_unit_cost * (self.indirect_cost_pct / 100)
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def profit_per_unit(self):
        """Calculate profit per unit"""
        return self.unit_price - self.unit_cost

    @property
    def profit_margin(self):
        """Calculate profit margin percentage"""
        if self.unit_price > 0:
            return ((self.unit_price - self.unit_cost) / self.unit_price) * 100
        return 0

    @property
    def get_available_uoms(self):
        """
        Return list of resource unit of measure options for API/sales (code, description, default, quantity_per_unit).
        Mirrors item's get_available_uoms for consistency.
        """
        ruoms = (
            ResourceUnitOfMeasure.objects.filter(resource=self)
            .select_related("unit_of_measure")
            .order_by("-default", "unit_of_measure__code")
        )
        return [
            {
                "code": ruom.unit_of_measure.code,
                "description": ruom.unit_of_measure.description,
                "default": ruom.default,
                "quantity_per_unit": ruom.quantity_per_unit,
            }
            for ruom in ruoms
        ]


class ResourceUnitOfMeasure(BaseModel):
    """
    Unit(s) of measure for a resource (e.g. Hour, Day, Session).
    When base_unit is set on the Resource card, a row is created/updated here with
    quantity_per_unit=1 and default=True.
    """

    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="resource_units_of_measure",
        verbose_name="Resource",
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        on_delete=models.CASCADE,
        related_name="resource_unit_of_measure_set",
        verbose_name="Unit of Measure",
    )
    quantity_per_unit = models.PositiveIntegerField(
        default=1,
        verbose_name="Quantity per Unit",
        help_text="Quantity per unit (1 for base unit).",
    )
    default = models.BooleanField(
        default=False,
        verbose_name="Default",
        help_text="Default unit of measure for this resource (typically the base unit).",
    )

    class Meta:
        verbose_name = "Resource Unit of Measure"
        verbose_name_plural = "Resource Units of Measure"
        ordering = ["resource", "-default", "unit_of_measure__code"]
        unique_together = [("resource", "unit_of_measure")]

    def __str__(self):
        return f"{self.resource.code} - {self.unit_of_measure.code}"


class ResourceLedgerEntry(BaseModel):
    """
    Resource Ledger Entry (Business Central style).
    Tracks usage, sales, and costs per resource (posting date, document, quantity, UOM, totals).
    """

    class EntryType(models.TextChoices):
        USAGE = "Usage", "Usage"
        SALE = "Sale", "Sale"
        POSITIVE_ADJUSTMENT = "Positive_Adjustment", "Positive Adjustment"
        NEGATIVE_ADJUSTMENT = "Negative_Adjustment", "Negative Adjustment"

    class SourceType(models.TextChoices):
        DOCUMENT = "Document", "Document"
        JOURNAL = "Journal", "Journal"

    entry_type = models.CharField(
        max_length=50,
        choices=EntryType.choices,
        verbose_name="Entry Type",
        help_text="Usage, Sale, or Adjustment",
    )
    document_no = models.CharField(
        max_length=255,
        verbose_name="Document No.",
        db_index=True,
        help_text="Document number (e.g. invoice no, journal batch no)",
    )
    posting_date = models.DateField(
        verbose_name="Posting Date",
        db_index=True,
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        verbose_name="Resource",
        help_text="Resource No.",
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Description",
        blank=True,
    )
    work_type = models.CharField(
        max_length=50,
        verbose_name="Work Type",
        blank=True,
        null=True,
        help_text="Optional work type code",
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        default=0,
        verbose_name="Quantity",
        help_text="Quantity in the line UOM",
    )
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resource_ledger_entries",
        verbose_name="Unit of Measure Code",
    )
    total_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="Total Cost",
    )
    total_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="Total Price",
    )
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        verbose_name="Unit Price",
    )
    source_type = models.CharField(
        max_length=50,
        choices=SourceType.choices,
        verbose_name="Source Type",
        default=SourceType.DOCUMENT,
    )
    source_no = models.CharField(
        max_length=255,
        verbose_name="Source No.",
        blank=True,
        null=True,
        help_text="Source document or journal number",
    )
    qty_per_unit_of_measure = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        default=1,
        verbose_name="Qty. per Unit of Measure",
        help_text="Conversion to base UOM (e.g. 1 for HOUR, 60 for MINUTE when base is HOUR)",
    )
    quantity_base = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        default=0,
        verbose_name="Quantity (Base)",
        help_text="Quantity expressed in resource base unit",
    )

    class Meta:
        verbose_name = "Resource Ledger Entry"
        verbose_name_plural = "Resource Ledger Entries"
        ordering = ["-posting_date", "-created_at"]
        indexes = [
            models.Index(fields=["posting_date"]),
            models.Index(fields=["document_no"]),
            models.Index(fields=["resource", "posting_date"]),
        ]

    def __str__(self):
        return f"{self.document_no} - {self.resource.code} ({self.entry_type})"
