"""
Permission Management API Views

Provides API endpoints for managing permission sets and permission lines.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

from permissions.models import PermissionSet, PermissionSetLine
from permissions.serializers import (
    PermissionSetDetailSerializer,
)
from authentication.user_management_serializers import PermissionSetListSerializer


class PermissionSetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Permission Set Management
    Page ID: 10803 (Permission Set Management Page)
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = PermissionSetListSerializer

    def get_queryset(self):
        """Get all permission sets in current tenant"""
        queryset = PermissionSet.objects.prefetch_related("permissionsetline_set")

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
            return PermissionSetDetailSerializer
        return PermissionSetListSerializer

    def get_serializer_context(self):
        """Add permission_lines to context for create/update"""
        context = super().get_serializer_context()
        if self.action in ["create", "update", "partial_update"]:
            permission_lines = self.request.data.get("permission_lines", [])
            context["permission_lines"] = permission_lines
        return context

    def list(self, request, *args, **kwargs):
        """List permission sets - requires READ permission"""
        has_permission, source = request.user.check_object_permission(10803, "read")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need read permission to view permission sets",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Create permission set - requires INSERT permission"""
        has_permission, source = request.user.check_object_permission(10803, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to create permission sets",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Set created_by
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Add created_by before save
        permission_set = serializer.save(created_by=request.user)

        return Response(
            PermissionSetDetailSerializer(permission_set).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Update permission set - requires MODIFY permission"""
        has_permission, source = request.user.check_object_permission(10803, "modify")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need modify permission to update permission sets",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Delete permission set - requires DELETE permission"""
        has_permission, source = request.user.check_object_permission(10803, "delete")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need delete permission to delete permission sets",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if permission set is in use
        instance = self.get_object()
        group_count = instance.user_groups.count()

        if group_count > 0:
            return Response(
                {
                    "error": "Permission set in use",
                    "detail": f"This permission set is assigned to {group_count} user group(s)",
                    "user_group_count": group_count,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def clone(self, request, pk=None):
        """Clone a permission set with new code and name"""
        has_permission, source = request.user.check_object_permission(10803, "insert")
        if not has_permission:
            return Response(
                {
                    "error": "Insufficient permissions",
                    "detail": "You need insert permission to clone permission sets",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        source_set = self.get_object()
        new_code = request.data.get("new_code")
        new_name = request.data.get("new_name")

        if not new_code or not new_name:
            return Response(
                {"error": "new_code and new_name are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if code already exists
        if PermissionSet.objects.filter(code=new_code).exists():
            return Response(
                {"error": "Permission set with this code already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create new permission set
        new_set = PermissionSet.objects.create(
            code=new_code,
            name=new_name,
            description=source_set.description,
            is_active=True,
            created_by=request.user,
        )

        # Clone all permission lines
        for line in source_set.permissionsetline_set.all():
            PermissionSetLine.objects.create(
                permissionset=new_set,
                application_object=line.application_object,
                read_permission=line.read_permission,
                insert_permission=line.insert_permission,
                modify_permission=line.modify_permission,
                delete_permission=line.delete_permission,
                execute_permission=line.execute_permission,
            )

        return Response(
            PermissionSetDetailSerializer(new_set).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        """Preview permissions in human-readable format"""
        permission_set = self.get_object()

        # Group permissions by module
        modules = {}
        for line in permission_set.permissionsetline_set.select_related(
            "application_object"
        ):
            module = line.application_object.app_label or "other"

            if module not in modules:
                modules[module] = []

            permissions = []
            if line.read_permission:
                permissions.append("View")
            if line.insert_permission:
                permissions.append("Create")
            if line.modify_permission:
                permissions.append("Edit")
            if line.delete_permission:
                permissions.append("Delete")
            if line.execute_permission:
                permissions.append("Execute")

            modules[module].append(
                {
                    "page": line.application_object.object_name,
                    "permissions": permissions,
                    "summary": f"Can {', '.join(permissions).lower()} {line.application_object.object_name.lower()}",
                }
            )

        return Response({"permission_set": permission_set.name, "modules": modules})
