from django.db.models import Max
from rest_framework import serializers
from . import models
from .enums import OrderItemStatus, OrderStatus
from .order_guards import CLOSED_ORDER_ERROR, order_is_closed
from items.models import ItemImages, Item
from items.serializers import ImageSerializers


def _restaurant_order_line_primary_image_url(order_item, request):
    """First product image for the line's Item (same rules as POS menu tiles)."""
    if not request:
        return None
    item = getattr(order_item, "item", None)
    if not item:
        return None
    try:
        row = (
            ItemImages.objects.filter(item=item)
            .exclude(url__isnull=True)
            .exclude(url="")
            .order_by("-created_at")
            .first()
        )
        if not row or not row.url:
            return None
        rel = row.url.url
        if rel and str(rel).startswith(("http://", "https://")):
            return str(rel)
        return request.build_absolute_uri(rel)
    except Exception:
        return None


class ItemNoField(serializers.Field):
    """Custom field that handles Item's 'no' (string primary key) for both read and write"""
    
    def to_representation(self, value):
        """Return the item's 'no' value when reading"""
        if value is None:
            return None
        # If value is already a string (shouldn't happen, but handle it)
        if isinstance(value, str):
            return value
        # If value is an Item object, return its 'no' field
        if hasattr(value, 'no'):
            return value.no
        # Fallback: try to get the 'no' attribute
        try:
            return getattr(value, 'no', None)
        except:
            return None
    
    def to_internal_value(self, data):
        """Accept item 'no' string and return Item object when writing"""
        if data is None:
            return None
        if isinstance(data, str):
            try:
                return Item.objects.get(no=data)
            except Item.DoesNotExist:
                raise serializers.ValidationError(f"Item with no '{data}' not found")
        elif isinstance(data, Item):
            return data
        else:
            raise serializers.ValidationError("Item must be a string 'no' value or Item object")
    
    def get_attribute(self, instance):
        """Get the Item object from the MenuItem instance"""
        # Return the Item object from the MenuItem's 'item' field
        return getattr(instance, 'item', None)


class FloorSerializer(serializers.ModelSerializer):
    """Serializer for Floor model"""

    location_description = serializers.CharField(
        source="location.description", read_only=True, allow_null=True
    )

    class Meta:
        model = models.Floor
        fields = [
            "id",
            "no",
            "name",
            "description",
            "display_order",
            "location",
            "location_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "created_at", "updated_at", "location_description"]

    def validate(self, attrs):
        location = attrs.get("location", serializers.empty)
        if self.instance is None:
            if location is serializers.empty or location is None:
                raise serializers.ValidationError(
                    {"location": "Location is required when creating a floor plan."}
                )
            return attrs
        merged_location = (
            location
            if location is not serializers.empty
            else self.instance.location
        )
        if merged_location is None:
            raise serializers.ValidationError(
                {"location": "Location is required. Choose a location for this floor plan."}
            )
        return attrs


class FloorSectionSerializer(serializers.ModelSerializer):
    """Serializer for floor sections (table groupings)."""

    floor_name = serializers.CharField(source="floor.name", read_only=True)

    class Meta:
        model = models.FloorSection
        fields = [
            "id",
            "floor",
            "floor_name",
            "name",
            "display_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "floor_name"]


class TableSerializer(serializers.ModelSerializer):
    """Serializer for Table model"""

    floor_name = serializers.CharField(source="floor.name", read_only=True)
    section_name = serializers.CharField(
        source="section.name", read_only=True, allow_null=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    shape_display = serializers.CharField(source="get_shape_display", read_only=True)

    class Meta:
        model = models.Table
        fields = [
            "id",
            "no",
            "table_number",
            "floor",
            "floor_name",
            "section",
            "section_name",
            "capacity",
            "status",
            "status_display",
            "shape",
            "shape_display",
            "location_x",
            "location_y",
            "plan_width",
            "plan_height",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "created_at", "updated_at", "section_name"]


class ReservationSerializer(serializers.ModelSerializer):
    """Serializer for Reservation model"""

    customer_name = serializers.CharField(source="customer.name", read_only=True)
    table_number = serializers.CharField(source="table.table_number", read_only=True, allow_null=True)
    waiter_name = serializers.CharField(source="waiter.full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = models.Reservation
        fields = [
            "id",
            "no",
            "customer",
            "customer_name",
            "table",
            "table_number",
            "reservation_date",
            "party_size",
            "status",
            "status_display",
            "special_requests",
            "waiter",
            "waiter_name",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "created_at", "updated_at"]


class MenuCategorySerializer(serializers.ModelSerializer):
    """Serializer for MenuCategory model"""

    class Meta:
        model = models.MenuCategory
        fields = [
            "id",
            "no",
            "name",
            "description",
            "display_order",
            "is_active",
            "routes_to_kitchen",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "created_at", "updated_at"]


class MenuItemSerializer(serializers.ModelSerializer):
    """Serializer for MenuItem model"""

    # Use custom field that handles Item's 'no' (string primary key)
    item = ItemNoField()
    item_no = serializers.CharField(source="item.no", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    unit_price = serializers.IntegerField(source="item.unit_price", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    item_images = serializers.SerializerMethodField()

    def to_representation(self, instance):
        """Override to ensure item field always returns the 'no' value"""
        ret = super().to_representation(instance)
        
        # Ensure item field returns the 'no' value (primary key from Items.tsx)
        if instance.item:
            ret['item'] = instance.item.no
            # Also ensure item_no is set (should already be set, but double-check)
            if 'item_no' not in ret or not ret['item_no']:
                ret['item_no'] = instance.item.no
        
        return ret

    class Meta:
        model = models.MenuItem
        fields = [
            "id",
            "system_id",
            "item",
            "item_no",
            "item_name",
            "unit_price",
            "category",
            "category_name",
            "menu",
            "display_group",
            "description",
            "image",
            "item_images",
            "is_available",
            "routes_to_kitchen",
            "preparation_time",
            "is_featured",
            "spice_level",
            "available_sides",
            "dietary_info",
            "allergens",
            "display_order",
            "kitchen_facing_name",
            "tile_accent_color",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["system_id", "created_at", "updated_at"]

    def create(self, validated_data):
        instance = models.MenuItem(**validated_data)
        instance.full_clean()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        return instance

    def get_item_images(self, obj):
        """Get item images from the linked Item"""
        if obj.item:
            images = ItemImages.objects.filter(item=obj.item)
            return ImageSerializers(images, many=True, context=self.context).data
        return []


class RestaurantOrderItemSerializer(serializers.ModelSerializer):
    """Serializer for RestaurantOrderItem model"""

    # Use custom field that handles Item's 'no' (string primary key)
    item = ItemNoField()
    item_no = serializers.CharField(source="item.no", read_only=True)
    item_name = serializers.CharField(source="item.item_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    routes_to_kitchen = serializers.SerializerMethodField()
    # Make order read-only when used as nested serializer (order is set by parent)
    order = serializers.PrimaryKeyRelatedField(read_only=True)
    waiter_name = serializers.CharField(
        source="order.waiter.full_name", read_only=True, allow_null=True
    )
    order_no = serializers.CharField(source="order.no", read_only=True)
    table_number = serializers.CharField(
        source="order.table.table_number", read_only=True, allow_null=True
    )
    course_display = serializers.CharField(source="get_course_display", read_only=True)
    fire_state_display = serializers.CharField(
        source="get_fire_state_display", read_only=True
    )
    primary_image_url = serializers.SerializerMethodField()

    def get_routes_to_kitchen(self, obj):
        return models.restaurant_order_item_routes_to_kitchen(obj)

    def get_primary_image_url(self, obj):
        return _restaurant_order_line_primary_image_url(
            obj, self.context.get("request")
        )

    class Meta:
        model = models.RestaurantOrderItem
        fields = [
            "id",
            "order",
            "restaurant_check",
            "item",
            "item_no",
            "item_name",
            "primary_image_url",
            "quantity",
            "unit_price",
            "total_price",
            "status",
            "status_display",
            "routes_to_kitchen",
            "seat_no",
            "course",
            "course_display",
            "fire_state",
            "fire_state_display",
            "fired_at",
            "started_at",
            "special_instructions",
            "selected_sides",
            "spice_level",
            "preparation_time",
            "waiter_name",
            "order_no",
            "table_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["order", "total_price", "created_at", "updated_at", "started_at"]


class RestaurantOrderSerializer(serializers.ModelSerializer):
    """Serializer for RestaurantOrder model"""

    table_number = serializers.CharField(source="table.table_number", read_only=True, allow_null=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    waiter_name = serializers.CharField(source="waiter.full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    order_type_display = serializers.CharField(
        source="get_order_type_display", read_only=True
    )
    order_items = RestaurantOrderItemSerializer(many=True, read_only=True)
    reservation_no = serializers.CharField(source="reservation.no", read_only=True)
    ready_items_count = serializers.SerializerMethodField()
    active_checks = serializers.SerializerMethodField()
    
    def get_ready_items_count(self, obj):
        """Count items with ready status"""
        if hasattr(obj, 'ready_items_count'):
            # Use annotated count if available (from ready_orders query)
            return obj.ready_items_count
        # Fallback: count from order_items if available
        if hasattr(obj, 'order_items'):
            return sum(1 for item in obj.order_items.all() if item.status == 'ready')
        return 0

    def get_active_checks(self, obj):
        return list(
            obj.checks.filter(is_voided=False)
            .exclude(status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELLED])
            .values(
                "id",
                "name",
                "status",
                "subtotal_amount",
                "total_amount",
                "seat_numbers",
            )
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "covers" not in attrs:
            return attrs
        covers = attrs["covers"]
        inst = getattr(self, "instance", None)
        if not inst or not getattr(inst, "pk", None):
            return attrs

        max_seat = (
            inst.order_items.exclude(status=OrderItemStatus.CANCELLED)
            .filter(seat_no__isnull=False)
            .aggregate(m=Max("seat_no"))
            .get("m")
        ) or 0

        if covers is None:
            if max_seat > 0:
                raise serializers.ValidationError(
                    {
                        "covers": "Cannot clear covers while items are assigned to seats.",
                    }
                )
            return attrs

        if max_seat and covers < max_seat:
            raise serializers.ValidationError(
                {
                    "covers": (
                        f"Cover count cannot be less than the highest assigned seat ({max_seat})."
                    ),
                }
            )
        return attrs

    global_dimension_1 = serializers.IntegerField(
        source="global_dimension_1_id", allow_null=True, read_only=True
    )

    class Meta:
        model = models.RestaurantOrder
        fields = [
            "id",
            "no",
            "table",
            "table_number",
            "reservation",
            "reservation_no",
            "customer",
            "customer_name",
            "waiter",
            "waiter_name",
            "status",
            "status_display",
            "order_type",
            "order_type_display",
            "covers",
            "total_amount",
            "notes",
            "sales_invoice",
            "global_dimension_1",
            "order_items",
            "ready_items_count",
            "active_checks",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "total_amount", "created_at", "updated_at"]


class RestaurantOrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating RestaurantOrder with items"""

    order_items = RestaurantOrderItemSerializer(many=True, required=False)

    class Meta:
        model = models.RestaurantOrder
        fields = [
            "id",
            "table",
            "reservation",
            "customer",
            "waiter",
            "status",
            "order_type",
            "covers",
            "notes",
            "order_items",
        ]
        extra_kwargs = {
            "table": {"required": False, "allow_null": True},
        }

    def validate(self, attrs):
        """Validate that table is provided for Dine In orders"""
        if self.instance and order_is_closed(self.instance):
            raise serializers.ValidationError(CLOSED_ORDER_ERROR)

        order_type = attrs.get("order_type", getattr(self.instance, "order_type", None))
        table = attrs.get("table", getattr(self.instance, "table", None))
        
        if order_type == "dine_in" and not table:
            raise serializers.ValidationError({
                "table": "Table is required for Dine In orders"
            })
        
        return attrs

    def create(self, validated_data):
        order_items_data = validated_data.pop("order_items", [])
        request = self.context.get("request")
        if request:
            from dimension.branch_filter import get_branch_for_request

            br = get_branch_for_request(request)
            if br and "global_dimension_1" not in validated_data:
                validated_data["global_dimension_1"] = br
        order = models.RestaurantOrder.objects.create(**validated_data)
        
        # Resolve items by 'no' if they're strings (Item uses 'no' as primary key)
        from items.models import Item
        for item_data in order_items_data:
            # Resolve item by 'no' if it's a string
            if 'item' in item_data and isinstance(item_data['item'], str):
                try:
                    item_obj = Item.objects.get(no=item_data['item'])
                    item_data['item'] = item_obj
                except Item.DoesNotExist:
                    raise serializers.ValidationError(
                        f"Item with no '{item_data['item']}' not found"
                    )
            
            models.RestaurantOrderItem.objects.create(order=order, **item_data)
        
        # Recalculate total and refresh from database to get the updated total_amount
        order.recalculate_total()
        order.refresh_from_db()
        return order

    def to_internal_value(self, data):
        """Override to manually validate nested order_items"""
        # Get the raw order_items data before validation
        order_items_raw = data.get('order_items', None)
        
        # Call parent to validate other fields
        validated = super().to_internal_value(data)
        
        # Manually validate order_items if present
        if order_items_raw is not None:
            order_items_serializer = RestaurantOrderItemSerializer(many=True, data=order_items_raw)
            if order_items_serializer.is_valid():
                validated['order_items'] = order_items_serializer.validated_data
            else:
                raise serializers.ValidationError({
                    'order_items': order_items_serializer.errors
                })
        
        return validated

    def update(self, instance, validated_data):
        if order_is_closed(instance):
            raise serializers.ValidationError(CLOSED_ORDER_ERROR)
        # Extract order_items from validated_data (already validated by nested serializer)
        order_items_data = validated_data.pop("order_items", None)
        
        # Update order fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle order_items if provided
        if order_items_data is not None and len(order_items_data) > 0:
            # Delete existing order items if replacing
            instance.order_items.all().delete()
            
            # Create new order items (item is already resolved to Item object by nested serializer)
            from .enums import OrderItemStatus
            from items.models import Item
            
            for item_data in order_items_data:
                # Ensure item is an Item object (should already be resolved by nested serializer)
                item = item_data.get('item')
                if isinstance(item, str):
                    # Fallback: if item is still a string, resolve it
                    try:
                        item = Item.objects.get(no=item)
                    except Item.DoesNotExist:
                        raise serializers.ValidationError(
                            f"Item with no '{item_data.get('item')}' not found"
                        )
                
                models.RestaurantOrderItem.objects.create(
                    order=instance,
                    item=item,
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('unit_price', 0),
                    special_instructions=item_data.get('special_instructions'),
                    selected_sides=item_data.get('selected_sides', []),
                    spice_level=item_data.get('spice_level'),
                    status=item_data.get('status', OrderItemStatus.PENDING),
                )
            
            # Recalculate total and refresh from database
            instance.recalculate_total()
            instance.refresh_from_db()
        
        return instance


class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Menu
        fields = "__all__"
        extra_kwargs = {
            "code": {"required": False, "allow_blank": True},
        }

    def create(self, validated_data):
        # Optional field omitted from JSON is absent from validated_data; model.save() assigns code when blank.
        if not validated_data.get("code"):
            validated_data["code"] = ""
        return super().create(validated_data)


class MenuLocationSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = models.MenuLocation
        fields = "__all__"


class MenuDisplayGroupSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = models.MenuDisplayGroup
        fields = [
            "id",
            "menu",
            "name",
            "parent",
            "display_order",
            "is_active",
            "tile_color",
            "icon",
            "children",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        instance = models.MenuDisplayGroup(**validated_data)
        instance.full_clean()
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.full_clean()
        instance.save()
        return instance

    def get_children(self, obj):
        cache = getattr(obj, "_prefetched_objects_cache", None)
        if cache and "children" in cache:
            ch = list(cache["children"])
            ch.sort(key=lambda c: (c.display_order, c.name))
        else:
            ch = obj.children.order_by("display_order", "name")
        return MenuDisplayGroupSerializer(ch, many=True).data


class MenuLayoutTileSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.item.item_name", read_only=True)
    display_group_name = serializers.CharField(source="display_group.name", read_only=True)
    is_orderable_leaf = serializers.SerializerMethodField()
    item_no = serializers.CharField(
        source="menu_item.item.no", read_only=True, allow_null=True
    )
    menu_item_unit_price = serializers.DecimalField(
        source="menu_item.item.unit_price",
        max_digits=12,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    kitchen_facing_name = serializers.CharField(
        source="menu_item.kitchen_facing_name",
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )

    class Meta:
        model = models.MenuLayoutTile
        fields = "__all__"

    def validate(self, attrs):
        inst = self.instance
        mi = attrs["menu_item"] if "menu_item" in attrs else (
            getattr(inst, "menu_item", None) if inst else None
        )
        dg = attrs["display_group"] if "display_group" in attrs else (
            getattr(inst, "display_group", None) if inst else None
        )
        if mi is not None and dg is not None:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Link either a menu item or a display group on a tile, not both."
                    ]
                }
            )
        page = attrs.get("page") or (inst.page if inst else None)
        if dg is not None and page is not None:
            if getattr(dg, "menu_id", None) != page.menu_id:
                raise serializers.ValidationError(
                    {"display_group": "Display group must belong to the same menu as the page."}
                )
        return attrs

    def get_is_orderable_leaf(self, obj):
        return obj.menu_item_id is not None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.menu_item_id and getattr(instance, "menu_item", None):
            ret["menu_item_tile_accent_color"] = (
                (instance.menu_item.tile_accent_color or "").strip()
            )
        else:
            ret["menu_item_tile_accent_color"] = ""
        return ret


class MenuLayoutPageSerializer(serializers.ModelSerializer):
    tiles = MenuLayoutTileSerializer(many=True, read_only=True)

    class Meta:
        model = models.MenuLayoutPage
        fields = "__all__"


class RestaurantCheckSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source="order.no", read_only=True)

    class Meta:
        model = models.RestaurantCheck
        fields = "__all__"


class ModifierOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ModifierOption
        fields = "__all__"


class ModifierGroupSerializer(serializers.ModelSerializer):
    options = ModifierOptionSerializer(many=True, read_only=True)

    class Meta:
        model = models.ModifierGroup
        fields = "__all__"


class MenuItemModifierGroupSerializer(serializers.ModelSerializer):
    modifier_group_name = serializers.CharField(
        source="modifier_group.name", read_only=True
    )

    class Meta:
        model = models.MenuItemModifierGroup
        fields = "__all__"


class OrderItemModifierSerializer(serializers.ModelSerializer):
    modifier_group_name = serializers.CharField(
        source="modifier_group.name", read_only=True
    )
    modifier_option_name = serializers.CharField(
        source="modifier_option.name", read_only=True
    )

    class Meta:
        model = models.OrderItemModifier
        fields = "__all__"

    def validate(self, attrs):
        group = attrs.get("modifier_group") or getattr(
            self.instance, "modifier_group", None
        )
        option = attrs.get("modifier_option") or getattr(
            self.instance, "modifier_option", None
        )
        order_item = attrs.get("order_item") or getattr(
            self.instance, "order_item", None
        )
        if group and option and option.group_id != group.id:
            raise serializers.ValidationError(
                {"modifier_option": "Option does not belong to the selected group."}
            )
        if group and order_item:
            existing = models.OrderItemModifier.objects.filter(
                order_item=order_item, modifier_group=group
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            next_count = existing.count() + 1
            if next_count > group.max_selections:
                raise serializers.ValidationError(
                    {"modifier_group": "Maximum selections exceeded for this group."}
                )
        return attrs


class OrderActionLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True)

    class Meta:
        model = models.OrderActionLog
        fields = "__all__"

