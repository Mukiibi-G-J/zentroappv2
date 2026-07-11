from rest_framework import serializers
from .models import ConfigPackage, ConfigPackageTable
from base.models import Objects
from base.serializers import ObjectsSerializer


class ConfigPackageSerializer(serializers.ModelSerializer):
    # total = serializers.SerializerMethodField()
    class Meta:
        model = ConfigPackage
        fields = [
            "code",
            "package_name",
            "status",
            "created_at",
            "updated_at",
            "system_id",
        ]
        read_only_fields = ["system_id", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        # Ensure system_id is not updated
        validated_data.pop("system_id", None)
        return super().update(instance, validated_data)
    
    # def get_total(self, obj):
    #     return ConfigPackageTable.objects.filter(package_code=obj).count()


class ConfigPackageTableSerializer(serializers.ModelSerializer):
    # table_object = ObjectsSerializer(source="table_id", read_only=True)

    class Meta:
        model = ConfigPackageTable
        fields = [
            "id",
            "package_code",
            "table_id",
            "table_name",
            "description",
            # "table_object",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ConfigPackageDetailSerializer(serializers.ModelSerializer):
    tables = ConfigPackageTableSerializer(
        source="configpackagetable_set", many=True, read_only=True
    )

    class Meta:
        model = ConfigPackage
        fields = [
            "code",
            "package_name",
            "status",
            "tables",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
