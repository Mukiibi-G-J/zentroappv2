from django.contrib import admin
from django.utils import timezone
from .models import SystemSettings, DataSyncConfig, MobileAppUserSettings

# Import sync utilities
from utils.admin_sync import sync_from_json_file, sync_all_models_from_json


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "setting_key",
        "description",
        "is_active",
        "created_at",
        "updated_at",
    )
    search_fields = ("setting_key", "description", "setting_value")
    list_filter = ("is_active",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(DataSyncConfig)
class DataSyncConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for managing JSON data synchronization.
    Use the action dropdown to sync data from JSON files.
    """

    list_display = (
        "name",
        "json_file_path",
        "last_sync_date",
        "last_sync_status",
        "is_active",
    )
    search_fields = ("name", "description", "json_file_path")
    list_filter = ("is_active", "last_sync_status", "last_sync_date")
    readonly_fields = (
        "last_sync_date",
        "last_sync_status",
        "last_sync_summary",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "description", "is_active"),
            },
        ),
        (
            "Sync Configuration",
            {
                "fields": ("json_file_path",),
                "description": "Configure the JSON file to sync from",
            },
        ),
        (
            "Last Sync Details",
            {
                "fields": (
                    "last_sync_date",
                    "last_sync_status",
                    "last_sync_summary",
                ),
                "description": "Information about the last sync operation",
            },
        ),
        (
            "System Fields",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # Add the sync actions to this admin
    actions = [sync_from_json_file, sync_all_models_from_json]

    def get_queryset(self, request):
        """Override to show helpful message if no configs exist."""
        queryset = super().get_queryset(request)
        if not queryset.exists():
            # Create a default config if none exists
            DataSyncConfig.objects.get_or_create(
                name="Default Sync Config",
                defaults={
                    "description": "Default configuration for JSON data sync",
                    "json_file_path": "tenant_semuna_export_20250227_062346.json",
                },
            )
        return queryset


@admin.register(MobileAppUserSettings)
class MobileAppUserSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "search_mode",
        "barcode_scanner_enabled",
        "barcode_beep_enabled",
        "printer_type",
        "updated_at",
    )
    search_fields = ("user__username", "user__email", "printer_device_name")
    list_filter = (
        "search_mode",
        "barcode_scanner_enabled",
        "barcode_beep_enabled",
        "printer_type",
        "printer_paper_width",
    )
    readonly_fields = ("created_at", "updated_at")
