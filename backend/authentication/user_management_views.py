"""
User Management API Views

Provides API endpoints for managing users, user groups, roles, and role centers.
Frontend-facing CRUD operations with proper permission checks.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone

from authentication.models import UserGroup, Role, RoleCenter, RestaurantStaffDevice
from permissions.models import PermissionSet
from base.models import Objects
from authentication.user_management_serializers import (
    UserListSerializer,
    UserDetailSerializer,
    UserGroupListSerializer,
    UserGroupDetailSerializer,
    RoleListSerializer,
    RoleDetailSerializer,
    RoleCenterListSerializer,
    RoleCenterDetailSerializer,
    PermissionSetListSerializer,
)

User = get_user_model()

DEBUG_USER_EMAILS = {"mukiibijoseph19@gmail.com"}
DEBUG_USER_USERNAMES = {"debug_admin"}


class UserManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User Management
    Page ID: 10801 (User Management Page)
    """

    permission_classes = [IsAuthenticated]
    # JWT first: SessionAuthentication enforces CSRF on PATCH/POST and will 403 SPA requests.
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    serializer_class = UserListSerializer

    def get_queryset(self):
        """Get all users in current tenant"""
        queryset = User.objects.select_related().prefetch_related(
            "user_groups", "user_groups__default_profile"
        )

        # Hide terminated users from default user table/listing.
        queryset = queryset.filter(terminated=False)

        queryset = queryset.exclude(
            Q(email__in=DEBUG_USER_EMAILS) | Q(username__in=DEBUG_USER_USERNAMES)
        )

        # Apply filters
        search = self.request.query_params.get("search", None)
        is_active = self.request.query_params.get("is_active", None)
        user_group = self.request.query_params.get("user_group", None)

        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(username__icontains=search)
                | Q(full_name__icontains=search)
            )

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        if user_group:
            queryset = queryset.filter(user_groups__id=user_group)

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return UserDetailSerializer
        return UserListSerializer

    def list(self, request, *args, **kwargs):
        """List users - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10801, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view users",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create user - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10801, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create users",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Enforce user limit (same logic as company create_user)
        from django_tenants.utils import get_tenant

        company = get_tenant(request)
        if company:
            effective_max = company.get_effective_max_users()
            current_count = (
                User.objects.filter(is_active=True)
                .exclude(username__in=DEBUG_USER_USERNAMES)
                .count()
            )
            if current_count >= effective_max:
                return Response(
                    {
                        "error": "User limit reached",
                        "code": "USER_LIMIT_REACHED",
                        "max_users": effective_max,
                        "current_users": current_count,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update user - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10801, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update users",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete user - requires DELETE permission (soft delete)"""
        has_permission, source = request.user.check_object_permission(10801, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to delete users",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Soft delete - deactivate and mark as terminated so user no longer appears in list.
        instance = self.get_object()
        instance.is_active = False
        instance.terminated = True
        instance.save()

        return Response(
            {"message": "User deactivated successfully"},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        """Reset user password"""
        has_permission, source = request.user.check_object_permission(10801, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to reset passwords",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user = self.get_object()
        new_password = request.data.get("password")

        if not new_password:
            return Response(
                {"error": "Password is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password reset successfully"})

    @action(detail=True, methods=["post"])
    def force_logout(self, request, pk=None):
        """Invalidate all active sessions for a user."""
        has_permission, source = request.user.check_object_permission(10801, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to force logout users",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user = self.get_object()
        user.token_valid_after = timezone.now()
        user.save(update_fields=["token_valid_after", "updated_at"])

        return Response(
            {
                "message": "User has been logged out from all active sessions",
                "user_id": user.id,
                "token_valid_after": user.token_valid_after,
            }
        )

    @action(detail=False, methods=["post"])
    def bulk_force_logout(self, request):
        """Invalidate active sessions for multiple users."""
        has_permission, source = request.user.check_object_permission(10801, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to force logout users",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_ids = request.data.get("user_ids", [])
        if not user_ids:
            return Response(
                {"error": "user_ids is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp = timezone.now()
        updated_count = User.objects.filter(id__in=user_ids).update(
            token_valid_after=timestamp
        )

        return Response(
            {
                "message": "Users logged out from all active sessions",
                "updated_count": updated_count,
                "token_valid_after": timestamp,
            }
        )

    @action(detail=False, methods=["post"], url_path="revoke-restaurant-device")
    def revoke_restaurant_device(self, request):
        """Revoke restaurant quick-login registration for a device (e.g. lost tablet)."""
        has_permission, _source = request.user.check_object_permission(10801, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to revoke restaurant devices",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        device_id = (request.data.get("device_id") or "").strip()
        if not device_id:
            return Response(
                {"error": "device_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = RestaurantStaffDevice.objects.filter(device_id=device_id).update(
            is_revoked=True
        )
        if not updated:
            return Response(
                {"detail": "Device not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"message": "Device revoked", "device_id": device_id})

    @action(detail=False, methods=["post"])
    def bulk_assign_groups(self, request):
        """Bulk assign users to groups"""
        has_permission, source = request.user.check_object_permission(10801, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to assign groups",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user_ids = request.data.get("user_ids", [])
        group_ids = request.data.get("group_ids", [])

        if not user_ids or not group_ids:
            return Response(
                {"error": "user_ids and group_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = User.objects.filter(id__in=user_ids)
        groups = UserGroup.objects.filter(id__in=group_ids)

        for user in users:
            for group in groups:
                group.add_member(user)

        return Response(
            {"message": f"Assigned {len(users)} users to {len(groups)} groups"}
        )


class UserGroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User Group Management
    Page ID: 10802 (User Group Management Page)
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    serializer_class = UserGroupListSerializer

    def get_queryset(self):
        """Get all user groups in current tenant"""
        queryset = UserGroup.objects.prefetch_related(
            "members", "permission_sets", "default_profile"
        )

        # Apply filters
        search = self.request.query_params.get("search", None)
        is_active = self.request.query_params.get("is_active", None)

        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(name__icontains=search)
            )

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("name")

    def get_serializer_class(self):
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return UserGroupDetailSerializer
        return UserGroupListSerializer

    def list(self, request, *args, **kwargs):
        """List user groups - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10802, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view user groups",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create user group - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10802, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create user groups",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update user group - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10802, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update user groups",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete user group - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10802, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to delete user groups",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        """Add a member to the group"""
        has_permission, source = request.user.check_object_permission(10802, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to add members",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        group = self.get_object()
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=user_id)
            group.add_member(user)
            return Response(
                {"message": f"User {user.username} added to group successfully"}
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        """Remove a member from the group"""
        has_permission, source = request.user.check_object_permission(10802, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to remove members",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        group = self.get_object()
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=user_id)
            group.remove_member(user)
            return Response(
                {"message": f"User {user.username} removed from group successfully"}
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Role Management
    Page ID: 10804 (Role Management Page)
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    queryset = Role.objects.all()

    def get_queryset(self):
        queryset = Role.objects.select_related("role_center")

        # Apply filters
        search = self.request.query_params.get("search", None)
        is_active = self.request.query_params.get("is_active", None)

        if search:
            queryset = queryset.filter(Q(name__icontains=search))

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("name")

    def get_serializer_class(self):
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return RoleDetailSerializer
        return RoleListSerializer

    def list(self, request, *args, **kwargs):
        """List roles - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10804, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view roles",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create role - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10804, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create roles",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update role - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10804, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update roles",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete role - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10804, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to delete roles",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class RoleCenterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Role Center Management
    Page ID: 10805 (Role Center Management Page)
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    queryset = RoleCenter.objects.all()

    def get_queryset(self):
        queryset = RoleCenter.objects.all()

        # Apply filters
        search = self.request.query_params.get("search", None)
        is_active = self.request.query_params.get("is_active", None)

        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(name__icontains=search)
            )

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset.order_by("name")

    def get_serializer_class(self):
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return RoleCenterDetailSerializer
        return RoleCenterListSerializer

    def list(self, request, *args, **kwargs):
        """List role centers - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10805, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view role centers",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create role center - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10805, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create role centers",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Update role center - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10805, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update role centers",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete role center - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10805, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to delete role centers",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


class ObjectsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Application Objects
    Used by permission builder to show available pages/tables
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    queryset = Objects.objects.filter(is_active=True)
    serializer_class = None  # Will use simple serializer

    def get_queryset(self):
        queryset = Objects.objects.filter(is_active=True)

        # Apply filters
        object_type = self.request.query_params.get("object_type", None)
        module = self.request.query_params.get("module", None)
        requires_permission = self.request.query_params.get("requires_permission", None)

        if object_type:
            queryset = queryset.filter(object_type=object_type)

        if module:
            queryset = queryset.filter(app_label=module)

        if requires_permission is not None:
            queryset = queryset.filter(
                requires_permission=requires_permission.lower() == "true"
            )

        return queryset.order_by("app_label", "object_name")

    def list(self, request, *args, **kwargs):
        """List application objects"""
        # Allow any authenticated user to view objects
        queryset = self.get_queryset()

        # Group by module
        modules = {}
        for obj in queryset:
            module = obj.app_label or "other"
            if module not in modules:
                modules[module] = []

            modules[module].append(
                {
                    "object_id": obj.object_id,
                    "object_type": obj.object_type,
                    "object_name": obj.object_name,
                    "object_caption": obj.object_caption,
                    "object_subtype": obj.object_subtype,
                    "requires_permission": obj.requires_permission,
                }
            )

        return Response(modules)
