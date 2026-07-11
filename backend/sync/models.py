from django.db import models
from utils.utils import BaseModel


class SyncDevice(BaseModel):
    CLIENT_DESKTOP = "desktop"
    CLIENT_WEB = "web"
    CLIENT_MOBILE = "mobile"
    CLIENT_CHOICES = [
        (CLIENT_DESKTOP, "Desktop"),
        (CLIENT_WEB, "Web"),
        (CLIENT_MOBILE, "Mobile"),
    ]

    device_id = models.CharField(max_length=36, unique=True, db_index=True)
    name = models.CharField(max_length=200, blank=True, default="")
    client_type = models.CharField(
        max_length=20, choices=CLIENT_CHOICES, default=CLIENT_DESKTOP
    )
    branch_id = models.IntegerField(null=True, blank=True, db_index=True)
    app_version = models.CharField(max_length=50, blank=True, default="")
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sync_device"
        verbose_name = "Sync Device"
        verbose_name_plural = "Sync Devices"

    def __str__(self):
        return f"{self.device_id} ({self.client_type})"


class SyncEvent(BaseModel):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    event_id = models.CharField(max_length=36, unique=True, db_index=True)
    device_id = models.CharField(max_length=36, db_index=True)
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    error_message = models.TextField(blank=True, default="")
    result = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    client_created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sync_event"
        ordering = ["created_at"]
        verbose_name = "Sync Event"
        verbose_name_plural = "Sync Events"

    def __str__(self):
        return f"{self.event_type}:{self.event_id}"


class SyncCursor(BaseModel):
    device_id = models.CharField(max_length=36, db_index=True)
    resource = models.CharField(max_length=64, db_index=True)
    branch_id = models.IntegerField(null=True, blank=True, db_index=True)
    updated_since = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sync_cursor"
        unique_together = [("device_id", "resource", "branch_id")]
        verbose_name = "Sync Cursor"
        verbose_name_plural = "Sync Cursors"


class InventorySnapshot(BaseModel):
    item_system_id = models.CharField(max_length=36, db_index=True)
    branch_id = models.IntegerField(null=True, blank=True, db_index=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    item_no = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        db_table = "sync_inventory_snapshot"
        unique_together = [("item_system_id", "branch_id")]
        verbose_name = "Inventory Snapshot"
        verbose_name_plural = "Inventory Snapshots"
