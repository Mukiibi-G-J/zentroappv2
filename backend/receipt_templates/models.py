from django.db import models

from dimension.models import DimensionValue
from utils.utils import BaseModel

from .enums import (
    DeviceType,
    EditorMode,
    LayoutPreset,
    PrinterType,
    ReceiptProcess,
    ReceiptType,
)


class ReceiptTemplate(BaseModel):
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    receipt_type = models.CharField(
        max_length=32,
        choices=ReceiptType.choices,
        db_index=True,
    )
    layout_preset = models.CharField(
        max_length=16,
        choices=LayoutPreset.choices,
        default=LayoutPreset.STANDARD,
    )
    paper_profile = models.JSONField(default=dict)
    sections = models.JSONField(default=list)
    editor_mode = models.CharField(
        max_length=20,
        choices=EditorMode.choices,
        default=EditorMode.VISUAL,
    )
    format_string = models.TextField(
        blank=True,
        default="",
        help_text="Thermal format string with {placeholders} when editor_mode is format_string.",
    )
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["receipt_type", "name"]
        verbose_name = "Receipt template"
        verbose_name_plural = "Receipt templates"

    def __str__(self):
        return f"{self.name} ({self.code})"


class ReceiptTemplateAssignment(BaseModel):
    template = models.ForeignKey(
        ReceiptTemplate,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    device_type = models.CharField(
        max_length=16,
        choices=DeviceType.choices,
        default=DeviceType.ANY,
        db_index=True,
    )
    printer_type = models.CharField(
        max_length=20,
        choices=PrinterType.choices,
        default=PrinterType.ANY,
        db_index=True,
    )
    process = models.CharField(
        max_length=32,
        choices=ReceiptProcess.choices,
        default=ReceiptProcess.ANY,
        db_index=True,
    )
    branch = models.ForeignKey(
        DimensionValue,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="receipt_template_assignments",
    )
    priority = models.IntegerField(default=0)

    class Meta:
        ordering = ["-priority", "-created_at"]
        verbose_name = "Receipt template assignment"
        verbose_name_plural = "Receipt template assignments"

    def __str__(self):
        return (
            f"{self.template.code} ← {self.device_type}/{self.printer_type}/"
            f"{self.process} (p={self.priority})"
        )
