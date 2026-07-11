from django.db import models
from utils.utils import BaseModel


class SystemSettings(BaseModel):
    """
    System-wide settings and configuration.
    This model serves as a central place for system management actions.
    """

    setting_key = models.CharField(max_length=100, unique=True, primary_key=True)
    setting_value = models.TextField(blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"
        db_table = "settings_systemsettings"

    def __str__(self):
        return self.setting_key


class DataSyncConfig(BaseModel):
    """
    Configuration for data synchronization from JSON files.
    This model provides a UI for managing JSON sync operations.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    json_file_path = models.CharField(
        max_length=255,
        default="tenant_semuna_export_20250227_062346.json",
        help_text="Path to JSON export file (relative to BASE_DIR)",
    )
    last_sync_date = models.DateTimeField(blank=True, null=True)
    last_sync_status = models.CharField(max_length=50, blank=True, null=True)
    last_sync_summary = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Data Sync Configuration"
        verbose_name_plural = "Data Sync Configurations"
        db_table = "settings_datasyncconfig"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class MobileAppUserSettings(BaseModel):
    SEARCH_MODE_BARCODE = "barcode"
    SEARCH_MODE_REALTIME = "realtime"
    SEARCH_MODE_CHOICES = [
        (SEARCH_MODE_BARCODE, "Barcode"),
        (SEARCH_MODE_REALTIME, "Realtime"),
    ]

    PRINTER_TYPE_SUNMI = "sunmi"
    PRINTER_TYPE_BLUETOOTH = "bluetooth"
    PRINTER_TYPE_NONE = "none"
    PRINTER_TYPE_CHOICES = [
        (PRINTER_TYPE_SUNMI, "Sunmi"),
        (PRINTER_TYPE_BLUETOOTH, "Bluetooth"),
        (PRINTER_TYPE_NONE, "None"),
    ]

    PAPER_WIDTH_58 = "58"
    PAPER_WIDTH_80 = "80"
    PAPER_WIDTH_CHOICES = [
        (PAPER_WIDTH_58, "58"),
        (PAPER_WIDTH_80, "80"),
    ]

    user = models.OneToOneField(
        "authentication.CustomUser",
        on_delete=models.CASCADE,
        related_name="mobile_settings",
    )
    search_mode = models.CharField(
        max_length=20,
        choices=SEARCH_MODE_CHOICES,
        default=SEARCH_MODE_BARCODE,
    )
    barcode_scanner_enabled = models.BooleanField(default=False)
    barcode_beep_enabled = models.BooleanField(default=True)
    printer_type = models.CharField(
        max_length=20,
        choices=PRINTER_TYPE_CHOICES,
        default=PRINTER_TYPE_NONE,
    )
    printer_device_name = models.CharField(max_length=255, blank=True, default="")
    printer_mac_address = models.CharField(max_length=17, blank=True, default="")
    printer_paper_width = models.CharField(
        max_length=2,
        choices=PAPER_WIDTH_CHOICES,
        default=PAPER_WIDTH_58,
    )
    printer_copies = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "settings_mobileappusersettings"
        verbose_name = "Mobile App User Settings"
        verbose_name_plural = "Mobile App User Settings"

    def __str__(self):
        return f"Mobile settings for {self.user.username}"
