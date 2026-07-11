from rest_framework import serializers
from . import models


class RoomAmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RoomAmenity
        fields = [
            "id",
            "system_id",
            "code",
            "name",
            "category",
            "icon",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["system_id", "created_at", "updated_at"]


class RoomTypeSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = models.RoomType
        fields = [
            "id",
            "system_id",
            "no",
            "name",
            "description",
            "base_rate",
            "max_occupancy",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "created_at", "updated_at"]

    def create(self, validated_data):
        if validated_data.get("description") is None:
            validated_data["description"] = ""
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Only normalize description when it was explicitly sent in the request
        if "description" in validated_data and validated_data["description"] is None:
            validated_data["description"] = ""
        return super().update(instance, validated_data)


class RoomSerializer(serializers.ModelSerializer):
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = models.Room
        fields = [
            "id",
            "system_id",
            "no",
            "room_number",
            "room_type",
            "room_type_name",
            "floor",
            "status",
            "status_display",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["no", "created_at", "updated_at"]
