from rest_framework import serializers
from .models import Resource


class UnitOfMeasureRelatedField(serializers.SlugRelatedField):
    """SlugRelatedField for UnitOfMeasure by code; queryset supplied via get_queryset to avoid import-order issues."""

    def get_queryset(self):
        from items.models import UnitOfMeasure
        return UnitOfMeasure.objects.all()


class ResourceSerializer(serializers.ModelSerializer):
    """
    Serializer for Resource model with camelCase field names.
    base_unit picks from items.UnitOfMeasure (same model as items).
    """

    # CamelCase field mappings
    resourceType = serializers.CharField(source="resource_type")
    baseUnit = UnitOfMeasureRelatedField(
        source="base_unit",
        slug_field="code",
        required=False,
        allow_null=True,
    )

    # Cost Structure (Business Central approach)
    directUnitCost = serializers.DecimalField(
        source="direct_unit_cost", max_digits=10, decimal_places=2
    )
    indirectCostPct = serializers.DecimalField(
        source="indirect_cost_pct", max_digits=5, decimal_places=2
    )
    unitCost = serializers.DecimalField(
        source="unit_cost", max_digits=10, decimal_places=2, read_only=True
    )
    unitPrice = serializers.DecimalField(
        source="unit_price", max_digits=10, decimal_places=2
    )

    isActive = serializers.BooleanField(source="is_active")
    blocked = serializers.BooleanField()
    generalProductPostingGroup = serializers.PrimaryKeyRelatedField(
        source="general_product_posting_group", read_only=True, allow_null=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    # Computed fields
    indirectCostAmount = serializers.SerializerMethodField()
    profitPerUnit = serializers.SerializerMethodField()
    profitMargin = serializers.SerializerMethodField()
    dimension1 = serializers.PrimaryKeyRelatedField(
        source="dimension_1", read_only=True, allow_null=True
    )

    # Formatted fields with commas
    directUnitCostFormatted = serializers.SerializerMethodField()
    unitCostFormatted = serializers.SerializerMethodField()
    unitPriceFormatted = serializers.SerializerMethodField()
    indirectCostAmountFormatted = serializers.SerializerMethodField()
    profitPerUnitFormatted = serializers.SerializerMethodField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "code",
            "name",
            "resourceType",
            "baseUnit",
            "directUnitCost",
            "directUnitCostFormatted",
            "indirectCostPct",
            "indirectCostAmount",
            "indirectCostAmountFormatted",
            "unitCost",
            "unitCostFormatted",
            "unitPrice",
            "unitPriceFormatted",
            "isActive",
            "blocked",
            "generalProductPostingGroup",
            "description",
            "photo",
            "dimension1",
            "profitPerUnit",
            "profitPerUnitFormatted",
            "profitMargin",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["id", "code", "unitCost", "createdAt", "updatedAt"]

    def get_indirectCostAmount(self, obj):
        """Get calculated indirect cost amount"""
        return float(obj.indirect_cost_amount)

    def get_profitPerUnit(self, obj):
        """Get profit per unit"""
        return float(obj.profit_per_unit)

    def get_profitMargin(self, obj):
        """Get profit margin percentage"""
        return float(obj.profit_margin)

    def get_directUnitCostFormatted(self, obj):
        """Get formatted direct unit cost with commas"""
        return f"{obj.direct_unit_cost:,.2f}"

    def get_unitCostFormatted(self, obj):
        """Get formatted unit cost with commas"""
        return f"{obj.unit_cost:,.2f}"

    def get_unitPriceFormatted(self, obj):
        """Get formatted unit price with commas"""
        return f"{obj.unit_price:,.2f}"

    def get_indirectCostAmountFormatted(self, obj):
        """Get formatted indirect cost amount with commas"""
        return f"{obj.indirect_cost_amount:,.2f}"

    def get_profitPerUnitFormatted(self, obj):
        """Get formatted profit per unit with commas"""
        return f"{obj.profit_per_unit:,.2f}"

    def validate_directUnitCost(self, value):
        """Validate direct unit cost is not negative"""
        if value < 0:
            raise serializers.ValidationError("Direct unit cost cannot be negative")
        return value

    def validate_indirectCostPct(self, value):
        """Validate indirect cost percentage is valid"""
        if value < 0:
            raise serializers.ValidationError(
                "Indirect cost percentage cannot be negative"
            )
        if value > 100:
            raise serializers.ValidationError(
                "Indirect cost percentage cannot exceed 100%"
            )
        return value

    def validate_unitPrice(self, value):
        """Validate unit price is not negative"""
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative")
        return value

    def validate(self, data):
        """Validate that unit price is >= calculated unit cost"""
        from decimal import Decimal, ROUND_HALF_UP

        direct_unit_cost = data.get("direct_unit_cost", Decimal("0"))
        indirect_cost_pct = data.get("indirect_cost_pct", Decimal("0"))
        unit_price = data.get("unit_price")

        # Calculate what the unit cost will be (with proper rounding)
        calculated_unit_cost = direct_unit_cost * (1 + (indirect_cost_pct / 100))
        calculated_unit_cost = calculated_unit_cost.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if unit_price and unit_price < calculated_unit_cost:
            raise serializers.ValidationError(
                {
                    "unitPrice": f"Unit price must be greater than or equal to calculated unit cost ({calculated_unit_cost:.2f})"
                }
            )

        return data


class ResourceListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for resource lists (used in dropdowns, POS, etc.)
    """

    resourceType = serializers.CharField(source="resource_type")
    baseUnit = serializers.SerializerMethodField()

    def get_baseUnit(self, obj):
        return obj.base_unit.code if obj.base_unit else None
    directUnitCost = serializers.DecimalField(
        source="direct_unit_cost", max_digits=10, decimal_places=2
    )
    indirectCostPct = serializers.DecimalField(
        source="indirect_cost_pct", max_digits=5, decimal_places=2
    )
    unitCost = serializers.DecimalField(
        source="unit_cost", max_digits=10, decimal_places=2, read_only=True
    )
    unitPrice = serializers.DecimalField(
        source="unit_price", max_digits=10, decimal_places=2
    )
    isActive = serializers.BooleanField(source="is_active")
    blocked = serializers.BooleanField()

    class Meta:
        model = Resource
        fields = [
            "id",
            "code",
            "name",
            "resourceType",
            "baseUnit",
            "directUnitCost",
            "indirectCostPct",
            "unitCost",
            "unitPrice",
            "isActive",
            "blocked",
        ]
