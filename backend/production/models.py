import uuid

from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal, ROUND_HALF_UP
from django.utils.timezone import datetime
from datetime import date
from utils.utils import BaseModel
from items.models import Item, Location, UnitOfMeasure
from resources.models import Resource
from helpers.helpers import increment_item_number
from production.enums import (
    CapacityUnitOfMeasureType,
    DayOfWeek,
    UnitCostCalculation,
)


class ProductionBOM(BaseModel):
    """
    Production Bill of Materials (BOM) model.
    Defines the "recipe" for delivering a service by specifying required resources and materials.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    bom_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="BOM Code",
        help_text="Auto-generated BOM code (e.g., BOM-XXX-0001)",
    )
    name = models.CharField(
        max_length=100, verbose_name="Name", help_text="Name of this BOM"
    )

    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit of Measure Code",
        help_text="Unit of measure for this BOM (e.g., PCS, HOUR, KG)",
        to_field="code",
    )

    STATUS_CHOICES = [
        ("new", "New"),
        ("certified", "Certified"),
        ("under_development", "Under Development"),
        ("closed", "Closed"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        verbose_name="Status",
        help_text="Status of the BOM",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Whether this BOM is currently active",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes",
        help_text="Additional notes about this BOM",
    )

    class Meta:
        verbose_name = "Production BOM"
        verbose_name_plural = "Production BOMs"
        ordering = ["bom_code"]
        indexes = [
            models.Index(fields=["bom_code"]),
            models.Index(fields=["is_active"]),
        ]

    def clean(self):
        """Validate the model fields"""
        super().clean()

    def save(self, *args, **kwargs):
        """Override save to auto-generate code using number series"""
        from setup.models import ManufacturingSetup, NoSeriesLines
        from helpers.helpers import ConfigurationError

        # Auto-generate code if not provided
        if not self.bom_code:
            try:
                manufacturing_setup = ManufacturingSetup.objects.all().first()
                if manufacturing_setup and manufacturing_setup.bom_no_series:
                    bom_no_series = NoSeriesLines.objects.filter(
                        no_series=manufacturing_setup.bom_no_series
                    ).first()

                    if bom_no_series:
                        increment_by = bom_no_series.increment_by
                        if bom_no_series.last_used_number:
                            # Generate new number using existing logic
                            self.bom_code = increment_item_number(
                                bom_no_series.last_used_number, increment_by
                            )
                        else:
                            # Use start number if no previous number exists
                            self.bom_code = bom_no_series.start_number

                        # Update the NoSeriesLines object
                        bom_no_series.last_used_number = self.bom_code
                        bom_no_series.last_used_date = datetime.now().date()
                        bom_no_series.save()
                    else:
                        # Fallback if no series lines configured
                        import random
                        import string

                        self.bom_code = (
                            f"BOM-TMP-{''.join(random.choices(string.digits, k=4))}"
                        )
                else:
                    # Fallback if no manufacturing setup configured
                    import random
                    import string

                    self.bom_code = (
                        f"BOM-TMP-{''.join(random.choices(string.digits, k=4))}"
                    )
            except Exception as e:
                # Fallback on any error
                import random
                import string

                self.bom_code = f"BOM-TMP-{''.join(random.choices(string.digits, k=4))}"
                print(f"Error generating BOM code: {e}")

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bom_code} - {self.name}"

    def calculate_total_cost(self):
        """Calculate total cost of all BOM lines"""
        total = self.lines.aggregate(total_cost=Sum("total_cost"))["total_cost"]
        return total if total else 0

    def calculate_profit_margin(self):
        """Calculate profit margin percentage"""
        # Get the item associated with this BOM (reverse relationship)
        try:
            service_item = self.item
            if not service_item or not service_item.unit_price:
                return 0

            service_price = float(service_item.unit_price)
            total_cost = float(self.calculate_total_cost())

            if service_price > 0:
                return ((service_price - total_cost) / service_price) * 100
            return 0
        except Item.DoesNotExist:
            return 0

    def get_item_requirements(self):
        """Get list of item lines with quantities"""
        return self.lines.filter(line_type="item").select_related("item")

    def get_production_bom_requirements(self):
        """Get list of production BOM lines with quantities"""
        return self.lines.filter(line_type="production_bom").select_related("item")

    @property
    def total_cost(self):
        """Property to access total cost"""
        return self.calculate_total_cost()

    @property
    def profit_margin(self):
        """Property to access profit margin"""
        return self.calculate_profit_margin()


class BOMLine(BaseModel):
    """
    BOM Line model representing individual components (resources or inventory) within a BOM.
    Following Business Central format.
    """

    LINE_TYPES = (
        ("item", "Item"),
        ("production_bom", "Production BOM"),
    )

    bom = models.ForeignKey(
        ProductionBOM,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="BOM",
    )
    line_number = models.IntegerField(
        verbose_name="Line Number",
        help_text="Sequence number for this line",
        null=True,
        blank=True,
    )
    line_type = models.CharField(
        max_length=20,
        choices=LINE_TYPES,
        verbose_name="Type",
        help_text="Type of line: item or production bom",
    )

    # Item/Resource selection
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bom_lines_as_item",
        verbose_name="No.",
        help_text="Item number (for inventory items) or Resource (for resource lines)",
    )

    # Description (auto-filled from item/resource)
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Description",
        help_text="Description of the item or resource",
    )

    # Quantity per unit
    quantity_per = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        verbose_name="Quantity per",
        help_text="Quantity required per unit of the parent item",
    )

    # Unit of Measure
    unit_of_measure = models.ForeignKey(
        "items.UnitOfMeasure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit of Measure Code",
        help_text="Unit of measure (e.g., PCS, HOUR, KG)",
        to_field="code",
    )

    # Scrap percentage
    scrap_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Scrap %",
        help_text="Scrap percentage (0-100)",
    )

    # Cost fields (auto-calculated)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Unit Cost",
        help_text="Cost per unit (auto-calculated)",
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False,
        verbose_name="Total Cost",
        help_text="Total cost for this line (auto-calculated)",
    )

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes",
        help_text="Additional notes for this line",
    )

    class Meta:
        verbose_name = "BOM Line"
        verbose_name_plural = "BOM Lines"
        ordering = ["bom", "line_number"]
        indexes = [
            models.Index(fields=["bom"]),
            models.Index(fields=["line_type"]),
            models.Index(fields=["item"]),
        ]
        unique_together = [["bom", "line_number"]]

    def clean(self):
        """Validate the model fields"""
        super().clean()

        # Validate scrap percentage
        if self.scrap_pct < 0 or self.scrap_pct > 100:
            raise ValidationError(
                {"scrap_pct": "Scrap percentage must be between 0 and 100"}
            )

        # Validate quantity per
        if self.quantity_per <= 0:
            raise ValidationError(
                {"quantity_per": "Quantity per must be greater than 0"}
            )

        # Validate that item is set
        if not self.item:
            raise ValidationError({"item": "Item is required for all line types"})

        # Validate production BOM lines have a production BOM
        if self.line_type == "production_bom":
            if not hasattr(self.item, "production_bom") or not self.item.production_bom:
                raise ValidationError(
                    {
                        "item": "Item must have a Production BOM for Production BOM line type"
                    }
                )

    def save(self, *args, **kwargs):
        """Override save to auto-fill description and calculate costs"""
        # Auto-generate line number if not provided
        if self.line_number is None:
            # Get the max line number for this BOM and add 10000
            max_line = BOMLine.objects.filter(bom=self.bom).aggregate(
                max_num=models.Max("line_number")
            )["max_num"]
            self.line_number = (max_line or 0) + 10000

        # Auto-fill description based on line type and item
        if self.line_type == "item" and self.item:
            # For item lines
            self.description = self.item.item_name
            self.unit_of_measure = self.item.unit_of_measure

            # Use manual_unit_cost for service/non-inventory items, or calculate for inventory items
            if self.item.type in ["Service", "Non-Inventory"]:
                raw_uc = self.item.manual_unit_cost or 0
                self.unit_cost = Decimal(str(raw_uc)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                # For inventory items, calculate average cost from item ledger
                from items.models import ItemLedgerEntries

                total_cost_of_goods = ItemLedgerEntries.objects.filter(
                    item=self.item, entry_type="Purchase"
                ).aggregate(Sum("total"))["total__sum"] or Decimal("0.00")
                total_quantity_on_hand = ItemLedgerEntries.objects.filter(
                    item=self.item
                ).aggregate(Sum("quantity"))["quantity__sum"] or Decimal("0.00")

                if total_quantity_on_hand > 0:
                    # Sum() may return float; divide as Decimal before quantize
                    tc = Decimal(str(total_cost_of_goods))
                    tq = Decimal(str(total_quantity_on_hand))
                    self.unit_cost = (tc / tq).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                else:
                    self.unit_cost = Decimal("0.00")

            self.total_cost = (
                Decimal(str(self.quantity_per)) * self.unit_cost
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif self.line_type == "production_bom" and self.item:
            # For production BOM lines, the item should have a production BOM
            self.description = self.item.item_name
            self.unit_of_measure = self.item.unit_of_measure
            # Cost will be calculated from the nested BOM
            if hasattr(self.item, "production_bom") and self.item.production_bom:
                bom_cost = self.item.production_bom.calculate_total_cost()
                self.unit_cost = (
                    Decimal(str(bom_cost)) if bom_cost else Decimal("0.00")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                self.unit_cost = Decimal("0.00")
            self.total_cost = (
                Decimal(str(self.quantity_per)) * self.unit_cost
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        if self.item:
            return (
                f"{self.bom.bom_code} - Line {self.line_number}: {self.item.item_name}"
            )
        return f"{self.bom.bom_code} - Line {self.line_number}"


class ProductionOrder(BaseModel):
    """
    Production Order model.
    Represents a production order for manufacturing items.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    no = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="No.",
        help_text="Auto-generated production order number (e.g., PROD-XXX-0001)",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Name",
        help_text="Name of this production order",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description of the production order",
    )

    SOURCE_TYPE_CHOICES = [
        ("item", "Item"),
        ("production_bom", "Production BOM"),
    ]

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default="item",
        verbose_name="Source Type",
        help_text="Type of source: item or production bom",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Item",
        help_text="Item to produce (must have a Production BOM); optional while order is draft",
        related_name="production_orders",
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Quantity",
        help_text="Quantity to produce",
    )

    blocked = models.BooleanField(
        default=False,
        verbose_name="Blocked",
        help_text="Whether this production order is blocked",
    )

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("released", "Released"),
        ("finished", "Finished"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="released",
        verbose_name="Status",
        help_text="Status of the production order",
    )

    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Global Dimension 1",
        help_text="Branch for list filtering and posting; set on create and refresh",
        related_name="branch_production_orders",
    )

    class Meta:
        verbose_name = "Production Order"
        verbose_name_plural = "Production Orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["no"]),
            models.Index(fields=["source_type"]),
            models.Index(fields=["item"]),
            models.Index(fields=["blocked"]),
            models.Index(fields=["status"]),
            models.Index(fields=["global_dimension_1"]),
        ]

    def clean(self):
        """Validate the model fields"""
        super().clean()

        if self.quantity is None or self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than 0"})

        is_draft = self.status == "draft"
        if not self.item_id and not is_draft:
            raise ValidationError({"item": "Item is required"})

    def save(self, *args, **kwargs):
        """Override save to auto-generate number using number series"""
        from setup.models import ManufacturingSetup, NoSeriesLines

        # Auto-generate number if not provided
        if not self.no:
            try:
                manufacturing_setup = ManufacturingSetup.objects.all().first()
                if (
                    manufacturing_setup
                    and manufacturing_setup.production_order_no_series
                ):
                    order_no_series = NoSeriesLines.objects.filter(
                        no_series=manufacturing_setup.production_order_no_series
                    ).first()

                    if order_no_series:
                        increment_by = order_no_series.increment_by
                        if order_no_series.last_used_number:
                            # Generate new number using existing logic
                            self.no = increment_item_number(
                                order_no_series.last_used_number, increment_by
                            )
                        else:
                            # Use start number if no previous number exists
                            self.no = order_no_series.start_number

                        # Update the NoSeriesLines object
                        order_no_series.last_used_number = self.no
                        order_no_series.last_used_date = datetime.now().date()
                        order_no_series.save()
                    else:
                        # Fallback if no series lines configured
                        import random
                        import string

                        self.no = (
                            f"PROD-TMP-{''.join(random.choices(string.digits, k=4))}"
                        )
                else:
                    # Fallback if no manufacturing setup configured
                    import random
                    import string

                    self.no = f"PROD-TMP-{''.join(random.choices(string.digits, k=4))}"
            except Exception as e:
                # Fallback on any error
                import random
                import string

                self.no = f"PROD-TMP-{''.join(random.choices(string.digits, k=4))}"
                print(f"Error generating production order number: {e}")

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.no} - {self.name}"

    @property
    def last_date_modified(self):
        """Property to access last modified date from BaseModel"""
        return self.updated_at

    def refresh_production_details(self, user=None, request=None):
        """
        Refresh production order lines based on current BOM setup.
        Similar to 'Refresh Production Order' in Microsoft Business Central.
        Recalculates and updates production order line data based on the current BOM.

        Before refreshing, deletes all existing Item Journals, Production Order
        Components, and Production Order Lines for this order so they are
        recreated from the current BOM.

        Args:
            user: User object to associate with created ItemJournal entries
            request: Optional HttpRequest; branch/dimensions follow ``get_branch_for_request``
                (``X-Branch-Id``) like sales, then fall back to ``user.global_dimension_1``.
        """
        from decimal import Decimal
        from items.models import ItemJournal

        # Step 0: Delete all existing lines related to this production order
        # Order: ItemJournals first, then Components (reference lines), then Lines
        ItemJournal.objects.filter(production_order=self).delete()
        self.components.all().delete()
        self.lines.all().delete()

        # Get the production BOM from the item
        if not self.item:
            raise ValueError("Item is required to refresh production details")

        production_bom = None
        if hasattr(self.item, "production_bom") and self.item.production_bom:
            production_bom = self.item.production_bom
        else:
            raise ValueError(
                f"Item '{self.item.item_name}' does not have an associated Production BOM"
            )

        # BOMs linked from item cards / temp codes (e.g. BOM-TMP-*) may exist with
        # is_active=False. Starting or refreshing a production order implies we use
        # this BOM now — activate it instead of failing with an unrelated-looking error.
        if not production_bom.is_active:
            production_bom.is_active = True
            production_bom.save(update_fields=["is_active"])

        # Get all BOM lines
        bom_lines = list(
            production_bom.lines.all().select_related("item", "unit_of_measure")
        )

        if not bom_lines:
            raise ValueError(
                f"Production BOM '{production_bom.bom_code}' has no lines defined"
            )

        def refresh_bom_line_costs(bom_lines_list):
            """Refresh BOM line unit_cost/total_cost from item data. Recursively
            refresh nested production_bom lines first so their calculate_total_cost works."""
            for bl in bom_lines_list:
                if bl.line_type == "production_bom" and bl.item and getattr(
                    bl.item, "production_bom", None
                ):
                    nested_lines = list(
                        bl.item.production_bom.lines.all().select_related(
                            "item", "unit_of_measure"
                        )
                    )
                    if nested_lines:
                        refresh_bom_line_costs(nested_lines)
                bl.save()

        # Step 0: Refresh BOM line costs from current item data so
        # production_bom.calculate_total_cost() returns fresh values
        refresh_bom_line_costs(bom_lines)

        # Helper: get effective unit cost for a BOM line from item/ledger (used when
        # stored BOM line cost is still 0 after refresh, e.g. cost only in ValueEntry)
        def get_bom_line_unit_cost_from_item(bom_line):
            if not bom_line or not bom_line.item:
                return Decimal("0.00")
            item = bom_line.item
            if bom_line.line_type == "item":
                if item.type in ["Service", "Non-Inventory"]:
                    cost = (item.manual_unit_cost if item.manual_unit_cost else 0) or 0
                    return Decimal(str(cost)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                # Try ValueEntry (Item.unit_cost) first - often the current cost
                try:
                    uc = getattr(item, "unit_cost", None) or 0
                    if uc and float(uc) > 0:
                        return Decimal(str(float(uc))).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                except (TypeError, ValueError):
                    pass
                # Fallback: ItemLedgerEntries (Purchase average cost)
                from items.models import ItemLedgerEntries

                total_cost_of_goods = ItemLedgerEntries.objects.filter(
                    item=item, entry_type="Purchase"
                ).aggregate(Sum("total"))["total__sum"] or Decimal("0.00")
                total_qty = ItemLedgerEntries.objects.filter(item=item).aggregate(
                    Sum("quantity")
                )["quantity__sum"] or Decimal("0.00")
                if total_qty and float(total_qty) > 0:
                    tc = Decimal(str(total_cost_of_goods))
                    tq = Decimal(str(total_qty))
                    return (tc / tq).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                return Decimal("0.00")
            if bom_line.line_type == "production_bom" and getattr(item, "production_bom", None):
                nested = item.production_bom.calculate_total_cost()
                return (
                    Decimal(str(nested)) if nested else Decimal("0.00")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return Decimal("0.00")

        # Calculate unit cost for finished product from BOM lines (cost per 1 unit of output)
        # Use production_bom.calculate_total_cost() (now fresh after BOM line save above);
        # if still 0, recalc from item sources (ValueEntry, ItemLedgerEntries)
        line_unit_cost = production_bom.calculate_total_cost()
        line_unit_cost = Decimal(str(line_unit_cost)) if line_unit_cost else Decimal("0.00")
        line_unit_cost = line_unit_cost.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if line_unit_cost <= 0:
            bom_total_cost = Decimal("0.00")
            for bom_line in bom_lines:
                if not bom_line.item:
                    continue
                unit_cost_val = get_bom_line_unit_cost_from_item(bom_line)
                line_cost = Decimal(str(bom_line.quantity_per)) * unit_cost_val
                bom_total_cost += line_cost
            line_unit_cost = bom_total_cost.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Header dimensions: prefer X-Branch-Id (same as sales/items), then user branch
        from dimension.branch_filter import get_branch_for_request
        from dimension.models import get_posting_dimension_payload
        from dimension.utils import get_first_branch_dimension_value

        effective_branch = None
        if request:
            effective_branch = get_branch_for_request(request)
        if not effective_branch and user and getattr(user, "is_authenticated", False):
            effective_branch = getattr(user, "global_dimension_1", None)
        if not effective_branch:
            effective_branch = get_first_branch_dimension_value()
        _dim_payload = get_posting_dimension_payload(global_dimension_1=effective_branch)
        prod_line_dim_set = _dim_payload.get("dimension_set")
        prod_line_g1 = _dim_payload.get("global_dimension_1") or effective_branch
        if not prod_line_dim_set or not prod_line_g1:
            raise ValueError(
                "Cannot refresh production order: Global Dimension 1 and dimension set "
                "are required on production lines. Check General Ledger Setup and user branch."
            )

        user_location = Location.objects.filter(code=prod_line_g1.code).first()
        if not user_location:
            raise ValueError(
                f"Location '{prod_line_g1.code}' not found for branch. "
                "Create a Location with code matching the branch dimension code."
            )

        # Step 1: Create/Update ProductionOrderLine for the finished product
        production_line, line_created = ProductionOrderLine.objects.get_or_create(
            production_order=self,
            item=self.item,
            defaults={
                "description": self.item.item_name,
                "quantity": self.quantity,
                "unit_of_measure_code": self.item.unit_of_measure,
                "production_bom_no": production_bom,
                "status": "released",  # Set to released on update production details
                "unit_cost": line_unit_cost,
                "location_code": user_location,
                "global_dimension_1": prod_line_g1,
                "dimension_set": prod_line_dim_set,
            },
        )

        # Update existing production line
        if not line_created:
            preserve_location = production_line.location_code
            preserve_dimension = production_line.global_dimension_1
            preserve_dimension_set = production_line.dimension_set
            preserve_start_date = production_line.start_date
            preserve_ending_date = production_line.ending_date
            preserve_due_date = production_line.due_date
            preserve_finished_quantity = production_line.finished_quantity

            production_line.description = self.item.item_name
            production_line.quantity = self.quantity
            production_line.unit_of_measure_code = self.item.unit_of_measure
            production_line.production_bom_no = production_bom
            production_line.item = self.item
            production_line.unit_cost = line_unit_cost
            production_line.status = "released"  # Set to released on update production details

            # Restore preserved fields
            if preserve_location:
                production_line.location_code = preserve_location
            else:
                production_line.location_code = user_location
            if preserve_dimension:
                production_line.global_dimension_1 = preserve_dimension
            else:
                production_line.global_dimension_1 = prod_line_g1
            if preserve_dimension_set:
                production_line.dimension_set = preserve_dimension_set
            else:
                production_line.dimension_set = prod_line_dim_set
            if preserve_start_date:
                production_line.start_date = preserve_start_date
            if preserve_ending_date:
                production_line.ending_date = preserve_ending_date
            if preserve_due_date:
                production_line.due_date = preserve_due_date
            if preserve_finished_quantity:
                if preserve_finished_quantity > self.quantity:
                    production_line.finished_quantity = self.quantity
                else:
                    production_line.finished_quantity = preserve_finished_quantity

            production_line.save()

        # Step 2: Create/Update ProductionOrderComponent entries for each BOM component
        existing_components = {
            comp.item_id: comp for comp in self.components.all() if comp.item
        }

        component_created_count = 0
        component_updated_count = 0

        for bom_line in bom_lines:
            if not bom_line.item:
                continue  # Skip lines without items

            # Calculate quantity needed: quantity_per * production_order.quantity
            # Round to 3 decimal places to match the field's decimal_places constraint
            required_quantity = (
                Decimal(str(bom_line.quantity_per)) * Decimal(str(self.quantity))
            ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

            # Unit cost (cost per unit): prefer BOM line, else item's ValueEntry cost
            unit_cost_val = (
                Decimal(str(bom_line.unit_cost))
                if bom_line.unit_cost
                else Decimal("0.00")
            )
            if unit_cost_val <= 0 and bom_line.item:
                try:
                    item_cost = getattr(bom_line.item, "unit_cost", 0)
                    unit_cost_val = (
                        Decimal(str(float(item_cost))) if item_cost else Decimal("0.00")
                    )
                except (AttributeError, TypeError, ValueError):
                    unit_cost_val = Decimal("0.00")

            unit_cost_val = unit_cost_val.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Check if component already exists for this item
            if bom_line.item_id in existing_components:
                # Update existing component
                component = existing_components[bom_line.item_id]

                # Preserve manually set fields
                preserve_location = component.location_code
                preserve_expected_quantity = component.expected_quantity

                # Update fields from BOM
                component.item_name = bom_line.item.item_name
                component.description = bom_line.description or bom_line.item.item_name
                component.quantity = required_quantity
                component.quantity_per = bom_line.quantity_per
                component.unit_of_measure_code = bom_line.unit_of_measure
                component.production_order_line = production_line
                component.unit_cost = unit_cost_val
                component.status = "released"  # Set to released on update production details

                # Restore preserved fields
                if preserve_location:
                    component.location_code = preserve_location
                if preserve_expected_quantity:
                    component.expected_quantity = preserve_expected_quantity
                else:
                    component.expected_quantity = required_quantity

                component.save()
                component_updated_count += 1
            else:
                # Create new component
                ProductionOrderComponent.objects.create(
                    production_order=self,
                    production_order_line=production_line,
                    item=bom_line.item,
                    item_name=bom_line.item.item_name,
                    description=bom_line.description or bom_line.item.item_name,
                    quantity=required_quantity,
                    expected_quantity=required_quantity,
                    quantity_per=bom_line.quantity_per,
                    unit_of_measure_code=bom_line.unit_of_measure,
                    unit_cost=unit_cost_val,
                    status="released",  # Set to released on update production details
                )
                component_created_count += 1

        # Remove components that are no longer in the BOM
        bom_item_ids = {bom_line.item_id for bom_line in bom_lines if bom_line.item}
        components_to_remove = [
            comp
            for comp in self.components.all()
            if comp.item and comp.item_id not in bom_item_ids
        ]
        component_removed_count = len(components_to_remove)
        for component in components_to_remove:
            component.delete()

        # Step 3: Create ItemJournal entries for consumption (components) and output (finished product)
        from items.models import ItemJournal, ItemJournalTemplate
        from items.enums import EntryType
        from setup.models import NoSeriesLines
        from django.contrib.auth import get_user_model

        User = get_user_model()
        journal_entries_created = 0

        # Get or create the "PROD. ORDE" template
        prod_template, _ = ItemJournalTemplate.objects.get_or_create(
            name="PROD. ORDE",
            defaults={
                "description": "Production Order Item Journal",
                "type": "production_order",
            },
        )

        # Get the no series for the template
        no_series = None
        if prod_template.no_series:
            no_series = prod_template.no_series
        else:
            # Try to get PRODORDE no series
            from setup.models import NoSeries

            try:
                prodorde_no_series = NoSeries.objects.get(code="PRODORDE")
                prod_template.no_series = prodorde_no_series
                prod_template.save()
                no_series = prodorde_no_series
            except NoSeries.DoesNotExist:
                pass

        # Helper function to generate document number from no series
        def generate_document_no_from_no_series(no_series_obj):
            """Generate document number from NoSeries.

            Fallback must be unique per call: ItemJournal.document_no is globally unique,
            and several journals are created in one refresh (multiple consumptions + output).
            A second-precision timestamp collides within the same second and aborts the rest.
            """
            if not no_series_obj:
                return f"PRODORDE-{uuid.uuid4().hex[:24].upper()}"

            no_series_line = NoSeriesLines.objects.filter(
                no_series=no_series_obj
            ).first()
            if not no_series_line:
                return f"PRODORDE-{uuid.uuid4().hex[:24].upper()}"

            if no_series_line.last_used_number:
                document_no = increment_item_number(
                    no_series_line.last_used_number, no_series_line.increment_by
                )
            else:
                document_no = no_series_line.start_number

            # Update the no series line
            no_series_line.last_used_number = document_no
            no_series_line.last_used_date = datetime.now().date()
            no_series_line.save()

            return document_no

        # Item journals use the same branch location as lines (resolved above).

        # Create consumption entries for components.
        # Step 0 already deleted all ItemJournals for this order, so always create one
        # journal per component row. Do not look up by item+entry_type+PO only: two BOM
        # lines can reference the same Item (or duplicate component rows), and the
        # second pass would match the journal created in the first pass and skip a row.
        for component in self.components.all():
            if not component.item:
                continue

            # Get unit of measure for the component
            unit_of_measure = None
            if component.unit_of_measure_code:
                unit_of_measure = component.item.itemunitofmeasure_set.filter(
                    unit_of_measure=component.unit_of_measure_code
                ).first()

            # Always use user's location for item journals
            location_to_use = user_location

            # Get unit cost: prefer component (from BOM), else item's ValueEntry cost
            component_cost = float(component.unit_cost) if component.unit_cost else 0.0
            if component_cost <= 0 and component.item:
                try:
                    item_cost = getattr(component.item, "unit_cost", 0)
                    component_cost = float(item_cost) if item_cost else 0.0
                except (AttributeError, TypeError, ValueError):
                    component_cost = 0.0

            document_no = generate_document_no_from_no_series(no_series)

            ItemJournal.objects.create(
                item=component.item,
                journal_template=prod_template,
                entry_type=EntryType.Consumption.name,
                document_no=document_no,
                description=f"Consumption for Production Order {self.no} - {component.item.item_name}",
                quantity=int(component.quantity),
                item_unit_of_measure=unit_of_measure,
                unit_cost=component_cost,
                location_code=location_to_use,
                date=datetime.now().date(),
                user=user,
                production_order=self,
                global_dimension_1=prod_line_g1,
                global_dimension_2=_dim_payload.get("global_dimension_2"),
                dimension_set=prod_line_dim_set,
            )
            journal_entries_created += 1

        # Create output entry for finished product (Positive Adjustment)
        if production_line.item:
            # Same as consumption: journals were cleared in Step 0; always create output.
            unit_of_measure = None
            if production_line.unit_of_measure_code:
                unit_of_measure = production_line.item.itemunitofmeasure_set.filter(
                    unit_of_measure=production_line.unit_of_measure_code
                ).first()

            location_to_use = user_location

            document_no = generate_document_no_from_no_series(no_series)

            ItemJournal.objects.create(
                item=production_line.item,
                journal_template=prod_template,
                entry_type=EntryType.Output.name,
                type="work_center",  # Set type to work_center for Output entries
                document_no=document_no,
                description=f"Output for Production Order {self.no} - {production_line.item.item_name}",
                quantity=int(production_line.quantity),
                item_unit_of_measure=unit_of_measure,
                unit_cost=(
                    float(production_line.unit_cost)
                    if production_line.unit_cost
                    else 0.0
                ),
                location_code=location_to_use,
                date=datetime.now().date(),
                user=user,
                production_order=self,
                global_dimension_1=prod_line_g1,
                global_dimension_2=_dim_payload.get("global_dimension_2"),
                dimension_set=prod_line_dim_set,
            )
            journal_entries_created += 1

        # Header branch for branch-scoped list API (lines may be absent on draft until refresh)
        self.global_dimension_1 = prod_line_g1
        save_fields = ["global_dimension_1", "updated_at"]
        if self.status != "released":
            self.status = "released"
            save_fields.append("status")
        self.save(update_fields=save_fields)

        return {
            "production_line_created": line_created,
            "production_line_updated": not line_created,
            "components_created": component_created_count,
            "components_updated": component_updated_count,
            "components_removed": component_removed_count,
            "total_bom_lines": len(bom_lines),
            "journal_entries_created": journal_entries_created,
        }


class ProductionOrderLine(BaseModel):
    """
    Production Order Line model.
    Represents individual lines/components within a production order.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("released", "Released"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Production Order",
        help_text="Parent production order",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Item No.",
        help_text="Item number for this production order line",
        related_name="production_order_lines",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Status",
        help_text="Status of this production order line",
    )

    description = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description of this production order line",
    )

    location_code = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Location Code",
        help_text="Location code for this production order line",
        related_name="production_order_lines",
    )

    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        verbose_name="Global Dimension 1",
        help_text="Global Dimension 1 value",
        related_name="production_order_lines_global_dimension_1",
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="production_order_lines",
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Quantity",
        help_text="Quantity to produce",
    )

    finished_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Finished Quantity",
        help_text="Quantity that has been finished",
    )

    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Start Date",
        help_text="Start date for production",
    )

    ending_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ending Date",
        help_text="Ending date for production",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Due Date",
        help_text="Due date for this production order line",
    )

    production_bom_no = models.ForeignKey(
        ProductionBOM,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Production BOM No.",
        help_text="Production BOM used for this line",
        related_name="production_order_lines",
    )

    unit_of_measure_code = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit of Measure Code",
        help_text="Unit of measure code",
        to_field="code",
        related_name="production_order_lines",
    )

    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Cost",
        help_text="Cost per unit",
    )

    class Meta:
        verbose_name = "Production Order Line"
        verbose_name_plural = "Production Order Lines"
        ordering = ["production_order", "id"]
        indexes = [
            models.Index(fields=["production_order"]),
            models.Index(fields=["status"]),
            models.Index(fields=["item"]),
            models.Index(fields=["location_code"]),
            models.Index(fields=["production_bom_no"]),
        ]

    def clean(self):
        """Validate the model fields"""
        super().clean()

        # Validate quantity
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than 0"})

        # Validate finished quantity doesn't exceed quantity
        if self.finished_quantity > self.quantity:
            raise ValidationError(
                {"finished_quantity": "Finished quantity cannot exceed total quantity"}
            )

        # Validate dates
        if self.start_date and self.ending_date:
            if self.ending_date < self.start_date:
                raise ValidationError(
                    {"ending_date": "Ending date cannot be before start date"}
                )

    def save(self, *args, **kwargs):
        """Override save to auto-fill fields and validate"""
        # Auto-fill description from production BOM if not provided
        if not self.description and self.production_bom_no:
            self.description = self.production_bom_no.name

        # Auto-fill unit of measure from production BOM if not provided
        if not self.unit_of_measure_code and self.production_bom_no:
            self.unit_of_measure_code = self.production_bom_no.unit_of_measure

        # Auto-calculate unit cost from production BOM if not set
        if self.unit_cost == 0 and self.production_bom_no:
            bom_cost = self.production_bom_no.calculate_total_cost()
            if bom_cost:
                self.unit_cost = Decimal(str(bom_cost)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):
        """Calculate remaining quantity"""
        return max(Decimal("0"), self.quantity - self.finished_quantity)

    @property
    def cost_amount(self):
        """Calculate total cost amount: Quantity × Unit Cost (cost per unit)."""
        qty = float(self.quantity) if self.quantity else 0.0
        cost_per_unit = float(self.unit_cost) if self.unit_cost else 0.0
        return round(qty * cost_per_unit, 2)

    def __str__(self):
        return (
            f"{self.production_order.no} - Line {self.id}: {self.description or 'N/A'}"
        )


class ProductionOrderComponent(BaseModel):
    """
    Production Order Component model.
    Represents components/raw materials needed for production from the BOM.
    Similar to Business Central's Prod. Order Component table.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("released", "Released"),
        ("finished", "Finished"),
    ]

    production_order = models.ForeignKey(
        ProductionOrder,
        on_delete=models.CASCADE,
        related_name="components",
        verbose_name="Production Order",
        help_text="Parent production order",
    )

    production_order_line = models.ForeignKey(
        ProductionOrderLine,
        on_delete=models.CASCADE,
        related_name="components",
        verbose_name="Production Order Line",
        help_text="Production order line this component belongs to",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="planned",
        verbose_name="Status",
        help_text="Status of this component",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Item No.",
        help_text="Component item number",
        related_name="production_order_components",
    )

    item_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Item Name",
        help_text="Item name (auto-filled from item)",
    )

    description = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description (auto-filled from item name)",
    )

    unit_of_measure_code = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit of Measure Code",
        help_text="Unit of measure code",
        to_field="code",
        related_name="production_order_components",
    )

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Quantity",
        help_text="Quantity required",
    )

    expected_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        verbose_name="Expected Quantity",
        help_text="Expected quantity to be consumed",
    )

    quantity_per = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        default=0,
        verbose_name="Quantity per",
        help_text="Quantity required per unit of finished product",
    )

    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Unit Cost",
        help_text="Cost per unit",
    )

    location_code = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Location Code",
        help_text="Location code for this component",
        related_name="production_order_components",
    )

    class Meta:
        verbose_name = "Production Order Component"
        verbose_name_plural = "Production Order Components"
        ordering = ["production_order", "id"]
        indexes = [
            models.Index(fields=["production_order"]),
            models.Index(fields=["production_order_line"]),
            models.Index(fields=["status"]),
            models.Index(fields=["item"]),
            models.Index(fields=["location_code"]),
        ]

    def clean(self):
        """Validate the model fields"""
        super().clean()

        # Validate quantity
        if self.quantity < 0:
            raise ValidationError({"quantity": "Quantity cannot be negative"})

        # Validate expected_quantity
        if self.expected_quantity < 0:
            raise ValidationError(
                {"expected_quantity": "Expected quantity cannot be negative"}
            )

    def save(self, *args, **kwargs):
        """Override save to auto-fill fields and validate"""
        # Auto-fill item_name and description from item if not provided
        if self.item:
            if not self.item_name:
                self.item_name = self.item.item_name
            if not self.description:
                self.description = self.item.item_name

            # Auto-fill unit of measure from item if not provided
            if not self.unit_of_measure_code and self.item.unit_of_measure:
                self.unit_of_measure_code = self.item.unit_of_measure

        # Set expected_quantity to quantity if not set
        if not self.expected_quantity:
            self.expected_quantity = self.quantity

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    @property
    def remaining_quantity(self):
        """Calculate remaining quantity"""
        return max(Decimal("0"), self.expected_quantity)

    @property
    def cost_amount(self):
        """Calculate total cost amount: Quantity × Unit Cost (cost per unit)."""
        qty = float(self.quantity) if self.quantity else 0.0
        cost_per_unit = float(self.unit_cost) if self.unit_cost else 0.0
        return round(qty * cost_per_unit, 2)

    def __str__(self):
        return (
            f"{self.production_order.no} - Component {self.id}: "
            f"{self.item_name or 'N/A'}"
        )


class CapacityUnitOfMeasure(BaseModel):
    """
    Capacity Unit of Measure model for managing capacity units in production.
    Defines the unit of measure for capacity calculations (e.g., Hours, Minutes, Days).
    Note: Company isolation handled by Django Tenants schema separation.
    """

    code = models.CharField(
        max_length=10,
        unique=True,
        primary_key=True,
        verbose_name="Code",
        help_text="Capacity unit of measure code (e.g., HOURS, MINUTES)",
    )
    description = models.CharField(
        max_length=100,
        verbose_name="Description",
        help_text="Description of the capacity unit of measure",
    )
    type = models.CharField(
        max_length=20,
        choices=CapacityUnitOfMeasureType.choices(),
        verbose_name="Type",
        help_text="Type of capacity unit (Milliseconds, Minutes, Hours, Days, Seconds, 100/Hour)",
    )

    class Meta:
        verbose_name = "Capacity Unit of Measure"
        verbose_name_plural = "Capacity Units of Measure"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"


class WorkCenter(BaseModel):
    """
    Work Center model for managing work centers in production.
    A work center is a group of machines or people that perform similar operations.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        verbose_name="Code",
        help_text="Auto-generated work center code (e.g., WORKCTR-000001)",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Name",
        help_text="Name of the work center",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Additional details about the work center",
    )
    general_prod_posting_group = models.ForeignKey(
        "postings.GeneralProductPostingGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="General Prod. Posting Group",
        help_text="General product posting group for this work center",
        related_name="work_centers",
        to_field="code",
    )
    unit_cost_calculation = models.CharField(
        max_length=10,
        choices=UnitCostCalculation.choices(),
        null=True,
        blank=True,
        verbose_name="Unit Cost Calculation",
        help_text="Unit cost calculation method: Units or Time",
    )
    unit_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        verbose_name="Unit Cost",
        help_text="Unit cost for this work center",
    )
    direct_unit_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        verbose_name="Direct Unit Cost",
        help_text="Direct unit cost for this work center",
    )
    unit_of_measure_code = models.ForeignKey(
        CapacityUnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Capacity Unit of Measure Code",
        help_text="Unit of measure code for capacity calculations",
        related_name="work_centers",
        to_field="code",
    )
    capacity = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        default=1,
        verbose_name="Capacity",
        help_text="Capacity of the work center",
    )
    shop_calendar_code = models.ForeignKey(
        "ShopCalendar",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Shop Calendar Code",
        help_text="Shop calendar for scheduling this work center",
        related_name="work_centers",
        to_field="code",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Whether this work center is currently active",
    )

    class Meta:
        verbose_name = "Work Center"
        verbose_name_plural = "Work Centers"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs):
        """Override save to auto-generate code using number series"""
        from setup.models import ManufacturingSetup, NoSeriesLines

        # Auto-generate code if not provided
        if not self.code:
            try:
                manufacturing_setup = ManufacturingSetup.objects.all().first()
                if manufacturing_setup and manufacturing_setup.work_center_no_series:
                    work_center_no_series = NoSeriesLines.objects.filter(
                        no_series=manufacturing_setup.work_center_no_series
                    ).first()

                    if work_center_no_series:
                        increment_by = work_center_no_series.increment_by
                        if work_center_no_series.last_used_number:
                            # Generate new number using existing logic
                            self.code = increment_item_number(
                                work_center_no_series.last_used_number, increment_by
                            )
                        else:
                            # Use start number if no previous number exists
                            self.code = work_center_no_series.start_number

                        # Update the NoSeriesLines object
                        work_center_no_series.last_used_number = self.code
                        work_center_no_series.last_used_date = datetime.now().date()
                        work_center_no_series.save()
                    else:
                        # Fallback if no series lines configured
                        import random
                        import string

                        self.code = (
                            f"WORKCTR-TMP-{''.join(random.choices(string.digits, k=4))}"
                        )
                else:
                    # Fallback if no manufacturing setup configured
                    import random
                    import string

                    self.code = (
                        f"WORKCTR-TMP-{''.join(random.choices(string.digits, k=4))}"
                    )
            except Exception as e:
                # Fallback on any error
                import random
                import string

                self.code = f"WORKCTR-TMP-{''.join(random.choices(string.digits, k=4))}"

        # Validate capacity is not negative
        if self.capacity and self.capacity < 0:
            raise ValidationError({"capacity": "Capacity cannot be negative"})

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.code} - {self.name}"
            if self.code
            else f"New Work Center - {self.name}"
        )


class MachineCenter(BaseModel):
    """
    Machine Center model for managing machine centers in production.
    A machine center is a specific machine or equipment used in production.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Code",
        help_text="Machine center code (e.g., MC-001)",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Name",
        help_text="Name of the machine center",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Additional details about the machine center",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Whether this machine center is currently active",
    )

    class Meta:
        verbose_name = "Machine Center"
        verbose_name_plural = "Machine Centers"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class CapacityLedgerEntry(BaseModel):
    """
    Capacity Ledger Entry model for tracking production capacity usage.
    Records how production capacity is used over time, answering questions like:
    - Which work center or machine was used?
    - When was it used?
    - How much time was spent (setup, run, stop)?
    - What output was produced?
    - Which production order and item caused this capacity consumption?
    Note: Company isolation handled by Django Tenants schema separation.
    """

    TYPE_CHOICES = [
        ("work_center", "Work Center"),
        ("machine_center", "Machine Center"),
        ("resource", "Resource"),
    ]

    ORDER_TYPE_CHOICES = [
        ("production", "Production"),
    ]

    # Identification
    no = models.CharField(
        max_length=20,
        verbose_name="No.",
        help_text="Code reference to Work Center, Machine Center, or Resource based on Type",
    )
    posting_date = models.DateField(
        verbose_name="Posting Date",
        help_text="Date when the capacity was used",
    )
    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Type",
        help_text="Type of capacity: Work Center, Machine Center, or Resource",
    )
    document_no = models.CharField(
        max_length=255,
        verbose_name="Document No.",
        help_text="Document number for this capacity entry",
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description of the capacity usage",
    )
    operation_no = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Operation No.",
        help_text="Operation number",
    )

    # Capacity references (one will be set based on type)
    work_center = models.ForeignKey(
        "WorkCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Work Center",
        help_text="Work center used (if type is Work Center)",
        related_name="capacity_ledger_entries",
    )
    machine_center = models.ForeignKey(
        "MachineCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Machine Center",
        help_text="Machine center used (if type is Machine Center)",
        related_name="capacity_ledger_entries",
    )
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Resource",
        help_text="Resource used (if type is Resource)",
        related_name="capacity_ledger_entries",
    )

    # Time tracking
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Quantity",
        help_text="Quantity of capacity used",
    )
    setup_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Setup Time",
        help_text="Setup time in hours",
    )
    run_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Run Time",
        help_text="Run time in hours",
    )
    stop_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Stop Time",
        help_text="Stop time in hours",
    )
    output_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Output Quantity",
        help_text="Quantity of output produced",
    )
    cap_unit_of_measure_code = models.ForeignKey(
        "items.UnitOfMeasure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Cap. Unit of Measure Code",
        help_text="Unit of measure for capacity",
        to_field="code",
    )

    # Production order linkage
    item_no = models.ForeignKey(
        "items.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Item No.",
        help_text="Item that caused this capacity consumption",
        related_name="capacity_ledger_entries",
    )
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        default="production",
        verbose_name="Order Type",
        help_text="Type of order (currently only Production)",
    )
    order_no = models.ForeignKey(
        "ProductionOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Order No.",
        help_text="Production order that caused this capacity consumption",
        related_name="capacity_ledger_entries",
    )
    order_line_no = models.ForeignKey(
        "ProductionOrderLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Order Line No.",
        help_text="Production order line that caused this capacity consumption",
        related_name="capacity_ledger_entries",
    )

    class Meta:
        verbose_name = "Capacity Ledger Entry"
        verbose_name_plural = "Capacity Ledger Entries"
        ordering = ["-posting_date", "-created_at"]
        indexes = [
            models.Index(fields=["posting_date"]),
            models.Index(fields=["type"]),
            models.Index(fields=["order_no"]),
            models.Index(fields=["order_line_no"]),
            models.Index(fields=["item_no"]),
        ]

    def clean(self):
        """Validate that the correct reference is set based on type"""
        super().clean()

        if self.type == "work_center":
            if not self.work_center:
                raise ValidationError(
                    {"work_center": "Work Center must be set when Type is Work Center"}
                )
            if self.machine_center or self.resource:
                raise ValidationError(
                    "Only Work Center should be set when Type is Work Center"
                )
            # Set no from work_center code
            if self.work_center:
                self.no = self.work_center.code

        elif self.type == "machine_center":
            if not self.machine_center:
                raise ValidationError(
                    {
                        "machine_center": "Machine Center must be set when Type is Machine Center"
                    }
                )
            if self.work_center or self.resource:
                raise ValidationError(
                    "Only Machine Center should be set when Type is Machine Center"
                )
            # Set no from machine_center code
            if self.machine_center:
                self.no = self.machine_center.code

        elif self.type == "resource":
            if not self.resource:
                raise ValidationError(
                    {"resource": "Resource must be set when Type is Resource"}
                )
            if self.work_center or self.machine_center:
                raise ValidationError(
                    "Only Resource should be set when Type is Resource"
                )
            # Set no from resource code
            if self.resource:
                self.no = self.resource.code

    def save(self, *args, **kwargs):
        """Override save to auto-set no field and validate"""
        # Auto-set no field based on type
        if self.type == "work_center" and self.work_center:
            self.no = self.work_center.code
        elif self.type == "machine_center" and self.machine_center:
            self.no = self.machine_center.code
        elif self.type == "resource" and self.resource:
            self.no = self.resource.code

        # Run validation
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.document_no} - {self.no} ({self.type})"


class ShopCalendar(BaseModel):
    """
    Shop Calendar model for managing shop calendars in production.
    Defines working days and holidays for production scheduling.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    code = models.CharField(
        max_length=10,
        unique=True,
        primary_key=True,
        verbose_name="Code",
        help_text="Shop calendar code (e.g., STANDARD, SHIFT1)",
    )
    description = models.CharField(
        max_length=100,
        verbose_name="Description",
        help_text="Description of the shop calendar",
    )

    class Meta:
        verbose_name = "Shop Calendar"
        verbose_name_plural = "Shop Calendars"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"

    def delete(self, *args, **kwargs):
        """Override delete to cascade delete related working days and holidays"""
        # Delete related working days
        ShopCalendarWorkingDays.objects.filter(shop_calendar=self).delete()
        # Delete related holidays
        ShopCalendarHoliday.objects.filter(shop_calendar=self).delete()
        super().delete(*args, **kwargs)


class ShopCalendarWorkingDays(BaseModel):
    """
    Shop Calendar Working Days model for managing working days for each shop calendar.
    Defines which days of the week are working days and their time ranges.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    shop_calendar = models.ForeignKey(
        ShopCalendar,
        on_delete=models.CASCADE,
        verbose_name="Shop Calendar",
        help_text="Shop calendar this working day belongs to",
        related_name="working_days",
        to_field="code",
    )
    day = models.CharField(
        max_length=10,
        choices=DayOfWeek.choices(),
        verbose_name="Day",
        help_text="Day of the week",
    )
    starting_time = models.TimeField(
        verbose_name="Starting Time",
        help_text="Starting time for this working day (e.g., 08:00:00)",
    )
    ending_time = models.TimeField(
        verbose_name="Ending Time",
        help_text="Ending time for this working day (e.g., 16:00:00)",
    )
    work_shift_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name="Work Shift Code",
        help_text="Work shift code (e.g., 1, 2, 3)",
    )

    class Meta:
        verbose_name = "Shop Calendar Working Day"
        verbose_name_plural = "Shop Calendar Working Days"
        ordering = ["shop_calendar", "day", "starting_time"]
        unique_together = [["shop_calendar", "day", "starting_time", "work_shift_code"]]
        indexes = [
            models.Index(fields=["shop_calendar", "day"]),
            models.Index(fields=["shop_calendar", "starting_time"]),
        ]

    def clean(self):
        """Validate that ending time is after starting time"""
        if self.starting_time and self.ending_time:
            if self.ending_time <= self.starting_time:
                raise ValidationError(
                    {"ending_time": "Ending time must be after starting time"}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_calendar.code} - {self.day} ({self.starting_time} - {self.ending_time})"


class ShopCalendarHoliday(BaseModel):
    """
    Shop Calendar Holiday model for managing holidays for each shop calendar.
    Defines dates when the shop is closed.
    Note: Company isolation handled by Django Tenants schema separation.
    """

    shop_calendar = models.ForeignKey(
        ShopCalendar,
        on_delete=models.CASCADE,
        verbose_name="Shop Calendar",
        help_text="Shop calendar this holiday belongs to",
        related_name="holidays",
        to_field="code",
    )
    starting_date_time = models.DateTimeField(
        verbose_name="Starting Date-Time",
        help_text="Starting date and time for this holiday",
    )
    ending_time = models.TimeField(
        verbose_name="Ending Time",
        help_text="Ending time for this holiday",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Description",
        help_text="Description of the holiday",
    )

    class Meta:
        verbose_name = "Shop Calendar Holiday"
        verbose_name_plural = "Shop Calendar Holidays"
        ordering = ["shop_calendar", "starting_date_time"]
        indexes = [
            models.Index(fields=["shop_calendar", "starting_date_time"]),
        ]

    def clean(self):
        """Validate that ending time is after starting time on the same day"""
        if self.starting_date_time and self.ending_time:
            starting_time = self.starting_date_time.time()
            if self.ending_time <= starting_time:
                raise ValidationError(
                    {"ending_time": "Ending time must be after starting time"}
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_calendar.code} - {self.starting_date_time.date()} ({self.description or 'Holiday'})"
