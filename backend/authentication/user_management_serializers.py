"""
User Management Serializers

Serializers for frontend user, user group, and role management.
These provide lightweight serializers for CRUD operations.
"""

from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import serializers
from authentication.models import CustomUser, UserGroup, Role, RoleCenter
from authentication.restaurant_pin_utils import (
    restaurant_pin_taken_in_tenant,
    validate_restaurant_pin_format,
)
from permissions.models import PermissionSet

_RESTAURANT_PIN_OMIT = object()


class UserGroupListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for user group lists"""

    member_count = serializers.SerializerMethodField()
    permission_set_count = serializers.SerializerMethodField()
    default_profile_name = serializers.CharField(
        source="default_profile.name", read_only=True, allow_null=True
    )

    class Meta:
        model = UserGroup
        fields = [
            "id",
            "code",
            "name",
            "description",
            "default_profile_name",
            "member_count",
            "permission_set_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_member_count(self, obj):
        """Get member count excluding debug_admin"""
        return obj.members.exclude(username="debug_admin").count()

    def get_permission_set_count(self, obj):
        return obj.permission_sets.count()


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for user lists"""

    user_groups = UserGroupListSerializer(many=True, read_only=True)
    global_dimension_1_obj = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "full_name",
            "phone_number",
            "global_dimension_1",
            "global_dimension_1_obj",
            "can_switch_branch",
            "avatar",
            "is_active",
            "terminated",
            "is_staff",
            "is_superuser",
            "user_groups",
            "created_at",
            "updated_at",
        ]

    def get_global_dimension_1_obj(self, obj):
        gd1 = getattr(obj, "global_dimension_1", None)
        if not gd1:
            return None
        return {
            "id": gd1.id,
            "code": getattr(gd1, "code", None),
            "description": getattr(gd1, "description", None) or "",
        }


class PermissionSetListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for permission set lists"""

    line_count = serializers.SerializerMethodField()
    user_group_count = serializers.SerializerMethodField()

    class Meta:
        model = PermissionSet
        fields = [
            "id",
            "code",
            "name",
            "description",
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


class RoleCenterListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for role center lists"""

    role_count = serializers.SerializerMethodField()

    class Meta:
        model = RoleCenter
        fields = [
            "id",
            "code",
            "name",
            "description",
            "modules",
            "features",
            "dashboard_widgets",
            "role_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_role_count(self, obj):
        return obj.assigned_roles.count()


class RoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for role lists"""

    role_center = RoleCenterListSerializer(read_only=True)
    user_group_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "role_center",
            "permissions",
            "user_group_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_user_group_count(self, obj):
        return obj.user_groups_default.count()


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for user CRUD operations"""

    user_groups = UserGroupListSerializer(many=True, read_only=True)
    global_dimension_1_obj = serializers.SerializerMethodField()
    user_group_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=UserGroup.objects.all(),
        write_only=True,
        required=False,
        allow_empty=True,
        source="user_groups",
    )
    inherited_roles = serializers.SerializerMethodField()
    inherited_permissions = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    restaurant_pin = serializers.CharField(
        write_only=True,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="4-6 digit restaurant mobile PIN. Omit to leave unchanged; blank or null clears.",
    )

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "full_name",
            "phone_number",
            "global_dimension_1",
            "global_dimension_1_obj",
            "can_switch_branch",
            "password",  # ✅ ADDED: Password field was missing!
            "restaurant_pin",
            "avatar",
            "avatar_url",
            "is_active",
            "terminated",
            "is_staff",
            "is_superuser",
            "user_groups",
            "user_group_ids",
            "inherited_roles",
            "inherited_permissions",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "required": True},
            "phone_number": {"required": False, "allow_blank": True},
            "global_dimension_1": {
                "required": False,
                "allow_null": True,
            },  # ForeignKey uses allow_null
        }

    def get_global_dimension_1_obj(self, obj):
        gd1 = getattr(obj, "global_dimension_1", None)
        if not gd1:
            return None
        return {
            "id": gd1.id,
            "code": getattr(gd1, "code", None),
            "description": getattr(gd1, "description", None) or "",
        }

    def validate_restaurant_pin(self, value):
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        pin = validate_restaurant_pin_format(value)
        exclude = self.instance.pk if getattr(self, "instance", None) else None
        if restaurant_pin_taken_in_tenant(pin, exclude_user_id=exclude):
            raise serializers.ValidationError(
                "This PIN is already assigned to another active user."
            )
        return pin

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_inherited_roles(self, obj):
        """Get roles from user groups"""
        roles = []
        for group in obj.user_groups.filter(is_active=True):
            if group.default_profile and group.default_profile.is_active:
                roles.append(
                    {
                        "name": group.default_profile.name,
                        "from_group": group.name,
                    }
                )
        return roles

    def get_inherited_permissions(self, obj):
        """Get page permissions from user groups"""
        page_permissions = {}

        for group in obj.user_groups.filter(is_active=True):
            for perm_set in group.permission_sets.filter(is_active=True):
                page_lines = perm_set.permissionsetline_set.filter(
                    application_object__object_type="Page"
                )

                for line in page_lines:
                    page_name = line.application_object.object_name

                    if page_name not in page_permissions:
                        page_permissions[page_name] = {
                            "read": False,
                            "insert": False,
                            "modify": False,
                            "delete": False,
                            "source": [],
                        }

                    # OR logic - if any permission set grants access, user has it
                    page_permissions[page_name]["read"] = (
                        page_permissions[page_name]["read"] or line.read_permission
                    )
                    page_permissions[page_name]["insert"] = (
                        page_permissions[page_name]["insert"] or line.insert_permission
                    )
                    page_permissions[page_name]["modify"] = (
                        page_permissions[page_name]["modify"] or line.modify_permission
                    )
                    page_permissions[page_name]["delete"] = (
                        page_permissions[page_name]["delete"] or line.delete_permission
                    )

                    # Track source
                    source = f"{perm_set.name} (from {group.name})"
                    if source not in page_permissions[page_name]["source"]:
                        page_permissions[page_name]["source"].append(source)

        return page_permissions

    def create(self, validated_data):
        user_groups = validated_data.pop("user_groups", [])
        password = validated_data.pop("password", None)
        restaurant_pin = validated_data.pop("restaurant_pin", _RESTAURANT_PIN_OMIT)

        # Handle blank phone_number with unique constraint
        if not validated_data.get("phone_number"):
            # Generate a unique placeholder phone number
            import uuid

            validated_data["phone_number"] = f"NO_PHONE_{uuid.uuid4().hex[:8]}"

        user = CustomUser.objects.create(**validated_data)

        if password:
            user.set_password(password)
            user.save()

        # Add user groups
        for group in user_groups:
            group.add_member(user)

        if restaurant_pin is not _RESTAURANT_PIN_OMIT:
            if restaurant_pin is None:
                user.restaurant_pin_hash = None
                user.restaurant_pin_set_at = None
            else:
                user.restaurant_pin_hash = make_password(restaurant_pin)
                user.restaurant_pin_set_at = timezone.now()
            user.save(
                update_fields=["restaurant_pin_hash", "restaurant_pin_set_at"]
            )

        return user

    def update(self, instance, validated_data):
        user_groups = validated_data.pop("user_groups", None)
        password = validated_data.pop("password", None)
        restaurant_pin = validated_data.pop("restaurant_pin", _RESTAURANT_PIN_OMIT)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        if restaurant_pin is not _RESTAURANT_PIN_OMIT:
            if restaurant_pin is None:
                instance.restaurant_pin_hash = None
                instance.restaurant_pin_set_at = None
            else:
                instance.restaurant_pin_hash = make_password(restaurant_pin)
                instance.restaurant_pin_set_at = timezone.now()

        instance.save()

        # Update user groups if provided
        if user_groups is not None:
            # Remove from old groups
            for group in instance.user_groups.all():
                group.remove_member(instance)

            # Add to new groups
            for group in user_groups:
                group.add_member(instance)

        return instance


class UserGroupDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for user group CRUD operations"""

    code = serializers.CharField(required=False, allow_blank=True)

    members = UserListSerializer(many=True, read_only=True)
    member_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False,
        source="members",
    )
    permission_sets = PermissionSetListSerializer(many=True, read_only=True)
    permission_set_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=PermissionSet.objects.all(),
        write_only=True,
        required=False,
        source="permission_sets",
    )
    default_profile = RoleListSerializer(read_only=True)
    default_profile_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        source="default_profile",
    )

    class Meta:
        model = UserGroup
        fields = [
            "id",
            "code",
            "name",
            "description",
            "default_profile",
            "default_profile_id",
            "permission_sets",
            "permission_set_ids",
            "members",
            "member_ids",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        members = validated_data.pop("members", [])
        permission_sets = validated_data.pop("permission_sets", [])

        # Auto-generate code if not provided
        if not validated_data.get("code"):
            # Generate code from name (e.g., "Admin Group" -> "ADMIN_GROUP")
            base_code = (
                validated_data.get("name", "USER_GROUP").upper().replace(" ", "_")
            )

            # Ensure uniqueness by appending a number if needed
            code = base_code
            counter = 1
            while UserGroup.objects.filter(code=code).exists():
                code = f"{base_code}_{counter}"
                counter += 1

            validated_data["code"] = code

        group = UserGroup.objects.create(**validated_data)

        # Add members
        for member in members:
            group.add_member(member)

        # Add permission sets
        group.permission_sets.set(permission_sets)

        return group

    def update(self, instance, validated_data):
        members = validated_data.pop("members", None)
        permission_sets = validated_data.pop("permission_sets", None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update members if provided
        if members is not None:
            # Remove all current members
            for member in instance.members.all():
                instance.remove_member(member)

            # Add new members
            for member in members:
                instance.add_member(member)

        # Update permission sets if provided
        if permission_sets is not None:
            instance.permission_sets.set(permission_sets)

        return instance


class RoleDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for role CRUD operations"""

    role_center = RoleCenterListSerializer(read_only=True)
    role_center_id = serializers.PrimaryKeyRelatedField(
        queryset=RoleCenter.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        source="role_center",
    )

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "role_center",
            "role_center_id",
            "permissions",
            "is_active",
            "created_at",
            "updated_at",
        ]


class RoleCenterDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for role center CRUD operations"""

    code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = RoleCenter
        fields = [
            "id",
            "code",
            "name",
            "description",
            "modules",
            "features",
            "dashboard_widgets",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        # Auto-generate code if not provided
        if not validated_data.get("code"):
            # Generate code from name (e.g., "Sales Center" -> "SALES_CENTER")
            base_code = (
                validated_data.get("name", "ROLE_CENTER").upper().replace(" ", "_")
            )

            # Ensure uniqueness by appending a number if needed
            code = base_code
            counter = 1
            while RoleCenter.objects.filter(code=code).exists():
                code = f"{base_code}_{counter}"
                counter += 1

            validated_data["code"] = code

        return super().create(validated_data)
