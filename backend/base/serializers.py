from rest_framework import serializers
from .models import ObjectType, Objects


class ObjectTypeSerializer(serializers.ModelSerializer):
    object_count = serializers.SerializerMethodField()

    class Meta:
        model = ObjectType
        fields = [
            "id",
            "name",
            "code",
            "description",
            "sort_order",
            "object_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_object_count(self, obj):
        return obj.application_objects.count()


class ObjectsSerializer(serializers.ModelSerializer):
    object_type_name = serializers.CharField(
        source="object_type_ref.name", read_only=True
    )

    class Meta:
        model = Objects
        fields = [
            "system_id",
            "object_id",
            "object_type",
            "object_name",
            "object_caption",
            "object_subtype",
            "is_active",
            "object_type_ref",
            "object_type_name",
            "requires_permission",
            "related_model",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "system_id"]
