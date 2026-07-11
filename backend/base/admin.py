from django.contrib import admin
from django.db.models import Count
from .models import ObjectType, Objects


@admin.register(ObjectType)
class ObjectTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sort_order", "object_count"]
    list_filter = ["name"]
    search_fields = ["name", "code", "description"]
    ordering = ["sort_order", "name"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(objects_count=Count("application_objects"))

    def object_count(self, obj):
        return obj.objects_count

    object_count.short_description = "Objects Count"
    object_count.admin_order_field = "objects_count"


@admin.register(Objects)
class ObjectsAdmin(admin.ModelAdmin):
    list_display = [
        "object_id",
        "object_name",
        "object_type_ref",
        "object_caption",
        "requires_permission",
        "related_model",
        "created_at",
    ]
    list_filter = [
        "object_type_ref",
        "requires_permission",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "object_name",
        "object_caption",
        "object_id",
        "related_model",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["object_type_ref", "object_id"]

    fieldsets = (
        (
            "Object Information",
            {
                "fields": (
                    "object_id",
                    "object_name",
                    "object_caption",
                    "object_type_ref",
                )
            },
        ),
        (
            "Permission Settings",
            {
                "fields": ("requires_permission", "related_model"),
                "description": "Configure whether this object requires permission management",
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("object_type_ref")

    def has_delete_permission(self, request, obj=None):
        # Allow deletion of objects (they can be repopulated)
        return super().has_delete_permission(request, obj)
