from django.db.models import Sum

from rest_framework import serializers

from items.models import (
    Item,
    ItemImages,
    TrackingSpecification,
    ItemTrackingCodes,
    Location,
    ValueEntry,
    ItemUnitOfMeasure,
    ItemJournal,
    ItemJournalBatch,
    get_default_item_journal_batch,
    get_default_item_journal_template,
    ItemAttribute,
    ItemAttributeValue,
    ItemAttributeEntry,
)
from production.models import ProductionBOM
from financials.models import G_LAccount
from .models import ItemCategory, UnitOfMeasure, ItemLedgerEntries
from authentication.models import CustomUser as User
from items.enums import EntryType


class ImageSerializers(serializers.ModelSerializer):

    class Meta:
        model = ItemImages
        fields = "__all__"


class ItemImagesSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(),
        slug_field="no",
    )

    class Meta:
        model = ItemImages
        fields = ["id", "item", "url", "alt_text"]
        extra_kwargs = {"url": {"required": True}}

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.url:
            request = self.context.get("request")
            if request:
                data["url"] = request.build_absolute_uri(instance.url.url)
            else:
                data["url"] = instance.url.url
        return data

    def validate_url(self, value):
        if not value:
            return value
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if getattr(value, "content_type", None) and value.content_type not in allowed:
            raise serializers.ValidationError(
                "Only JPEG, PNG, or WebP images are allowed."
            )
        if value.size > 500_000:
            raise serializers.ValidationError(
                "Image must be 500 KB or smaller."
            )
        return value


class ItemUnitOfMeasureSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(), slug_field="no", allow_null=True, required=False
    )
    unit_of_measure = serializers.SlugRelatedField(
        queryset=UnitOfMeasure.objects.all(),
        slug_field="code",
    )
    unit_of_measure_description = serializers.CharField(
        source="unit_of_measure.description", read_only=True
    )

    effective_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        help_text="Effective price: uses price if set, otherwise calculates from item.unit_price * quantity_per_unit",
    )

    class Meta:
        model = ItemUnitOfMeasure
        fields = [
            "system_id",
            "id",
            "item",
            "unit_of_measure",
            "unit_of_measure_description",
            "quantity_per_unit",
            "default",
            "price",
            "effective_price",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate that default ItemUnitOfMeasure must have quantity_per_unit = 1 and prevent unsetting last default"""
        default = attrs.get(
            "default", self.instance.default if self.instance else False
        )
        quantity_per_unit = attrs.get(
            "quantity_per_unit",
            self.instance.quantity_per_unit if self.instance else None,
        )

        # Validate quantity_per_unit for default ItemUnitOfMeasure
        if default and quantity_per_unit is not None and quantity_per_unit != 1:
            raise serializers.ValidationError(
                {
                    "quantity_per_unit": "Qty. per Unit of Measure must be equal to '1' in Item Unit of Measure."
                }
            )

        # Prevent unsetting the last default
        if self.instance and self.instance.default and not default:
            # Check if this is the only default for this item
            item = attrs.get("item", self.instance.item)
            other_defaults = ItemUnitOfMeasure.objects.filter(
                item=item, default=True
            ).exclude(pk=self.instance.pk)

            if not other_defaults.exists():
                raise serializers.ValidationError(
                    {
                        "default": "Cannot unset default. An item must always have a default unit of measure."
                    }
                )

        return attrs


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "code", "description", "address", "city", "phone", "email"]
        read_only_fields = ["id"]


class ItemTrackingCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemTrackingCodes
        fields = [
            "system_id",
            "code",
            "description",
            "require_serial_no",
            "require_lot_no",
            "require_expiry_date",
        ]


class CustomTrackingCodeRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        serializer = ItemTrackingCodeSerializer(value)
        return serializer.data

    def to_internal_value(self, data):
        try:
            return ItemTrackingCodes.objects.get(code=data)
        except ItemTrackingCodes.DoesNotExist:
            raise serializers.ValidationError(
                "Tracking code with this code does not exist."
            )
        except TypeError:
            raise serializers.ValidationError("Invalid format for tracking code.")


class ItemSerializer(serializers.ModelSerializer):
    item_images = serializers.SerializerMethodField()
    # Note: Item uses 'no' (CharField) as primary key, not an auto-incrementing 'id'
    # We'll add item_id in to_representation using pk
    inventory = serializers.SerializerMethodField()
    uom_options = serializers.SerializerMethodField()
    markup_percentage = serializers.SerializerMethodField()
    profit_percentage = serializers.SerializerMethodField()
    unit_cost = serializers.IntegerField(required=False, allow_null=True)
    item_units_of_measure = ItemUnitOfMeasureSerializer(
        many=True, read_only=True, source="itemunitofmeasure_set"
    )
    tracking_code = CustomTrackingCodeRelatedField(
        queryset=ItemTrackingCodes.objects.all(),
        allow_null=True,
        required=False,
    )
    attribute_entries = serializers.SerializerMethodField()
    production_bom = serializers.PrimaryKeyRelatedField(
        queryset=ProductionBOM.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Item
        # fields = "__all__"
        exclude = [
            "general_product_posting_group",
            "inventory_posting_group",
            "manual_unit_cost",  # Hide internal field from API
            "manufacturing_policy",  # Admin only; not exposed to frontend yet
            # 'created_at',
            # 'updated_at',
            # 'system_id',
            # Add any other fields you want to exclude
        ]

        # fields = [
        #     "no",
        #     "item_id",
        #     "bar_code_no",
        #     "system_id",
        #     "item_name",
        #     "inventory",
        #     "unit_price",
        #     "item_images",
        # ]

    def get_inventory(self, obj):
        """Branch-filtered inventory when multi-branch is enabled."""
        if getattr(obj, "type", None) in ("Service", "Non-Inventory"):
            return None
        request = self.context.get("request")
        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
            if (
                gl_setup
                and getattr(gl_setup, "enable_multiple_branches", False)
                and request
            ):
                from dimension.branch_filter import get_branch_for_request

                branch = get_branch_for_request(request)
                if not branch:
                    branch = getattr(request.user, "global_dimension_1", None)
                if branch:
                    result = ItemLedgerEntries.objects.filter(
                        item=obj, global_dimension_1=branch
                    ).aggregate(total=Sum("remaining_quantity"))
                    return result["total"] or 0
        except ImportError:
            pass
        return obj.inventory

    def get_item_images(self, obj):
        # Query the ItemImages model for the images related to this item
        images = ItemImages.objects.filter(item=obj)
        return ImageSerializers(images, many=True, context=self.context).data

    def get_uom_options(self, obj):
        return obj.get_available_uoms

    def get_markup_percentage(self, obj):
        return obj.markup_percentage

    def get_profit_percentage(self, obj):
        return obj.profit_percentage

    def get_unit_cost(self, obj):
        """
        Return a branch/location-aware unit cost for Inventory items.

        - Branch is resolved from request (X-Branch-Id) or user.global_dimension_1.
        - Location is derived by convention: Location.code == branch.code.
        - Falls back to the model's global unit_cost property when context cannot be resolved.
        """
        # Service + Non-Inventory use manual (global) cost — never use list annotation
        # (multi-branch list annotates 0 when there is no on-hand stock).
        if getattr(obj, "type", None) in ["Service", "Non-Inventory"]:
            return obj.unit_cost

        # If viewset annotated the value (list payload), use it to avoid N+1 queries.
        annotated = getattr(obj, "_unit_cost_context", None)
        if annotated is not None:
            return annotated

        request = self.context.get("request")
        if not request:
            return obj.unit_cost

        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
            if not (gl_setup and getattr(gl_setup, "enable_multiple_branches", False)):
                return obj.unit_cost

            from dimension.branch_filter import get_branch_for_request

            branch = get_branch_for_request(request) or getattr(
                request.user, "global_dimension_1", None
            )
            if not branch:
                return obj.unit_cost

            # Location convention: location code matches branch code.
            loc = Location.objects.filter(
                code__iexact=getattr(branch, "code", "")
            ).first()

            # Prefer branch+location latest value-entry cost when available.
            # Do not gate by remaining_quantity; items can be out of stock but still
            # need to display the latest buying price.
            ve_branch_qs = ValueEntry.objects.filter(item=obj, global_dimension_1=branch)

            if loc:
                ve_loc_qs = ve_branch_qs.filter(location_code=loc)
                ve = ve_loc_qs.order_by("-created_at").first()
                if ve and ve.cost_per_unit:
                    return ve.cost_per_unit

            # Fallback: branch-wide cost when branch-location convention does not match
            # where the stock was posted for this item.
            ve = ve_branch_qs.order_by("-created_at").first()
            if ve and ve.cost_per_unit:
                return ve.cost_per_unit
            return 0
        except Exception:
            # Be defensive: never break item APIs due to missing setups/data.
            return obj.unit_cost

        return obj.unit_cost

    def get_attribute_entries(self, obj):
        """Get all attribute entries for this item"""
        if not obj or not obj.system_id:
            return []

        entries = (
            ItemAttributeEntry.objects.filter(item=obj)
            .select_related("attribute")
            .prefetch_related("selected_values")
        )
        return ItemAttributeEntrySerializer(entries, many=True).data

    def _get_production_bom_repr(self, obj):
        """Get production BOM summary for this item (when manufacturing is enabled)."""
        if not obj or not hasattr(obj, "production_bom") or not obj.production_bom:
            return None
        bom = obj.production_bom
        return {
            "id": bom.id,
            "bomCode": bom.bom_code,
            "name": bom.name,
            "lineCount": bom.lines.count() if hasattr(bom, "lines") else 0,
        }

    def to_representation(self, instance):
        """Override to return calculated unit_cost for reading and apply user permissions"""
        representation = super().to_representation(instance)
        # Replace production_bom pk with nested object for API response (PrimaryKeyRelatedField returns id otherwise)
        representation["production_bom"] = self._get_production_bom_repr(instance)

        # Item uses 'no' as primary key (CharField), but we need a numeric item_id for BOM linking
        # Since Django doesn't auto-generate an 'id' field when using custom PK, we use 'no' here
        # Note: The frontend expects item_id to be the unique identifier for BOM operations
        representation["item_id"] = instance.no

        # Present a single unit_cost field that is branch/location-aware when multi-branch is enabled.
        representation["unit_cost"] = self.get_unit_cost(instance)

        # Apply user permissions to hide sensitive pricing information
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            from authentication.models import UserSetup

            try:
                user_setup = UserSetup.objects.select_related("user").get(
                    user=request.user
                )

                # Hide buying price/cost if user doesn't have permission
                if not user_setup.can_see_buying_price:
                    representation.pop("unit_cost", None)
                    representation.pop("last_direct_cost", None)

                # Hide profit margins if user doesn't have permission
                if not user_setup.can_see_profit_margin:
                    representation.pop("markup_percentage", None)
                    representation.pop("profit_percentage", None)

            except UserSetup.DoesNotExist:
                # If no user setup exists, create one with default permissions (all granted)
                UserSetup.get_or_create_for_user(request.user)

        return representation

    def update(self, instance, validated_data):
        """Handle unit_cost updates for Service and Non-Inventory items"""
        unit_cost_value = validated_data.pop("unit_cost", None)

        # Save manual_unit_cost for Service/Non-Inventory items
        if (
            instance.type in ["Service", "Non-Inventory"]
            and unit_cost_value is not None
        ):
            instance.manual_unit_cost = unit_cost_value

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    def create(self, validated_data):
        """Handle unit_cost creation for Service and Non-Inventory items"""
        unit_cost_value = validated_data.pop("unit_cost", None)

        # Create the item
        item = Item.objects.create(**validated_data)

        # Set manual_unit_cost for Service/Non-Inventory items
        if item.type in ["Service", "Non-Inventory"] and unit_cost_value is not None:
            item.manual_unit_cost = unit_cost_value
            item.save()

        return item


class ItemListSerializer(serializers.ModelSerializer):
    """
    Lean list payload for the Items grid and item pickers (Sales, modals).
    Omits attribute_entries, nested tracking payloads, and production BOM detail;
    retrieve still uses ItemSerializer for the full shape.
    """

    item_images = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()
    uom_options = serializers.SerializerMethodField()
    item_units_of_measure = ItemUnitOfMeasureSerializer(
        many=True, read_only=True, source="itemunitofmeasure_set"
    )
    tracking_code = serializers.SerializerMethodField()
    item_category = serializers.CharField(
        source="item_category.code", read_only=True, allow_null=True
    )
    unit_of_measure = serializers.CharField(
        source="unit_of_measure.code", read_only=True, allow_null=True
    )

    class Meta:
        model = Item
        fields = [
            "no",
            "system_id",
            "item_name",
            "bar_code_no",
            "shelf_no",
            "minimum_stock",
            "type",
            "blocked",
            "unit_price",
            "costing_method",
            "description",
            "item_category",
            "unit_of_measure",
            "created_at",
            "updated_at",
            "item_images",
            "inventory",
            "uom_options",
            "item_units_of_measure",
            "tracking_code",
        ]

    def _list_user_setup(self):
        cache_key = "_item_list_user_setup"
        if cache_key in self.context:
            return self.context[cache_key]
        request = self.context.get("request")
        user_setup = None
        if request and hasattr(request, "user"):
            from authentication.models import UserSetup

            try:
                user_setup = UserSetup.objects.select_related("user").get(
                    user=request.user
                )
            except UserSetup.DoesNotExist:
                user_setup = UserSetup.get_or_create_for_user(request.user)
        self.context[cache_key] = user_setup
        return user_setup

    def _unit_cost_helper(self):
        helper = self.context.get("_item_list_unit_cost_helper")
        if helper is None:
            helper = ItemSerializer(context=self.context)
            self.context["_item_list_unit_cost_helper"] = helper
        return helper

    def get_item_images(self, obj):
        cache = getattr(obj, "_prefetched_objects_cache", None)
        if cache and "itemimages_set" in cache:
            images = list(cache["itemimages_set"])[:1]
        else:
            images = list(
                ItemImages.objects.filter(item=obj).order_by("-created_at")[:1]
            )
        return ImageSerializers(images, many=True, context=self.context).data

    def get_tracking_code(self, obj):
        t = getattr(obj, "tracking_code", None)
        if not t:
            return None
        return {
            "system_id": str(t.system_id),
            "code": t.code,
            "description": t.description or "",
            "require_serial_no": t.require_serial_no,
            "require_lot_no": t.require_lot_no,
            "require_expiry_date": t.require_expiry_date,
        }

    def get_uom_options(self, obj):
        cache = getattr(obj, "_prefetched_objects_cache", None)
        if cache and "itemunitofmeasure_set" in cache:
            rels = list(cache["itemunitofmeasure_set"])
        else:
            rels = list(
                obj.itemunitofmeasure_set.select_related("unit_of_measure").all()
            )
        return [
            {
                "code": rel.unit_of_measure.code,
                "description": rel.unit_of_measure.description,
                "default": rel.default,
                "quantity_per_unit": rel.quantity_per_unit,
            }
            for rel in rels
        ]

    def get_inventory(self, obj):
        if getattr(obj, "type", None) in ("Service", "Non-Inventory"):
            return None
        if getattr(obj, "inventory_total", None) is not None:
            return obj.inventory_total or 0
        v = getattr(obj, "_list_inventory", None)
        if v is not None:
            return int(v)
        request = self.context.get("request")
        try:
            from financials.models import GeneralLedgerSetup

            gl_setup = GeneralLedgerSetup.objects.first()
            if (
                gl_setup
                and getattr(gl_setup, "enable_multiple_branches", False)
                and request
            ):
                from dimension.branch_filter import get_branch_for_request

                branch = get_branch_for_request(request)
                if not branch:
                    branch = getattr(request.user, "global_dimension_1", None)
                if branch:
                    result = ItemLedgerEntries.objects.filter(
                        item=obj, global_dimension_1=branch
                    ).aggregate(total=Sum("remaining_quantity"))
                    return result["total"] or 0
        except ImportError:
            pass
        return obj.inventory

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["item_id"] = instance.no
        user_setup = self._list_user_setup()
        if user_setup is None or user_setup.can_see_buying_price:
            representation["unit_cost"] = self._unit_cost_helper().get_unit_cost(
                instance
            )
        return representation


class ItemCategorySerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        queryset=ItemCategory.objects.all(),
        source="parent",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ItemCategory
        fields = [
            "system_id",
            "code",
            "description",
            "parent_id",
            "level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["system_id", "level", "created_at", "updated_at"]


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitOfMeasure
        fields = ["system_id", "code", "description", "created_at", "updated_at"]
        read_only_fields = ["system_id", "created_at", "updated_at"]


class ItemLedgerEntriesSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.description", read_only=True)
    unit_of_measure_code = serializers.CharField(
        source="unit_of_measure.code", read_only=True
    )

    class Meta:
        model = ItemLedgerEntries
        fields = [
            "id",
            "posting_date",
            "entry_type",
            "document_type",
            "document_no",
            "description",
            "location_name",
            "quantity",
            "remaining_quantity",
            "unit_of_measure_code",
            "lot_no",
            "serial_no",
            "expiry_date",
            "total",
            "date",
            "created_at",
        ]


class TrackingSpecificationSerializer(serializers.ModelSerializer):
    source_template_name = serializers.SerializerMethodField()
    source_batch_display = serializers.SerializerMethodField()

    class Meta:
        model = TrackingSpecification
        fields = "__all__"

    def get_source_template_name(self, obj):
        return obj.source_template.name if obj.source_template else None

    def get_source_batch_display(self, obj):
        if obj.source_batch:
            return f"{obj.source_batch.journal_template.name} - {obj.source_batch.name}"
        return None

    def validate_serial_no(self, value):
        # Model.save enforces inbound uniqueness / outbound availability.
        if not value or not str(value).strip():
            return value
        return str(value).strip()

    def update(self, instance, validated_data):
        # get creat user from request
        user = self.context["request"].user
        user = User.objects.get(id=user.id)
        dimension = getattr(user, "global_dimension_1", None)
        if not dimension:
            raise serializers.ValidationError(
                {"location_code": "User does not have a default location assigned."}
            )
        location = Location.objects.filter(code=dimension.code).first()
        if not location:
            raise serializers.ValidationError(
                {"location_code": f"Location '{dimension.code}' not found."}
            )
        validated_data["location_code"] = location
        return super().update(instance, validated_data)

    def create(self, validated_data):
        user = self.context["request"].user
        user = User.objects.get(id=user.id)
        dimension = getattr(user, "global_dimension_1", None)
        if not dimension:
            raise serializers.ValidationError(
                {"location_code": "User does not have a default location assigned."}
            )
        location = Location.objects.filter(code=dimension.code).first()
        if not location:
            raise serializers.ValidationError(
                {"location_code": f"Location '{dimension.code}' not found."}
            )
        validated_data["location_code"] = location

        # Default source_template and source_batch from item_journal when provided
        item_journal = validated_data.get("item_journal")
        if item_journal:
            if (
                "source_template" not in validated_data
                and item_journal.journal_template_id
            ):
                validated_data["source_template"] = item_journal.journal_template
            if "source_batch" not in validated_data and item_journal.journal_batch_id:
                validated_data["source_batch"] = item_journal.journal_batch

        # Default to ITEM template and DEFAULT batch when not set
        if validated_data.get("source_template") is None:
            default_template = get_default_item_journal_template()
            if default_template:
                validated_data["source_template"] = default_template
        if validated_data.get("source_batch") is None:
            default_batch = get_default_item_journal_batch()
            if default_batch:
                validated_data["source_batch"] = default_batch

        return super().create(validated_data)


class ItemJournalSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="no")
    entry_type = serializers.ChoiceField(
        choices=[(tag.name, tag.value) for tag in EntryType],
        required=False,
    )
    item_name = serializers.SerializerMethodField()
    unit_of_measure_detail = ItemUnitOfMeasureSerializer(
        source="item_unit_of_measure", read_only=True
    )
    item_unit_of_measure = serializers.PrimaryKeyRelatedField(
        queryset=ItemUnitOfMeasure.objects.all(), allow_null=True
    )
    location_code = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), allow_null=True, required=False
    )
    location_code_name = serializers.SerializerMethodField()
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), allow_null=True, required=False
    )
    item_specification = serializers.PrimaryKeyRelatedField(
        queryset=TrackingSpecification.objects.all(), allow_null=True, required=False
    )
    item_tracking_required = serializers.SerializerMethodField()
    tracking_code = serializers.SerializerMethodField()
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    physical_quantity = serializers.IntegerField(required=False, allow_null=True)
    calculated_quantity = serializers.IntegerField(read_only=True)
    quantity_difference = serializers.SerializerMethodField()
    unit_of_measure_display = serializers.SerializerMethodField()
    item_uom_options = serializers.SerializerMethodField()
    journal_batch = serializers.PrimaryKeyRelatedField(
        queryset=ItemJournalBatch.objects.all(), required=False, allow_null=True
    )
    journal_batch_name = serializers.CharField(
        source="journal_batch.name", read_only=True
    )
    quantity_before = serializers.SerializerMethodField()
    quantity_after = serializers.SerializerMethodField()

    def get_quantity_before(self, obj):
        """Running balance before this journal entry (from ItemLedgerEntries)."""
        if obj.status != "Posted" or not obj.item:
            return None
        our_entries = ItemLedgerEntries.objects.filter(
            item=obj.item, document_no=obj.document_no
        ).order_by("id")
        first = our_entries.first()
        if not first:
            return None
        total = (
            ItemLedgerEntries.objects.filter(
                item=obj.item,
                id__lt=first.id,
            ).aggregate(
                total=Sum("quantity")
            )["total"]
            or 0
        )
        return total

    def get_quantity_after(self, obj):
        """Running balance after this journal entry (from ItemLedgerEntries)."""
        qty_before = self.get_quantity_before(obj)
        if qty_before is None:
            return None
        delta = (
            ItemLedgerEntries.objects.filter(
                item=obj.item, document_no=obj.document_no
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        return qty_before + delta

    def get_item_tracking_required(self, obj):
        if obj.item.tracking_code:
            return True
        return False

    def get_tracking_code(self, obj):
        if obj.item.tracking_code:
            return {
                "system_id": obj.item.tracking_code.system_id,
                "code": obj.item.tracking_code.code,
                "description": obj.item.tracking_code.description,
                "require_serial_no": obj.item.tracking_code.require_serial_no,
                "require_lot_no": obj.item.tracking_code.require_lot_no,
                "require_expiry_date": obj.item.tracking_code.require_expiry_date,
            }
        return None

    def get_item_name(self, obj):
        return obj.item.item_name if obj.item else None

    def get_location_code_name(self, obj):
        if obj.location_code:
            return f"{obj.location_code.code} - {obj.location_code.description}"
        return None

    def get_quantity_difference(self, obj):
        if obj.physical_quantity is not None and obj.calculated_quantity is not None:
            return obj.physical_quantity - obj.calculated_quantity
        return None

    def get_unit_of_measure_display(self, obj):
        """Return UOM code for display - from item_unit_of_measure or item's base unit."""
        if obj.item_unit_of_measure:
            return obj.item_unit_of_measure.unit_of_measure.code
        if obj.item and obj.item.unit_of_measure:
            return obj.item.unit_of_measure.code
        return None

    def get_item_uom_options(self, obj):
        """Return item's UOM options for select dropdown: [{value: id, label: 'PCS - Pieces (1)'}]"""
        if not obj.item:
            return []
        uoms = ItemUnitOfMeasure.objects.filter(item=obj.item).select_related(
            "unit_of_measure"
        )
        return [
            {
                "value": uom.id,
                "label": f"{uom.unit_of_measure.code} - {uom.unit_of_measure.description} ({uom.quantity_per_unit})",
            }
            for uom in uoms
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        if request:
            attrs["user"] = request.user
            from dimension.branch_filter import get_branch_for_request

            dimension = get_branch_for_request(request) or getattr(
                request.user, "global_dimension_1", None
            )
            branch_code = getattr(dimension, "code", "") or ""
            loc = (
                Location.objects.filter(code__iexact=branch_code).first()
                if dimension and branch_code
                else None
            )
            if not loc:
                if dimension:
                    raise serializers.ValidationError(
                        {
                            "location_code": (
                                f"No Location found for branch {dimension.code!r}. "
                                "Create a Location whose code matches the branch code."
                            )
                        }
                    )
                raise serializers.ValidationError(
                    {
                        "location_code": "No locations found. Please create at least one location."
                    }
                )
            attrs["location_code"] = loc
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and not validated_data.get("user"):
            validated_data["user"] = request.user
        if not validated_data.get("entry_type"):
            validated_data["entry_type"] = EntryType.PositiveAdjustment.name

        # Always stamp journal dimensions (branch + dimension_set) from request/user context.
        from financials.models import GeneralLedgerSetup
        from dimension.models import get_posting_dimension_payload

        gl = GeneralLedgerSetup.objects.first()
        user = validated_data.get("user")
        g1 = None
        if request:
            try:
                from dimension.branch_filter import get_branch_for_request

                g1 = get_branch_for_request(request)
            except Exception:
                g1 = None
        if not g1:
            g1 = getattr(user, "global_dimension_1", None) if user else None
        g2 = getattr(user, "global_dimension_2", None) if user else None
        dim_payload = get_posting_dimension_payload(
            global_dimension_1=g1,
            global_dimension_2=g2,
            gl_setup=gl,
        )
        validated_data.setdefault(
            "global_dimension_1", dim_payload.get("global_dimension_1") or g1
        )
        validated_data.setdefault(
            "global_dimension_2", dim_payload.get("global_dimension_2") or g2
        )
        validated_data.setdefault("dimension_set", dim_payload.get("dimension_set"))

        # Default journal_template/journal_batch when not provided.
        # - Stock taking: PHYS. INV. / DEFAULT
        # - Regular journals: ITEM / DEFAULT
        is_stock_taking = (
            validated_data.get("physical_quantity") is not None
            or validated_data.get("calculated_quantity") is not None
        )
        if is_stock_taking:
            from items.models import ItemJournalTemplate, ItemJournalBatch

            template, _ = ItemJournalTemplate.objects.get_or_create(
                name="PHYS. INV.",
                defaults={"description": "Physical Inventory", "type": "phys_inventory"},
            )
            batch, _ = ItemJournalBatch.objects.get_or_create(
                journal_template=template,
                name="DEFAULT",
                defaults={"description": "Default Journal"},
            )
            validated_data.setdefault("journal_template", template)
            validated_data.setdefault("journal_batch", batch)
        else:
            if not validated_data.get("journal_template"):
                template = get_default_item_journal_template()
                if template:
                    validated_data["journal_template"] = template
            if not validated_data.get("journal_batch"):
                batch = get_default_item_journal_batch()
                if batch:
                    validated_data["journal_batch"] = batch
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and not validated_data.get("user"):
            validated_data["user"] = request.user
        return super().update(instance, validated_data)

    class Meta:
        model = ItemJournal
        fields = [
            "id",
            "system_id",
            "item",
            "item_name",
            "entry_type",
            "document_no",
            "description",
            "quantity",
            "item_unit_of_measure",
            "unit_of_measure_detail",
            "unit_amount",
            "amount",
            "unit_cost",
            "location_code",
            "location_code_name",
            "date",
            "user",
            "user_name",
            "status",
            "item_specification",
            "item_tracking_required",
            "tracking_code",
            "adjustment_type",
            "physical_quantity",
            "calculated_quantity",
            "quantity_difference",
            "unit_of_measure_display",
            "item_uom_options",
            "journal_batch",
            "journal_batch_name",
            "quantity_before",
            "quantity_after",
        ]

        read_only_fields = ["system_id", "id", "document_no", "item_name"]


# ========== Item Attribute Serializers ==========


class ItemAttributeValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemAttributeValue
        fields = ["id", "system_id", "value", "blocked", "created_at", "updated_at"]
        read_only_fields = ["system_id", "created_at", "updated_at"]


class ItemAttributeSerializer(serializers.ModelSerializer):
    values = ItemAttributeValueSerializer(many=True, read_only=True)
    value_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ItemAttributeValue.objects.all(),
        source="values",
        write_only=True,
        required=False,
    )

    class Meta:
        model = ItemAttribute
        fields = [
            "id",
            "system_id",
            "name",
            "type",
            "blocked",
            "values",
            "value_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["system_id", "created_at", "updated_at"]


class ItemAttributeEntrySerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(
        queryset=Item.objects.all(), slug_field="system_id"
    )
    attribute = serializers.PrimaryKeyRelatedField(queryset=ItemAttribute.objects.all())
    attribute_name = serializers.CharField(source="attribute.name", read_only=True)
    attribute_type = serializers.CharField(source="attribute.type", read_only=True)
    selected_values = serializers.PrimaryKeyRelatedField(
        many=True, queryset=ItemAttributeValue.objects.all(), required=False
    )
    selected_value_details = ItemAttributeValueSerializer(
        source="selected_values", many=True, read_only=True
    )
    display_value = serializers.CharField(read_only=True)

    class Meta:
        model = ItemAttributeEntry
        fields = [
            "id",
            "system_id",
            "item",
            "attribute",
            "attribute_name",
            "attribute_type",
            "selected_values",
            "selected_value_details",
            "value_text",
            "value_integer",
            "value_decimal",
            "value_date",
            "display_value",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["system_id", "created_at", "updated_at"]

    def validate(self, attrs):
        """Validate that the correct value field is used based on attribute type"""
        attribute = attrs.get("attribute")
        if not attribute:
            # If updating, get attribute from instance
            if self.instance:
                attribute = self.instance.attribute
            else:
                raise serializers.ValidationError(
                    {"attribute": "Attribute is required"}
                )

        attr_type = attribute.type

        # Validate based on attribute type
        if attr_type == ItemAttribute.AttributeType.OPTION:
            if not attrs.get("selected_values"):
                raise serializers.ValidationError(
                    {
                        "selected_values": "At least one value must be selected for option type attributes"
                    }
                )
            # Clear other fields
            attrs["value_text"] = None
            attrs["value_integer"] = None
            attrs["value_decimal"] = None
            attrs["value_date"] = None
        else:
            # Clear selected_values for non-option types
            attrs["selected_values"] = []

            # Validate that the correct field has a value
            if attr_type == ItemAttribute.AttributeType.TEXT:
                if not attrs.get("value_text"):
                    raise serializers.ValidationError(
                        {
                            "value_text": "Text value is required for text type attributes"
                        }
                    )
            elif attr_type == ItemAttribute.AttributeType.INTEGER:
                if attrs.get("value_integer") is None:
                    raise serializers.ValidationError(
                        {
                            "value_integer": "Integer value is required for integer type attributes"
                        }
                    )
            elif attr_type == ItemAttribute.AttributeType.DECIMAL:
                if attrs.get("value_decimal") is None:
                    raise serializers.ValidationError(
                        {
                            "value_decimal": "Decimal value is required for decimal type attributes"
                        }
                    )
            elif attr_type == ItemAttribute.AttributeType.DATE:
                if not attrs.get("value_date"):
                    raise serializers.ValidationError(
                        {
                            "value_date": "Date value is required for date type attributes"
                        }
                    )

        return attrs

    def to_representation(self, instance):
        """Add display_value to representation"""
        representation = super().to_representation(instance)
        representation["display_value"] = instance.display_value
        return representation


# ── Item Variant Serializers ──────────────────────────────────────────────────

from items.models import ItemVariantOption, ItemVariantOptionValue, ItemVariant


class ItemVariantOptionValueSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemVariantOptionValue
        fields = ["id", "option", "value", "display_order"]
        read_only_fields = ["id"]


class ItemVariantOptionSerializer(serializers.ModelSerializer):
    values = ItemVariantOptionValueSerializer(many=True, read_only=True)
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="no")

    class Meta:
        model = ItemVariantOption
        fields = ["id", "item", "name", "display_order", "values"]
        read_only_fields = ["id"]


class ItemVariantSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="no")
    option_values = serializers.PrimaryKeyRelatedField(
        many=True, queryset=ItemVariantOptionValue.objects.all(), required=False
    )
    option_value_labels = serializers.SerializerMethodField()
    effective_price = serializers.IntegerField(read_only=True)
    inventory = serializers.IntegerField(read_only=True)

    class Meta:
        model = ItemVariant
        fields = [
            "id",
            "item",
            "code",
            "description",
            "option_values",
            "option_value_labels",
            "unit_price",
            "effective_price",
            "bar_code_no",
            "blocked",
            "inventory",
        ]
        read_only_fields = ["id", "effective_price", "inventory", "option_value_labels"]

    def get_option_value_labels(self, obj):
        return [str(ov) for ov in obj.option_values.all()]
