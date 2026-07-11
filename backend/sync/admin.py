from django.contrib import admin

from .models import InventorySnapshot, SyncDevice, SyncEvent


@admin.register(SyncDevice)
class SyncDeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "name", "client_type", "branch_id", "last_seen_at")
    search_fields = ("device_id", "name")


@admin.register(SyncEvent)
class SyncEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "device_id", "status", "processed_at")
    list_filter = ("status", "event_type")
    search_fields = ("event_id",)


@admin.register(InventorySnapshot)
class InventorySnapshotAdmin(admin.ModelAdmin):
    list_display = ("item_no", "item_system_id", "branch_id", "quantity", "updated_at")
