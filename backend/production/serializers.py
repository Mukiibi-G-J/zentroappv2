from rest_framework import serializers
from .models import ProductionBOM, BOMLine, ProductionOrder, ProductionOrderLine, ProductionOrderComponent
from resources.serializers import ResourceListSerializer
from items.models import Item, UnitOfMeasure


class BOMLineSerializer(serializers.ModelSerializer):
    """
    Serializer for BOM Line model with camelCase field names.
    Following Business Central format.
    """

    lineNumber = serializers.IntegerField(source="line_number")
    lineType = serializers.CharField(source="line_type")
    itemNo = serializers.SerializerMethodField()
    itemData = serializers.SerializerMethodField()
    description = serializers.CharField()
    quantityPer = serializers.DecimalField(
        source="quantity_per", max_digits=8, decimal_places=3
    )
    unitOfMeasureCode = serializers.CharField(
        source="unit_of_measure.code", read_only=True
    )
    scrapPct = serializers.DecimalField(
        source="scrap_pct", max_digits=5, decimal_places=2
    )
    unitCost = serializers.DecimalField(
        source="unit_cost", max_digits=10, decimal_places=2, read_only=True
    )
    totalCost = serializers.DecimalField(
        source="total_cost", max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = BOMLine
        fields = [
            "id",
            "lineNumber",
            "lineType",
            "item",
            "itemNo",
            "itemData",
            "description",
            "quantityPer",
            "unitOfMeasureCode",
            "scrapPct",
            "unitCost",
            "totalCost",
            "notes",
        ]

    def get_itemData(self, obj):
        """Get item details"""
        if obj.item:
            return {
                "no": obj.item.no,  # Item uses 'no' as primary key
                "name": obj.item.item_name,
                "type": obj.item.type,
                "unitPrice": float(obj.item.unit_price) if obj.item.unit_price else 0,
                "unitCost": float(obj.item.unit_cost) if obj.item.unit_cost else 0,
            }
        return None

    def get_itemNo(self, obj):
        """Get item number"""
        if obj.item:
            return obj.item.no
        return None


class ProductionBOMSerializer(serializers.ModelSerializer):
    """
    Serializer for Production BOM model with camelCase field names.
    Includes nested BOM lines.
    """

    systemId = serializers.UUIDField(source="system_id", read_only=True)
    bomCode = serializers.CharField(source="bom_code", read_only=True)
    unitOfMeasureCode = serializers.CharField(
        source="unit_of_measure.code", read_only=True, allow_null=True
    )
    unitOfMeasure = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    # Accepted from Item Card / POS flows; linking is done in the view from request.data.
    serviceItem = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    status = serializers.CharField()
    isActive = serializers.BooleanField(
        source="is_active", required=False, default=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    # Nested BOM lines
    lines = BOMLineSerializer(many=True, read_only=True)

    # Computed fields
    totalCost = serializers.SerializerMethodField()
    profitMargin = serializers.SerializerMethodField()
    lineCount = serializers.SerializerMethodField()

    class Meta:
        model = ProductionBOM
        fields = [
            "id",
            "systemId",
            "bomCode",
            "name",
            "unitOfMeasureCode",
            "unitOfMeasure",
            "serviceItem",
            "status",
            "isActive",
            "notes",
            "lines",
            "totalCost",
            "profitMargin",
            "lineCount",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "systemId", "bomCode", "createdAt", "updatedAt"]

    def validate_unitOfMeasure(self, value):
        """Validate unit of measure code"""
        if not value or value.strip() == "":
            return None
        try:
            UnitOfMeasure.objects.get(code=value)
            return value
        except UnitOfMeasure.DoesNotExist:
            raise serializers.ValidationError(
                f"Unit of Measure with code '{value}' does not exist."
            )

    def create(self, validated_data):
        """Create ProductionBOM with unit_of_measure handling"""
        validated_data.pop("serviceItem", None)
        unit_of_measure_code = validated_data.pop("unitOfMeasure", None)
        bom = ProductionBOM.objects.create(**validated_data)
        if unit_of_measure_code:
            try:
                uom = UnitOfMeasure.objects.get(code=unit_of_measure_code)
                bom.unit_of_measure = uom
                bom.save()
            except UnitOfMeasure.DoesNotExist:
                pass
        return bom

    def update(self, instance, validated_data):
        """Update ProductionBOM with unit_of_measure handling"""
        validated_data.pop("serviceItem", None)
        unit_of_measure_code = validated_data.pop("unitOfMeasure", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if unit_of_measure_code is not None:
            if unit_of_measure_code:
                try:
                    uom = UnitOfMeasure.objects.get(code=unit_of_measure_code)
                    instance.unit_of_measure = uom
                except UnitOfMeasure.DoesNotExist:
                    pass
            else:
                instance.unit_of_measure = None
        instance.save()
        return instance

    def get_totalCost(self, obj):
        """Get total cost from BOM calculation"""
        return float(obj.calculate_total_cost())

    def get_profitMargin(self, obj):
        """Get profit margin from BOM calculation"""
        return float(obj.calculate_profit_margin())

    def get_lineCount(self, obj):
        """Get number of BOM lines"""
        return obj.lines.count()


class ProductionBOMListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for BOM lists (without nested lines)
    """

    systemId = serializers.UUIDField(source="system_id", read_only=True)
    bomCode = serializers.CharField(source="bom_code", read_only=True)
    unitOfMeasureCode = serializers.CharField(
        source="unit_of_measure.code", read_only=True, allow_null=True
    )
    isActive = serializers.BooleanField(source="is_active")
    totalCost = serializers.SerializerMethodField()
    profitMargin = serializers.SerializerMethodField()
    lineCount = serializers.SerializerMethodField()

    class Meta:
        model = ProductionBOM
        fields = [
            "id",
            "systemId",
            "bomCode",
            "name",
            "unitOfMeasureCode",
            "status",
            "isActive",
            "totalCost",
            "profitMargin",
            "lineCount",
        ]

    def get_totalCost(self, obj):
        """Get total cost"""
        return float(obj.calculate_total_cost())

    def get_profitMargin(self, obj):
        """Get profit margin"""
        return float(obj.calculate_profit_margin())

    def get_lineCount(self, obj):
        """Get line count"""
        return obj.lines.count()


# Production Order Serializers
class ProductionOrderComponentSerializer(serializers.ModelSerializer):
    """Serializer for Production Order Component (line items)."""
    itemNo = serializers.SerializerMethodField()
    itemName = serializers.CharField(source="item_name", read_only=True)
    quantityPer = serializers.DecimalField(source="quantity_per", max_digits=8, decimal_places=3, read_only=True)
    expectedQuantity = serializers.DecimalField(source="expected_quantity", max_digits=10, decimal_places=3)
    unitOfMeasureCode = serializers.SerializerMethodField()
    costAmount = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrderComponent
        fields = [
            "id", "itemNo", "itemName", "description", "quantity",
            "expectedQuantity", "quantityPer", "unitOfMeasureCode",
            "status", "unit_cost", "costAmount",
        ]

    def get_itemNo(self, obj):
        return obj.item.no if obj.item else None

    def get_unitOfMeasureCode(self, obj):
        return obj.unit_of_measure_code.code if obj.unit_of_measure_code else None

    def get_costAmount(self, obj):
        """Cost Amount = Quantity × Unit Cost (cost per unit)."""
        return round(float(obj.cost_amount or 0), 2)


class ProductionOrderLineSerializer(serializers.ModelSerializer):
    """Serializer for Production Order Line (output)."""
    itemNo = serializers.SerializerMethodField()
    itemName = serializers.SerializerMethodField()
    unitOfMeasureCode = serializers.SerializerMethodField()
    unit_cost = serializers.SerializerMethodField()
    costAmount = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrderLine
        fields = [
            "id", "itemNo", "itemName", "description", "quantity",
            "finished_quantity", "status", "unitOfMeasureCode", "unit_cost", "costAmount",
        ]

    def get_itemNo(self, obj):
        return obj.item.no if obj.item else None

    def get_itemName(self, obj):
        return obj.item.item_name if obj.item else (obj.description or "")

    def get_unitOfMeasureCode(self, obj):
        return obj.unit_of_measure_code.code if obj.unit_of_measure_code else None

    def get_unit_cost(self, obj):
        """Return unit cost as number for frontend display."""
        return round(float(obj.unit_cost or 0), 2)

    def get_costAmount(self, obj):
        """Cost Amount = Quantity × Unit Cost (cost per unit)."""
        return round(float(obj.cost_amount or 0), 2)

    def to_representation(self, instance):
        """Ensure unit_cost and costAmount are always present as numbers for frontend."""
        data = super().to_representation(instance)
        unit_cost_val = data.get("unit_cost")
        cost_amount_val = data.get("costAmount")
        if unit_cost_val is not None:
            data["unit_cost"] = round(float(unit_cost_val), 2)
            data["unitCost"] = data["unit_cost"]  # camelCase alias for frontend
        if cost_amount_val is not None:
            data["costAmount"] = round(float(cost_amount_val), 2)
            data["cost_amount"] = data["costAmount"]  # snake_case alias
        return data


class ProductionOrderSerializer(serializers.ModelSerializer):
    """Full serializer for Production Order with lines and components."""
    systemId = serializers.UUIDField(source="system_id", read_only=True)
    itemNo = serializers.SerializerMethodField()
    itemName = serializers.SerializerMethodField()
    lines = ProductionOrderLineSerializer(many=True, read_only=True)
    components = ProductionOrderComponentSerializer(many=True, read_only=True)
    componentCount = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "systemId",
            "no",
            "name",
            "description",
            "source_type",
            "status",
            "itemNo",
            "itemName",
            "quantity",
            "blocked",
            "lines",
            "components",
            "componentCount",
        ]
        read_only_fields = ["id", "systemId", "no"]

    def get_itemNo(self, obj):
        return obj.item.no if obj.item else None

    def get_itemName(self, obj):
        return obj.item.item_name if obj.item else None

    def get_componentCount(self, obj):
        return obj.components.count()


class ProductionOrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Production Order list."""
    systemId = serializers.UUIDField(source="system_id", read_only=True)
    itemNo = serializers.SerializerMethodField()
    itemName = serializers.SerializerMethodField()
    componentCount = serializers.SerializerMethodField()

    class Meta:
        model = ProductionOrder
        fields = [
            "id",
            "systemId",
            "no",
            "name",
            "status",
            "itemNo",
            "itemName",
            "quantity",
            "blocked",
            "componentCount",
        ]

    def get_itemNo(self, obj):
        return obj.item.no if obj.item else None

    def get_itemName(self, obj):
        return obj.item.item_name if obj.item else None

    def get_componentCount(self, obj):
        return obj.components.count()
