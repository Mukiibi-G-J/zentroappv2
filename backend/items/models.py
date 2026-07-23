from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from mptt.models import MPTTModel, TreeForeignKey
from django.apps import apps
from datetime import datetime
from django.core.files.storage import default_storage
from django.db.models.signals import post_delete
from django.dispatch import receiver
from decimal import Decimal


from items.enums import (
    InventoryType,
    CostingMethod,
    EntryType,
    DocumentType,
    ReplenishmentSystem,
    ManufacturingPolicy,
    FlushingMethod,
)
from common.enums import Status
from setup.models import InventorySetup, NoSeriesLines, JournalSetup
from authentication.models import CustomUser as User
from postings.models import GeneralProductPostingGroup, InventoryPostingGroup


from helpers.helpers import increment_item_number, generate_document_number


from utils.utils import BaseModel
from helpers.helpers import generate_random_code


user = get_user_model()


def _physical_inventory_entry_type_codes():
    """EntryType name or value strings that imply location-based inventory."""
    return frozenset(
        {
            EntryType.Purchase.name,
            EntryType.Purchase.value,
            EntryType.Sales.name,
            EntryType.Sales.value,
            EntryType.DirectCost.name,
            EntryType.DirectCost.value,
            EntryType.Consumption.name,
            EntryType.Consumption.value,
            EntryType.Output.name,
            EntryType.Output.value,
            EntryType.PositiveAdjustment.name,
            EntryType.PositiveAdjustment.value,
            EntryType.NegativeAdjustment.name,
            EntryType.NegativeAdjustment.value,
        }
    )


def _item_entry_type_requires_location_and_dimensions(entry_type):
    if not entry_type:
        return False
    return entry_type in _physical_inventory_entry_type_codes()


class ItemAttributeValue(BaseModel):
    value = models.CharField(max_length=255, unique=True)
    blocked = models.BooleanField(default=False)

    class Meta:
        db_table = "items_itemattributevalue"
        ordering = ["value"]
        verbose_name = "Item Attribute Value"
        verbose_name_plural = "Item Attribute Values"

    def __str__(self):
        return self.value


class ItemAttribute(BaseModel):
    class AttributeType(models.TextChoices):
        OPTION = "option", "Option"
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        DATE = "date", "Date"

    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(
        max_length=20,
        choices=AttributeType.choices,
        default=AttributeType.OPTION,
    )
    blocked = models.BooleanField(default=False)
    values = models.ManyToManyField(
        ItemAttributeValue, related_name="attributes", blank=True
    )

    class Meta:
        db_table = "items_itemattribute"
        ordering = ["name"]
        verbose_name = "Item Attribute"
        verbose_name_plural = "Item Attributes"

    def __str__(self):
        return self.name


class ItemAttributeEntry(BaseModel):
    item = models.ForeignKey(
        "Item",
        on_delete=models.CASCADE,
        related_name="attribute_entries",
    )
    attribute = models.ForeignKey(
        ItemAttribute,
        on_delete=models.CASCADE,
        related_name="item_entries",
    )
    selected_values = models.ManyToManyField(
        ItemAttributeValue,
        related_name="attribute_entries",
        blank=True,
    )
    value_text = models.CharField(max_length=255, null=True, blank=True)
    value_integer = models.IntegerField(null=True, blank=True)
    value_decimal = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    value_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "items_itemattributeentry"
        ordering = ["attribute__name"]
        unique_together = ("item", "attribute")
        verbose_name = "Item Attribute Entry"
        verbose_name_plural = "Item Attribute Entries"

    def __str__(self):
        return f"{self.item.item_name} - {self.attribute.name}"

    @property
    def display_value(self):
        attr_type = self.attribute.type if self.attribute_id else None
        if attr_type == ItemAttribute.AttributeType.OPTION:
            return ", ".join(self.selected_values.values_list("value", flat=True))
        if attr_type == ItemAttribute.AttributeType.TEXT:
            return self.value_text or ""
        if attr_type == ItemAttribute.AttributeType.INTEGER:
            return str(self.value_integer or "")
        if attr_type == ItemAttribute.AttributeType.DECIMAL:
            return str(self.value_decimal or "")
        if attr_type == ItemAttribute.AttributeType.DATE:
            return self.value_date.strftime("%Y-%m-%d") if self.value_date else ""
        return ""

    def clean(self):
        if not self.attribute_id:
            return

        attr_type = self.attribute.type
        allowed_field = {
            ItemAttribute.AttributeType.TEXT: "value_text",
            ItemAttribute.AttributeType.INTEGER: "value_integer",
            ItemAttribute.AttributeType.DECIMAL: "value_decimal",
            ItemAttribute.AttributeType.DATE: "value_date",
        }.get(attr_type)

        if attr_type == ItemAttribute.AttributeType.OPTION:
            # Ensure non-option fields are cleared
            self.value_text = None
            self.value_integer = None
            self.value_decimal = None
            self.value_date = None
            return

        # Non option types should not retain selected values
        self._clear_selected_values = True

        # Reset irrelevant fields
        for field in ["value_text", "value_integer", "value_decimal", "value_date"]:
            if field != allowed_field:
                setattr(self, field, None)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if getattr(self, "_clear_selected_values", False):
            self.selected_values.clear()
            delattr(self, "_clear_selected_values")


# ------------------------------- new code implementation ------------------------------------------
class Item(BaseModel):
    no = models.CharField(
        max_length=225,
        verbose_name="No.",
        editable=False,
        primary_key=True,
        db_index=True,
    )
    item_name = models.CharField(max_length=225, verbose_name="Item Name", unique=True)
    bar_code_no = models.CharField(
        max_length=225, verbose_name="Bar Code No", null=True, blank=True
    )
    type = models.CharField(
        verbose_name="Type",
        max_length=20,
        choices=[(tag.value, tag.value) for tag in InventoryType],
        default=InventoryType.Inventory.value,
    )
    blocked = models.BooleanField(verbose_name="Blocked", default=False)

    shelf_no = models.CharField(
        max_length=225, verbose_name="Shelf No", null=True, blank=True
    )

    minimum_stock = models.PositiveIntegerField(
        verbose_name="Minimum Stock",
        null=True,
        blank=True,
        help_text="Reorder threshold; item is low stock when on-hand is at or below this value.",
    )

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Unit Price",
        default=Decimal("0.00"),
    )

    manual_unit_cost = models.DecimalField(
        verbose_name="Manual Unit Cost",
        null=True,
        blank=True,
        help_text="Manual unit cost for Service and Non-Inventory items",
        max_digits=15,
        decimal_places=2,
    )

    costing_method = models.CharField(
        verbose_name="Costing Method",
        max_length=20,
        choices=[(tag.name, tag.value) for tag in CostingMethod],
        default=CostingMethod.FIFO.value,
    )
    description = models.TextField(verbose_name="Description", null=True, blank=True)

    unit_of_measure = models.ForeignKey(
        "UnitOfMeasure",
        verbose_name="Unit of Measure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="code",
    )
    purchase_unit_of_measure = models.ForeignKey(
        "ItemUnitOfMeasure",
        verbose_name="Purchase Unit of Measure",
        related_name="purchase_unit_of_measure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sales_unit_of_measure = models.ForeignKey(
        "ItemUnitOfMeasure",
        verbose_name="Sales Unit of Measure",
        related_name="sales_unit_of_measure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    item_category = models.ForeignKey(
        "ItemCategory",
        verbose_name="Item Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        to_field="code",
    )

    general_product_posting_group = models.ForeignKey(
        "postings.GeneralProductPostingGroup",
        on_delete=models.SET_NULL,
        verbose_name="General Product Posting Group",
        null=True,
        blank=True,
        to_field="code",
    )
    vat_product_posting_group = models.ForeignKey(
        "postings.VATProductPostingGroup",
        on_delete=models.SET_NULL,
        verbose_name="VAT Prod. Posting Group",
        null=True,
        blank=True,
        to_field="code",
        help_text=_("VAT posting group for this item (when VAT is enabled)."),
    )

    inventory_posting_group = models.ForeignKey(
        "postings.InventoryPostingGroup",
        on_delete=models.SET_NULL,
        verbose_name="Inventory Posting Group",
        null=True,
        blank=True,
        to_field="code",
    )

    tracking_code = models.ForeignKey(
        "ItemTrackingCodes",
        related_name="items_tracking_code",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Production BOM relationship
    production_bom = models.OneToOneField(
        "production.ProductionBOM",
        on_delete=models.CASCADE,
        related_name="item",
        verbose_name="Production BOM",
        null=True,
        blank=True,
        help_text="Production BOM for this item (Service or Non-Inventory items only)",
    )

    # Manufacturing and Replenishment fields
    replenishment_system = models.CharField(
        max_length=20,
        choices=ReplenishmentSystem.choices(),
        null=True,
        blank=True,
        verbose_name="Replenishment System",
        help_text="Replenishment system for this item",
    )
    manufacturing_policy = models.CharField(
        max_length=20,
        choices=ManufacturingPolicy.choices(),
        null=True,
        blank=True,
        verbose_name="Manufacturing Policy",
        help_text="Manufacturing policy: Make-to-Stock or Make-to-Order",
    )
    flushing_method = models.CharField(
        max_length=20,
        choices=FlushingMethod.choices(),
        null=True,
        blank=True,
        verbose_name="Flushing Method",
        help_text="Flushing method for production orders",
    )

    def __str__(self):
        return self.item_name

    @property
    def inventory(self):
        # Sum the quantity of all related ItemLedgerEntries for this item
        total_quantity = (
            ItemLedgerEntries.objects.filter(item=self).aggregate(
                total=Sum("remaining_quantity")
            )["total"]
            or 0
        )
        return total_quantity

    @property
    def profit_percentage(self):
        # get the cost price of the last entry in the item ledger
        unit_cost_entry = (
            ValueEntry.objects.filter(item=self).order_by("-created_at").first()
        )
        if unit_cost_entry and unit_cost_entry.cost_per_unit and self.unit_price > 0:
            cost_per_unit = Decimal(str(unit_cost_entry.cost_per_unit))
            profit = self.unit_price - cost_per_unit
            profit_percentage = (profit / self.unit_price) * 100
            return round(profit_percentage, 0)
        return 0

    @property
    def markup_percentage(self):
        unit_cost_entry = (
            ValueEntry.objects.filter(item=self).order_by("-created_at").first()
        )
        if (
            unit_cost_entry
            and unit_cost_entry.cost_per_unit
            and unit_cost_entry.cost_per_unit > 0
        ):
            cost_per_unit = Decimal(str(unit_cost_entry.cost_per_unit))
            markup = self.unit_price - cost_per_unit
            markup_percentage = (markup / cost_per_unit) * 100
            return round(markup_percentage, 0)
        return 0

    @property
    def unit_cost(self):
        # For Service and Non-Inventory items, use manual cost
        if self.type in ["Service", "Non-Inventory"]:
            return self.manual_unit_cost if self.manual_unit_cost else Decimal("0.00")

        # For Inventory items, calculate from ValueEntry
        unit_cost = (
            ValueEntry.objects.filter(item=self)
            .order_by("-created_at")
            .first()
            .cost_per_unit
            if ValueEntry.objects.filter(item=self).exists()
            else 0
        )
        if not unit_cost:
            return Decimal("0.00")
        return Decimal(str(unit_cost))

    @property
    def requires_tracking_line(self):
        if not self.tracking_code:
            return False

        tracking = self.tracking_code
        return {
            "serial_no": tracking.require_serial_no,
            "lot_no": tracking.require_lot_no,
            "expiry_date": tracking.require_expiry_date,
        }

    @property
    def image(self):
        default_image = {"url": "images/default.png", "alt_text": self.item_name}
        item_image = ItemImages.objects.filter(item=self).first()
        if item_image:
            return {
                "url": item_image.url,
                "alt_text": item_image.alt_text or self.item_name,
            }
        return default_image

    @property
    def get_image(self):
        """Get the first associated image or return default"""
        item_image = self.itemimages_set.first()  # Get the first associated image
        if item_image:
            return {
                "url": item_image.url.url,
                "alt_text": item_image.alt_text or self.item_name,
            }
        return {
            "url": "/media/images/default.png",  # Adjust this path to your default image
            "alt_text": self.item_name,
        }

    @property
    def get_all_images(self):
        return ItemImages.objects.filter(item=self)

    @property
    def get_available_uoms(self):
        """
        Returns a list of available Units of Measure for this item
        """
        uom_relations = self.itemunitofmeasure_set.all()

        return [
            {
                # "id": uom_rel.unit_of_measure.id,
                "code": uom_rel.unit_of_measure.code,
                "description": uom_rel.unit_of_measure.description,
                "default": uom_rel.default,
                "quantity_per_unit": uom_rel.quantity_per_unit,
                # "conversion_factor": uom_rel.conversion_factor,
                # "is_base": uom_rel.is_base
            }
            for uom_rel in uom_relations
        ]

    def clean(self):
        # if self.costing_method == CostingMethod.FIFO.value:
        #     if self.type != InventoryType.Inventory.value:
        #         raise ValidationError(
        #             "FIFO costing method is only applicable to Inventory type items"
        #         )
        # if self.type == InventoryType.Inventory.value:
        #     if self.costing_method != CostingMethod.FIFO.value:
        #         raise ValidationError(
        #             "Inventory type items can only use FIFO costing method"
        #         )

        if not InventorySetup.objects.all().first():
            raise ValidationError(
                " Inventory setup is not set",
            )

        # Validate Replenishment System
        if self.replenishment_system:
            if self.replenishment_system == ReplenishmentSystem.Purchase.value:
                # Purchase requires Assembly Policy = "Assemble-to-Stock"
                # Note: Assembly Policy field not yet implemented, skipping this check
                pass
            elif self.replenishment_system == ReplenishmentSystem.ProdOrder.value:
                # Prod. Order requires Assembly Policy = "Assemble-to-Stock" AND Type = Inventory
                # Note: Assembly Policy field not yet implemented, skipping that check
                if self.type != InventoryType.Inventory.value:
                    raise ValidationError(
                        {
                            "replenishment_system": "Prod. Order replenishment system requires Type to be Inventory"
                        }
                    )
            elif self.replenishment_system == ReplenishmentSystem.Transfer.value:
                # Transfer validation - can be extended later
                pass
            elif self.replenishment_system == ReplenishmentSystem.Assembly.value:
                # Assembly requires Type = Inventory
                if self.type != InventoryType.Inventory.value:
                    raise ValidationError(
                        {
                            "replenishment_system": "Assembly replenishment system requires Type to be Inventory"
                        }
                    )

    def save(self, *args, **kwargs):
        """
        Save method for Item model that handles both new item creation and updates.

        For new items (no primary key):
        - Generates barcode automatically
        - Generates item number using no-series if not provided
        - Assigns default posting groups, unit of measure, etc.

        For existing items (updates):
        - Assigns default values for any missing fields
        - Ensures unit of measure relationships are properly set
        - Maintains existing item number and barcode
        """
        self.full_clean()

        # Check if this is a new item (no primary key) or if we need to generate item number
        is_new_item = not self.pk

        if is_new_item:  # Only for new items
            with transaction.atomic():
                # Existing barcode generation
                self.bar_code_no = generate_random_code(13)
                while Item.objects.filter(bar_code_no=self.bar_code_no).exists():
                    self.bar_code_no = generate_random_code(13)

                # Only generate item number if one is not already provided
                if not self.no:
                    inventory_setup = InventorySetup.objects.all().first()
                    if inventory_setup:
                        # generate_number = generate_document_number(InventorySetup,'item_no_series','item_no_series',)
                        # print(generate_number)
                        item_no_series = NoSeriesLines.objects.filter(
                            no_series=InventorySetup.objects.all()
                            .first()
                            .item_no_series
                        ).first()
                        if item_no_series:
                            increment_by = item_no_series.increment_by
                            if item_no_series.last_used_number:
                                # split if were the first number is start number ie wew00001, IJ_t000001
                                self.no = increment_item_number(
                                    item_no_series.last_used_number, increment_by
                                )
                                item_no_series.last_used_number = self.no
                                item_no_series.last_used_date = datetime.now()
                                item_no_series.save()
                                print(f"Generated item number: {self.no}")
                            else:
                                self.no = item_no_series.start_number
                                item_no_series.last_used_number = self.no
                                item_no_series.last_used_date = datetime.now()
                                item_no_series.save()
                                print(f"Generated item number from start: {self.no}")
                        else:
                            # Fallback if no series is not found
                            print("Warning: No item number series found, using default")
                            self.no = f"ITM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    else:
                        # Fallback if inventory setup is not found
                        print("Warning: No inventory setup found, using default")
                        self.no = f"ITM-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    print(f"Using provided item number: {self.no}")

        # Handle default field assignments for both new items and updates
        with transaction.atomic():
            # Check if type has changed (for existing items)
            type_changed = False
            if self.pk:
                try:
                    old_item = Item.objects.get(pk=self.pk)
                    if old_item.type != self.type:
                        type_changed = True
                except Item.DoesNotExist:
                    pass

            # Assign general product posting group based on item type
            # Update posting group if: not set OR type has changed
            if not self.general_product_posting_group or type_changed:
                # If item is Service type, assign SERVICE posting group
                if self.type == InventoryType.Service.value:
                    service_gen_prod = GeneralProductPostingGroup.objects.filter(
                        code="SERVICE"
                    ).first()
                    if service_gen_prod:
                        self.general_product_posting_group = service_gen_prod
                else:
                    # For Inventory and Non-Inventory, use default (RETAIL)
                    default_gen_prod = GeneralProductPostingGroup.objects.filter(
                        default=True
                    ).first()
                    if default_gen_prod:
                        self.general_product_posting_group = default_gen_prod

            # Only set inventory_posting_group for Inventory type items
            if (
                self.type == InventoryType.Inventory.value
                and not self.inventory_posting_group
            ):
                try:
                    # If not found, use default
                    default_inv = InventoryPostingGroup.objects.filter(
                        default=True
                    ).first()
                    if default_inv:
                        self.inventory_posting_group = default_inv

                except Exception:
                    # Fallback to default if any error occurs
                    default_inv = InventoryPostingGroup.objects.filter(
                        default=True
                    ).first()
                    if default_inv:
                        self.inventory_posting_group = default_inv
            elif self.type in [
                InventoryType.Service.value,
                InventoryType.NonInventory.value,
            ]:
                # Clear inventory_posting_group for Service and Non-Inventory items
                self.inventory_posting_group = None

            if not self.type:
                self.type = InventoryType.Inventory.value

            # Handle unit_of_measure - convert string codes to instances
            if self.unit_of_measure:
                # If it's a string (code), convert to instance
                if isinstance(self.unit_of_measure, str):
                    self.unit_of_measure, _ = UnitOfMeasure.objects.get_or_create(
                        code=self.unit_of_measure
                    )
            else:
                # Default to PCS if not set
                self.unit_of_measure = UnitOfMeasure.objects.get_or_create(code="PCS")[
                    0
                ]

            if not self.unit_price:
                self.unit_price = 0

        # Save the item first to ensure it exists in the database
        # if item has entries you can't change lot no

        if ItemLedgerEntries.objects.filter(item=self).exists():
            # Check if this is an update (not a new item)
            if self.pk:
                try:
                    # Get the original item from database
                    original_item = Item.objects.get(pk=self.pk)
                    # Check if tracking_code has changed
                    if original_item.tracking_code != self.tracking_code:
                        raise ValidationError(
                            "Item has entries, you can't change tracking code"
                        )
                except Item.DoesNotExist:
                    # This is a new item, no validation needed
                    pass

        super().save(**kwargs)

        # Handle unit of measure relationships after the item is saved
        with transaction.atomic():
            # Use the unit_of_measure (already converted to instance if needed)
            # At this point, self.unit_of_measure is guaranteed to be a UnitOfMeasure instance
            base_uom = self.unit_of_measure

            if not self.sales_unit_of_measure:
                sales_uom, created = ItemUnitOfMeasure.objects.get_or_create(
                    item=self,
                    unit_of_measure=base_uom,
                    defaults={"quantity_per_unit": 1, "default": True},
                )
                # If it was just created or if we need to set it as default
                if created or not sales_uom.default:
                    sales_uom.default = True
                    # Ensure quantity_per_unit is 1 for default ItemUnitOfMeasure
                    sales_uom.quantity_per_unit = 1
                    sales_uom.save()

                self.sales_unit_of_measure = sales_uom
                # Save again to update the sales_unit_of_measure field
                super().save(update_fields=["sales_unit_of_measure"])

            if not self.purchase_unit_of_measure:
                purchase_uom, created = ItemUnitOfMeasure.objects.get_or_create(
                    item=self,
                    unit_of_measure=base_uom,
                    defaults={"quantity_per_unit": 1, "default": True},
                )
                # If it was just created or if we need to set it as default
                if created or not purchase_uom.default:
                    purchase_uom.default = True
                    # Ensure quantity_per_unit is 1 for default ItemUnitOfMeasure
                    purchase_uom.quantity_per_unit = 1
                    purchase_uom.save()

                self.purchase_unit_of_measure = purchase_uom
                # Save again to update the purchase_unit_of_measure field
                super().save(update_fields=["purchase_unit_of_measure"])

            # Final safeguard: Ensure item always has at least one default ItemUnitOfMeasure
            default_uoms = ItemUnitOfMeasure.objects.filter(item=self, default=True)
            if not default_uoms.exists():
                # No default exists, create one using the base unit of measure
                default_uom, _ = ItemUnitOfMeasure.objects.get_or_create(
                    item=self,
                    unit_of_measure=base_uom,
                    defaults={"quantity_per_unit": 1, "default": True},
                )
                if not default_uom.default:
                    default_uom.default = True
                    default_uom.quantity_per_unit = 1
                    default_uom.save()

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=["item_name", "no"],
                name="unique_item_name",
                condition=models.Q(type=InventoryType.Inventory.value),
            )
        ]
        # Add if not already present
        db_table = "items"  # Specify your table name
        verbose_name = "Item"
        verbose_name_plural = "Items"
        ordering = ["item_name"]  # Add default ordering to prevent pagination warnings
        indexes = [
            models.Index(fields=["updated_at", "no"], name="items_item_upd_no_idx"),
            models.Index(fields=["bar_code_no"], name="items_item_barcode_idx"),
        ]


class ItemUnitOfMeasure(BaseModel):

    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    unit_of_measure = models.ForeignKey("UnitOfMeasure", on_delete=models.CASCADE)
    quantity_per_unit = models.PositiveIntegerField(
        verbose_name="Quantity per Unit of Measure"
    )
    default = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Price",
        help_text="Price for this unit of measure. If blank, calculated from item.unit_price * quantity_per_unit",
    )

    def clean(self):
        # Enforce that default ItemUnitOfMeasure must have quantity_per_unit = 1
        if self.default and self.quantity_per_unit != 1:
            raise ValidationError(
                "Qty. per Unit of Measure must be equal to '1' in Item Unit of Measure."
            )

        # should only be one default per item
        if self.default:
            if (
                ItemUnitOfMeasure.objects.filter(item=self.item, default=True)
                .exclude(pk=self.pk)
                .exists()
            ):
                # if exist make the on exiting to false and
                # raise ValidationError("There can only be one default unit of measure per item.")
                pass

    def save(self, *args, **kwargs):
        # Enforce that default ItemUnitOfMeasure must have quantity_per_unit = 1
        if self.default and self.quantity_per_unit != 1:
            raise ValidationError(
                "Qty. per Unit of Measure must be equal to '1' in Item Unit of Measure."
            )

        # Check if we're trying to unset default
        if self.pk and not self.default:
            # Get the current state from database
            try:
                old_instance = ItemUnitOfMeasure.objects.get(pk=self.pk)
                # If it was default and we're unsetting it, ensure there's another default
                if old_instance.default:
                    other_defaults = ItemUnitOfMeasure.objects.filter(
                        item=self.item, default=True
                    ).exclude(pk=self.pk)
                    if not other_defaults.exists():
                        # This is the last default, cannot unset it
                        raise ValidationError(
                            "Cannot unset default. An item must always have a default unit of measure."
                        )
            except ItemUnitOfMeasure.DoesNotExist:
                pass  # New instance, no old state to check

        if not self.default:
            # check if there is any other default
            if (
                not ItemUnitOfMeasure.objects.filter(item=self.item, default=True)
                .exclude(pk=self.pk if self.pk else None)
                .exists()
            ):
                # No other default exists, this must be the default
                self.default = True
                self.quantity_per_unit = 1  # Ensure quantity is 1 for default

        if self.default:
            # Unset other defaults for this item
            ItemUnitOfMeasure.objects.filter(item=self.item, default=True).exclude(
                pk=self.pk if self.pk else None
            ).update(default=False)

        # Call full_clean to run all validations including clean()
        self.full_clean()
        super(ItemUnitOfMeasure, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of the last default ItemUnitOfMeasure"""
        if self.default:
            # Check if there are other ItemUnitOfMeasure records for this item
            other_uoms = ItemUnitOfMeasure.objects.filter(item=self.item).exclude(
                pk=self.pk
            )
            if not other_uoms.exists():
                raise ValidationError(
                    "Cannot delete the last unit of measure. An item must always have at least one unit of measure."
                )
            # If there are other UOMs, set the first one as default before deletion
            first_other = other_uoms.first()
            if first_other:
                first_other.default = True
                first_other.quantity_per_unit = 1  # Ensure quantity is 1 for default
                first_other.save()

        super(ItemUnitOfMeasure, self).delete(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "unit_of_measure"],
                name="unique_item_unit_of_measure",
            )
        ]
        verbose_name = "Item Unit of Measure"
        verbose_name_plural = "Item Units of Measure"
        db_table = "items_itemunitofmeasure"

    @property
    def effective_price(self):
        """Returns the price if set, otherwise calculates from item.unit_price * quantity_per_unit"""
        if self.price is not None:
            return Decimal(str(self.price))
        if self.item and self.item.unit_price:
            return Decimal(str(self.item.unit_price)) * Decimal(
                str(self.quantity_per_unit)
            )
        return Decimal("0.00")

    def __str__(self):
        return f"{self.item.item_name} - {self.unit_of_measure.code}-{self.quantity_per_unit}"


def money_decimal(value):
    """Normalize monetary values to Decimal(…, 2dp) for DB storage."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    cleaned = str(value).replace(",", "").strip()
    if cleaned == "":
        return None
    return Decimal(cleaned).quantize(Decimal("0.01"))


class ItemJournal(BaseModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    journal_template = models.ForeignKey(
        "ItemJournalTemplate",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name="Journal Template",
        help_text="Item journal template",
        related_name="item_journals",
    )
    entry_type = models.CharField(
        max_length=255,
        choices=([tag.name, tag.value] for tag in EntryType),
    )
    type = models.CharField(
        max_length=20,
        choices=[
            ("work_center", "Work Center"),
            ("machine_center", "Machine Center"),
            ("resource", "Resource"),
        ],
        null=True,
        blank=True,
        verbose_name="Type",
        help_text="Type of capacity used (Work Center, Machine Center, or Resource). Filled when entry_type is Output.",
    )
    document_no = models.CharField(max_length=255, unique=True)
    description = models.TextField(default="", null=True, blank=True)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    physical_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Physical Quantity",
        help_text="Physically counted quantity",
    )
    calculated_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Calculated Quantity",
        help_text="System-calculated quantity from ItemLedgerEntries",
        editable=False,
    )
    journal_batch = models.ForeignKey(
        "ItemJournalBatch",
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name="Journal Batch",
        related_name="item_journals",
    )
    # total = models.FloatField(editable=False)
    item_unit_of_measure = models.ForeignKey(
        ItemUnitOfMeasure,
        on_delete=models.PROTECT,
        verbose_name="Item Unit of Measure",
        related_name="item_journals",
        null=True,
        blank=True,
    )
    unit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Unit Amount",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Amount",
        default=Decimal("0.00"),
        null=True,
        blank=True,
    )
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Unit Cost",
        blank=True,
        null=True,
    )
    location_code = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, null=True, blank=True
    )
    date = models.DateField(null=True, blank=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="item_journals"
    )
    item_specification = models.ForeignKey(
        "items.TrackingSpecification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="item_journal_tracking_specifications",
    )
    status = models.CharField(
        max_length=255,
        choices=([tag.name, tag.value] for tag in Status),
        default=Status.Open.value,
    )
    adjustment_type = models.CharField(
        max_length=20,
        choices=[
            ("operational", "Operational Adjustment"),
            ("opening_balance", "Opening Balance"),
        ],
        default="operational",
        null=True,
        blank=True,
        verbose_name="Adjustment Type",
        help_text="Select whether this adjustment is operational or part of opening balance",
    )
    production_order = models.ForeignKey(
        "production.ProductionOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Production Order",
        help_text="Production order this journal entry is linked to",
        related_name="item_journals",
    )

    # Dimensions (Branch / DimensionSet) for inventory journal visibility and auditing.
    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        related_name="item_journals_global_dim_1",
        null=True,
        blank=True,
        verbose_name=_("Global Dimension 1"),
    )
    global_dimension_2 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        related_name="item_journals_global_dim_2",
        null=True,
        blank=True,
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="item_journals",
        null=True,
        blank=True,
        verbose_name=_("Dimension Set"),
    )

    def __str__(self):
        return self.document_no

    @property
    def total(self):
        """Calculate the total value for the journal entry"""
        return self.quantity * self.unit_cost if self.quantity and self.unit_cost else 0

    @property
    def quantity_difference(self):
        """Calculate difference between physical and calculated quantities"""
        if self.physical_quantity is not None and self.calculated_quantity is not None:
            return self.physical_quantity - self.calculated_quantity
        return None

    def clean(self):
        """
        Enforce branch/location tagging for journals.
        Imports and admin creates should not produce unscoped inventory journals.
        """
        super().clean()
        from financials.models import GeneralLedgerSetup

        if self.item_id:
            item_type = getattr(self.item, "type", None)
            if item_type in ("Service", "Non-Inventory"):
                raise ValidationError(
                    {
                        "item": _(
                            "Opening balances and inventory adjustments are not "
                            "allowed for Service or Non-Inventory items."
                        )
                    }
                )

        if not self.location_code_id:
            raise ValidationError({"location_code": _("Location is required.")})

        gl_setup = GeneralLedgerSetup.objects.first()
        if gl_setup and getattr(gl_setup, "enable_multiple_branches", False):
            if not self.global_dimension_1_id and not self.dimension_set_id:
                raise ValidationError(
                    {
                        "global_dimension_1": _(
                            "Branch (Global Dimension 1) is required when multi-branch is enabled."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        # Determine template based on journal type when missing.
        # Stock taking rows use PHYS. INV.; regular item journals use ITEM.
        if not self.journal_template_id:
            is_stock_taking = (
                self.physical_quantity is not None or self.calculated_quantity is not None
            )
            template_name = "PHYS. INV." if is_stock_taking else "ITEM"
            defaults = (
                {"description": "Physical Inventory", "type": "phys_inventory"}
                if is_stock_taking
                else {"description": "Item Journal", "type": "item"}
            )
            self.journal_template, _ = ItemJournalTemplate.objects.get_or_create(
                name=template_name,
                defaults=defaults,
            )

        # Set default journal batch to "DEFAULT" if template is set but batch is not
        if self.journal_template_id and not self.journal_batch_id:
            self.journal_batch, _ = ItemJournalBatch.objects.get_or_create(
                journal_template=self.journal_template,
                name="DEFAULT",
                defaults={"description": "Default Journal"},
            )

        try:
            # Ensure numeric values are properly set before saving
            if self.quantity is not None:
                self.quantity = int(str(self.quantity).replace(",", ""))

            if self.unit_amount is not None:
                self.unit_amount = money_decimal(self.unit_amount)
                self.unit_cost = self.unit_amount

            if self.unit_cost is not None and self.unit_amount is None:
                self.unit_cost = money_decimal(self.unit_cost)

            # For physical inventory journals, set entry_type and quantity based on difference.
            if (
                self.journal_template
                and self.journal_template.type == "phys_inventory"
                and self.physical_quantity is not None
                and self.calculated_quantity is not None
            ):
                diff = self.physical_quantity - self.calculated_quantity
                if diff > 0:
                    self.entry_type = EntryType.PositiveAdjustment.name
                    self.quantity = abs(diff)
                elif diff < 0:
                    self.entry_type = EntryType.NegativeAdjustment.name
                    self.quantity = abs(diff)
                else:
                    # No difference - set to positive adjustment with 0 quantity
                    self.entry_type = EntryType.PositiveAdjustment.name
                    self.quantity = 0

            # Calculate amount and unit_amount (use unit_cost for stock taking when unit_amount is None)
            if self.quantity is not None:
                cost_per_unit = (
                    self.unit_amount if self.unit_amount is not None else self.unit_cost
                )
                if cost_per_unit is not None:
                    cost_dec = money_decimal(cost_per_unit) or Decimal("0.00")
                    self.amount = (
                        Decimal(int(self.quantity)) * cost_dec
                    ).quantize(Decimal("0.01"))
                    if self.unit_amount is None and self.unit_cost is not None:
                        self.unit_amount = money_decimal(self.unit_cost)

            print(
                "Model save values:",
                {
                    "quantity": self.quantity,
                    "unit_amount": self.unit_amount,
                    "amount": self.amount,
                    "unit_cost": self.unit_cost,
                    "physical_quantity": self.physical_quantity,
                    "calculated_quantity": self.calculated_quantity,
                },
            )

            # Validate required fields before burning a document number.
            if not self.item_id:
                raise ValidationError({"item": _("This field cannot be null.")})

            # Handle document number generation
            if not self.pk and not self.document_no:
                try:
                    # First try to use template's no_series if available
                    if self.journal_template and self.journal_template.no_series:
                        journal_no_series = NoSeriesLines.objects.filter(
                            no_series=self.journal_template.no_series
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
                            self.status = Status.Open.value
                            print(
                                f"Generated document number from template: {self.document_no}"
                            )
                    # Fallback to JournalSetup if template doesn't have no_series
                    elif JournalSetup.objects.all().first():
                        journal_no_series = NoSeriesLines.objects.filter(
                            no_series=JournalSetup.objects.all()
                            .first()
                            .journal_no_series
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
                        self.status = Status.Open.value
                        print(f"Generated document number: {self.document_no}")

                except ValueError as e:
                    print(f"Error parsing document number: {e}")

            self.full_clean()
            if not self.date:
                self.date = datetime.now().date()
            if not self.description:
                self.description = f"Adjustment of item {self.item.item_name} with quantity {self.quantity}"
            super().save(*args, **kwargs)

        except Exception as e:
            print(f"Error saving ItemJournal: {e}")
            raise

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["created_at"],
                name="items_itemj_created_e51c0b_idx",
            ),
            models.Index(
                fields=["system_id"],
                name="items_itemj_system__6c21d9_idx",
            ),
            models.Index(
                fields=["status", "journal_template"],
                name="items_ij_status_tpl_idx",
            ),
        ]


class ItemJournalTemplate(BaseModel):
    """
    Item Journal Template model.
    Defines templates for different types of item journals.
    Similar to Business Central's Item Journal Template.
    """

    TYPE_CHOICES = [
        ("item", "Item"),
        ("transfer", "Transfer"),
        ("phys_inventory", "Phys. Inventory"),
        ("output", "Output"),
        ("production_order", "Production Order"),
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Name",
        help_text="Template name (e.g., ITEM)",
    )

    description = models.CharField(
        max_length=200,
        verbose_name="Description",
        help_text="Template description",
    )

    type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        verbose_name="Type",
        help_text="Journal template type",
    )

    no_series = models.ForeignKey(
        "setup.NoSeries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="No. Series",
        help_text="Number series for journal entries",
        related_name="item_journal_templates",
    )

    class Meta:
        verbose_name = "Item Journal Template"
        verbose_name_plural = "Item Journal Templates"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.description}"


class ItemJournalBatch(BaseModel):
    """
    Item Journal Batch model.
    Organizes journal entries within a template.
    Similar to Business Central's Item Journal Batch.
    """

    journal_template = models.ForeignKey(
        ItemJournalTemplate,
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name="Journal Template",
    )
    name = models.CharField(
        max_length=50,
        verbose_name="Name",
        help_text="Batch name (e.g., DEFAULT)",
    )
    description = models.CharField(
        max_length=200,
        verbose_name="Description",
        help_text="Batch description",
        blank=True,
    )
    no_series = models.ForeignKey(
        "setup.NoSeries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="No. Series",
        help_text="Number series for posting",
        related_name="item_journal_batches",
    )

    class Meta:
        verbose_name = "Item Journal Batch"
        verbose_name_plural = "Item Journal Batches"
        unique_together = [("journal_template", "name")]
        ordering = ["journal_template", "name"]

    def __str__(self):
        return f"{self.journal_template.name} - {self.name}"


def get_default_item_journal_template():
    """
    Returns the default Item Journal template (ITEM) for TrackingSpecification.
    Used when source_template is null and cannot be inferred from item_journal.
    """
    try:
        return ItemJournalTemplate.objects.get(name="ITEM")
    except ItemJournalTemplate.DoesNotExist:
        return None


def get_default_item_journal_batch():
    """
    Returns the default Item Journal batch (ITEM - DEFAULT) for TrackingSpecification.
    Used when source_batch is null and cannot be inferred from item_journal.
    """
    try:
        return ItemJournalBatch.objects.get(
            journal_template__name="ITEM", name="DEFAULT"
        )
    except ItemJournalBatch.DoesNotExist:
        return None


class PhysInventoryLedgerEntry(BaseModel):
    """
    Physical Inventory Ledger Entry model.
    Records all physical inventory counts for audit trail and analysis.
    This is separate from Item Ledger Entries and tracks the counting activity itself.
    """

    entry_no = models.AutoField(primary_key=True, verbose_name="Entry No.")

    # Document Information
    document_no = models.CharField(
        max_length=20, verbose_name="Document No.", help_text="Journal document number"
    )
    posting_date = models.DateField(
        verbose_name="Posting Date",
        help_text="Date when the physical inventory was posted",
    )

    # Item Information
    item = models.ForeignKey(
        "Item",
        on_delete=models.PROTECT,
        related_name="phys_inventory_ledger_entries",
        verbose_name="Item",
    )
    item_no = models.CharField(
        max_length=20,
        verbose_name="Item No.",
        help_text="Item number (denormalized for reporting)",
    )
    description = models.CharField(max_length=255, verbose_name="Description")

    # Location Information
    location_code = models.ForeignKey(
        "Location",
        on_delete=models.PROTECT,
        related_name="phys_inventory_ledger_entries",
        verbose_name="Location Code",
    )

    # Quantities - The core audit data
    qty_expected = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        verbose_name="Qty. (Expected)",
        help_text="System quantity before physical count (calculated quantity)",
    )
    qty_phys_inventory = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        verbose_name="Qty. (Phys. Inventory)",
        help_text="Actual counted quantity (physical quantity)",
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=5,
        verbose_name="Quantity",
        help_text="Variance (Phys. Inventory - Expected)",
    )

    # Entry Type
    entry_type = models.CharField(
        max_length=50,
        verbose_name="Entry Type",
        help_text="Positive or Negative Adjustment",
    )

    # Unit of Measure
    unit_of_measure = models.ForeignKey(
        "ItemUnitOfMeasure",
        on_delete=models.PROTECT,
        related_name="phys_inventory_ledger_entries",
        verbose_name="Unit of Measure",
    )

    # Values
    unit_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Unit Amount",
        help_text="Unit cost used for this count",
    )
    unit_cost = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name="Unit Cost"
    )

    # Audit Information
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="phys_inventory_ledger_entries",
        verbose_name="User",
        help_text="User who posted the physical inventory",
    )

    # Link to the actual adjustment
    item_ledger_entry = models.ForeignKey(
        "ItemLedgerEntries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="phys_inventory_ledger_entries",
        verbose_name="Item Ledger Entry No.",
        help_text="Link to the item ledger entry created by this count",
    )

    # Journal Reference
    journal_batch = models.ForeignKey(
        ItemJournalBatch,
        on_delete=models.PROTECT,
        related_name="phys_inventory_ledger_entries",
        verbose_name="Journal Batch",
    )

    class Meta:
        verbose_name = "Phys. Inventory Ledger Entry"
        verbose_name_plural = "Phys. Inventory Ledger Entries"
        db_table = "items_physinventoryledgerentry"
        ordering = ["-posting_date", "-entry_no"]
        indexes = [
            models.Index(fields=["item", "posting_date"]),
            models.Index(fields=["location_code", "posting_date"]),
            models.Index(fields=["document_no"]),
        ]

    def __str__(self):
        return f"{self.entry_no} - {self.item_no} ({self.posting_date})"

    @property
    def variance_percentage(self):
        """Calculate variance as a percentage of expected quantity."""
        if self.qty_expected and self.qty_expected != 0:
            return (self.quantity / self.qty_expected) * 100
        return 0


class ItemImages(BaseModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    alt_text = models.CharField(
        verbose_name=_("Alternative text"),
        max_length=255,
        help_text=_("Please add alternative text"),
        null=True,
        blank=True,
    )
    url = models.ImageField(
        max_length=200,
        verbose_name=_("image"),
        help_text=_("Upload a product image"),
        upload_to="images/",
        null=True,
        blank=True,
        default="images/default.png",
    )

    def delete(self, *args, **kwargs):
        # Delete the file from storage (S3 or local)
        if self.url and self.url.name and default_storage.exists(self.url.name):
            self.url.delete(save=False)
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Item Image"
        verbose_name_plural = "Item Images"
        db_table = "Item Images"
        ordering = ("-created_at",)


class UnitOfMeasure(BaseModel):
    code = models.CharField(max_length=10, unique=True, primary_key=True)
    description = models.CharField(max_length=100)
    international_stnd_code = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Unit of Measure"
        verbose_name_plural = "Units of Measure"
        db_table = "items_unitofmeasure"
        ordering = ["code"]  # Add default ordering to prevent pagination warnings


class ItemCategory(BaseModel, MPTTModel):
    code = models.CharField(
        verbose_name="Code",
        max_length=255,
        unique=True,
        null=False,
        blank=False,
        primary_key=True,
    )
    description = models.CharField(
        verbose_name="Description", max_length=255, unique=True
    )
    parent = TreeForeignKey(
        "self",
        verbose_name="Parent Category",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    attributes = models.ManyToManyField(
        ItemAttribute,
        blank=True,
        related_name="categories",
    )

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        # if not self.code:
        #     starter = "IC-0001"
        #     last_item = ItemCategory.objects.order_by("-code").first()

        #     if last_item and last_item.code:
        #         try:
        #             last_code_number = int(last_item.code.split("-")[1])
        #             new_code_number = str(last_code_number + 1).zfill(4)
        #             self.code = f"IC-{new_code_number}"
        #         except (IndexError, ValueError):
        #             self.code = starter
        #     else:
        #         self.code = starter

        if self.description is None:
            self.description = ""

        if self.description is not None:
            if self.description != self.description.upper():
                self.description = self.description.upper()
                if ItemCategory.objects.filter(description=self.description).exists():
                    raise ValidationError(
                        {
                            "description": "This category already exists".format(
                                self.description
                            )
                        }
                    )

        super().save(*args, **kwargs)

    class MPTTMeta:
        order_insertion_by = ["description"]

    class Meta:
        verbose_name = _("Item Category")
        verbose_name_plural = _("Item Categories")
        unique_together = ("description", "parent")


class ItemLedgerEntries(BaseModel):
    item = models.ForeignKey("Item", on_delete=models.CASCADE, editable=False)
    entry_type = models.CharField(
        max_length=255,
        choices=([tag.name, tag.value] for tag in EntryType),
        editable=False,
    )
    document_type = models.CharField(
        max_length=255,
        choices=([tag.name, tag.value] for tag in DocumentType),
        editable=False,
        default=DocumentType.default.value,
        null=True,
        blank=True,
    )
    posting_date = models.DateField(editable=False, null=True, blank=True)
    document_no = models.CharField(max_length=255, editable=False)
    description = models.TextField(editable=False)
    quantity = models.IntegerField(editable=False)
    remaining_quantity = models.PositiveIntegerField(editable=False)
    total = models.FloatField(editable=False)
    unit_of_measure = models.CharField(max_length=255, default="PCS", editable=False)
    # unit_cost = models.FloatField(editable=False)
    # unit_amount = models.FloatField(editable=False, null=True, blank=True)
    # amount = models.FloatField(editable=False, null=True, blank=True)
    quantity_per_unit_of_measure = models.CharField(
        max_length=255,
        verbose_name="Quantity per Unit of Measure",
        editable=False,
        null=True,
        blank=True,
    )
    unit_of_measure_code = models.ForeignKey(
        ItemUnitOfMeasure,
        on_delete=models.SET_NULL,
        verbose_name="Unit of Measure Code",
        editable=False,
        null=True,
        blank=True,
    )
    cost_amount = models.FloatField(editable=False, null=True, blank=True)
    sales_amount = models.FloatField(editable=False, null=True, blank=True)
    purchase_amount = models.FloatField(editable=False, null=True, blank=True)
    date = models.DateField(editable=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, editable=False)
    receipt_no = models.CharField(max_length=255, editable=False, null=True, blank=True)
    serial_no = models.CharField(max_length=255, null=True, blank=True)
    lot_no = models.CharField(max_length=255, null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    location = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, editable=False, null=True, blank=True
    )
    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        related_name="item_ledger_entries",
    )
    global_dimension_2 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="item_ledger_entries_global_dim_2",
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="item_ledger_entries",
    )
    transaction_no = models.CharField(
        max_length=255, verbose_name="Transaction No.", blank=True, null=True
    )
    open = models.BooleanField(default=True)
    applies_to_entry = models.CharField(max_length=255, null=True, blank=True)

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
        related_name="item_ledger_reversals",
        blank=True,
        null=True,
        help_text="User who performed the reversal",
    )

    def clean(self):
        super().clean()
        if not _item_entry_type_requires_location_and_dimensions(self.entry_type):
            return
        from dimension.models import get_dimension_value_from_set
        from financials.models import GeneralLedgerSetup

        if (
            self.location_id is None
            and not self.global_dimension_1_id
            and not self.dimension_set_id
        ):
            raise ValidationError(
                {
                    "location": _(
                        "Location or dimensions (global dimension 1 / dimension set) "
                        "is required for this item ledger entry type."
                    )
                }
            )
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
                    _(
                        "Item ledger entries of this type require global dimension 1 "
                        "or a dimension set that includes it (per General Ledger Setup)."
                    )
                )
        if gl_setup.global_dimension_2_id:
            resolved_id = self.global_dimension_2_id
            if not resolved_id and ds:
                v = get_dimension_value_from_set(ds, gl_setup.global_dimension_2)
                resolved_id = v.pk if v else None
            if not resolved_id:
                raise ValidationError(
                    _(
                        "Item ledger entries of this type require global dimension 2 "
                        "or a dimension set that includes it (per General Ledger Setup)."
                    )
                )

    def save(self, *args, **kwargs):
        skip = kwargs.pop("skip_inventory_entry_dimension_validation", False)
        # Always keep posting_date populated for list/report UI (legacy paths
        # historically wrote only ``date``).
        if self.posting_date is None and self.date is not None:
            self.posting_date = self.date
        elif self.date is None and self.posting_date is not None:
            self.date = self.posting_date
        if not skip and self._state.adding:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.document_no

    @property
    def is_reversal_entry(self):
        """Check if this entry is a reversal of another entry"""
        return self.reverses_entry_no is not None

    @property
    def can_be_reversed(self):
        """Check if this entry can be reversed"""
        return not self.reversed

    @property
    def cost_amount(self):
        value_entries = ValueEntry.objects.filter(item_ledger_entry_no=self.id)
        if value_entries.exists():
            return sum(float(entry.cost_amount or 0) for entry in value_entries)
        return 0

    class Meta:
        verbose_name = "Item Ledger Entry"
        verbose_name_plural = "Item Ledger Entries"
        db_table = "Item Ledger Entries"
        ordering = [
            "-posting_date",
            "-created_at",
        ]  # Add default ordering to prevent pagination warnings
        indexes = [
            models.Index(
                fields=["item", "global_dimension_1"],
                name="items_ile_item_branch_idx",
            ),
            models.Index(
                fields=["item", "posting_date"],
                name="items_ile_item_date_idx",
            ),
            models.Index(fields=["document_no"], name="items_ile_doc_no_idx"),
        ]


class ValueEntry(BaseModel):
    vat_posting_group = models.ForeignKey(
        "postings.VATProductPostingGroup",
        on_delete=models.SET_NULL,
        verbose_name="VAT Posting Group",
        editable=False,
        null=True,
        blank=True,
    )
    vat_business_posting_group = models.ForeignKey(
        "postings.VATBusinessPostingGroup",
        on_delete=models.SET_NULL,
        verbose_name="VAT Business Posting Group",
        editable=False,
        null=True,
        blank=True,
    )
    posting_date = models.DateField(verbose_name="Posting Date", default=datetime.now)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    entry_type = models.CharField(
        max_length=255,
        choices=([tag.name, tag.value] for tag in EntryType),
        editable=False,
    )
    document_type = models.CharField(
        max_length=255,
        choices=([tag.name, tag.value] for tag in DocumentType),
        editable=False,
        default=DocumentType.default.value,
        null=True,
        blank=True,
    )
    document_no = models.CharField(max_length=255, editable=False)
    location_code = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, editable=False, null=True, blank=True
    )
    description = models.TextField(editable=False)
    item_ledger_entry_no = models.ForeignKey(
        ItemLedgerEntries, on_delete=models.CASCADE, verbose_name="Item Ledger Entry No"
    )
    cost_amount = models.CharField(max_length=255, verbose_name="Cost Amount (Actual)")
    sales_amount = models.CharField(max_length=255, verbose_name="Sales Amount(Actual)")
    cost_per_unit = models.FloatField(verbose_name="Cost Per Unit", default=0)
    item_ledger_entry_quantity = models.IntegerField(
        verbose_name="Item Ledger Entry Quantity", default=0
    )
    valued_quantity = models.IntegerField(verbose_name="Valued Quantity", default=0)
    invoiced_quantity = models.IntegerField(verbose_name="Invoiced Quantity", default=0)
    inventory_posting_group = models.ForeignKey(
        "postings.InventoryPostingGroup",
        on_delete=models.CASCADE,
        verbose_name="Inventory Posting Group",
        null=True,
        blank=True,
    )
    general_product_posting_group = models.ForeignKey(
        "postings.GeneralProductPostingGroup",
        on_delete=models.CASCADE,
        verbose_name="General Product Posting Group",
        null=True,
        blank=True,
    )
    general_business_posting_group = models.ForeignKey(
        "postings.GeneralBusinessPostingGroup",
        on_delete=models.CASCADE,
        verbose_name="General Business Posting Group",
        null=True,
        blank=True,
    )
    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        related_name="value_entries",
    )
    global_dimension_2 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="value_entries_global_dim_2",
        verbose_name=_("Global Dimension 2"),
    )
    dimension_set = models.ForeignKey(
        "dimension.DimensionSet",
        on_delete=models.PROTECT,
        related_name="value_entries",
    )
    transaction_no = models.CharField(
        max_length=255, verbose_name="Transaction No.", blank=True, null=True
    )
    cost_amount_non_invtbl = models.DecimalField(
        verbose_name="Cost Amount (Non-Invtbl.)",
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="Cost for Service and Non-Inventory items (not reconciled to G/L)",
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
    reverses_value_entry_no = models.IntegerField(
        verbose_name="Reverses Value Entry No.",
        blank=True,
        null=True,
        db_index=True,
        help_text="If this is a reversing entry, the ID of the value entry it reverses",
    )
    reversed_by_user = models.ForeignKey(
        User,
        verbose_name="Reversed By User",
        on_delete=models.PROTECT,
        related_name="value_entry_reversals",
        blank=True,
        null=True,
        help_text="User who performed the reversal",
    )

    def clean(self):
        super().clean()
        if not _item_entry_type_requires_location_and_dimensions(self.entry_type):
            return
        from dimension.models import get_dimension_value_from_set
        from financials.models import GeneralLedgerSetup

        if (
            self.location_code_id is None
            and not self.global_dimension_1_id
            and not self.dimension_set_id
        ):
            raise ValidationError(
                {
                    "location_code": _(
                        "Location or dimensions (global dimension 1 / dimension set) "
                        "is required for this value entry type."
                    )
                }
            )
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
                    _(
                        "Value entries of this type require global dimension 1 "
                        "or a dimension set that includes it (per General Ledger Setup)."
                    )
                )
        if gl_setup.global_dimension_2_id:
            resolved_id = self.global_dimension_2_id
            if not resolved_id and ds:
                v = get_dimension_value_from_set(ds, gl_setup.global_dimension_2)
                resolved_id = v.pk if v else None
            if not resolved_id:
                raise ValidationError(
                    _(
                        "Value entries of this type require global dimension 2 "
                        "or a dimension set that includes it (per General Ledger Setup)."
                    )
                )

    def save(self, *args, **kwargs):
        skip = kwargs.pop("skip_inventory_entry_dimension_validation", False)
        skip_signs = kwargs.pop("skip_bc_value_entry_sign_normalization", False)
        if not skip_signs:
            from items.value_entry_posting import apply_bc_signs_to_value_entry_instance

            apply_bc_signs_to_value_entry_instance(self)
        if not skip and self._state.adding:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_reversal_entry(self):
        """Check if this entry is a reversal of another entry"""
        return self.reverses_value_entry_no is not None

    @property
    def can_be_reversed(self):
        """Check if this entry can be reversed"""
        return not self.reversed

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["created_at"],
                name="items_value_created_8a93ed_idx",
            ),
            models.Index(
                fields=["system_id"],
                name="items_value_system__838d7f_idx",
            ),
            models.Index(fields=["document_no"], name="items_ve_doc_no_idx"),
            models.Index(
                fields=["item", "posting_date"],
                name="items_ve_item_date_idx",
            ),
        ]


class ItemTrackingCodes(BaseModel):
    code = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    require_serial_no = models.BooleanField(verbose_name="Serial No.", default=False)
    require_lot_no = models.BooleanField(verbose_name="Lot No.", default=False)
    require_expiry_date = models.BooleanField(verbose_name="Expiry Date", default=False)

    def __str__(self):

        return self.code

    def delete(self, *args, **kwargs):
        if self.code == "ALL LOT":
            raise ValidationError(
                "This tracking code is system default and cannot be deleted"
            )
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = "Item Tracking Code"
        verbose_name_plural = "Item Tracking Codes"
        db_table = "items_itemtrackingcodes"
        ordering = ["code"]  # Add default ordering to prevent pagination warnings


def _parse_positive_quantity_base(value, *, field_name="quantity_base"):
    """Coerce page/API values to a non-negative integer quantity (base)."""
    if value is None or value == "":
        raise ValidationError({field_name: "Enter a valid quantity (base)."})
    if isinstance(value, bool):
        quantity = int(value)
    elif isinstance(value, int):
        quantity = value
    elif isinstance(value, float):
        if value != value or value < 0:
            raise ValidationError({field_name: "Enter a valid quantity (base)."})
        quantity = int(value)
    elif isinstance(value, Decimal):
        quantity = int(value)
    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            raise ValidationError({field_name: "Enter a valid quantity (base)."})
        try:
            quantity = int(Decimal(cleaned))
        except Exception:
            raise ValidationError({field_name: "Enter a valid quantity (base)."})
    else:
        try:
            quantity = int(Decimal(str(value)))
        except Exception:
            raise ValidationError({field_name: "Enter a valid quantity (base)."})
    if quantity < 0:
        raise ValidationError({field_name: "Enter a valid quantity (base)."})
    return quantity


def _expected_purchase_line_quantity(purchase_line):
    qpu = 1
    if purchase_line.item_unit_of_measure_id:
        qpu = purchase_line.item_unit_of_measure.quantity_per_unit or 1
    return int(purchase_line.quantity or 0) * int(qpu or 1)


def _expected_sales_line_quantity(sales_line):
    qpu = 1
    if getattr(sales_line, 'item_unit_of_measure_id', None):
        qpu = sales_line.item_unit_of_measure.quantity_per_unit or 1
    return int(sales_line.quantity or 0) * int(qpu or 1)


def _item_requires_serial_no(item) -> bool:
    tracking = getattr(item, 'tracking_code', None) if item is not None else None
    return bool(tracking and getattr(tracking, 'require_serial_no', False))


def _item_requires_lot_no(item) -> bool:
    tracking = getattr(item, 'tracking_code', None) if item is not None else None
    return bool(tracking and getattr(tracking, 'require_lot_no', False))


def _validate_serial_quantity_base(item, quantity_base: int) -> None:
    """BC: Quantity (Base) must be 1 when Serial No. tracking is required."""
    if _item_requires_serial_no(item) and quantity_base != 1:
        raise ValidationError(
            {
                'quantity_base': (
                    'Quantity (Base) must be 1 when Serial No. is stated.'
                ),
            },
        )


_NEGATIVE_ENTRY_TYPES = frozenset({
    'NegativeAdjustment',
    'Negative Adjustment',
    'Sales',
})


def _is_outbound_tracking_context(*, sales_invoice_line=None, item_journal=None) -> bool:
    if sales_invoice_line is not None:
        return True
    if item_journal is not None:
        return getattr(item_journal, 'entry_type', None) in _NEGATIVE_ENTRY_TYPES
    return False


def _serial_remaining_in_stock(item, serial_no: str, *, location=None) -> int:
    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    qs = ItemLedgerEntries.objects.filter(
        item=item,
        serial_no__iexact=str(serial_no).strip(),
        remaining_quantity__gt=0,
    )
    if location is not None:
        qs = qs.filter(location=location)
    return int(
        qs.aggregate(total=Coalesce(Sum('remaining_quantity'), 0))['total'] or 0
    )


def _validate_inbound_serial_unique(serial_no: str, *, item=None, exclude_pk=None) -> None:
    """Inbound (purchase / +adj): serial must not already exist in stock or open inbound specs."""
    serial = str(serial_no).strip()
    if not serial:
        return

    if item is not None and _serial_remaining_in_stock(item, serial) > 0:
        raise ValidationError(
            {'serial_no': f'Serial No. "{serial}" already exists in inventory.'},
        )

    qs = TrackingSpecification.objects.filter(serial_no__iexact=serial).filter(
        models.Q(purchase_invoice_line__isnull=False)
        | models.Q(
            item_journal__isnull=False,
            item_journal__entry_type='PositiveAdjustment',
        )
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError(
            {'serial_no': f'Serial No. "{serial}" is already assigned. Enter a unique serial number.'},
        )


def _validate_outbound_serial_available(
    serial_no: str,
    *,
    item,
    location=None,
    exclude_pk=None,
) -> None:
    """Outbound (sales / −adj): serial must exist in stock with remaining qty."""
    serial = str(serial_no).strip()
    if not serial:
        return
    available = _serial_remaining_in_stock(item, serial, location=location)
    if available <= 0:
        raise ValidationError(
            {
                'serial_no': (
                    f'Serial No. "{serial}" is not available in inventory for this item.'
                ),
            },
        )
    # Same serial cannot be assigned twice on open outbound docs while still in stock once.
    outbound_qs = TrackingSpecification.objects.filter(serial_no__iexact=serial).filter(
        models.Q(sales_invoice_line__isnull=False)
        | models.Q(
            item_journal__isnull=False,
            item_journal__entry_type='NegativeAdjustment',
        )
    )
    if exclude_pk:
        outbound_qs = outbound_qs.exclude(pk=exclude_pk)
    if outbound_qs.exists() and available <= outbound_qs.count():
        raise ValidationError(
            {'serial_no': f'Serial No. "{serial}" is already selected on another line.'},
        )


def _validate_unique_serial_no(
    serial_no: str | None,
    *,
    item=None,
    location=None,
    outbound: bool = False,
    exclude_pk=None,
) -> None:
    if not serial_no or not str(serial_no).strip():
        return
    if outbound:
        _validate_outbound_serial_available(
            serial_no, item=item, location=location, exclude_pk=exclude_pk,
        )
    else:
        _validate_inbound_serial_unique(serial_no, item=item, exclude_pk=exclude_pk)


def _expected_journal_quantity(journal):
    qpu = 1
    if getattr(journal, 'item_unit_of_measure_id', None):
        qpu = journal.item_unit_of_measure.quantity_per_unit or 1
    return int(journal.quantity or 0) * int(qpu or 1)


def _validate_journal_tracking_quantity(item_journal, quantity_base, *, exclude_pk=None):
    journal = ItemJournal.objects.select_related(
        'item_unit_of_measure', 'item__tracking_code', 'location_code',
    ).get(
        id=item_journal.id if hasattr(item_journal, 'id') else item_journal
    )
    expected_quantity = _expected_journal_quantity(journal)
    line_quantity = _parse_positive_quantity_base(quantity_base)
    _validate_serial_quantity_base(getattr(journal, 'item', None), line_quantity)

    specifications = TrackingSpecification.objects.filter(item_journal=journal.id)
    if exclude_pk:
        specifications = specifications.exclude(pk=exclude_pk)
    total_quantity = specifications.aggregate(total=Sum('quantity_base'))['total'] or 0
    assigned_quantity = int(total_quantity) + line_quantity

    if assigned_quantity > expected_quantity:
        raise ValidationError(
            'Quantity in tracking specification must match journal quantity. '
            f'Expected: {expected_quantity}, assigned: {assigned_quantity}.'
        )
    return line_quantity


def _validate_purchase_tracking_quantity(purchase_invoice_line, quantity_base, *, exclude_pk=None):
    PurchaseInvoiceLine = apps.get_model("purchases", "PurchaseInvoiceLine")

    purchase_line = PurchaseInvoiceLine.objects.select_related(
        "item_unit_of_measure", "item__tracking_code",
    ).get(
        id=purchase_invoice_line.id
        if hasattr(purchase_invoice_line, "id")
        else purchase_invoice_line
    )
    expected_quantity = _expected_purchase_line_quantity(purchase_line)
    line_quantity = _parse_positive_quantity_base(quantity_base)
    _validate_serial_quantity_base(getattr(purchase_line, 'item', None), line_quantity)

    specifications = TrackingSpecification.objects.filter(
        purchase_invoice_line=purchase_line.id
    )
    if exclude_pk:
        specifications = specifications.exclude(pk=exclude_pk)
    total_quantity = specifications.aggregate(total=Sum("quantity_base"))["total"] or 0
    assigned_quantity = int(total_quantity) + line_quantity

    if assigned_quantity > expected_quantity:
        raise ValidationError(
            "Quantity in tracking specification must match purchase line quantity. "
            f"Expected: {expected_quantity}, assigned: {assigned_quantity}."
        )
    return line_quantity


def _validate_sales_tracking_quantity(sales_invoice_line, quantity_base, *, exclude_pk=None):
    SalesInvoiceLine = apps.get_model("sales", "SalesInvoiceLine")

    sales_line = SalesInvoiceLine.objects.select_related(
        "item_unit_of_measure", "item__tracking_code",
    ).get(
        id=sales_invoice_line.id
        if hasattr(sales_invoice_line, "id")
        else sales_invoice_line
    )
    expected_quantity = _expected_sales_line_quantity(sales_line)
    line_quantity = _parse_positive_quantity_base(quantity_base)
    _validate_serial_quantity_base(getattr(sales_line, 'item', None), line_quantity)

    specifications = TrackingSpecification.objects.filter(
        sales_invoice_line=sales_line.id
    )
    if exclude_pk:
        specifications = specifications.exclude(pk=exclude_pk)
    total_quantity = specifications.aggregate(total=Sum("quantity_base"))["total"] or 0
    assigned_quantity = int(total_quantity) + line_quantity

    if assigned_quantity > expected_quantity:
        raise ValidationError(
            "Quantity in tracking specification must match sales line quantity. "
            f"Expected: {expected_quantity}, assigned: {assigned_quantity}."
        )
    return line_quantity


class TrackingSpecification(BaseModel):
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, related_name="tracking_specifications"
    )
    location_code = models.ForeignKey(
        "Location", on_delete=models.SET_NULL, null=True, blank=True
    )
    serial_no = models.CharField(
        verbose_name="Serial No.", max_length=255, blank=True, null=True
    )
    lot_no = models.CharField(
        verbose_name="Lot No.", max_length=255, blank=True, null=True
    )
    expiry_date = models.DateField(verbose_name="Expiry Date", blank=True, null=True)
    quantity_base = models.PositiveIntegerField(
        verbose_name="Quantity (Base)", default=1
    )

    item_journal = models.ForeignKey(
        ItemJournal,
        on_delete=models.CASCADE,
        verbose_name="Item Journal",
        null=True,
        blank=True,
        related_name="item_journal_tracking_specifications",
    )
    # Source identification for differentiating journal batch types (Item Journal vs Phys. Inventory)
    source_template = models.ForeignKey(
        ItemJournalTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_specifications",
        verbose_name="Source ID",
        help_text="Journal template (e.g. PHYS. INV., ITEM)",
    )
    source_batch = models.ForeignKey(
        ItemJournalBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_specifications",
        verbose_name="Source Batch Name",
        help_text="Journal batch (e.g. DEFAULT)",
    )
    purchase_invoice = models.ForeignKey(
        "purchases.PurchaseInvoice",
        on_delete=models.CASCADE,
        verbose_name="Purchase Invoice",
        null=True,
        blank=True,
    )
    purchase_invoice_line = models.ForeignKey(
        "purchases.PurchaseInvoiceLine",
        on_delete=models.CASCADE,
        verbose_name="Purchase Invoice Line",
        null=True,
        blank=True,
    )
    sales_invoice = models.ForeignKey(
        "sales.SalesInvoice",
        on_delete=models.CASCADE,
        verbose_name="Sales Invoice",
        null=True,
        blank=True,
    )
    sales_invoice_line = models.ForeignKey(
        "sales.SalesInvoiceLine",
        on_delete=models.CASCADE,
        verbose_name="Sales Invoice Line",
        null=True,
        blank=True,
    )

    description = models.TextField()

    user = models.ForeignKey(
        "authentication.CustomUser",
        on_delete=models.CASCADE,
        related_name="created_records",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.item.item_name} - {self.lot_no} - {self.expiry_date}"

    def save(self, *args, **kwargs):

        # it should at leas have on of the field
        if (
            not self.purchase_invoice_line
            and not self.sales_invoice_line
            and not self.item_journal
        ):
            raise ValidationError(
                "Purchase Invoice Line, Sales Invoice Line or Item Journal is required"
            )

        # Keep parent + item in sync with the source document line/journal.
        # Worksheet creates can omit item; a stale/wrong item FK makes posting
        # think tracking is missing (filter used to require item=line.item).
        if self.purchase_invoice_line_id:
            line = self.purchase_invoice_line
            if line.purchase_invoice_id:
                self.purchase_invoice_id = line.purchase_invoice_id
            if line.item_id:
                self.item_id = line.item_id
        elif self.sales_invoice_line_id:
            line = self.sales_invoice_line
            if line.sales_invoice_id:
                self.sales_invoice_id = line.sales_invoice_id
            if getattr(line, 'item_id', None):
                self.item_id = line.item_id
        elif self.item_journal_id:
            journal = self.item_journal
            if getattr(journal, 'item_id', None):
                self.item_id = journal.item_id

        # Serial No. stated → qty must be 1; inbound unique / outbound must exist in stock.
        serial_stated = bool(self.serial_no and str(self.serial_no).strip())
        if serial_stated:
            qty = _parse_positive_quantity_base(self.quantity_base)
            if qty != 1:
                raise ValidationError(
                    {
                        'quantity_base': (
                            'Quantity (Base) must be -1, 0 or 1 when Serial No. is stated.'
                        ),
                    },
                )
            outbound = _is_outbound_tracking_context(
                sales_invoice_line=self.sales_invoice_line if self.sales_invoice_line_id else None,
                item_journal=self.item_journal if self.item_journal_id else None,
            )
            item = self.item
            location = getattr(self, 'location_code', None)
            if outbound and self.sales_invoice_line_id:
                item = item or getattr(self.sales_invoice_line, 'item', None)
                location = location or getattr(self.sales_invoice_line, 'location_code', None)
            elif self.item_journal_id:
                item = item or getattr(self.item_journal, 'item', None)
                location = location or getattr(self.item_journal, 'location_code', None)
            elif self.purchase_invoice_line_id:
                item = item or getattr(self.purchase_invoice_line, 'item', None)
            _validate_unique_serial_no(
                self.serial_no,
                item=item,
                location=location,
                outbound=outbound,
                exclude_pk=self.pk,
            )

        if self.purchase_invoice_line:
            self.quantity_base = _validate_purchase_tracking_quantity(
                self.purchase_invoice_line,
                self.quantity_base,
                exclude_pk=self.pk,
            )
        elif self.sales_invoice_line:
            self.quantity_base = _validate_sales_tracking_quantity(
                self.sales_invoice_line,
                self.quantity_base,
                exclude_pk=self.pk,
            )
        elif self.item_journal:
            self.quantity_base = _validate_journal_tracking_quantity(
                self.item_journal,
                self.quantity_base,
                exclude_pk=self.pk,
            )
            # Auto-populate source_template and source_batch from item_journal
            if self.item_journal.journal_template_id:
                self.source_template = self.item_journal.journal_template
            if self.item_journal.journal_batch_id:
                self.source_batch = self.item_journal.journal_batch

        # Default to ITEM template and DEFAULT batch when not set
        if self.source_template is None:
            default_template = get_default_item_journal_template()
            if default_template:
                self.source_template = default_template
        if self.source_batch is None:
            default_batch = get_default_item_journal_batch()
            if default_batch:
                self.source_batch = default_batch

        super().save(*args, **kwargs)

    class Meta:
        constraints = []
        verbose_name = "Tracking Specification"
        verbose_name_plural = "Tracking Specifications"
        db_table = "items_trackingspecification"


class Location(BaseModel):
    code = models.CharField(max_length=255, unique=True)
    description = models.TextField()

    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        db_table = "items_location"

    def __str__(self):
        return self.code


# ── Item Variants ────────────────────────────────────────────────────────────


class ItemVariantOption(BaseModel):
    """An option dimension on an item, e.g. 'Size' or 'Color'."""

    item = models.ForeignKey(
        "Item",
        on_delete=models.CASCADE,
        related_name="variant_options",
        verbose_name="Item",
    )
    name = models.CharField(
        max_length=50, verbose_name="Option Name"
    )  # "Size", "Color"
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("item", "name")]
        ordering = ["display_order", "name"]
        verbose_name = "Item Variant Option"
        verbose_name_plural = "Item Variant Options"
        db_table = "items_variantoption"

    def __str__(self):
        return f"{self.item_id} – {self.name}"


class ItemVariantOptionValue(BaseModel):
    """A value within an option, e.g. 'XL' inside 'Size'."""

    option = models.ForeignKey(
        ItemVariantOption,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name="Option",
    )
    value = models.CharField(max_length=50, verbose_name="Value")  # "XL", "Red"
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("option", "value")]
        ordering = ["display_order", "value"]
        verbose_name = "Item Variant Option Value"
        verbose_name_plural = "Item Variant Option Values"
        db_table = "items_variantoptionvalue"

    def __str__(self):
        return f"{self.option.name}: {self.value}"


class ItemVariant(BaseModel):
    """A specific SKU combination, e.g. 'XL / Red'."""

    item = models.ForeignKey(
        "Item",
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="Item",
    )
    code = models.CharField(
        max_length=50,
        verbose_name="Variant Code",
        help_text="Auto-generated (e.g. XL-RED) or entered manually.",
    )
    description = models.CharField(
        max_length=200, blank=True, verbose_name="Description"
    )
    option_values = models.ManyToManyField(
        ItemVariantOptionValue,
        blank=True,
        verbose_name="Option Values",
        related_name="variants",
    )
    unit_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Unit Price",
        help_text="Leave blank to inherit the item's base price.",
    )
    bar_code_no = models.CharField(max_length=100, blank=True, verbose_name="Barcode")
    blocked = models.BooleanField(default=False, verbose_name="Blocked")

    class Meta:
        unique_together = [("item", "code")]
        ordering = ["code"]
        verbose_name = "Item Variant"
        verbose_name_plural = "Item Variants"
        db_table = "items_variant"

    def __str__(self):
        return f"{self.item_id} – {self.code}"

    @property
    def effective_price(self) -> int:
        """Variant price if set, else falls back to item base price."""
        return self.unit_price if self.unit_price is not None else self.item.unit_price

    @property
    def inventory(self) -> int:
        """Sum of remaining_quantity in ledger entries for this specific variant."""
        total = (
            ItemLedgerEntries.objects.filter(item=self.item, variant=self).aggregate(
                total=Sum("remaining_quantity")
            )["total"]
            or 0
        )
        return total


# ── Add variant FK to ItemLedgerEntries (nullable — existing entries unaffected) ──
# The field is defined here via monkey-patch so it does not require moving the class.
ItemLedgerEntries.add_to_class(
    "variant",
    models.ForeignKey(
        "ItemVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
        verbose_name="Variant",
        editable=False,
    ),
)


# Signal to delete file from storage on bulk delete
@receiver(post_delete, sender=ItemImages)
def delete_item_image_file(sender, instance, **kwargs):
    if instance.url and instance.url.name and default_storage.exists(instance.url.name):
        instance.url.delete(save=False)
