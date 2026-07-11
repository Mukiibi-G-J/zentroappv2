import re
import secrets

from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from django.utils import timezone
from datetime import datetime

from utils.utils import BaseModel
from setup.models import NoSeries, NoSeriesLines
from helpers.helpers import increment_item_number
from authentication.models import CustomUser
from .enums import (
    TableStatus,
    TableShape,
    ReservationStatus,
    OrderStatus,
    OrderItemStatus,
    OrderType,
    CourseType,
    FireState,
    PosActionType,
)


class Floor(BaseModel):
    """Floor/Location management for restaurant"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Floor number/code"),
    )
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True, null=True)
    display_order = models.IntegerField(_("Display Order"), default=0)
    location = models.ForeignKey(
        "items.Location",
        on_delete=models.PROTECT,
        related_name="restaurant_floors",
        null=True,
        blank=True,
        help_text=_("Inventory location this floor plan belongs to (e.g. branch / site)."),
    )

    class Meta:
        verbose_name = _("Floor")
        verbose_name_plural = _("Floors")
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.no} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.no:
            # Generate floor number using number series
            try:
                floor_series = NoSeries.objects.filter(code="FLOOR").first()
                if floor_series:
                    no_series_line = NoSeriesLines.objects.filter(
                        no_series=floor_series
                    ).first()
                    if no_series_line:
                        increment_by = no_series_line.increment_by
                        if no_series_line.last_used_number:
                            self.no = increment_item_number(
                                no_series_line.last_used_number, increment_by
                            )
                        else:
                            self.no = no_series_line.start_number
                        no_series_line.last_used_number = self.no
                        no_series_line.last_used_date = timezone.now().date()
                        no_series_line.save()
                    else:
                        self.no = f"FLOOR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    self.no = f"FLOOR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception as e:
                self.no = f"FLOOR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class FloorSection(BaseModel):
    """Logical grouping of tables on a floor (e.g. Bar, Patio) for layout and reporting."""

    floor = models.ForeignKey(
        Floor,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    name = models.CharField(_("Section name"), max_length=100)
    display_order = models.IntegerField(_("Display order"), default=0)

    class Meta:
        verbose_name = _("Floor section")
        verbose_name_plural = _("Floor sections")
        ordering = ["floor", "display_order", "name"]

    def __str__(self):
        return f"{self.floor.name}: {self.name}"


def _fallback_table_document_no() -> str:
    """Unique ``Table.no`` when the TABLE number series is missing or fails.

    Second-resolution timestamps collide when many tables are created in one
    request (e.g. ``generate_tables``); microseconds + a short random suffix
    keep ``no`` within the 50-char field and satisfy the unique constraint.
    """
    return f"TABLE-{timezone.now().strftime('%Y%m%d%H%M%S%f')}{secrets.token_hex(2)}"


class Table(BaseModel):
    """Table management for restaurant"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Table number"),
    )
    table_number = models.CharField(_("Table Number"), max_length=50)
    floor = models.ForeignKey(
        Floor, on_delete=models.CASCADE, related_name="tables", null=True, blank=True
    )
    section = models.ForeignKey(
        "FloorSection",
        on_delete=models.SET_NULL,
        related_name="tables",
        null=True,
        blank=True,
        help_text=_("Optional section grouping (e.g. Bar, Patio)."),
    )
    capacity = models.IntegerField(_("Capacity"), default=4)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=TableStatus.choices,
        default=TableStatus.AVAILABLE,
    )
    shape = models.CharField(
        _("Shape"),
        max_length=20,
        choices=TableShape.choices,
        default=TableShape.ROUND,
    )
    location_x = models.DecimalField(
        _("Location X"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("X position for floor plan"),
    )
    location_y = models.DecimalField(
        _("Location Y"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Y position for floor plan"),
    )
    plan_width = models.PositiveSmallIntegerField(
        _("Plan width"),
        default=80,
        help_text=_("Table tile width on floor plan canvas (pixels)."),
    )
    plan_height = models.PositiveSmallIntegerField(
        _("Plan height"),
        default=80,
        help_text=_("Table tile height on floor plan canvas (pixels)."),
    )
    notes = models.TextField(_("Notes"), blank=True, null=True)

    class Meta:
        verbose_name = _("Table")
        verbose_name_plural = _("Tables")
        ordering = ["floor", "section", "table_number"]

    def __str__(self):
        return f"{self.table_number} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.no:
            # Generate table number using number series
            try:
                table_series = NoSeries.objects.filter(code="TABLE").first()
                if table_series:
                    no_series_line = NoSeriesLines.objects.filter(
                        no_series=table_series
                    ).first()
                    if no_series_line:
                        increment_by = no_series_line.increment_by
                        if no_series_line.last_used_number:
                            self.no = increment_item_number(
                                no_series_line.last_used_number, increment_by
                            )
                        else:
                            self.no = no_series_line.start_number
                        no_series_line.last_used_number = self.no
                        no_series_line.last_used_date = timezone.now().date()
                        no_series_line.save()
                    else:
                        self.no = _fallback_table_document_no()
                else:
                    self.no = _fallback_table_document_no()
            except Exception as e:
                self.no = _fallback_table_document_no()
        super().save(*args, **kwargs)


class Reservation(BaseModel):
    """Reservation management for restaurant"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Reservation number"),
    )
    customer = models.ForeignKey(
        "sales.Customer",
        on_delete=models.PROTECT,
        related_name="restaurant_reservations",
    )
    table = models.ForeignKey(
        Table,
        on_delete=models.SET_NULL,
        related_name="reservations",
        null=True,
        blank=True,
        help_text=_("Table can be assigned later"),
    )
    reservation_date = models.DateTimeField(_("Reservation Date"))
    party_size = models.IntegerField(_("Party Size"), default=2)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
    )
    special_requests = models.TextField(_("Special Requests"), blank=True, null=True)
    waiter = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="reservations",
        null=True,
        blank=True,
    )
    notes = models.TextField(_("Notes"), blank=True, null=True)

    class Meta:
        verbose_name = _("Reservation")
        verbose_name_plural = _("Reservations")
        ordering = ["-reservation_date"]

    def __str__(self):
        return f"{self.no} - {self.customer.name} - {self.reservation_date}"

    def save(self, *args, **kwargs):
        if not self.no:
            # Generate reservation number using number series
            try:
                res_series = NoSeries.objects.filter(code="RESERVATION").first()
                if res_series:
                    no_series_line = NoSeriesLines.objects.filter(
                        no_series=res_series
                    ).first()
                    if no_series_line:
                        increment_by = no_series_line.increment_by
                        if no_series_line.last_used_number:
                            self.no = increment_item_number(
                                no_series_line.last_used_number, increment_by
                            )
                        else:
                            self.no = no_series_line.start_number
                        no_series_line.last_used_number = self.no
                        no_series_line.last_used_date = timezone.now().date()
                        no_series_line.save()
                    else:
                        self.no = f"RES-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    self.no = f"RES-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception as e:
                self.no = f"RES-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class MenuCategory(BaseModel):
    """Menu category for organizing menu items"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Category code"),
    )
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(_("Description"), blank=True, null=True)
    display_order = models.IntegerField(_("Display Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)
    routes_to_kitchen = models.BooleanField(
        _("Routes to kitchen / KDS"),
        default=True,
        help_text=_(
            "When enabled, items in this category are sent to the kitchen on Fire. "
            "Disable for bar-only categories (e.g. drinks) so they skip KDS."
        ),
    )

    class Meta:
        verbose_name = _("Menu Category")
        verbose_name_plural = _("Menu Categories")
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.no:
            # Generate category number using number series
            try:
                cat_series = NoSeries.objects.filter(code="MENU-CAT").first()
                if cat_series:
                    no_series_line = NoSeriesLines.objects.filter(
                        no_series=cat_series
                    ).first()
                    if no_series_line:
                        increment_by = no_series_line.increment_by
                        if no_series_line.last_used_number:
                            self.no = increment_item_number(
                                no_series_line.last_used_number, increment_by
                            )
                        else:
                            self.no = no_series_line.start_number
                        no_series_line.last_used_number = self.no
                        no_series_line.last_used_date = timezone.now().date()
                        no_series_line.save()
                    else:
                        self.no = f"MCAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    self.no = f"MCAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception as e:
                self.no = f"MCAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)


class MenuItem(BaseModel):
    """Menu item linked to POS Item"""

    item = models.OneToOneField(
        "items.Item",
        on_delete=models.CASCADE,
        related_name="menu_item",
        help_text=_("Links to existing POS item"),
    )
    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.SET_NULL,
        related_name="menu_items",
        null=True,
        blank=True,
    )
    menu = models.ForeignKey(
        "restaurant_management.Menu",
        on_delete=models.SET_NULL,
        related_name="menu_items",
        null=True,
        blank=True,
        help_text=_(
            "When set, this catalog row is scoped to that POS menu (Menu Builder list)."
        ),
    )
    description = models.TextField(
        _("Description"), help_text=_("Extended description for menu"), blank=True, default=""
    )
    image = models.ImageField(
        _("Image"), upload_to="restaurant/menu_items/", blank=True, null=True
    )
    is_available = models.BooleanField(_("Available"), default=True)
    routes_to_kitchen = models.BooleanField(
        _("Routes to kitchen / KDS"),
        null=True,
        blank=True,
        help_text=_(
            "If set, overrides the category for Fire/KDS routing. "
            "If unset, use the menu category flag."
        ),
    )
    preparation_time = models.IntegerField(
        _("Preparation Time (minutes)"), default=15, help_text=_("Average prep time")
    )
    is_featured = models.BooleanField(_("Featured"), default=False)
    spice_level = models.IntegerField(
        _("Spice Level"), default=0, help_text=_("0-5 spice level")
    )
    dietary_info = models.JSONField(
        _("Dietary Info"),
        default=list,
        blank=True,
        help_text=_("List: vegetarian, vegan, gluten_free, etc."),
    )
    allergens = models.JSONField(
        _("Allergens"),
        default=list,
        blank=True,
        help_text=_("List of allergens"),
    )
    available_sides = models.JSONField(
        _("Available Sides"),
        default=list,
        blank=True,
        help_text=_("List of available side options (e.g., ['fries', 'naan', 'rice', 'salad'])"),
    )
    display_order = models.IntegerField(_("Display Order"), default=0)
    kitchen_facing_name = models.CharField(
        _("Kitchen facing name"),
        max_length=120,
        blank=True,
        default="",
        help_text=_(
            "Short label for kitchen tickets / KDS (often lowercase, no spaces)."
        ),
    )
    tile_accent_color = models.CharField(
        _("Tile accent color"),
        max_length=16,
        blank=True,
        default="",
        help_text=_(
            "Preset key or #RRGGBB for POS tile styling when the layout tile has no accent override."
        ),
    )
    display_group = models.ForeignKey(
        "MenuDisplayGroup",
        on_delete=models.SET_NULL,
        related_name="menu_items",
        null=True,
        blank=True,
        help_text=_(
            "POS display group for this menu (one group per item; null = Home screen on the top-level grid)."
        ),
    )

    class Meta:
        verbose_name = _("Menu Item")
        verbose_name_plural = _("Menu Items")
        ordering = ["category", "display_order", "item__item_name"]

    def __str__(self):
        return f"{self.item.item_name}"

    def save(self, *args, **kwargs):
        if self.item_id and not (self.kitchen_facing_name or "").strip():
            name = self.item.item_name if self.item else ""
            slug = re.sub(r"[^a-zA-Z0-9]+", "", (name or "").lower())[:120]
            self.kitchen_facing_name = slug
        super().save(*args, **kwargs)

    def clean(self):
        if self.spice_level < 0 or self.spice_level > 5:
            raise ValidationError({"spice_level": "Spice level must be between 0 and 5"})
        if self.display_group_id:
            dg = self.display_group
            if self.menu_id and dg.menu_id != self.menu_id:
                raise ValidationError(
                    {
                        "display_group": _(
                            "Display group must belong to the same menu as this menu item."
                        )
                    }
                )
            if dg and MenuDisplayGroup.objects.filter(parent=dg).exists():
                raise ValidationError(
                    {
                        "display_group": _(
                            "This group contains sub-groups; assign items only to leaf groups."
                        )
                    }
                )


class RestaurantOrder(BaseModel):
    """Restaurant order management"""

    no = models.CharField(
        _("No."),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Order number"),
    )
    table = models.ForeignKey(
        Table, 
        on_delete=models.PROTECT, 
        related_name="orders",
        null=True,
        blank=True,
        help_text=_("Table is required for Dine In orders, optional for Takeaway/Delivery")
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.SET_NULL,
        related_name="orders",
        null=True,
        blank=True,
    )
    customer = models.ForeignKey(
        "sales.Customer",
        on_delete=models.SET_NULL,
        related_name="restaurant_orders",
        null=True,
        blank=True,
    )
    waiter = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="restaurant_orders"
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.NEW,
    )
    order_type = models.CharField(
        _("Order Type"),
        max_length=20,
        choices=OrderType.choices,
        default=OrderType.DINE_IN,
    )
    covers = models.PositiveIntegerField(
        _("Covers"),
        default=1,
        null=True,
        blank=True,
        help_text=_(
            "Number of guests (covers) for this order/check; null when not tracked (No covers)."
        ),
    )
    total_amount = models.DecimalField(
        _("Total Amount"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    notes = models.TextField(_("Notes"), blank=True, null=True)
    sales_invoice = models.ForeignKey(
        "sales.SalesInvoice",
        on_delete=models.SET_NULL,
        related_name="restaurant_orders",
        null=True,
        blank=True,
        help_text=_("Link to POS invoice when order is billed"),
    )
    global_dimension_1 = models.ForeignKey(
        "dimension.DimensionValue",
        on_delete=models.PROTECT,
        related_name="restaurant_orders",
        verbose_name=_("Branch (Global Dimension 1)"),
        help_text=_("Branch this order belongs to (set automatically from session context)."),
    )

    class Meta:
        verbose_name = _("Restaurant Order")
        verbose_name_plural = _("Restaurant Orders")
        ordering = ["-created_at"]

    def __str__(self):
        table_info = f"{self.table.table_number}" if self.table else "No Table"
        return f"{self.no} - {table_info} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.no:
            # Generate order number using number series
            try:
                order_series = NoSeries.objects.filter(code="REST-ORDER").first()
                if order_series:
                    no_series_line = NoSeriesLines.objects.filter(
                        no_series=order_series
                    ).first()
                    if no_series_line:
                        increment_by = no_series_line.increment_by
                        if no_series_line.last_used_number:
                            self.no = increment_item_number(
                                no_series_line.last_used_number, increment_by
                            )
                        else:
                            self.no = no_series_line.start_number
                        no_series_line.last_used_number = self.no
                        no_series_line.last_used_date = timezone.now().date()
                        no_series_line.save()
                    else:
                        self.no = f"REST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    self.no = f"REST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception as e:
                self.no = f"REST-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Calculate total from order items (excluding cancelled items)
        # Only recalculate if total_amount is NOT explicitly in update_fields
        # This prevents double calculation when recalculate_total() is called
        update_fields = kwargs.get('update_fields', None)
        should_recalculate = self.pk and (
            update_fields is None or 'total_amount' not in update_fields
        )
        
        if should_recalculate:
            from django.db import connection
            
            # Use raw SQL for reliability - directly query database
            # IMPORTANT: Use .value to get the string value of the enum
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COALESCE(SUM(total_price), 0) as total
                    FROM restaurant_management_restaurantorderitem
                    WHERE order_id = %s
                    AND status != %s
                """, [
                    self.id,
                    OrderItemStatus.CANCELLED.value,  # Use .value to get "cancelled" string
                ])
                row = cursor.fetchone()
                calculated_total = Decimal(str(row[0])) if row and row[0] is not None else Decimal('0.00')
            
            self.total_amount = calculated_total
            
            # Add total_amount to update_fields if it exists
            if update_fields is not None and 'total_amount' not in update_fields:
                update_fields = list(update_fields) + ['total_amount']
                kwargs['update_fields'] = update_fields

        super().save(*args, **kwargs)

    def recalculate_total(self):
        """Recalculate total from order items (excluding cancelled items)"""
        from django.db import connection
        
        # Use raw SQL query to be absolutely sure we're getting the right data
        # This bypasses any ORM caching or relationship issues
        # IMPORTANT: Use .value to get the string value of the enum
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(total_price), 0) as total
                FROM restaurant_management_restaurantorderitem
                WHERE order_id = %s
                AND status != %s
            """, [
                self.id,
                OrderItemStatus.CANCELLED.value,  # Use .value to get "cancelled" string
            ])
            row = cursor.fetchone()
            new_total = Decimal(str(row[0])) if row and row[0] is not None else Decimal('0.00')
        
        self.total_amount = new_total
        
        # Save with update_fields to prevent the save() method from recalculating
        self.save(update_fields=["total_amount"])


class RestaurantOrderItem(BaseModel):
    """Order line items"""

    order = models.ForeignKey(
        RestaurantOrder,
        on_delete=models.CASCADE,
        related_name="order_items",
    )
    restaurant_check = models.ForeignKey(
        "RestaurantCheck",
        on_delete=models.SET_NULL,
        related_name="order_items",
        null=True,
        blank=True,
        help_text=_("Optional check segment this item belongs to"),
    )
    item = models.ForeignKey(
        "items.Item", on_delete=models.PROTECT, related_name="restaurant_order_items"
    )
    quantity = models.DecimalField(
        _("Quantity"), max_digits=10, decimal_places=2, default=Decimal("1.00")
    )
    unit_price = models.DecimalField(
        _("Unit Price"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total_price = models.DecimalField(
        _("Total Price"), max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=OrderItemStatus.choices,
        default=OrderItemStatus.PENDING,
    )
    seat_no = models.PositiveIntegerField(
        _("Seat No."),
        null=True,
        blank=True,
        help_text=_("Seat assignment for service and split logic"),
    )
    course = models.CharField(
        _("Course"),
        max_length=20,
        choices=CourseType.choices,
        default=CourseType.STRAIGHT_FIRE,
    )
    fire_state = models.CharField(
        _("Fire State"),
        max_length=10,
        choices=FireState.choices,
        default=FireState.HOLD,
    )
    fired_at = models.DateTimeField(
        _("Fired At"),
        null=True,
        blank=True,
        help_text=_("When item was sent/fired to production"),
    )
    started_at = models.DateTimeField(
        _("Started At"),
        null=True,
        blank=True,
        help_text=_("When kitchen staff started preparation (pending → preparing)"),
    )
    special_instructions = models.TextField(_("Special Instructions"), blank=True, null=True)
    selected_sides = models.JSONField(
        _("Selected Sides"),
        default=list,
        blank=True,
        help_text=_("List of selected side items (e.g., ['fries', 'naan', 'rice'])"),
    )
    spice_level = models.IntegerField(
        _("Spice Level"),
        null=True,
        blank=True,
        help_text=_("Customer-selected spice level (0-5). If null, uses menu item default."),
    )
    preparation_time = models.IntegerField(
        _("Preparation Time (minutes)"),
        null=True,
        blank=True,
        help_text=_("Estimated preparation time"),
    )

    class Meta:
        verbose_name = _("Restaurant Order Item")
        verbose_name_plural = _("Restaurant Order Items")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.order.no} - {self.item.item_name} x {self.quantity}"

    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.quantity * self.unit_price
        if self.fire_state == FireState.FIRE and not self.fired_at:
            self.fired_at = timezone.now()

        # Get preparation time from menu item if not set
        if not self.preparation_time:
            try:
                menu_item = self.item.menu_item
                if menu_item:
                    self.preparation_time = menu_item.preparation_time
            except:
                pass

        # Check if this is a status update (which will be handled by the view)
        # We only skip recalculation if status is being updated to avoid double calculation
        is_status_update = 'status' in kwargs.get('update_fields', []) if kwargs.get('update_fields') else False
        
        super().save(*args, **kwargs)

        # Recalculate order total - but skip if this is just a status update
        # The view will handle recalculation for status updates to ensure fresh data
        if self.order_id and not is_status_update:
            # Get fresh order instance to avoid cached data
            from django.apps import apps
            Order = apps.get_model('restaurant_management', 'RestaurantOrder')
            try:
                order = Order.objects.get(id=self.order_id)
                order.recalculate_total()
            except Order.DoesNotExist:
                pass

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be greater than 0"})
        if self.unit_price < 0:
            raise ValidationError({"unit_price": "Unit price cannot be negative"})
        if self.spice_level is not None and (self.spice_level < 0 or self.spice_level > 5):
            raise ValidationError({"spice_level": "Spice level must be between 0 and 5"})


def restaurant_order_item_routes_to_kitchen(order_item: RestaurantOrderItem) -> bool:
    """
    True if this line belongs on KDS / should be included in POS kitchen Send.
    Matches ``_order_items_routes_to_kitchen_q`` in restaurant_management.views.
    """
    from django.core.exceptions import ObjectDoesNotExist

    try:
        item = order_item.item
    except ObjectDoesNotExist:
        return True
    try:
        menu_item = item.menu_item
    except ObjectDoesNotExist:
        return True
    if menu_item.routes_to_kitchen is True:
        return True
    if menu_item.routes_to_kitchen is False:
        return False
    cat = menu_item.category
    if cat is None:
        return True
    return bool(cat.routes_to_kitchen)


class Menu(BaseModel):
    """POS / builder menu (pages, tiles, time windows) linked to locations via MenuLocation."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("Menu")
        verbose_name_plural = _("Menus")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        raw_code = (self.code or "").strip()
        if not raw_code:
            try:
                menu_series = NoSeries.objects.filter(code="SERV-MENU").first()
                if menu_series:
                    no_series_line = NoSeriesLines.objects.filter(
                        no_series=menu_series
                    ).first()
                    if no_series_line:
                        increment_by = no_series_line.increment_by
                        if no_series_line.last_used_number:
                            raw_code = increment_item_number(
                                no_series_line.last_used_number, increment_by
                            )
                        else:
                            raw_code = no_series_line.start_number
                        no_series_line.last_used_number = raw_code
                        no_series_line.last_used_date = timezone.now().date()
                        no_series_line.save()
                    else:
                        raw_code = f"SMENU-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                else:
                    raw_code = f"SMENU-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception:
                raw_code = f"SMENU-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.code = raw_code[:50]
        super().save(*args, **kwargs)


class MenuLocation(BaseModel):
    """Links a Menu to an inventory Location (where it applies in POS)."""

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="locations")
    location = models.ForeignKey(
        "items.Location",
        on_delete=models.CASCADE,
        related_name="menu_location_links",
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = [("menu", "location")]
        verbose_name = _("Menu location")
        verbose_name_plural = _("Menu locations")


# Max levels of nested display groups (root = 0). 4 => root + 3 child group levels.
MENU_DISPLAY_GROUP_MAX_DEPTH = 4


class MenuDisplayGroup(BaseModel):
    menu = models.ForeignKey(
        Menu, on_delete=models.CASCADE, related_name="display_groups"
    )
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    tile_color = models.CharField(
        _("Tile color"),
        max_length=16,
        blank=True,
        default="",
        help_text=_("Preset key or #RRGGBB for POS tile background."),
    )
    icon = models.CharField(
        _("Icon key"),
        max_length=64,
        blank=True,
        default="",
        help_text=_("Optional icon identifier for POS (e.g. react-icons export name)."),
    )

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def depth_from_root(self) -> int:
        d = 0
        node = self
        while node.parent_id:
            d += 1
            node = node.parent
        return d

    def clean(self):
        if self.parent_id:
            if self.parent.menu_id != self.menu_id:
                raise ValidationError(
                    {"parent": _("Parent display group must belong to the same menu.")}
                )
            parent_depth = self.parent.depth_from_root()
            if parent_depth + 1 >= MENU_DISPLAY_GROUP_MAX_DEPTH:
                raise ValidationError(
                    {
                        "parent": _(
                            "Maximum display group nesting depth exceeded."
                        )
                    }
                )
        if self.pk:
            has_children = MenuDisplayGroup.objects.filter(parent=self).exists()
            has_items = MenuItem.objects.filter(display_group=self).exists()
            if has_children and has_items:
                raise ValidationError(
                    _(
                        "A display group cannot contain both sub-groups and menu items. "
                        "Remove items or remove sub-groups."
                    )
                )


class MenuLayoutPage(BaseModel):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="pages")
    page_number = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=100, default="Page")

    class Meta:
        unique_together = [("menu", "page_number")]
        ordering = ["menu", "page_number"]


class MenuLayoutTile(BaseModel):
    page = models.ForeignKey(
        MenuLayoutPage, on_delete=models.CASCADE, related_name="tiles"
    )
    display_group = models.ForeignKey(
        MenuDisplayGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="layout_tiles",
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="layout_tiles",
    )
    row = models.PositiveIntegerField(default=1)
    column = models.PositiveIntegerField(default=1)
    row_span = models.PositiveIntegerField(default=1)
    col_span = models.PositiveIntegerField(default=1)
    display_order = models.IntegerField(default=0)
    accent_color = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text=_("Preset key (e.g. indigo) or #RRGGBB for POS tile styling."),
    )

    class Meta:
        ordering = ["page", "display_order", "row", "column"]


class RestaurantCheck(BaseModel):
    order = models.ForeignKey(
        RestaurantOrder, on_delete=models.CASCADE, related_name="checks"
    )
    name = models.CharField(max_length=100, default="Check")
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.NEW,
    )
    seat_numbers = models.JSONField(default=list, blank=True)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_voided = models.BooleanField(default=False)
    is_comped = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]


class ModifierGroup(BaseModel):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    selection_mode = models.CharField(
        max_length=20,
        choices=[("single", "Single"), ("multiple", "Multiple")],
        default="single",
    )
    min_selections = models.PositiveIntegerField(default=0)
    max_selections = models.PositiveIntegerField(default=1)
    required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]


class ModifierOption(BaseModel):
    group = models.ForeignKey(
        ModifierGroup, on_delete=models.CASCADE, related_name="options"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("group", "code")]
        ordering = ["name"]


class MenuItemModifierGroup(BaseModel):
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name="modifier_groups"
    )
    modifier_group = models.ForeignKey(
        ModifierGroup, on_delete=models.CASCADE, related_name="menu_items"
    )
    required = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)

    class Meta:
        unique_together = [("menu_item", "modifier_group")]
        ordering = ["menu_item", "display_order"]


class OrderItemModifier(BaseModel):
    order_item = models.ForeignKey(
        RestaurantOrderItem, on_delete=models.CASCADE, related_name="modifiers"
    )
    modifier_group = models.ForeignKey(
        ModifierGroup, on_delete=models.PROTECT, related_name="order_item_modifiers"
    )
    modifier_option = models.ForeignKey(
        ModifierOption, on_delete=models.PROTECT, related_name="order_item_modifiers"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total_price_delta = self.unit_price_delta * self.quantity
        super().save(*args, **kwargs)


class OrderActionLog(BaseModel):
    order = models.ForeignKey(
        RestaurantOrder, on_delete=models.CASCADE, related_name="action_logs"
    )
    order_item = models.ForeignKey(
        RestaurantOrderItem,
        on_delete=models.SET_NULL,
        related_name="action_logs",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    action_type = models.CharField(max_length=40, choices=PosActionType.choices)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

