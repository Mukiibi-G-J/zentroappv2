from django.contrib import admin
from django.utils.html import format_html
from .models import PermissionSet, PermissionSetLine


class PermissionSetLineInline(admin.TabularInline):
    """Inline admin for Permission Set Lines"""

    model = PermissionSetLine
    extra = 0
    fields = [
        "application_object",
        "read_permission",
        "insert_permission",
        "modify_permission",
        "delete_permission",
        "execute_permission",
    ]

    def get_queryset(self, request):
        """Filter objects to only show those that require permissions"""
        qs = super().get_queryset(request)
        return qs.select_related("application_object")


@admin.register(PermissionSet)
class PermissionSetAdmin(admin.ModelAdmin):
    """Admin interface for Permission Sets"""

    list_display = [
        "name",
        "code",
        "is_active",
        "permission_count",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "code", "description"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "code", "description", "is_active"),
                "description": "Permission sets are assigned to User Groups, not roles directly.",
            },
        ),
        (
            "Audit Information",
            {
                "fields": ("created_at", "updated_at", "created_by"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [PermissionSetLineInline]

    def permission_count(self, obj):
        """Display the number of permission lines"""
        count = obj.get_permission_count()
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                f"{count} permissions",
            )
        return format_html('<span style="color: red;">No permissions</span>')

    permission_count.short_description = "Permissions"

    def save_model(self, request, obj, form, change):
        """Set created_by field"""
        if not change:  # Only set on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PermissionSetLine)
class PermissionSetLineAdmin(admin.ModelAdmin):
    """Admin interface for Permission Set Lines"""

    list_display = [
        "permissionset",
        "application_object",
        "permission_summary",
        "created_at",
    ]
    list_filter = [
        "permissionset",
        "read_permission",
        "insert_permission",
        "modify_permission",
        "delete_permission",
        "execute_permission",
    ]
    search_fields = [
        "permissionset__name",
        "permissionset__code",
        "application_object__object_name",
        "application_object__object_id",
    ]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Permission Set", {"fields": ("permissionset", "application_object")}),
        (
            "Permissions",
            {
                "fields": (
                    "read_permission",
                    "insert_permission",
                    "modify_permission",
                    "delete_permission",
                    "execute_permission",
                ),
                "description": "Select which actions are allowed for this object",
            },
        ),
        (
            "Audit Information",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def permission_summary(self, obj):
        """Display a summary of granted permissions"""
        permissions = obj.get_permissions_list()
        if not permissions:
            return format_html('<span style="color: red;">No permissions</span>')

        # Create colored badges for each permission
        badges = []
        colors = {
            "read": "blue",
            "insert": "green",
            "modify": "orange",
            "delete": "red",
            "execute": "purple",
        }

        for perm in permissions:
            color = colors.get(perm, "gray")
            badges.append(
                format_html(
                    '<span style="background-color: {}; color: white; padding: 2px 6px; '
                    'border-radius: 3px; font-size: 10px; margin-right: 2px;">{}</span>',
                    color,
                    perm.upper(),
                )
            )

        return format_html("".join(badges))

    permission_summary.short_description = "Permissions"

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return (
            super()
            .get_queryset(request)
            .select_related("permissionset", "application_object")
        )
