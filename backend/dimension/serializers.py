from rest_framework import serializers
from .models import Dimension, DimensionValue, DimensionSet, DimensionSetEntry


class DimensionSerializer(serializers.ModelSerializer):
    """Serializer for dimensions (tracking codes / dimension codes)."""

    value_count = serializers.SerializerMethodField()

    class Meta:
        model = Dimension
        fields = ["id", "code", "description", "value_count"]

    def get_value_count(self, obj):
        """Count of dimension values for this dimension."""
        return obj.dimension_code.count()


class DimensionValueSerializer(serializers.ModelSerializer):
    """Serializer for dimension values (e.g. branches, departments)."""

    dimension_type = serializers.SerializerMethodField()
    dimension_code_display = serializers.SerializerMethodField()

    class Meta:
        model = DimensionValue
        fields = [
            "id",
            "code",
            "description",
            "dimension_type",
            "dimension_code",
            "dimension_code_display",
        ]
    
    def get_dimension_code_display(self, obj):
        return obj.dimension_code.code if obj.dimension_code else None
    
    def get_dimension_type(self, obj):
        """Convert dimension_type enum to string value."""
        if obj.dimension_type:
            return str(obj.dimension_type)
        return None


class DimensionSetEntrySerializer(serializers.ModelSerializer):
    dimension_code = serializers.CharField(source="dimension_code.code", read_only=True)
    dimension_value_code = serializers.CharField(
        source="dimension_value.code", read_only=True
    )

    class Meta:
        model = DimensionSetEntry
        fields = ["id", "dimension_code", "dimension_value", "dimension_value_code"]


class DimensionSetSerializer(serializers.ModelSerializer):
    """Serializer for dimension sets. Returns dimension_set_id and expanded dimensions."""

    dimensions = serializers.SerializerMethodField()

    class Meta:
        model = DimensionSet
        fields = ["id", "dimensions"]

    def get_dimensions(self, obj):
        """Return expanded list of {dimension_code, dimension_value_id, dimension_value_code}."""
        if not obj:
            return []
        from dimension.models import expand_dimension_set_to_dict

        d = expand_dimension_set_to_dict(obj)
        return [
            {
                "dimension_code": dim.code,
                "dimension_value_id": val.id,
                "dimension_value_code": val.code,
            }
            for dim, val in d.items()
        ]



