from django.contrib import admin
from django.utils.html import format_html
from .models import ScheduledReport, ReportLog


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    """Admin interface for Scheduled Reports"""

    list_display = [
        "name",
        "report_type",
        "frequency",
        "export_format",
        "is_active_status",
        "recipient_count",
        "last_run",
        "next_run",
        "created_by",
    ]
    list_filter = ["report_type", "frequency", "export_format", "is_active", "created_at"]
    search_fields = ["name", "created_by__full_name", "created_by__email"]
    readonly_fields = ["created_at", "updated_at", "last_run"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Report Configuration",
            {
                "fields": ("name", "report_type", "frequency", "export_format"),
                "description": "Configure the report type and delivery settings",
            },
        ),
        (
            "Recipients",
            {
                "fields": ("recipients",),
                "description": "Email addresses to receive the report (JSON array format)",
            },
        ),
        (
            "Filters",
            {
                "fields": ("filters",),
                "classes": ("collapse",),
                "description": "Stored filter parameters (optional)",
            },
        ),
        (
            "Status & Schedule",
            {
                "fields": ("is_active", "next_run", "last_run"),
                "description": "Enable/disable and schedule information",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def is_active_status(self, obj):
        """Display active status with color"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html('<span style="color: gray;">✗ Inactive</span>')

    is_active_status.short_description = "Status"

    def recipient_count(self, obj):
        """Display number of recipients"""
        count = len(obj.recipients) if obj.recipients else 0
        return format_html(
            '<span style="color: blue; font-weight: bold;">{} recipients</span>', count
        )

    recipient_count.short_description = "Recipients"


@admin.register(ReportLog)
class ReportLogAdmin(admin.ModelAdmin):
    """Admin interface for Report Logs (read-only for auditing)"""

    list_display = [
        "id",
        "report_type",
        "generated_by",
        "generated_at",
        "execution_time_display",
        "cached_status",
        "export_format",
    ]
    list_filter = ["report_type", "cached", "export_format", "generated_at"]
    search_fields = ["report_type", "generated_by__full_name", "generated_by__email"]
    readonly_fields = [
        "report_type",
        "generated_by",
        "generated_at",
        "filters_applied",
        "export_format",
        "execution_time_ms",
        "cached",
        "scheduled_report",
        "ip_address",
    ]
    ordering = ["-generated_at"]

    def has_add_permission(self, request):
        """Report logs are auto-generated, not manually created"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup, but only for admins"""
        return request.user.is_superuser

    def execution_time_display(self, obj):
        """Display execution time with color coding"""
        time_ms = obj.execution_time_ms
        
        # Color code based on performance
        if time_ms < 1000:  # < 1 second (green)
            color = "green"
        elif time_ms < 3000:  # 1-3 seconds (orange)
            color = "orange"
        else:  # > 3 seconds (red)
            color = "red"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ms</span>',
            color,
            time_ms,
        )

    execution_time_display.short_description = "Execution Time"

    def cached_status(self, obj):
        """Display cached status"""
        if obj.cached:
            return format_html('<span style="color: blue;">✓ Cached</span>')
        return format_html('<span style="color: gray;">Generated</span>')

    cached_status.short_description = "Cache"
