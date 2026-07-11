from django.contrib import admin

from receipt_templates.models import ReceiptTemplate, ReceiptTemplateAssignment


@admin.register(ReceiptTemplate)
class ReceiptTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "receipt_type",
        "layout_preset",
        "is_system",
        "is_active",
    )
    list_filter = ("receipt_type", "layout_preset", "is_system", "is_active")
    search_fields = ("code", "name")


@admin.register(ReceiptTemplateAssignment)
class ReceiptTemplateAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "device_type",
        "printer_type",
        "process",
        "branch",
        "priority",
    )
    list_filter = ("device_type", "printer_type", "process")
    raw_id_fields = ("template", "branch")
