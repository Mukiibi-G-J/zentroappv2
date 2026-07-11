"""
Permission Management Serializers

Serializers for permission sets and permission set lines.
"""

from rest_framework import serializers
from permissions.models import PermissionSet, PermissionSetLine
from base.models import Objects


class ApplicationObjectSerializer(serializers.ModelSerializer):
    """Serializer for application objects (used in permission builder)"""

    class Meta:
        model = Objects
        fields = [
            "object_id",
            "object_type",
            "object_name",
            "object_caption",
            "object_subtype",
            "app_label",
            "requires_permission",
            "is_active",
        ]


class PermissionSetLineSerializer(serializers.ModelSerializer):
    """Serializer for permission set lines"""

    application_object = ApplicationObjectSerializer(read_only=True)
    application_object_id = serializers.IntegerField(
        write_only=True, source="application_object.object_id"
    )

    class Meta:
        model = PermissionSetLine
        fields = [
            "id",
            "permissionset",
            "application_object",
            "application_object_id",
            "read_permission",
            "insert_permission",
            "modify_permission",
            "delete_permission",
            "execute_permission",
            "created_at",
            "updated_at",
        ]


class PermissionSetDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for permission set CRUD operations"""

    permission_lines = PermissionSetLineSerializer(
        many=True, read_only=True, source="permissionsetline_set"
    )
    line_count = serializers.SerializerMethodField()
    user_group_count = serializers.SerializerMethodField()

    class Meta:
        model = PermissionSet
        fields = [
            "id",
            "code",
            "name",
            "description",
            "permission_lines",
            "line_count",
            "user_group_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_line_count(self, obj):
        return obj.permissionsetline_set.count()

    def get_user_group_count(self, obj):
        return obj.user_groups.count()

    def create(self, validated_data):
        permission_lines_data = self.context.get("permission_lines", [])

        # Create permission set
        permission_set = PermissionSet.objects.create(**validated_data)

        # Create permission lines
        for line_data in permission_lines_data:
            object_id = line_data.pop("application_object_id")
            application_object = Objects.objects.get(object_id=object_id)

            PermissionSetLine.objects.create(
                permissionset=permission_set,
                application_object=application_object,
                **line_data,
            )

        return permission_set

    def update(self, instance, validated_data):
        permission_lines_data = self.context.get("permission_lines", None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update permission lines if provided
        if permission_lines_data is not None:
            # Clear existing lines
            instance.permissionsetline_set.all().delete()

            # Create new lines
            for line_data in permission_lines_data:
                object_id = line_data.pop("application_object_id")
                application_object = Objects.objects.get(object_id=object_id)

                PermissionSetLine.objects.create(
                    permissionset=instance,
                    application_object=application_object,
                    **line_data,
                )

        return instance
